import unittest
from aki.evidence_audit import audit_evidence
from aki.exact_cache import fixture_policy, ExactResultCache
from aki.policy import Policy
from aki.store import Store, StaleRevision
from aki.task_benefit import BASELINES, run_fixtures, DEFAULTS


class AdversarialFreshnessTests(unittest.TestCase):
    def test_harness_rejects_stale_answer_and_shared_parser_gap_with_manual_expectations(self):
        docs={'a.py':'import b\n','b.py':'x=1\n','c.py':'x=1\n'}
        event={'phase':'manual','documents':docs,'operation':{'root':'a.py','kind':'dependencies'},
               'expected_answer':['b.py'],'valid_paths':['b.py'],'expected_edges':[('a.py','b.py',1)]}
        case={'kind':'synthetic_fixture','task_id':'manual','events':[event]}
        class StaleAnswer(Policy):
            def query(self,*args,**kwargs):
                _,cost=super().query(*args,**kwargs)
                return ['c.py'],cost
        row=run_fixtures([case],('lru',),DEFAULTS,policy_factory=StaleAnswer)['lru'][0]
        self.assertFalse(row['correct']);self.assertFalse(row['fresh'])
        dynamic=docs|{'a.py':'import importlib\nb=importlib.import_module("b")\n'}
        case['events']=[event|{'documents':dynamic,'expected_edges':[('a.py','b.py',2)]}]
        row=run_fixtures([case],('disabled',),DEFAULTS)['disabled'][0]
        self.assertFalse(row['correct']);self.assertTrue(row['fresh'])  # Missing relation, no stale source served.

    def test_hand_authored_boundary_mutations_across_all_matched_policies(self):
        # Manual edges and answers: never call the implementation parser/oracle.
        original={'a.py':'x=1\n','b.py':'import a\n','c.py':'x=2\n'}
        snapshots=[
            (original,[('b.py','a.py',1)],['b.py']),
            (original|{'c.py':'import b\n'},[('b.py','a.py',1),('c.py','b.py',1)],['b.py','c.py']),
            (original|{'c.py':'import a\n'},[('b.py','a.py',1),('c.py','a.py',1)],['b.py','c.py']),
            ({'a.py':'x=1\n','moved.py':'import a\n','c.py':'import b\n'},[('moved.py','a.py',1)],['moved.py']),
            ({'a.py':'x=2\n','c.py':'import b\n'},[],[]),
            (original,[('b.py','a.py',1)],['b.py']),  # branch restoration
        ]
        for name in BASELINES+('aki',):
            with self.subTest(policy=name):
                s=Store(':memory:','manual-adversary');p=fixture_policy(s,name,4096)
                try:
                    for docs,edges,expected in snapshots:
                        old=s.revision;p.refresh(docs,'original mutation fixture','selective')
                        if old and old!=s.revision:
                            with self.assertRaises(StaleRevision):p.query('a.py','ripple',old)
                        self.assertTrue(audit_evidence(s,docs,edges)['passed'])
                        for _ in range(3):
                            actual,_=p.query('a.py','ripple',s.revision,budget=100)
                            self.assertEqual(actual,expected);self.assertLessEqual(s.usage(),4096)
                finally:s.close()

    def test_new_module_and_package_initializer_change_resolution(self):
        sequence=[
            ({'caller.py':'import pkg.child\n'},[],[]),
            ({'caller.py':'import pkg.child\n','pkg/child.py':'x=1\n'},[('caller.py','pkg/child.py',1)],['pkg/child.py']),
            ({'caller.py':'import pkg.child\n','pkg/child.py':'x=1\n','pkg/__init__.py':'import helper\n','helper.py':'x=1\n'},
             [('caller.py','pkg/child.py',1),('caller.py','pkg/__init__.py',1),('pkg/__init__.py','helper.py',1)],
             ['helper.py','pkg/__init__.py','pkg/child.py']),
        ]
        for name in BASELINES+('aki',):
            s=Store(':memory:','negative-dependency');p=fixture_policy(s,name,4096)
            try:
                for docs,edges,expected in sequence:
                    p.refresh(docs,'original fixture','selective')
                    for _ in range(3):self.assertEqual(p.query('caller.py','dependencies',s.revision)[0],expected)
                    self.assertTrue(audit_evidence(s,docs,edges)['passed'])
            finally:s.close()

    def test_same_edge_new_source_recomputes_packing_and_evidence(self):
        for name in BASELINES+('aki',):
            s=Store(':memory:','packing');p=fixture_policy(s,name,4096)
            try:
                docs={'a.py':'import b\n','b.py':'x=1\n'};p.refresh(docs,'small','selective')
                for _ in range(3):self.assertEqual(p.query('a.py','dependencies',s.revision,budget=10)[0],['b.py'])
                docs['b.py']='x='+('1+'*40)+'1\n';docs['a.py']='# shifted evidence\nimport b\n'
                p.refresh(docs,'large','selective')
                self.assertEqual(p.query('a.py','dependencies',s.revision,budget=10)[0],[])
                self.assertTrue(audit_evidence(s,docs,[('a.py','b.py',2)])['passed'])
            finally:s.close()

    def test_exact_key_covers_kind_text_token_budget_and_revision(self):
        s=Store(':memory:','key');p=ExactResultCache(s,budget=4096)
        try:
            docs={'a.py':'import b\nimport c\n','b.py':'x=1\n','c.py':'x=2\n'}
            p.refresh(docs,'fixture')
            for kind,text,budget,expected in [('dependencies','',3,['b.py']),('dependencies','c',3,['c.py']),
                                                ('dependencies','',6,['b.py','c.py']),('ripple','',6,[])]:
                self.assertEqual(p.query('a.py',kind,s.revision,text,budget)[0],expected)
                self.assertTrue(p.query('a.py',kind,s.revision,text,budget)[1]['hit'])
            old=s.revision;p.refresh(docs|{'c.py':'x=3\n'},'changed')
            self.assertFalse(p.query('a.py','dependencies',s.revision)[1]['hit'])
            with self.assertRaises(StaleRevision):p.query('a.py','dependencies',old)
        finally:s.close()

    def test_exact_cache_durable_bytes_eviction_and_restart_are_accounted(self):
        s=Store(':memory:','bounded');p=ExactResultCache(s,budget=450)
        try:
            p.refresh({'a.py':'import b\n','b.py':'x=1\n'},'fixture')
            for text in ('one','two','three'):
                p.query('a.py','dependencies',s.revision,text)
                self.assertEqual(sum(p.resident.values()),s.usage());self.assertLessEqual(s.usage(),450)
            self.assertEqual(len(p.resident),1)
            replacement=ExactResultCache(s,budget=450)
            self.assertEqual(s.usage(),0);self.assertFalse(replacement.query('a.py','dependencies',s.revision)[1]['hit'])
        finally:s.close()

    def test_fault_injected_stale_edge_and_source_are_detected(self):
        docs={'a.py':'import b\n','b.py':'x=1\n','c.py':'x=1\n'}
        s=Store(':memory:','fault')
        try:
            s.refresh(docs);self.assertTrue(audit_evidence(s,docs,[('a.py','b.py',1)])['passed'])
            s.db.execute("INSERT INTO edges VALUES('a.py','c.py')")
            self.assertIn('edge_set_mismatch',audit_evidence(s,docs,[('a.py','b.py',1)])['errors'])
            s.db.execute("UPDATE spans SET text='old evidence' WHERE path='a.py'")
            self.assertIn('stale_or_ungrounded_span',audit_evidence(s,docs,[('a.py','b.py',1)])['errors'])
            s.db.execute("UPDATE files SET hash='old' WHERE path='b.py'")
            self.assertIn('source_hash_mismatch',audit_evidence(s,docs,[('a.py','b.py',1)])['errors'])
        finally:s.close()

    def test_shared_parser_agreement_cannot_establish_runtime_import_completeness(self):
        # A known unsupported dynamic import: an independent requirement exposes
        # the gap even though every cache and a fresh rebuild agree on no edge.
        docs={'a.py':'import importlib\nb=importlib.import_module("b")\n','b.py':'x=1\n'}
        s=Store(':memory:','unsupported')
        try:
            s.refresh(docs)
            self.assertEqual(s.closure('a.py','forward'),[])
            self.assertFalse(audit_evidence(s,docs,[('a.py','b.py',2)])['passed'])
        finally:s.close()
