"""Original cache fixtures; no network, VM, container or model execution."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import task420_live_worker as worker
import run_task420_attempt as supervisor
from aki.setup_budget import SharedBudget


def digest(data):return hashlib.sha256(data).hexdigest()


class CachedValidationTests(unittest.TestCase):
    def fixture(self,base):
        old=base/'closed';cache=old/'artifact-cache';(cache/'image/0').mkdir(parents=True);(cache/'packages').mkdir()
        layer=b'original layer fixture';package=b'original package fixture'
        config=json.dumps({'architecture':'arm64','os':'linux','rootfs':{'diff_ids':['sha256:'+digest(layer)]}}).encode()
        name=digest(config)+'.json'
        (cache/'image'/name).write_bytes(config);(cache/'image/0/layer.tar').write_bytes(layer)
        worker.save(cache/'image/manifest.json',[{'Config':name,'RepoTags':['fixture:old'],'Layers':['0/layer.tar']}])
        (cache/'packages/example.whl').write_bytes(package);worker.save(old/'budget.json',{'closed':True})
        proposal={'image':{'config_digest':'sha256:'+digest(config)},'candidate_dependencies':{'packages':[{'artifact':{'filename':'example.whl','size':len(package),'sha256':digest(package)}}]}}
        return old,cache,proposal

    def test_cached_stage_preserves_all_original_bytes_and_never_fetches(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);old,cache,proposal=self.fixture(base);new=base/'new';root=new/'run-fixture';root.mkdir(parents=True)
            worker.save(root/'supervisor.json',{'validation_only':True,'campaign':str(new),'cache_only_from':str(old)})
            before={p.relative_to(old).as_posix():p.read_bytes() for p in old.rglob('*') if p.is_file()}
            original_read=worker.read
            def read(path):return proposal if path==worker.PROJECT/'results/runtime/task420-setup-proposal.json' else original_read(path)
            with mock.patch.object(worker,'read',side_effect=read),mock.patch('urllib.request.urlopen',side_effect=AssertionError('network prohibited')):
                worker.stage_cached(root)
            self.assertEqual(before,{p.relative_to(old).as_posix():p.read_bytes() for p in old.rglob('*') if p.is_file()})
            self.assertEqual(original_read(root/'transfer.json')['download_bytes'],0)
            self.assertEqual(original_read(root/'transfer.json')['verified_files'],4)
            self.assertNotEqual(original_read(root/'image/manifest.json')[0]['RepoTags'],['fixture:old'])

    def test_cache_tampering_extra_files_and_symlinks_fail(self):
        with tempfile.TemporaryDirectory() as d:
            old,cache,proposal=self.fixture(Path(d))
            worker.verified_cache_files(cache,proposal)
            extra=cache/'unexpected';extra.write_text('fixture')
            with self.assertRaises(RuntimeError):worker.verified_cache_files(cache,proposal)
            extra.unlink();extra.symlink_to(cache/'image/0/layer.tar')
            with self.assertRaises(RuntimeError):worker.verified_cache_files(cache,proposal)
            extra.unlink();(cache/'image/0/layer.tar').write_bytes(b'altered fixture')
            with self.assertRaises(RuntimeError):worker.verified_cache_files(cache,proposal)

    def test_validation_worker_cannot_dispatch_network_or_model_phase(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);worker.save(root/'supervisor.json',{'validation_only':True})
            with mock.patch('urllib.request.urlopen',side_effect=AssertionError('network prohibited')),mock.patch.object(worker,'run',side_effect=AssertionError('subprocess prohibited')):
                with self.assertRaises(RuntimeError):worker.stage(root)
                with self.assertRaises(RuntimeError):worker.pilot(root)
        self.assertEqual([x[0] for x in supervisor.work_phases(True,True)],['stage-cached','start','import','setup'])
        with self.assertRaises(ValueError):supervisor.work_phases(False,True)

    def test_new_budget_has_zero_transfer_without_touching_old_budget(self):
        with tempfile.TemporaryDirectory() as d:
            old=Path(d)/'old';a=SharedBudget(old);a.state['closed']=True;a.save();a.close();before=(old/'budget.json').read_bytes()
            b=SharedBudget(Path(d)/'new',download_limit=0)
            try:self.assertEqual(b.state['download_limit'],0);self.assertEqual(b.begin('only'),300*10**9)
            finally:b.close()
            self.assertEqual((old/'budget.json').read_bytes(),before)


if __name__=='__main__':unittest.main()
