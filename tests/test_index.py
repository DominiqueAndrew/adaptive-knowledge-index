import tempfile
from pathlib import Path
import unittest
from aki.benchmark import oracle, synthetic
from aki.source import parse, snapshot_id
from aki.store import Store, StaleRevision
from aki.policy import Policy, POLICIES


DOCS = {"pkg/__init__.py":"", "pkg/a.py":"from .b import b\ndef a(): return b()\n",
        "pkg/b.py":"def b(): return 1\n", "tests/test_a.py":"from pkg.a import a\ndef test_a(): assert a()==1\n"}


class IndexTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name)/"db.sqlite", "scope")
        self.store.refresh(DOCS)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_known_relative_import_and_test_transitivity(self):
        edges = parse(DOCS).edges
        self.assertIn(("pkg/a.py", "pkg/b.py"), edges)
        self.assertIn("tests/test_a.py", self.store.closure("pkg/b.py", "reverse"))
        self.assertEqual(self.store.closure("pkg/a.py", "forward"), ["pkg/__init__.py", "pkg/b.py"])

    def test_scope_and_revision_rejected(self):
        with self.assertRaises(ValueError):
            Store(Path(self.tmp.name)/"db.sqlite", "another")
        with self.assertRaises(StaleRevision):
            self.store.check("invented")

    def test_mutation_invalidates_added_incoming_edge(self):
        p = Policy(self.store,"lru")
        old = self.store.revision
        p.query("pkg/b.py","tests",old)
        self.assertGreater(self.store.usage(),0)
        new = dict(DOCS, **{"tests/test_b.py":"from pkg.b import b\n"})
        p.refresh(new,"mutation")
        self.assertEqual(self.store.usage(),0)
        self.assertIn("tests/test_b.py",p.query("pkg/b.py","tests",self.store.revision)[0])
        with self.assertRaises(StaleRevision):
            p.query("pkg/b.py","tests",old)

    def test_immutable_old_spans(self):
        old = self.store.revision
        rows = self.store.db.execute("SELECT id,hash,text FROM spans WHERE revision=?",(old,)).fetchall()
        self.store.refresh({"pkg/b.py":"def b(): return 2\n"})
        self.assertEqual(rows,self.store.db.execute("SELECT id,hash,text FROM spans WHERE revision=?",(old,)).fetchall())

    def test_cycles_terminate(self):
        self.store.refresh({"a.py":"import b", "b.py":"import a"})
        self.assertEqual(self.store.closure("a.py","forward"),["b.py"])

    def test_all_policies_match_independent_bfs(self):
        docs = synthetic(28)
        edges = parse(docs).edges
        for name in POLICIES:
            self.store.refresh(docs)
            p = Policy(self.store,name,1200)
            p.initialize()
            for i in range(70):
                root = f"pkg/m{i%28:04d}.py"
                kind = ("dependencies","ripple","tests")[i%3]
                answer,_ = p.query(root,kind,self.store.revision,"test",600)
                self.assertEqual(answer,oracle(docs,edges,root,kind,"test",600))
                if name != "static_full":
                    self.assertLessEqual(self.store.usage(),1200)

    def test_frozen_holdout_cannot_adapt(self):
        p=Policy(self.store,"lru")
        p.frozen=True
        for _ in range(5): p.query("pkg/b.py","tests",self.store.revision)
        self.assertEqual(self.store.usage(),0)
        self.assertEqual(len(p.history),0)

    def test_invalid_syntax_still_authoritative_source(self):
        report=self.store.refresh({"broken.py":"def broken("})
        self.assertEqual(report["parse_errors"],["broken.py"])
        self.assertEqual(self.store.db.execute("SELECT text FROM spans").fetchall()[-1][0],"def broken(")

    def test_snapshot_ignores_insertion_order(self):
        self.assertEqual(snapshot_id(DOCS),snapshot_id(dict(reversed(list(DOCS.items())))))

    def test_edge_evidence_current_hash_and_source(self):
        from aki.source import digest
        evidence=self.store.edge_evidence("pkg/a.py","pkg/b.py",self.store.revision)
        self.assertEqual(evidence[0]["line"],1)
        self.assertEqual(evidence[0]["sha256"],digest(evidence[0]["text"]))
        self.assertIn("from .b import b",evidence[0]["text"])

    def test_empty_and_zero_budget_abstain(self):
        p=Policy(self.store,"lru")
        self.assertEqual(p.query("missing","tests",self.store.revision)[0],[])
        self.assertEqual(p.query("pkg/b.py","tests",self.store.revision,budget=0)[0],[])

    def test_unseen_roots_are_disjoint_and_query_strings_unique(self):
        from aki.benchmark import workloads
        queries=workloads(synthetic(100),8,100,"locality")
        seen={q["root"] for q in queries if q["phase"] in {"cold_adapt","warm_heldout"}}
        unseen={q["root"] for q in queries if q["phase"]=="unseen_roots"}
        self.assertFalse(seen & unseen)
        self.assertEqual(len({q["text"] for q in queries}),len(queries))

    def test_source_loader_refuses_lossy_decoding(self):
        from aki.source import read_python_tree
        root=Path(self.tmp.name)/"source"
        root.mkdir()
        (root/"broken.py").write_bytes(b"x='\xff'\n")
        with self.assertRaises(UnicodeDecodeError): read_python_tree(root)

    def test_multiline_import_evidence_spans_every_chunk(self):
        source="from b import (\n"+"".join(f"    name{i},\n" for i in range(170))+")\n"
        self.store.refresh({"a.py":source,"b.py":"name0=1\n"})
        evidence=self.store.edge_evidence("a.py","b.py",self.store.revision)
        self.assertEqual([e["start"] for e in evidence],[1,81,161])
        self.assertEqual("".join(e["text"] for e in evidence),source)


if __name__ == "__main__": unittest.main()
