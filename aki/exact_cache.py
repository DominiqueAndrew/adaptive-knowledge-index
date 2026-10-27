"""Matched durable exact-result LRU comparator for the fixture harness.

Same base store, FULL SQLite durability, incremental source refresh and logical-byte
cap as relationship policies. Whole-revision invalidation is intentional: the key
includes all inputs that can affect the packed answer. No selective result repair.
"""
from collections import OrderedDict
import json
import time
from .policy import Policy
from .source import STATIC_IMPORTS, require_relation_semantics


class ExactResultCache:
    def __init__(self, store, name='exact_lru', budget=65536):
        if name != 'exact_lru':
            raise ValueError(name)
        self.store, self.name, self.budget = store, name, budget
        self.base = Policy(store, 'disabled', budget)
        self.resident = OrderedDict()

    def refresh(self, documents, provenance, invalidation='selective'):
        start = time.perf_counter_ns()
        # Result entries contain ranking/packing decisions, not dependency paths.
        # A changed tree clears them under both requested invalidation strategies.
        report = self.base.refresh(documents, provenance, 'global')
        if not report['noop']:
            self.resident.clear()
        report['total_refresh_ns'] = time.perf_counter_ns() - start
        return report

    def query(self, root, kind, revision, text='', budget=4096, *, relation_semantics=STATIC_IMPORTS):
        start = time.perf_counter_ns(); self.store.check(revision)
        require_relation_semantics(relation_semantics)
        key = json.dumps(['exact', self.store.scope, self.store.extractor,
                          revision, root, kind, text, budget], separators=(',', ':'))
        lookup = time.perf_counter_ns()
        answer = self.store.get(key) if key in self.resident else None
        lookup_ns = time.perf_counter_ns() - lookup; hit = answer is not None
        build_ns = 0; evicted = 0; base_ns = 0
        if hit:
            self.resident.move_to_end(key)
        else:
            before = time.perf_counter_ns()
            answer, _ = self.base.query(root, kind, revision, text, budget)
            base_ns = time.perf_counter_ns() - before
            size = len(json.dumps(answer, separators=(',', ':')).encode()) + len(key.encode()) + 96
            if size <= self.budget:
                before = time.perf_counter_ns(); available = self.budget - sum(self.resident.values()); victims = []
                for victim, amount in self.resident.items():
                    if available >= size:
                        break
                    victims.append(victim); available += amount
                actual_size = self.store.install(key, answer, victims)
                for victim in victims:
                    del self.resident[victim]
                self.resident[key] = actual_size; evicted = len(victims)
                build_ns = time.perf_counter_ns() - before
        total = time.perf_counter_ns() - start
        return answer, {'hit': hit, 'base_ns': base_ns, 'lookup_ns': lookup_ns,
                        'build_ns': build_ns, 'total_ns': total,
                        'candidate': not hit, 'built': bool(build_ns), 'evicted': evicted,
                        'logical_bytes': sum(self.resident.values()),
                        'returned': len(answer), 'abstained': not answer, **self.store.relationship_scope()}


def fixture_policy(store, name, budget):
    return ExactResultCache(store, name, budget) if name == 'exact_lru' else Policy(store, name, budget)
