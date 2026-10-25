import json,tempfile,unittest
from pathlib import Path
from aki.replay import known_read,reconstruct,source_path,view_lines,sha

class ReplayTests(unittest.TestCase):
 def test_path_escape_rejected(self):
  for p in ['/etc/passwd','/testbed/../secret','relative.py']:
   with self.assertRaises(ValueError):source_path(p)
  self.assertEqual(source_path('/testbed/src/a.py'),'src/a.py')
  self.assertEqual(source_path('/workspace/repo/src/a.py','/workspace/repo'),'src/a.py')
  self.assertEqual(source_path('/workspace/repo','/workspace/repo'),'.')
 def test_read_screen_rejects_find_actions(self):
  self.assertTrue(known_read('cd /testbed && find . -name "*.py" -maxdepth 2'))
  self.assertTrue(known_read('cd /testbed && find . -name "*.py" -o -path "./src/*" | head -10'))
  for s in ['find . -exec rm {} +','find . -delete','find . -fprint out','python setup.py']:
   self.assertFalse(known_read(s))
 def test_view_selection_and_clipping(self):
  self.assertEqual(view_lines(b'a\r\nb\r\n',[2,-1]),{2:'b'})
  self.assertEqual(view_lines(b'a\n'),{1:'a',2:''})
  self.assertEqual(view_lines('x\u2028y\nz\n'.encode(),[2,2]),{2:'z'})
  self.assertEqual(view_lines(b'a'*17000),{})
 def test_prefix_stops_before_opaque_execution(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);root.joinpath('a.py').write_bytes(b'x=1\n')
   messages=[]
   for i,(name,args,response) in enumerate([('str_replace_editor',{'command':'view','path':'/testbed/a.py'},'1\tx=1\n2\t'),('execute_bash',{'command':'python mutate.py'},''),('str_replace_editor',{'command':'view','path':'/testbed/a.py'},'1\tchanged')]):
    messages.extend([{'role':'assistant','tool_calls':[{'id':str(i),'function':{'name':name,'arguments':json.dumps(args)}}]},{'role':'tool','tool_call_id':str(i),'content':response}])
   result=reconstruct({'trajectory':messages},root,{'entries':[{'path':'a.py','kind':'file','sha256':sha(b'x=1\n')}]})
   self.assertEqual(result['counts']['matched_views'],1)
   self.assertEqual(result['stop']['reason'],'opaque_shell_state_transition')
   self.assertEqual(len(result['events']),1)
 def test_unfollowed_link_never_reads_a_target(self):
  with tempfile.TemporaryDirectory() as tmp:
   row={'trajectory':[{'role':'assistant','tool_calls':[{'id':'1','function':{'name':'str_replace_editor','arguments':json.dumps({'command':'view','path':'/testbed/link.py'})}}]},{'role':'tool','tool_call_id':'1','content':'1\tx'}]}
   result=reconstruct(row,Path(tmp),{'entries':[{'path':'link.py','kind':'unfollowed-link','target_sha256':sha(b'outside')}]})
   self.assertEqual(result['stop']['reason'],'unfollowed_source_link')
   self.assertEqual(result['events'],[])


class ArchiveInputTests(unittest.TestCase):
 def archive(self, names):
  import io,tarfile
  stream=io.BytesIO()
  with tarfile.open(fileobj=stream,mode='w:gz') as tar:
   for name in names:
    content=b'Permission is hereby granted' if name.endswith('LICENSE') else b'inert'
    info=tarfile.TarInfo(name);info.size=len(content);tar.addfile(info,io.BytesIO(content))
  return stream.getvalue()
 def test_archive_rejects_escape_and_duplicate_paths(self):
  import sys
  sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
  from fetch_replay_development import unpack_inert
  for names in [['repo/../escape'],['repo/LICENSE','repo/LICENSE']]:
   with tempfile.TemporaryDirectory() as tmp:
    with self.assertRaises(ValueError):unpack_inert(self.archive(names),Path(tmp))
 def test_archive_is_inert_and_hashes_license(self):
  import sys
  sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
  from fetch_replay_development import unpack_inert
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);m=unpack_inert(self.archive(['repo/LICENSE','repo/setup.py']),root)
   self.assertEqual(root.joinpath('setup.py').stat().st_mode & 0o111,0)
   self.assertTrue(m['licenses'][0]['recognized_permissive_family'])
   self.assertEqual(len(m['entries']),2)

if __name__=='__main__':unittest.main()
