"""Fail-closed accounting adapter contract; no runtime creation or OS controls.

Linux control callbacks must come from a separately reviewed exclusive launcher.
Proof receipts are inputs, not facts discovered by this module. Fixture receipts
cannot certify a live runtime. Darwin PID sampling deliberately has no backend.
"""
from dataclasses import dataclass
import re
import time
from .setup_accounting import AccountingError
from .subtree_accounting import SubtreeLedger, read_cgroup_v2


class UnsupportedAccounting(AccountingError):
    pass


@dataclass(frozen=True)
class DomainProof:
    platform: str
    backend: str
    scope_identity: str
    capacity: int
    receipt_sha256: str
    # These must be established by the exclusive launcher before enrollment.
    owned: bool
    cgroup2_mount: bool
    domain: bool
    atomic_child_enrollment: bool
    migration_denied: bool
    external_dispatch_denied: bool
    counter_retained_until_final_read: bool

    def validate(self):
        if self.platform != 'linux' or self.backend != 'cgroup-v2':
            raise UnsupportedAccounting('complete descendant accounting requires an owned Linux cgroup-v2 domain; PID polling is unsupported')
        if not self.scope_identity or not re.fullmatch('[a-f0-9]{64}', self.receipt_sha256):
            raise AccountingError('bound identity and preflight receipt required')
        if type(self.capacity) is not int or self.capacity < 1:
            raise AccountingError('physical execution capacity required, not average quota')
        for name in ('owned', 'cgroup2_mount', 'domain', 'atomic_child_enrollment',
                     'migration_denied', 'external_dispatch_denied', 'counter_retained_until_final_read'):
            if getattr(self, name) is not True:
                raise AccountingError('unproved containment obligation: ' + name)


class CgroupAccountingAdapter:
    """One scope lifetime, enrolled empty before dispatch and retained until final.

    Injected callbacks: read() -> SubtreeSample; seal() closes the only launcher;
    stop() requests owned-domain termination (not deletion). Return True only on
    acknowledged control. No callback may act on a shared/default runtime. The
    owner must still wait for populated=0. Stop errors remain failures even if a
    later read finds the domain empty. Sampling errors can never become zero CPU.
    A successful receipt covers this domain only, not host/VM/observer overhead.
    """
    def __init__(self, proof, read, seal, stop, *, clock=time.monotonic_ns):
        proof.validate()  # Unsupported platform fails before any callback.
        self.proof, self.read, self.seal, self.stop, self.clock = proof, read, seal, stop, clock
        self.errors = []; self.closed = False; self.stop_acknowledged = False
        self.final = None; self.samples = []
        sample = read()
        if sample.identity != proof.scope_identity:
            raise AccountingError('preflight scope identity changed')
        self.ledger = SubtreeLedger(sample, proof.capacity, durable_counter=True,
                                    containment_verified=True)
        self.samples.append(sample)

    @classmethod
    def from_directory(cls, proof, directory, boot_id, seal, stop, *, clock=time.monotonic_ns):
        # This reader does not discover cgroups or verify mount/ownership authority.
        return cls(proof, lambda: read_cgroup_v2(directory, boot_id, clock=clock), seal, stop, clock=clock)

    def _error(self, stage, exc):
        self.errors.append({'stage': stage, 'error_type': type(exc).__name__, 'reason': str(exc)})

    def checkpoint(self):
        if self.final is not None:
            raise AccountingError('scope already finalized')
        try:
            sample = self.read(); self.ledger.observe(sample); self.samples.append(sample)
            if self.errors:
                raise AccountingError('earlier accounting/control failure remains unresolved')
            return self.ledger.upper_bound(self.clock())
        except Exception as exc:
            self._error('sample', exc)
            raise AccountingError('subtree accounting unavailable; dispatch prohibited') from exc

    def dispatch(self, operation):
        """Trusted launcher callback only; enrollment must precede every child fork."""
        if self.closed or self.errors or self.final is not None:
            raise AccountingError('dispatch closed or accounting failed')
        self.checkpoint()
        try:
            result = operation()
        except Exception as exc:
            self._error('operation', exc)
            raise
        self.checkpoint()
        return result

    def close_dispatch_and_stop(self):
        """One shutdown request. Never retries or deletes the accounting domain."""
        if self.closed:
            raise AccountingError('shutdown already requested')
        self.closed = True
        try:
            if self.seal() is not True:
                raise AccountingError('dispatch seal not acknowledged')
            self.ledger.seal_dispatch(self.clock())
        except Exception as exc:
            self._error('seal', exc)
        # Attempt-only stop is still appropriate if sealing failed, but cannot
        # yield a complete receipt. The callback must have bounded execution.
        try:
            if self.stop() is not True:
                raise AccountingError('owned-domain stop not acknowledged')
            self.stop_acknowledged = True
        except Exception as exc:
            self._error('stop', exc)

    def finish(self):
        """Poll after shutdown; pending populated scopes remain pending, not zero.

        The outer supervisor supplies the deadline; this method never sleeps.
        A final empty sample is read before any scope deletion is authorized.
        """
        if self.final is not None:
            return self.final
        if not self.closed:
            raise AccountingError('close dispatch and request owned stop first')
        result = None
        try:
            sample = self.read(); self.ledger.observe(sample); self.samples.append(sample)
            if not self.errors and self.stop_acknowledged and not sample.populated:
                result = self.ledger.finalize(sample)
        except Exception as exc:
            self._error('final_sample', exc)
        receipt = {'complete': result is not None, 'scope_only': True,
                   'cleanup_pending': result is None, 'may_delete_scope': result is not None,
                   'preflight_sha256': self.proof.receipt_sha256,
                   'accounting': result, 'errors': list(self.errors)}
        if result is not None:
            self.final = receipt
        return receipt


def capacity_plan(logical_cpus, work_wall_s, teardown_wall_s, *, budget_cpu_s):
    """Whole-machine worst-case reservation, not a measurement or CPU quota.

    Covers hidden/exited descendants without enumerating PIDs, provided the clock
    begins before charged work and the last owned activity ends before the bound.
    Failure to prove termination makes lifecycle compliance uncertified, even if
    the observation-window bound itself remains valid. Unrelated work is counted
    conservatively, never subtracted. Guest CPU is not added a second time.
    """
    values = (logical_cpus, work_wall_s, teardown_wall_s, budget_cpu_s)
    if any(type(v) is not int or v <= 0 for v in values):
        raise AccountingError('positive integral capacity, deadlines and budget required')
    required = logical_cpus * (work_wall_s + teardown_wall_s)
    return {'maximum_cpu_s': required, 'budget_cpu_s': budget_cpu_s,
            'fits': required <= budget_cpu_s, 'work_deadline_s': work_wall_s,
            'termination_deadline_s': work_wall_s + teardown_wall_s,
            'cost_kind': 'whole_machine_capacity_upper_bound',
            'requires_verified_owned_termination': True}
