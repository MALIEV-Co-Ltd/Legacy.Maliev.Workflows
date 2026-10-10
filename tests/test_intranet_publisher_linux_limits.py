"""Actual Linux process/file guards, with Python child fixtures and no Docker.

These establish inherited RLIMIT/timeout/temp cleanup, not real daemon export.
"""
import errno
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
workflow=(ROOT/'.github/workflows/publish-image.yml').read_text()
block=workflow.split('      - name: Verify packaged Intranet assets and source revision\n',1)[1].split('      - name: Verify packaged Web assets',1)[0]
program='\n'.join(line.removeprefix('          ') for line in block.split('        run: |\n',1)[1].splitlines()).rstrip()
namespace={'__name__':'linux_source_fixture'}
exec(compile(program,'actual_intranet_publisher_step','exec'),namespace)


class LinuxGuardTests(unittest.TestCase):
    def test_cli_child_inherits_limit_and_partial_file_is_bounded_and_removed(self):
        previous=resource.getrlimit(resource.RLIMIT_FSIZE)
        namespace['ARCHIVE_LIMIT']=4096
        with tempfile.TemporaryDirectory(prefix='intranet-linux-file-') as temporary:
            path=Path(temporary)/'partial-export'
            with namespace['export_disk_guard'](temporary):
                self.assertLessEqual(resource.getrlimit(resource.RLIMIT_FSIZE)[0],4096)
                result=subprocess.run([sys.executable,'-B','-c',
                    'import errno,sys\ntry:\n with open(sys.argv[1],"wb",buffering=0) as output:\n  output.write(b"x"*4096)\n  output.write(b"x")\nexcept OSError as failure:\n sys.exit(91 if failure.errno==errno.EFBIG else 92)',str(path)],
                    capture_output=True,timeout=5)
                self.assertEqual(91,result.returncode)
                self.assertLessEqual(path.stat().st_size,4096)
            self.assertEqual(previous,resource.getrlimit(resource.RLIMIT_FSIZE))
        self.assertFalse(Path(temporary).exists())

    def test_limit_restored_when_export_operation_raises(self):
        previous=resource.getrlimit(resource.RLIMIT_FSIZE)
        namespace['ARCHIVE_LIMIT']=4096
        with tempfile.TemporaryDirectory(prefix='intranet-linux-restore-') as temporary:
            with self.assertRaises(OSError),namespace['export_disk_guard'](temporary):
                raise OSError(errno.EFBIG,'synthetic file limit failure')
        self.assertEqual(previous,resource.getrlimit(resource.RLIMIT_FSIZE))
        self.assertFalse(Path(temporary).exists())

    def test_actual_native_timeout_terminates_direct_child_and_restores_temp_files(self):
        actual_run=subprocess.run
        seen=[]
        with tempfile.TemporaryDirectory(prefix='intranet-linux-timeout-') as temporary:
            ledger=Path(temporary)/'identity.json'
            fixture='''import json,os,pathlib,sys,time
p=pathlib.Path('/proc/self')
pathlib.Path(sys.argv[1]).write_text(json.dumps(dict(pid=os.getpid(),startTicks=(p/'stat').read_text().rsplit(')',1)[1].split()[19],executable=os.readlink(p/'exe'),purpose='finite direct-child timeout fixture',expiryUnix=time.time()+5,ports=[],persistentData=False)))
time.sleep(5)
'''
            def finite_fixture(arguments,**options):
                self.assertEqual(['docker','synthetic-timeout'],arguments)
                self.assertEqual(120,options['timeout'])
                seen.append(True)
                # Test-only executable/time substitution keeps the native
                # subprocess timeout implementation and direct-child cleanup.
                return actual_run([sys.executable,'-B','-c',fixture,str(ledger)],capture_output=True,timeout=1.5)
            with patch.object(namespace['subprocess'],'run',finite_fixture):
                with self.assertRaises(subprocess.TimeoutExpired):
                    namespace['native'](['synthetic-timeout'])
            self.assertEqual([True],seen)
            identity=json.loads(ledger.read_text())
            process=Path('/proc')/str(identity['pid'])
            if process.exists():
                current=(process/'stat').read_text().rsplit(')',1)[1].split()[19]
                self.assertNotEqual(identity['startTicks'],current,'Owned child remains alive after timeout')
        self.assertFalse(Path(temporary).exists())


if __name__=='__main__':
    if not sys.platform.startswith('linux'):
        raise RuntimeError('Linux runner required; no substitute enforcement claim.')
    unittest.main(verbosity=2)
