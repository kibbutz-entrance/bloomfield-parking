import importlib.util
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('persist', Path(__file__).resolve().parents[1]/'scripts/persist_snapshot.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = Path.cwd()
        root = Path(self.tmp.name)
        subprocess.run(['git','init','--bare',str(root/'remote')],check=True,capture_output=True)
        subprocess.run(['git','clone',str(root/'remote'),str(root/'work')],check=True,capture_output=True)
        os.chdir(root/'work')
        p.git('checkout','-b','main')
        p.git('config','user.name','test')
        p.git('config','user.email','test@example.com')
        Path('data').mkdir()
        Path('games.json').write_text('old')
        Path('data/source-cache.json').write_text('old')
        p.git('add','.')
        p.git('commit','-m','initial')
        p.git('push','origin','main')
        self.base = p.git('rev-parse','HEAD')
        Path('games.json').write_text('fresh')
        Path('data/source-cache.json').write_text('fresh cache')
        self.real = p.git

    def tearDown(self):
        os.chdir(self.old)
        self.tmp.cleanup()

    def remote(self):
        self.real('fetch','origin','main')
        return self.real('rev-parse','FETCH_HEAD')

    def test_saved_and_verified(self):
        self.assertEqual(p.persist(delay=lambda _:None),'saved')
        self.assertEqual(self.remote(),self.real('rev-parse','HEAD'))

    def test_transient_server_error_retries(self):
        pushes = []
        def flaky(*args):
            if args[0]=='push':
                pushes.append(args)
                if len(pushes)==1:
                    raise subprocess.CalledProcessError(1,args,stderr='Internal Server Error')
            return self.real(*args)
        with patch.object(p,'git',side_effect=flaky):
            self.assertEqual(p.persist(delay=lambda _:None),'saved')
        self.assertEqual(len(pushes),2)

    def test_lost_push_response_is_detected_without_second_push(self):
        pushes = []
        def ambiguous(*args):
            result = self.real(*args)
            if args[0]=='push':
                pushes.append(args)
                raise subprocess.TimeoutExpired(args,45)
            return result
        with patch.object(p,'git',side_effect=ambiguous):
            self.assertEqual(p.persist(delay=lambda _:None),'saved')
        self.assertEqual(len(pushes),1)

    def test_exhausted_retries_leave_remote_untouched(self):
        pushes=[]
        def offline(*args):
            if args[0]=='push':
                pushes.append(args)
                raise subprocess.CalledProcessError(1,args)
            return self.real(*args)
        with patch.object(p,'git',side_effect=offline):
            with self.assertRaises(RuntimeError):
                p.persist(delay=lambda _:None)
        self.assertEqual(len(pushes),3)
        self.assertEqual(self.remote(),self.base)

    def test_competing_revision_is_never_overwritten(self):
        tree=self.real('rev-parse','HEAD^{tree}')
        newer=self.real('commit-tree',tree,'-p',self.base,'-m','developer change')
        self.real('push','origin',newer+':refs/heads/main')
        self.assertEqual(p.persist(delay=lambda _:None),'superseded')
        self.assertEqual(self.remote(),newer)

    def test_unchanged_does_not_create_commit(self):
        self.real('checkout','--','games.json','data/source-cache.json')
        self.assertEqual(p.persist(),'unchanged')
        self.assertEqual(self.real('rev-parse','HEAD'),self.base)

    def test_competing_update_during_push_is_detected_on_retry(self):
        newer=self.real('commit-tree',self.real('rev-parse','HEAD^{tree}'),'-p',self.base,'-m','new code')
        pushes=[]
        def racing(*args):
            if args[0]=='push':
                pushes.append(args)
                self.real('push','origin',newer+':refs/heads/main')
            return self.real(*args)
        with patch.object(p,'git',side_effect=racing):
            self.assertEqual(p.persist(delay=lambda _:None),'superseded')
        self.assertEqual(len(pushes),1)
        self.assertEqual(self.remote(),newer)
