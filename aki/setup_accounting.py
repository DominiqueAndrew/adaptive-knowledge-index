"""Explicit CPU/resource accounting for bounded setup, not inferred zero cost."""
from dataclasses import dataclass
import ctypes
import os
import re
import sys


class AccountingError(RuntimeError):
    pass


@dataclass
class Counter:
    identity: str
    capacity: int
    value_ns: int
    observed_ns: int
    active: bool
    terminal_bound_ns: int = 0


class CpuLedger:
    REQUIRED = frozenset({'supervisor', 'workers', 'runtime_host', 'guest'})

    def __init__(self):
        self.counters = {}

    def register(self, name, identity, capacity, value_ns, observed_ns, *, active):
        if name not in self.REQUIRED or name in self.counters or not identity:
            raise AccountingError('missing, duplicate or unknown CPU identity')
        if type(capacity) is not int or capacity < 1:
            raise AccountingError('positive CPU capacity required')
        if type(value_ns) is not int or value_ns < 0 or observed_ns < 0:
            raise AccountingError('invalid initial CPU observation')
        self.counters[name] = Counter(identity, capacity, value_ns, observed_ns, active)

    def update(self, name, identity, value_ns, observed_ns):
        c = self.counters[name]
        if identity != c.identity or not c.active:
            raise AccountingError('CPU identity changed or already finalized')
        if type(value_ns) is not int or value_ns < c.value_ns or observed_ns < c.observed_ns:
            raise AccountingError('CPU counter or observation clock moved backward')
        c.value_ns = value_ns; c.observed_ns = observed_ns

    def finalize(self, name, at_ns, *, confirmed, final_value_ns=None):
        c = self.counters[name]
        if not confirmed or at_ns < c.observed_ns:
            raise AccountingError('CPU termination/boundary is unconfirmed')
        if not c.active:
            return
        if final_value_ns is not None:
            self.update(name, c.identity, final_value_ns, at_ns)
        else:
            # Covers shutdown between the last sample and confirmed termination.
            c.terminal_bound_ns = (at_ns - c.observed_ns) * c.capacity
        c.active = False

    def snapshot(self, at_ns):
        if set(self.counters) != self.REQUIRED:
            raise AccountingError('required CPU components are missing')
        measured = 0; bound = 0; rows = {}
        for name, c in self.counters.items():
            if at_ns < c.observed_ns:
                raise AccountingError('observation is from the future')
            tail = (at_ns - c.observed_ns) * c.capacity if c.active else c.terminal_bound_ns
            measured += c.value_ns; bound += tail
            rows[name] = {'identity': c.identity, 'measured_ns': c.value_ns,
                          'unobserved_upper_bound_ns': tail, 'active': c.active}
        return {'components': rows, 'measured_component_sum_ns': measured,
                'unobserved_upper_bound_ns': bound, 'conservative_cpu_ns': measured + bound,
                'finalized': not any(c.active for c in self.counters.values()),
                'interpretation': 'Conservative accounting; host VM and guest counters can overlap. Not additive physical CPU cost.'}


class ByteLedger:
    def __init__(self, transfer_limit=512*1024**2, disk_limit=3*1024**3):
        self.transfer_limit = transfer_limit; self.disk_limit = disk_limit
        self.transfer = 0; self.disk = 0; self.disk_peak = 0

    def receive(self, count):
        if type(count) is not int or count < 0 or self.transfer + count > self.transfer_limit:
            raise AccountingError('transfer ceiling')
        self.transfer += count

    def allocate(self, count):
        if type(count) is not int or count < 0 or self.disk + count > self.disk_limit:
            raise AccountingError('disk reservation ceiling')
        self.disk += count; self.disk_peak = max(self.disk_peak, self.disk)

    def release(self, count):
        if type(count) is not int or not 0 <= count <= self.disk:
            raise AccountingError('invalid disk release')
        self.disk -= count


def guest_cpu_snapshot(stat_text, clock_ticks, boot_id):
    """Use measured CLK_TCK and boot identity; exclude idle/iowait and double guest fields."""
    if type(clock_ticks) is not int or clock_ticks <= 0:
        raise AccountingError('CLK_TCK must be observed, not assumed')
    if not re.fullmatch(r'[0-9a-f-]{36}', boot_id):
        raise AccountingError('guest boot identity required')
    fields = stat_text.splitlines()[0].split()
    if fields[0] != 'cpu' or len(fields) < 9:
        raise AccountingError('malformed guest CPU record')
    values = [int(x) for x in fields[1:]]
    if any(x < 0 for x in values):
        raise AccountingError('negative CPU tick counter')
    busy = sum(values[i] for i in (0, 1, 2, 5, 6, 7))
    return {'identity': boot_id, 'cpu_ns': busy * 1_000_000_000 // clock_ticks}


def darwin_process_cpu(pid):
    """Read one explicitly registered PID; no process enumeration or session discovery.

    Layout: installed Apple SDK sys/resource.h rusage_info_v2 and libproc.h.
    Runtime adapters must register all owned daemon PIDs and retain exit evidence.
    """
    if sys.platform != 'darwin' or type(pid) is not int or pid <= 0:
        raise AccountingError('Darwin and an explicit positive PID are required')
    class RUsageV2(ctypes.Structure):
        _fields_ = [('uuid', ctypes.c_uint8 * 16)] + [(name, ctypes.c_uint64) for name in (
            'user', 'system', 'pkg_wakeups', 'interrupt_wakeups', 'pageins', 'wired',
            'resident', 'footprint', 'start', 'exit', 'child_user', 'child_system',
            'child_pkg_wakeups', 'child_interrupt_wakeups', 'child_pageins',
            'child_elapsed', 'disk_read', 'disk_write')]
    lib = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
    function = lib.proc_pid_rusage
    function.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
    function.restype = ctypes.c_int
    result = RUsageV2()
    if function(pid, 2, ctypes.byref(result)):
        error=AccountingError('explicit process CPU unavailable: '+str(ctypes.get_errno()))
        error.errno=ctypes.get_errno()
        raise error
    return {'identity': str(pid)+':'+str(result.start),
            'cpu_ns': int(result.user + result.system),
            'reaped_children_cpu_ns': int(result.child_user + result.child_system)}
