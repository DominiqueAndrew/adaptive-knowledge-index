"""Freshness properties against fresh graphs, including negative dependencies."""
import random
import unittest
from aki.store import Store
from aki.policy import Policy
from aki.source import parse
from aki.benchmark import oracle


class MutationTest(unittest.TestCase):
    def test_selective_matches_fresh_rebuild_across_80_mutations(self):
        rng=random.Random(802)
        docs={f"m{i}.py":f"import m{(i+1)%16}\nx={i}\n" for i in range(16)}
        store=Store(":memory:","mutation-property")
        store.refresh(docs)
        policy=Policy(store,"lru",1_000_000)
        checked=0
        for step in range(80):
            for root in sorted(docs):
                for kind in ("dependencies","ripple"):
                    actual,_=policy.query(root,kind,store.revision,budget=1_000_000)
                    self.assertEqual(actual,oracle(docs,parse(docs).edges,root,kind,"",1_000_000))
                    checked+=1
            name=f"m{rng.randrange(20)}.py"
            action=step%5
            if action==0:
                docs[name]=f"import m{rng.randrange(20)}\n"
            elif action==1:
                docs[name]="x=2\n"
            elif action==2:
                docs.pop(name,None)
            elif action==3 and name in docs:
                docs[f"m{20+step}.py"]=docs.pop(name)
            else:
                docs[name]=f"import m{rng.randrange(20)}\nimport m{rng.randrange(20)}\n"
            policy.refresh(docs,"generated mutation",invalidation="selective")
        self.assertGreater(checked,2000)
        store.close()

    def test_new_incoming_edge_invalidates_reverse_negative_dependency(self):
        store=Store(":memory:","incoming")
        docs={"a.py":"x=1", "b.py":"import a", "c.py":"x=2"}
        store.refresh(docs)
        p=Policy(store,"lru")
        p.query("a.py","ripple",store.revision)
        docs["c.py"]="import b"
        report=p.refresh(docs,"incoming",invalidation="selective")
        self.assertEqual(report["invalidated"],1)
        self.assertEqual(p.query("a.py","ripple",store.revision)[0],["b.py","c.py"])
        store.close()

    def test_unrelated_change_retains_valid_relation_but_refreshes_content(self):
        store=Store(":memory:","content")
        docs={"a.py":"x=1", "b.py":"import a", "c.py":"x=2"}
        store.refresh(docs)
        p=Policy(store,"lru")
        p.query("b.py","dependencies",store.revision)
        docs["a.py"]="x="+"1+"*1000+"1"
        report=p.refresh(docs,"content-only",invalidation="selective")
        self.assertEqual(report["retained"],1)
        answer,event=p.query("b.py","dependencies",store.revision,budget=100)
        self.assertTrue(event["hit"])
        self.assertEqual(answer,[])  # new content cannot fit; never old source tokens
        store.close()


if __name__=="__main__": unittest.main()
