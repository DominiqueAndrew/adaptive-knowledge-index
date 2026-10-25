import json,os,tempfile,unittest
from pathlib import Path
from aki.recorder import Recorder,CaptureError,verify,sha

class RecorderTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name);self.root=self.base/'fixture';self.root.mkdir();(self.root/'src').mkdir();(self.root/'src'/'x.py').write_bytes(b'original\r\n')
 def tearDown(self):self.tmp.cleanup()
 def recorder(self,**kwargs):
  return Recorder(root=self.root,scopes=['src'],output=self.base/'capture',allow_collection=True,source_kind='synthetic_fixture',**kwargs)
 def rows(self):
  with (self.base/'capture'/'events.jsonl').open() as stream:return [json.loads(x) for x in stream]
 def test_explicit_opt_in_and_scopes(self):
  with self.assertRaises(PermissionError):Recorder(root=self.root,scopes=['src'],output=self.base/'no',source_kind='synthetic_fixture')
  with self.assertRaises(CaptureError):Recorder(root=self.root,scopes=['../private'],output=self.base/'no',allow_collection=True,source_kind='synthetic_fixture')
  self.assertFalse((self.base/'no').exists())
 def test_hash_only_redacts_requests_outputs_and_paths(self):
  r=self.recorder()
  with r.operation('source_read',b'PRIVATE_QUERY_SENTINEL') as o:o.output(b'PRIVATE_OUTPUT_SENTINEL')
  r.close();text=(self.base/'capture'/'events.jsonl').read_text()
  for value in ['PRIVATE_QUERY_SENTINEL','PRIVATE_OUTPUT_SENTINEL','x.py',str(self.root),'original']:self.assertNotIn(value,text)
  self.assertFalse((self.base/'capture'/'source-blobs').exists())
  self.assertEqual(verify(self.base/'capture')['complete_operations'],1)
  self.assertEqual((self.base/'capture').stat().st_mode & 0o777,0o700)
  self.assertEqual((self.base/'capture'/'events.jsonl').stat().st_mode & 0o777,0o600)
 def test_mutations_additions_deletions_and_exact_bytes(self):
  r=self.recorder(store_source_blobs=True,store_tool_requests=True)
  with r.operation('source_edit',b'1') as o:
   (self.root/'src'/'x.py').write_bytes(b'changed');(self.root/'src'/'y.py').write_bytes(b'new');o.output(b'ok')
  with r.operation('source_edit',b'2') as o:(self.root/'src'/'y.py').unlink();o.output(b'ok')
  r.close();rows=self.rows()
  self.assertNotEqual(rows[1]['before']['scoped_tree_sha256'],rows[2]['after']['scoped_tree_sha256'])
  self.assertEqual(len(rows[4]['after']['deleted']),1)
  self.assertEqual((self.base/'capture'/'source-blobs'/sha(b'original\r\n')).read_bytes(),b'original\r\n')
  self.assertEqual(verify(self.base/'capture')['complete_operations'],2)
  self.assertEqual((self.base/'capture'/'requests'/sha(b'1')).read_bytes(),b'1')
 def test_unrelated_files_are_not_collected(self):
  (self.root/'private.txt').write_bytes(b'DO_NOT_COLLECT')
  r=self.recorder(store_source_blobs=True)
  with r.operation('source_read',b'1') as o:o.output(b'ok')
  r.close();self.assertFalse((self.base/'capture'/'source-blobs'/sha(b'DO_NOT_COLLECT')).exists())
 def test_symlink_and_hidden_file_fail_closed(self):
  (self.root/'src'/'link').symlink_to(self.base)
  r=self.recorder()
  with self.assertRaises((CaptureError,OSError)):
   with r.operation('source_read',b'1'):self.fail('operation must not start')
  r.close()
  with self.assertRaises(CaptureError):verify(self.base/'capture')
 def test_exception_messages_not_stored_and_external_cpu_unknown(self):
  r=self.recorder()
  with self.assertRaises(ValueError):
   with r.operation('source_execute',b'1'):raise ValueError('SECRET_EXCEPTION_TEXT')
  r.close();rows=self.rows();self.assertNotIn('SECRET_EXCEPTION_TEXT',json.dumps(rows));self.assertIsNone(rows[2]['executor_cpu_ns'])
  self.assertEqual(verify(self.base/'capture')['complete_operations'],1)
 def test_missing_output_and_crashed_session_rejected(self):
  r=self.recorder()
  with r.operation('source_read',b'1'):pass
  r.close()
  with self.assertRaises(CaptureError):verify(self.base/'capture')
 def test_nested_operation_rejected(self):
  r=self.recorder()
  with r.operation('source_read',b'1') as o:
   with self.assertRaises(CaptureError):
    with r.operation('source_read',b'2'):pass
   o.output(b'ok')
  r.close();self.assertEqual(verify(self.base/'capture')['complete_operations'],1)
 def test_tampering_and_missing_blob_detected(self):
  r=self.recorder(store_source_blobs=True)
  with r.operation('source_read',b'1') as o:o.output(b'ok')
  r.close();next((self.base/'capture'/'source-blobs').iterdir()).unlink()
  with self.assertRaises(CaptureError):verify(self.base/'capture')
 def test_caps_and_executor_metric_validation(self):
  r=self.recorder()
  with r.operation('source_read',b'1') as o:
   with self.assertRaises(ValueError):o.executor_metrics(cpu_ns=-1)
   o.executor_metrics(wall_ns=10,cpu_ns=3);o.output(b'')
  r.close();self.assertEqual(self.rows()[2]['executor_cpu_ns'],3)
 def test_source_changed_during_capture_rejected(self):
  from unittest.mock import patch
  r=self.recorder();changed=False
  def changing_hash(value):
   nonlocal changed
   if value==b'original\r\n' and not changed:
    changed=True;(self.root/'src'/'x.py').write_bytes(b'different source')
   return sha(value)
  with patch('aki.recorder.sha',side_effect=changing_hash):
   with self.assertRaises(CaptureError):
    with r.operation('source_read',b'1'):self.fail('unstable source must stop capture')
  r.close()
 def test_fifo_and_sensitive_paths_rejected_without_read(self):
  os.mkfifo(self.root/'src'/'pipe')
  r=self.recorder()
  with self.assertRaises(CaptureError):
   with r.operation('source_read',b'1'):self.fail('special file must not be read')
  (self.root/'src'/'pipe').unlink();(self.root/'src'/'.env').write_text('PRIVATE_SENTINEL')
  with self.assertRaises(CaptureError):
   with r.operation('source_read',b'2'):self.fail('sensitive path must not be read')
  r.close();self.assertNotIn('PRIVATE_SENTINEL',json.dumps(self.rows()))
 def test_tampered_or_truncated_journal_rejected(self):
  r=self.recorder()
  with r.operation('source_read',b'1') as o:o.output(b'ok')
  r.close();path=self.base/'capture'/'events.jsonl';lines=path.read_text().splitlines()
  path.write_text('\n'.join(lines[:-1])+'\n')
  with self.assertRaises(CaptureError):verify(self.base/'capture')
  rows=[json.loads(x) for x in lines];rows[2]['output_bytes']=999
  path.write_text(''.join(json.dumps(x)+'\n' for x in rows))
  with self.assertRaises(CaptureError):verify(self.base/'capture')
 def test_unobserved_change_between_tools_rejected(self):
  r=self.recorder()
  with r.operation('source_read',b'1') as o:o.output(b'ok')
  (self.root/'src'/'x.py').write_bytes(b'unobserved mutation')
  with self.assertRaises(CaptureError):
   with r.operation('source_read',b'2'):self.fail('unobserved source change must stop capture')
  r.close()
  with self.assertRaises(CaptureError):verify(self.base/'capture')

if __name__=='__main__':unittest.main()
