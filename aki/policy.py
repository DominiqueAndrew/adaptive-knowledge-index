"""Measured-cost online admission with byte budget, recency and hysteresis."""
from __future__ import annotations
import json
import time
from collections import OrderedDict, defaultdict, deque
from dataclasses import dataclass
from .store import Store

POLICIES = ("disabled", "static_full", "static_bounded", "lru", "frequency", "gds", "aki")


@dataclass
class Stat:
    base_ns: float = 0
    lookup_ns: float = 0
    build_ns: float = 0
    size: int = 0
    seen: int = 0


class Policy:
    def __init__(self, store: Store, name: str, budget: int = 65536, window: int = 128,
                 horizon: int = 64, hysteresis: float = 1.25):
        if name not in POLICIES:
            raise ValueError(name)
        self.store, self.name, self.budget = store, name, budget
        self.window, self.horizon, self.hysteresis = window, horizon, hysteresis
        self.stats: dict[str, Stat] = defaultdict(Stat)
        self.history = deque(maxlen=window)
        self.resident: OrderedDict[str, int] = OrderedDict()
        self.frozen = False
        self.events: list[dict] = []
        self.peak_bytes = 0
        self.counts = defaultdict(int)
        self.build_ema = 150_000.0
        self.gds_clock = 0.0
        self.gds = {}
        self.refresh_risk = 0.0

    def initialize(self) -> int:
        t = time.perf_counter_ns()
        if self.name.startswith("static"):
            for (root,) in self.store.db.execute("SELECT path FROM files ORDER BY path").fetchall():
                for direction in ("forward", "reverse"):
                    key = self.key(root, direction)
                    if key in self.resident:
                        continue
                    rows = self.store.closure(root, direction)
                    size = self.size(key, rows)
                    if self.name == "static_full" or sum(self.resident.values()) + size <= self.budget:
                        self.resident[key] = self.store.put(key, rows)
        self.peak_bytes = max(self.peak_bytes, sum(self.resident.values()))
        return time.perf_counter_ns() - t

    @staticmethod
    def key(root: str, direction: str) -> str:
        return json.dumps([root, direction], separators=(",", ":"))

    def size(self, key: str, rows: list[str]) -> int:
        return len(json.dumps(rows, separators=(",", ":")).encode()) + len(key.encode()) + 96

    def benefit(self, key: str) -> float:
        s = self.stats[key]
        expected = self.counts[key] * self.horizon / max(len(self.history), 1)
        # Only observed base and hit costs; initial lookup estimate is conservative.
        lookup = s.lookup_ns or 30_000
        return expected * max(0, s.base_ns - lookup)

    def query(self, root: str, kind: str, revision: str, text: str = "", budget: int = 4096) -> tuple[list[str], dict]:
        start = time.perf_counter_ns()
        self.store.check(revision)
        direction = "forward" if kind == "dependencies" else "reverse"
        key = self.key(root, direction)
        lookup_start = time.perf_counter_ns()
        rows = self.store.get(key) if key in self.resident else None
        lookup_ns = time.perf_counter_ns() - lookup_start
        hit = rows is not None
        base_ns = 0
        if rows is None:
            t = time.perf_counter_ns()
            rows = self.store.closure(root, direction)
            base_ns = time.perf_counter_ns() - t
        ranked = self.store.rank(root, rows, kind, text)
        packed = self.store.pack(ranked, budget)
        retrieval_end = time.perf_counter_ns()
        build_ns = 0
        candidate = False
        evicted = 0
        if not self.frozen and self.name not in {"disabled", "static_full", "static_bounded"}:
            if len(self.history) == self.window:
                expired = self.history[0]
                self.counts[expired] -= 1
                if not self.counts[expired] and expired not in self.resident:
                    self.counts.pop(expired, None)
                    self.stats.pop(expired, None)
            self.history.append(key)
            self.counts[key] += 1
            stat = self.stats[key]
            stat.seen += 1
            if base_ns:
                stat.base_ns = base_ns if not stat.base_ns else .7 * stat.base_ns + .3 * base_ns
            if hit:
                stat.lookup_ns = lookup_ns if not stat.lookup_ns else .7 * stat.lookup_ns + .3 * lookup_ns
                self.resident.move_to_end(key)
                if self.name == "gds":
                    self.gds[key] = self.gds_clock + stat.base_ns/max(self.resident[key],1)
            else:
                candidate = True
                stat.size = self.size(key, rows)
                admit = self.name in {"lru","gds"} or (self.name == "frequency" and self.counts[key] >= 2)
                if self.name == "aki":
                    # First build estimate is a measured-history prior, never future work.
                    estimate = (stat.build_ns or self.build_ema) * (1+self.refresh_risk)
                    admit = self.counts[key] >= 2 and self.benefit(key) > self.hysteresis * estimate
                if admit and stat.size <= self.budget:
                    victims = []
                    available = self.budget - sum(self.resident.values())
                    if self.name == "lru":
                        ordered = list(self.resident)
                    elif self.name == "frequency":
                        ordered = sorted(self.resident, key=lambda k: self.counts[k])
                    elif self.name == "gds":
                        ordered = sorted(self.resident, key=lambda k: self.gds[k])
                    else:
                        ordered = sorted(self.resident, key=lambda k: self.benefit(k)/max(self.resident[k],1))
                    for victim in ordered:
                        if available >= stat.size:
                            break
                        victims.append(victim)
                        available += self.resident[victim]
                    if self.name == "frequency" and victims:
                        admit = self.counts[key] > max(self.counts[v] for v in victims)
                    if self.name == "aki" and victims:
                        admit = self.benefit(key) > self.hysteresis * (sum(self.benefit(v) for v in victims) + estimate)
                    if admit:
                        t = time.perf_counter_ns()
                        for victim in victims:
                            if self.name == "gds":
                                self.gds_clock = self.gds.pop(victim)
                            self.store.remove(victim)
                            del self.resident[victim]
                            evicted += 1
                        self.resident[key] = self.store.put(key, rows)
                        build_ns = time.perf_counter_ns() - t
                        stat.build_ns = build_ns
                        self.build_ema = .7*self.build_ema + .3*build_ns
                        if self.name == "gds":
                            self.gds[key] = self.gds_clock + stat.base_ns/max(stat.size,1)
                        self.peak_bytes = max(self.peak_bytes, sum(self.resident.values()))
        end = time.perf_counter_ns()
        event = {"hit": hit, "base_ns": base_ns, "lookup_ns": lookup_ns,
                 "retrieval_ns": retrieval_end - start, "build_ns": build_ns,
                 "optimizer_ns": end - retrieval_end - build_ns, "total_ns": end - start,
                 "candidate": candidate, "built": bool(build_ns), "evicted": evicted,
                 "logical_bytes": sum(self.resident.values()), "returned": len(packed),
                 "abstained": not packed}
        return packed, event

    def refresh(self, documents: dict[str, str], provenance: str, invalidation: str = "global") -> dict:
        t = time.perf_counter_ns()
        report = self.store.refresh(documents, provenance, invalidation)
        kept = dict(self.store.db.execute("SELECT key,bytes FROM mats"))
        self.resident = OrderedDict((k,v) for k,v in self.resident.items() if k in kept)
        # Cost and demand estimates describe a different graph; discard them.
        self.stats.clear()
        self.history.clear()
        self.counts.clear()
        self.gds = {k: self.gds_clock for k in self.resident}
        self.refresh_risk = report["invalidated"]/max(1,report["invalidated"]+report["retained"])
        report["static_rebuild_ns"] = self.initialize()
        report["total_refresh_ns"] = time.perf_counter_ns() - t
        return report
