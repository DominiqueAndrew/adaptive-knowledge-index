import json
import unittest
from aki.trace_audit import audit_row, audit_shell_repeats, literal_read, numbered_lines

class TraceAuditTests(unittest.TestCase):
    def test_projection_drops_reasoning_and_edit_text(self):
        from scripts.fetch_trace_sample import project_messages
        row=self.row([('think',{'thought':'REMOVE_REASONING'},'REMOVE_REASONING'),
                      ('str_replace_editor',{'command':'create','path':'/a','file_text':'REMOVE_EDIT'},'done')])
        output=json.dumps(project_messages(row['trajectory']))
        self.assertNotIn('REMOVE_REASONING',output)
        self.assertNotIn('REMOVE_EDIT',output)
        self.assertIn('/a',output)

    def row(self, actions):
        messages=[]
        for i,(name,args,response) in enumerate(actions):
            messages += [{'role':'assistant','tool_calls':[{'id':str(i),'function':{'name':name,'arguments':json.dumps(args)}}]},
                         {'role':'tool','tool_call_id':str(i),'content':response}]
        return {'trajectory_id':'original-test','repo':'test/repo','trajectory':messages}

    def test_shell_expansions_and_mutation_are_opaque(self):
        for text in ['cat x > y','cat x &> y','echo $(whoami)','rg --pre bad x','python x.py','sed -i x y','cat x; rm y','cd .. && cat x']:
            self.assertFalse(literal_read(text),text)
        for text in ['grep -n pattern x','cd /testbed && sed -n \'1,20p\' a.py','cat x | head -20']:
            self.assertTrue(literal_read(text),text)

    def test_numbered_lines_require_unambiguous_structure(self):
        self.assertEqual(numbered_lines('header\n     1\tone\n     2\ttwo'),{1:'one',2:'two'})
        self.assertEqual(numbered_lines('1\tx\n1\ty'),{})
        self.assertEqual(numbered_lines('1\tx\n2\tpart<response clipped><NOTE>metadata</NOTE>'),{1:'x'})

    def test_overlap_beyond_exact_and_mutation_boundary(self):
        v=lambda r:{'command':'view','path':'/src/a.py','view_range':r}
        actions=[('str_replace_editor',v([1,2]),'1\tone\n2\ttwo'),
                 ('str_replace_editor',v([2,3]),'2\ttwo\n3\tthree'),
                 ('str_replace_editor',v([2,3]),'2\ttwo\n3\tthree'),
                 ('str_replace_editor',{'command':'str_replace','path':'/src/a.py'},'done'),
                 ('str_replace_editor',v([2,3]),'2\tnew\n3\tthree')]
        c=audit_row(self.row(actions))['counts']
        self.assertEqual(c['exact_equal_hits'],1)
        self.assertEqual(c['beyond_exact_overlap_lines'],1)
        self.assertEqual(c.get('line_observation_mismatches',0),0)

    def test_opaque_shell_clears_cache(self):
        v={'command':'view','path':'/src/a.py'}
        c=audit_row(self.row([('str_replace_editor',v,'1\tone'),('execute_bash',{'command':'python edit.py'},''),('str_replace_editor',v,'1\tone')]))['counts']
        self.assertEqual(c.get('exact_equal_hits',0),0)

    def test_changed_observation_and_budget(self):
        v={'command':'view','path':'/src/a.py'}
        c=audit_row(self.row([('str_replace_editor',v,'1\tone'),('str_replace_editor',v,'1\ttwo')]),budget=4)['counts']
        self.assertEqual(c['exact_observation_mismatches'],1)
        self.assertEqual(c.get('exact_equal_hits',0),0)
        self.assertLessEqual(c['peak_lru_bytes'],4)

    def test_shell_exact_reuse_requires_explicit_cwd_and_resets_on_edits(self):
        shell=lambda cmd:('execute_bash',{'command':cmd},'same output')
        actions=[shell('cd /testbed && grep -n key a.py'),shell('cd /testbed && grep -n key a.py'),
                 shell('grep -n key a.py'),
                 ('str_replace_editor',{'command':'create','path':'/testbed/a.py'},'done'),
                 shell('cd /testbed && grep -n key a.py')]
        c=audit_shell_repeats(self.row(actions))
        self.assertEqual(c['exact_equal_hits'],1)
        self.assertEqual(c['lru_equal_hits'],1)
        self.assertEqual(c['lexical_exact_equal_hits'],1)
        self.assertEqual(c['ambient_cwd_excluded'],1)

if __name__=='__main__': unittest.main()
