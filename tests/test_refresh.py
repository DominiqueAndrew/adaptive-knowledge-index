"""Regressions for measured-cost retention, restarts and incremental source updates."""
import tempfile
import unittest
from pathlib import Path
from aki.policy import Policy, POLICIES
from aki.source import digest, parse, snapshot_id
from aki.store import Store


class RefreshTest(unittest.TestCase):
    def test_retained_cost_and_gds_priority_survive(self):
        for name in ("aki", "gds"):
            s = Store(":memory:", "cost")
            docs = {"a.py":"import b", "b.py":"x=1"}
            s.refresh(docs)
            p = Policy(s, name)
            key = p.key("a.py", "forward")
            # Controlled observed-cost fixture avoids hardware-dependent admission.
            p.stats[key].base_ns = 100_000_000
            for _ in range(3): p.query("a.py", "dependencies", s.revision)
            self.assertIn(key, p.resident)
            before = p.stats[key].base_ns
            report = p.refresh(docs | {"unrelated.py":"x=2"}, "new", "selective")
            self.assertEqual(report["retained"], 1)
            self.assertEqual(p.stats[key].base_ns, before)
            _, event = p.query("a.py", "dependencies", s.revision)
            self.assertTrue(event["hit"])
            self.assertGreater(p.benefit(key), 0)
            if name == "gds": self.assertGreater(p.gds[key], 0)
            s.close()

    def test_noop_preserves_every_policy_state_in_both_refresh_modes(self):
        for mode in ("full", "incremental"):
            for name in POLICIES:
                s = Store(":memory:", "noop", mode)
                docs = {"a.py":"import b", "b.py":"x=1"}
                s.refresh(docs)
                p = Policy(s, name)
                p.initialize()
                p.query("a.py", "dependencies", s.revision)
                state = (dict(p.resident), dict(p.counts), list(p.history), dict(p.gds), dict(p.stats))
                changes = s.db.total_changes
                report = p.refresh(dict(reversed(list(docs.items()))), "another commit", "global")
                self.assertTrue(report["noop"])
                self.assertEqual(report["static_rebuild_ns"], 0)
                self.assertEqual(changes, s.db.total_changes)
                self.assertEqual(state, (dict(p.resident), dict(p.counts), list(p.history), dict(p.gds), dict(p.stats)))
                s.close()

    def test_restart_discards_untracked_cache_and_enforces_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"store.sqlite"
            s = Store(path, "restart")
            s.refresh({f"{x}.py":"x=1" for x in "abcd"})
            p = Policy(s, "lru", 250)
            for x in "ab": p.query(f"{x}.py", "dependencies", s.revision)
            self.assertEqual(s.usage(), 232)
            revision = s.revision
            s.close()
            s = Store(path, "restart")
            p = Policy(s, "lru", 250)
            self.assertEqual(s.usage(), 0)
            self.assertEqual(s.revision, revision)
            for x in "cd":
                p.query(f"{x}.py", "dependencies", s.revision)
                self.assertEqual(s.usage(), sum(p.resident.values()))
                self.assertLessEqual(s.usage(), 250)
            s.close()

    def test_new_module_re_resolves_unchanged_import_and_keeps_active_evidence(self):
        s = Store(":memory:", "new-module")
        docs = {"a.py":"import missing\n", "unrelated.py":"x=1"}
        s.refresh(docs)
        old_ids = dict(s.db.execute("SELECT path,span_id FROM active_spans"))
        docs["missing.py"] = "x=2"
        report = s.refresh(docs, "new module", "selective")
        self.assertEqual(report["parsed_files"], 1)
        self.assertEqual(report["reused_files"], 2)
        self.assertEqual(s.closure("a.py", "forward"), ["missing.py"])
        e = s.edge_evidence("a.py", "missing.py", s.revision)[0]
        self.assertEqual(e["span_id"], old_ids["a.py"])
        self.assertEqual(e["sha256"], digest(docs["a.py"]))
        self.assertEqual(e["current_revision"], snapshot_id(docs))
        s.close()

    def test_incremental_full_source_and_edge_evidence_parity(self):
        stores = [Store(":memory:", "parity", mode) for mode in ("full", "incremental")]
        docs = {"a.py":"import b\n", "b.py":"x=1", "bad.py":"def ("}
        episodes = [dict(docs)]
        docs["b.py"] = "import c\n"; episodes.append(dict(docs))
        docs["c.py"] = "from a import anything\n"; episodes.append(dict(docs))
        docs["moved.py"] = docs.pop("a.py"); episodes.append(dict(docs))
        docs["bad.py"] = "x=1"; episodes.append(dict(docs))
        del docs["b.py"]; episodes.append(dict(docs))
        for docs in episodes:
            for s in stores: s.refresh(docs, "mutation", "selective")
            for table, cols in (("files","*"),("edges","*"),("symbols","*"),("search","path,text")):
                self.assertEqual(sorted(stores[0].db.execute(f"SELECT {cols} FROM {table}")),
                                 sorted(stores[1].db.execute(f"SELECT {cols} FROM {table}")))
            for a,b in parse(docs).edges:
                ea,eb = (s.edge_evidence(a,b,s.revision) for s in stores)
                for e in ea+eb: self.assertEqual(e["sha256"],digest(e["text"]))
                self.assertEqual([(e["path"],e["start"],e["sha256"]) for e in ea],
                                 [(e["path"],e["start"],e["sha256"]) for e in eb])
            for root in docs:
                for direction in ("forward","reverse"):
                    self.assertEqual(*(s.closure(root,direction) for s in stores))
        for s in stores: s.close()

    def test_batched_replacement_has_one_transaction(self):
        s = Store(":memory:", "atomic")
        s.refresh({f"{x}.py":"x=1" for x in "abc"})
        p = Policy(s, "lru", 130)
        p.query("a.py","dependencies",s.revision)
        sql = []
        s.db.set_trace_callback(sql.append)
        p.query("b.py","dependencies",s.revision)
        self.assertEqual(sum(q == "COMMIT" for q in sql), 1)
        self.assertEqual(s.usage(), sum(p.resident.values()))
        s.close()

    def test_unicode_separators_do_not_shift_ast_evidence_lines(self):
        s = Store(":memory:", "physical-lines")
        for newline in ("\n", "\r\n", "\r"):
            source = 'x="' + '\u2028'*90 + '"' + newline + 'import b' + newline
            s.refresh({"a.py":source, "b.py":"x=1"})
            evidence = s.edge_evidence("a.py", "b.py", s.revision)
            self.assertEqual(evidence[0]["line"], 2)
            self.assertEqual(evidence[0]["end"], 2)
            self.assertEqual(evidence[0]["text"], source)
        s.close()

    def test_old_extractor_store_requires_refresh_before_policy_use(self):
        from aki.store import StaleRevision
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"old.sqlite"
            docs={"a.py":"import b", "b.py":"x=1"}
            s=Store(path,"migration")
            s.refresh(docs)
            with s.db: s.db.execute("UPDATE meta SET v='legacy-extractor' WHERE k='extractor'")
            s.close()
            s=Store(path,"migration")
            p=Policy(s,"lru")
            with self.assertRaises(StaleRevision): p.query("a.py","dependencies",s.revision)
            with self.assertRaises(StaleRevision): p.initialize()
            with self.assertRaises(StaleRevision): s.closure("a.py","forward")
            with self.assertRaises(StaleRevision): s.get(p.key("a.py","forward"))
            with self.assertRaises(StaleRevision): s.edge_evidence("a.py","b.py",s.revision)
            report=p.refresh(docs,"same bytes, new extractor","selective")
            self.assertFalse(report["noop"])
            self.assertEqual(p.query("a.py","dependencies",s.revision)[0],["b.py"])
            s.close()

    def test_source_loader_preserves_exact_utf8_line_endings(self):
        from aki.source import read_python_tree
        with tempfile.TemporaryDirectory() as tmp:
            source='x="\u2028"\r\nimport b\r'
            (Path(tmp)/"a.py").write_bytes(source.encode("utf-8"))
            self.assertEqual(read_python_tree(Path(tmp))["a.py"],source)


if __name__ == "__main__": unittest.main()
