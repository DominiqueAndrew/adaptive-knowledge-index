"""Outer deadline for an entire controlled command sequence, including cleanup.

Commands execute only when run() is explicitly called. Fixture tests use original
host programs; no Docker/model/network operation is automatic or implicit here.
"""
from dataclasses import dataclass
import os
import selectors
import signal
import subprocess
import threading
import time

from .setup_accounting import AccountingError, CpuLedger


@dataclass(frozen=True)
class Command:
    name: str
    argv: tuple[str, ...]
    timeout_s: float = 30
    input_bytes: bytes = b''
    environment: dict | None = None


class SetupStopped(RuntimeError):
    pass


class SetupWatchdog:
    def __init__(self, *, cpu_snapshot, total_s=600, teardown_reserve_s=90,
                 cpu_limit_ns=300_000_000_000, cleanup_cpu_reserve_ns=120_000_000_000,
                 output_limit=2*1024**2, clock=time.monotonic):
        if not 0 < teardown_reserve_s < total_s:
            raise ValueError('cleanup time must be reserved inside total time')
        if not 0 <= cleanup_cpu_reserve_ns < cpu_limit_ns:
            raise ValueError('invalid cleanup CPU reserve')
        self.cpu_snapshot = cpu_snapshot; self.total_s = total_s
        self.reserve_s = teardown_reserve_s; self.cpu_limit = cpu_limit_ns
        self.cpu_reserve = cleanup_cpu_reserve_ns; self.output_limit = output_limit
        self.clock = clock; self.current = None; self.lock = threading.Lock()
        self.stop_event = threading.Event(); self.reason = None; self.phase = 'work'
        self.cancelled = False; self.used = False
        self.accounting_faults = []; self.cpu_overrun = False
        self.accounting_fault_details = []
        self.finalize_reserve_s = min(5, teardown_reserve_s / 10)
        self.command_records = []

    def _snapshot(self):
        row = self.cpu_snapshot()
        if (not isinstance(row, dict) or type(row.get('conservative_cpu_ns')) is not int
                or row['conservative_cpu_ns'] < 0 or type(row.get('finalized')) is not bool
                or set(row.get('components', {})) != CpuLedger.REQUIRED):
            raise AccountingError('complete CPU accounting snapshot required')
        total = 0; active = False
        for component in row['components'].values():
            if type(component.get('active')) is not bool:
                raise AccountingError('CPU activity state missing')
            active |= component['active']
            for key in ('measured_ns', 'unobserved_upper_bound_ns'):
                value = component.get(key)
                if type(value) is not int or value < 0:
                    raise AccountingError('CPU component observation missing')
                total += value
        if total != row['conservative_cpu_ns'] or row['finalized'] != (not active):
            raise AccountingError('inconsistent CPU aggregate or finalization')
        return row

    def _kill_current(self):
        with self.lock:
            if self.current is not None:
                try: os.killpg(self.current.pid, signal.SIGKILL)
                except ProcessLookupError: pass

    def _watch(self):
        # Independent of reads, writes, command output, and CPU sampling.
        while not self.stop_event.wait(0.01):
            now = self.clock()
            if now >= self.hard_end:
                self.reason = 'total_deadline'; self.cancelled = True; self._kill_current()
            elif self.phase == 'work' and now >= self.work_end:
                self.reason = 'work_deadline_cleanup_reserved'; self.cancelled = True; self._kill_current()

    def _check(self):
        now = self.clock()
        end = self.work_end if self.phase == 'work' else self.hard_end-self.finalize_reserve_s
        if now >= end or (self.cancelled and self.phase == 'work'):
            raise SetupStopped(self.reason or 'deadline')
        # The provider must return an in-memory snapshot promptly. Slow collectors
        # run in supervised subprocesses; stale intervals become CPU upper bounds.
        try:
            row = self._snapshot()
        except Exception as exc:
            self.accounting_faults.append(str(exc))
            self.accounting_fault_details.append({'phase':self.phase,'at_monotonic_s':self.clock(),
                'component':getattr(exc,'counter_component',None),'context':getattr(exc,'counter_context',{}),'message':str(exc)})
            if self.phase == 'work': raise
            # Missing telemetry cannot justify leaving owned execution running.
            # Only bounded teardown continues; the final result must fail validation.
            return None
        limit = self.cpu_limit - self.cpu_reserve if self.phase == 'work' else self.cpu_limit
        if row['conservative_cpu_ns'] >= limit:
            if self.phase == 'work': raise SetupStopped('CPU ceiling with cleanup reserve')
            self.cpu_overrun = True
        return row

    def _run_command(self, command):
        self._check()
        if not command.argv or len(command.input_bytes) > 2*1024**2 or command.timeout_s <= 0:
            raise SetupStopped('invalid bounded command')
        start = self.clock(); end = min(start + command.timeout_s,
                                        self.work_end if self.phase == 'work' else self.hard_end-self.finalize_reserve_s)
        try:
            process = subprocess.Popen(command.argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, start_new_session=True,
                                       env=command.environment)
        except OSError as exc:
            self.command_records.append({'name': command.name, 'phase': self.phase,
                                         'wall_s': self.clock()-start, 'spawn_error': type(exc).__name__})
            raise
        with self.lock: self.current = process
        selector = selectors.DefaultSelector(); output = bytearray(); sent = 0
        os.set_blocking(process.stdout.fileno(), False)
        selector.register(process.stdout, selectors.EVENT_READ)
        if command.input_bytes:
            os.set_blocking(process.stdin.fileno(), False)
            selector.register(process.stdin, selectors.EVENT_WRITE)
        else:
            process.stdin.close()
        try:
            while selector.get_map() or process.poll() is None:
                self._check()
                if self.clock() >= end:
                    raise SetupStopped('command deadline: '+command.name)
                for key, events in selector.select(min(0.02, max(0, end-self.clock()))):
                    if key.fileobj is process.stdout:
                        chunk = os.read(process.stdout.fileno(), 65536)
                        if not chunk:
                            selector.unregister(process.stdout)
                        else:
                            if len(output) + len(chunk) > self.output_limit:
                                raise SetupStopped('command output cap')
                            output.extend(chunk)
                    else:
                        try: count = os.write(process.stdin.fileno(), command.input_bytes[sent:sent+65536])
                        except BrokenPipeError:
                            raise SetupStopped('command input transfer failed')
                        sent += count
                        if sent == len(command.input_bytes):
                            selector.unregister(process.stdin); process.stdin.close()
            code = process.wait(timeout=max(0.001, end-self.clock()))
            if code:
                raise SetupStopped('command failed: '+command.name+' exit='+str(code))
            return {'name': command.name, 'exit': code, 'wall_s': self.clock()-start,
                    'output_bytes': len(output)}
        finally:
            self._kill_current()  # Also quiesce children if their parent exited first.
            if process.poll() is None:
                try: process.wait(timeout=min(0.1, max(0.001, self.hard_end-self.clock())))
                except subprocess.TimeoutExpired: self.reason = 'owned_process_termination_pending'
            with self.lock: self.current = None
            self.command_records.append({'name': command.name, 'phase': self.phase,
                                         'exit': process.returncode, 'wall_s': self.clock()-start,
                                         'input_bytes_sent': sent, 'output_bytes_seen': len(output)})
            selector.close()
            if not process.stdin.closed: process.stdin.close()
            process.stdout.close()

    def run(self, work, cleanup):
        if self.used:
            raise SetupStopped('supervisor is one-shot; counters cannot be reset')
        self.used = True; self.started = self.clock()
        self.hard_end = self.started+self.total_s; self.work_end = self.hard_end-self.reserve_s
        result = {'work': [], 'cleanup': [], 'status': 'running', 'cleanup_pending': []}
        watcher = threading.Thread(target=self._watch, daemon=True); watcher.start()
        try:
            try:
                for command in work: result['work'].append(self._run_command(command))
                result['status'] = 'work_completed'
            except Exception as exc:
                result['status'] = 'work_stopped'; result['reason'] = str(exc)
            finally:
                self.phase = 'cleanup'
                for command in cleanup:
                    try: result['cleanup'].append(self._run_command(command))
                    except Exception as exc:
                        result['cleanup_pending'].append({'name': command.name, 'reason': str(exc)})
                try:
                    result['cpu'] = self._snapshot()
                    result['accounting_complete'] = bool(result['cpu'].get('finalized'))
                    if not result['accounting_complete']:
                        result['status'] = 'accounting_incomplete'
                except Exception as exc:
                    result['accounting_complete'] = False; result['accounting_error'] = str(exc)
                    result['status'] = 'accounting_incomplete'
        finally:
            self.stop_event.set(); self._kill_current(); watcher.join(timeout=0.1)
        result['elapsed_s'] = self.clock()-self.started
        result['deadline_exceeded'] = result['elapsed_s'] > self.total_s
        result['accounting_faults'] = self.accounting_faults
        result['accounting_fault_details'] = self.accounting_fault_details
        result['command_records'] = self.command_records
        result['cpu_ceiling_exceeded'] = self.cpu_overrun or result.get('cpu', {}).get('conservative_cpu_ns', 0) > self.cpu_limit
        if self.accounting_faults:
            result['accounting_complete'] = False; result['status'] = 'accounting_incomplete'
        if result['cpu_ceiling_exceeded']: result['status'] = 'cpu_ceiling_exceeded'
        if result['cleanup_pending']: result['status'] = 'cleanup_pending'
        if result['deadline_exceeded']: result['status'] = 'deadline_exceeded'
        return result
