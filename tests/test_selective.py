import unittest
from aki.selective import EvidenceGate


class GateTest(unittest.TestCase):
    def test_gate_requires_unambiguous_current_source_hint(self):
        chunks=[{"path":p,"kind":"file","text":""} for p in ("pkg/a.py","other/a.py","pkg/b.py")]
        chunks += [{"path":p,"kind":"symbol","symbol":name,"start_line":line,"end_line":line+2,"text":"def "+name+"(): pass"}
                   for p,name,line in (("pkg/a.py","specific_operation",1),("pkg/a.py","get",4),
                        ("pkg/a.py","duplicated",7),("other/a.py","duplicated",1))]
        g=EvidenceGate(chunks,{"get"})
        for query in ("fix pkg/a.py", "b.py crashes", "specific_operation fails"):
            self.assertTrue(g.check(query)["allowed"])
        for query in ("fix a.py", "get failed", "duplicated fails", "specific_operation_extra", "something vague"):
            self.assertFalse(g.check(query)["allowed"])
        self.assertEqual(g.check("something vague")["reason"],"insufficient_evidence")

    def test_repeated_symbol_locations_in_same_file_are_ambiguous(self):
        chunks=[{"kind":"file","path":"a.py"}]+[{"kind":"symbol","path":"a.py","symbol":"method","start_line":i,"end_line":i+1} for i in (1,5)]
        self.assertFalse(EvidenceGate(chunks,set()).check("method") ["allowed"])
