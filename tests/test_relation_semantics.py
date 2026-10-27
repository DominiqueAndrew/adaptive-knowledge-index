import tempfile
import unittest
from pathlib import Path
from aki.source import parse, STATIC_IMPORTS, UnsupportedRelations
from aki.store import Store, StaleRevision
from aki.exact_cache import fixture_policy
from aki.task_benefit import BASELINES
from aki.evidence_audit import audit_evidence


class RelationSemanticsTests(unittest.TestCase):
    def test_independent_dynamic_call_truth_and_static_edges_are_distinct(self):
        # Original closed fixtures. A stub records the requested module without
        # loading files or third-party code. The extractor/oracle is not used by
        # this runtime-call truth probe.
        sources=[
            '__import__("fixture_dependency")\n',
            'import importlib\nimportlib.import_module("fixture_dependency")\n',
            'import importlib as loader\nloader.import_module("fixture_dependency")\n',
            'from importlib import import_module as load\nload("fixture_dependency")\n',
        ]
        for source in sources:
            seen=[]
            class ImportStub:
                @staticmethod
                def import_module(name):seen.append(name)
            def imported(name,*args,**kwargs):
                if name=='importlib':return ImportStub
                seen.append(name);return object()
            exec(compile(source,'<original fixture>','exec'),{'__builtins__':{'__import__':imported}})
            self.assertEqual(seen,['fixture_dependency'])
            docs={'caller.py':source,'fixture_dependency.py':'value=1\n'}
            result=parse(docs)
            self.assertEqual(result.edges,frozenset())
            self.assertEqual(result.dynamic_imports,(('caller.py',source.count('\n')),))
            s=Store(':memory:','truth')
            try:
                s.refresh(docs)
                self.assertFalse(audit_evidence(s,docs,[('caller.py','fixture_dependency.py',source.count('\n'))])['passed'])
                with self.assertRaises(UnsupportedRelations):s.closure('caller.py','forward',relation_semantics='runtime-complete')
            finally:s.close()

    def test_unknown_indirection_never_becomes_a_completeness_certificate(self):
        docs={'caller.py':'loader=__import__\nloader("b")\n','b.py':'x=1\n'}
        self.assertEqual(parse(docs).dynamic_imports,())  # Detector is explicitly non-exhaustive.
        s=Store(':memory:','indirection')
        try:
            s.refresh(docs);self.assertFalse(s.relationship_scope()['runtime_complete'])
            with self.assertRaises(UnsupportedRelations):s.closure('caller.py','forward',relation_semantics='runtime-complete')
        finally:s.close()

    def test_every_policy_rejects_runtime_claim_before_a_cache_hit(self):
        for name in BASELINES+('aki',):
            s=Store(':memory:','semantics');p=fixture_policy(s,name,4096)
            try:
                p.refresh({'a.py':'import b\n','b.py':'x=1\n'},'fixture')
                for _ in range(3):
                    answer,cost=p.query('a.py','dependencies',s.revision)
                    self.assertEqual(answer,['b.py']);self.assertEqual(cost['relation_semantics'],STATIC_IMPORTS)
                    self.assertFalse(cost['runtime_complete'])
                before=s.usage()
                with self.assertRaises(UnsupportedRelations):p.query('a.py','dependencies',s.revision,relation_semantics='runtime-complete')
                self.assertEqual(s.usage(),before)
                with self.assertRaises(UnsupportedRelations):s.edge_evidence('a.py','b.py',s.revision,relation_semantics='runtime-complete')
            finally:s.close()

    def test_dynamic_diagnostics_survive_noop_reopen_and_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'db';s=Store(db,'diagnostics')
            docs={'a.py':'__import__("b")\n','b.py':'x=1\n'}
            r=s.refresh(docs);self.assertEqual(r['relationship_scope']['known_dynamic_import_site_count'],1)
            self.assertEqual(s.refresh(docs)['relationship_scope'],r['relationship_scope']);s.close()
            s=Store(db,'diagnostics')
            try:
                self.assertEqual(s.relationship_scope()['known_dynamic_import_site_count'],1)
                r=s.refresh(docs|{'a.py':'import b\n'})
                self.assertEqual(r['relationship_scope']['known_dynamic_import_site_count'],0)
                self.assertFalse(s.edge_evidence('a.py','b.py',s.revision)[0]['runtime_complete'])
            finally:s.close()

    def test_old_extractor_revision_cannot_reuse_answers_as_new_semantics(self):
        s=Store(':memory:','version')
        try:
            docs={'a.py':'import b\n','b.py':'x=1\n'};s.refresh(docs)
            s.db.execute("UPDATE meta SET v='python-ast-import-v3-physical-lines' WHERE k='extractor'")
            report=s.refresh(docs)
            self.assertFalse(report['noop']);self.assertFalse(report['relationship_scope']['runtime_complete'])
        finally:s.close()
