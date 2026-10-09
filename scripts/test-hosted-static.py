import base64
from datetime import datetime,timedelta,timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
import uuid
import zipfile

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('guarded',ROOT/'run-hosted-static.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

from functools import lru_cache

@lru_cache(maxsize=1)
def real_kit():
    policy=json.loads((ROOT/'hosted-static-policy.json').read_bytes())
    path=ROOT/'sealed-static-kit.zip'
    data=path.read_bytes() if path.is_file() else mod.fetch(policy)
    mod.verified_entries(data,policy)
    return data

def sealed_source(name):
    policy=json.loads((ROOT/'hosted-static-policy.json').read_bytes())
    return mod.verified_entries(real_kit(),policy)['outputs/'+name]

class SealedStaticControls(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,9,tzinfo=timezone.utc)
        self.policy={'worktree':'D:/fixed','baseSha':'a'*40,'candidateSha':'b'*64}
        self.permit={'issuedBy':mod.ROOT,'owner':mod.OWNER,'phase':'hosted-qualification','leaseId':str(uuid.uuid4()),'issuedUtc':self.now.isoformat(),'expiresUtc':(self.now+timedelta(minutes=10)).isoformat(),'worktree':'D:/fixed','baseSha':'a'*40,'candidateSha':'b'*64}
        self.context={'repository':mod.REPOSITORY,'ref':'refs/heads/main','eventName':'workflow_dispatch','sha':'c'*40,'job':{'workflow_repository':mod.REPOSITORY,'workflow_sha':'c'*40}}
    def encode(self,value): return json.dumps(value).encode()
    def kit(self,names=None,symlink=False):
        output=io.BytesIO();names=names or [('outputs/one.py',b'fixed')]
        with zipfile.ZipFile(output,'w') as z:
            for name,raw in names:
                item=zipfile.ZipInfo(name)
                if symlink:item.external_attr=0o120777<<16
                z.writestr(item,raw)
        data=output.getvalue()
        policy={'entries':{name:{'bytes':len(raw),'sha256':mod.digest(raw)} for name,raw in names},'kitBytes':len(data),'kitSha256':mod.digest(data),'kitGitBlob':hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()}
        return data,policy
    def test_exact_context(self): mod.validate_context(self.context,'c'*40)
    def test_foreign_context(self):
        self.context['repository']='foreign'
        with self.assertRaises(ValueError):mod.validate_context(self.context,'c'*40)
    def test_branch_context(self):
        self.context['ref']='refs/heads/proposal'
        with self.assertRaises(ValueError):mod.validate_context(self.context,'c'*40)
    def test_job_identity_missing(self):
        self.context.pop('job')
        with self.assertRaises(ValueError):mod.validate_context(self.context,'c'*40)
    def test_foreign_job_sha(self):
        self.context['job']['workflow_sha']='d'*40
        with self.assertRaises(ValueError):mod.validate_context(self.context,'c'*40)
    def test_exact_permit(self):self.assertEqual(self.permit,mod.validate_permit(self.encode(self.permit),self.policy,self.now))
    def test_foreign_issuer(self):
        self.permit['issuedBy']='foreign'
        with self.assertRaises(ValueError):mod.validate_permit(self.encode(self.permit),self.policy,self.now)
    def test_wrong_phase(self):
        self.permit['phase']='validation'
        with self.assertRaises(ValueError):mod.validate_permit(self.encode(self.permit),self.policy,self.now)
    def test_expired(self):
        with self.assertRaises(ValueError):mod.validate_permit(self.encode(self.permit),self.policy,self.now+timedelta(minutes=10))
    def test_extended_permit(self):
        self.permit['expiresUtc']=(self.now+timedelta(minutes=16)).isoformat()
        with self.assertRaises(ValueError):mod.validate_permit(self.encode(self.permit),self.policy,self.now)
    def test_extra_permit(self):
        self.permit['floor']='0'
        with self.assertRaises(ValueError):mod.validate_permit(self.encode(self.permit),self.policy,self.now)
    def test_exact_kit(self):
        data,policy=self.kit();self.assertEqual({'outputs/one.py':b'fixed'},mod.verified_entries(data,policy))
    def test_extra_member(self):
        data,policy=self.kit();policy['entries']={}
        with self.assertRaises(ValueError):mod.verified_entries(data,policy)
    def test_traversal_member(self):
        data,policy=self.kit([('outputs/../one.py',b'x')])
        with self.assertRaises(ValueError):mod.verified_entries(data,policy)
    def test_symlink_member(self):
        data,policy=self.kit(symlink=True)
        with self.assertRaises(ValueError):mod.verified_entries(data,policy)
    def test_changed_postimage(self):
        data,policy=self.kit();policy['entries']['outputs/one.py']['sha256']='0'*64
        with self.assertRaises(ValueError):mod.verified_entries(data,policy)
    def test_member_quota(self):
        data,policy=self.kit();policy['entries']['outputs/one.py']['bytes']=17*1024*1024
        with self.assertRaises(ValueError):mod.verified_entries(data,policy)
    def test_exact_git_blob(self):
        data,policy=self.kit();raw=self.encode({'sha':policy['kitGitBlob'],'size':len(data),'encoding':'base64','content':base64.b64encode(data).decode()})
        self.assertEqual(data,mod.decode_blob(raw,policy))
    def test_foreign_blob(self):
        data,policy=self.kit();raw=self.encode({'sha':'0'*40,'size':len(data),'encoding':'base64','content':base64.b64encode(data).decode()})
        with self.assertRaises(ValueError):mod.decode_blob(raw,policy)
    def test_duplicate_json(self):
        with self.assertRaises(ValueError):mod.validate_permit(b'{"owner":"one","owner":"two"}',self.policy,self.now)
    def test_real_sealed_candidate(self):
        policy=json.loads((ROOT/'hosted-static-policy.json').read_bytes());data=real_kit()
        files=mod.verified_entries(data,policy)
        self.assertEqual(174,len(files));self.assertEqual(policy['kitSha256'],mod.digest(data))
        core=files['outputs/hosted_static_core.py'];self.assertEqual(policy['coreSha256'],mod.digest(core))
        self.assertEqual(5120,policy['initialMemoryFloorMiB']);self.assertEqual(4096,policy['runtimeMemoryFloorMiB'])
    def test_native_fixed_commands(self):
        policy=json.loads((ROOT/'hosted-static-policy.json').read_bytes());data=real_kit()
        source=mod.verified_entries(data,policy)['outputs/hosted_static_core.py'].decode('utf-8')
        self.assertIn("'focused': [",source);self.assertIn("'suite': [",source)
        for token in ["'restore': [","'format': [","'audit': [","memory_limit=3 * 1024**3","cpu_rate=5000","output_limit=4 * 1024 * 1024","min(600", "--configfile"]:self.assertIn(token,source)


class PreparationCustodyControls(unittest.TestCase):
    def flags(self):
        return {name:True for name in ('terminal_state_verified','job_caps_readback_verified','cleanup_verified','process_handle_closed','thread_handle_closed','job_handle_closed','pipe_handles_closed','readers_settled','attribute_list_disposed')}
    def test_thrown_preparation_retains_birth_and_error_row(self):
        ledger=[];first=RuntimeError('first');first.resource_row={'pid':123,'actual_start_filetime':456,'executable_identity':'fixed.exe'}
        def failed(arguments,**kwargs):
            kwargs['on_event']('suspended-root-owned',first.resource_row)
            raise first
        with self.assertRaises(RuntimeError) as caught:mod.preparation_command(failed,ledger,['fixed'])
        self.assertIs(first,caught.exception);self.assertEqual(2,len(ledger));self.assertEqual(123,ledger[0]['pid']);self.assertEqual(456,ledger[1]['actual_start_filetime'])
    def test_error_row_retained_without_callback(self):
        ledger=[];first=OSError('first');first.resource_row={'pid':123}
        def failed(arguments,**kwargs):raise first
        with self.assertRaises(OSError):mod.preparation_command(failed,ledger,['fixed'])
        self.assertEqual([{'pid':123}],ledger)
    def test_success_requires_integer_zero_and_all_flags(self):
        from types import SimpleNamespace
        row=dict(self.flags(),remaining_job_processes=0)
        def success(arguments,**kwargs):return SimpleNamespace(returncode=0,stdout=b'ok'),row
        self.assertEqual(b'ok',mod.preparation_command(success,[],['fixed']))
        row['remaining_job_processes']=False
        with self.assertRaises(RuntimeError):mod.preparation_command(success,[],['fixed'])
    def test_missing_cleanup_flag_refused(self):
        from types import SimpleNamespace
        row=dict(self.flags(),remaining_job_processes=0);row.pop('attribute_list_disposed')
        with self.assertRaises(RuntimeError):mod.preparation_command(lambda *a,**k:(SimpleNamespace(returncode=0,stdout=b'ok'),row),[],['fixed'])
    def test_primary_preserved_when_cleanup_and_receipt_throw(self):
        first=RuntimeError('original')
        def cleanup():raise OSError('secondary cleanup')
        def receipt(state,errors):raise PermissionError('secondary receipt')
        with self.assertRaises(RuntimeError) as caught:mod.preserve_first_failure(first,cleanup,receipt)
        self.assertIs(first,caught.exception)
    def test_receipt_failure_becomes_failure_if_body_succeeded(self):
        failure=PermissionError('receipt')
        def receipt(state,errors):raise failure
        with self.assertRaises(PermissionError) as caught:mod.preserve_first_failure(None,lambda:{'cleanupVerified':True},receipt)
        self.assertIs(failure,caught.exception)

class PackageGraphControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from types import ModuleType
        policy=json.loads((ROOT/'hosted-static-policy.json').read_bytes())
        data=real_kit()
        source=mod.verified_entries(data,policy)['outputs/hosted_package_graph.py']
        cls.graph=ModuleType('sealed_package_graph')
        exec(compile(source,'sealed/hosted_package_graph.py','exec'),cls.graph.__dict__)
    def setUp(self):
        import tempfile,copy
        self.temporary=tempfile.TemporaryDirectory(prefix='sealed-graph-pure-');self.addCleanup(self.temporary.cleanup)
        self.repo=Path(self.temporary.name);self.cache=self.repo/'cache';self.package=self.cache/'x/1.0/x.1.0.nupkg';self.package.parent.mkdir(parents=True)
        raw=b'synthetic physical archive';self.package.write_bytes(raw)
        pin={'bytes':len(raw),'sha256':mod.digest(raw),'filename':self.package.name,'archiveSha512':base64.b64encode(hashlib.sha512(raw).digest()).decode(),'sha512':'signed-content-hash'}
        library={'type':'package','path':'x/1.0','sha512':'signed-content-hash'}
        self.assets={'targets':{'net10.0':{'x/1.0':{'type':'package'}}},'libraries':{'x/1.0':library},'packageFolders':{str(self.cache):{}}}
        self.snapshot={'projects':{},'packages':{'x/1.0':pin}}
        for name in ['one','two','three']:
            relative=name+'/obj/project.assets.json';path=self.repo/relative;path.parent.mkdir(parents=True);path.write_text(json.dumps(self.assets))
            self.snapshot['projects'][relative]={'identity':self.graph.identity(copy.deepcopy(self.assets))}
        self.assertTrue(self.graph.verify_restored(self.repo,self.snapshot,self.cache)['resolvedGraphMatched'])
    def mutate_assets(self,change):
        path=self.repo/'one/obj/project.assets.json';value=json.loads(path.read_bytes());change(value);path.write_text(json.dumps(value))
    def test_declared_signed_content_hash_distinct_from_archive_hash(self):
        self.assertNotEqual(self.snapshot['packages']['x/1.0']['sha512'],self.snapshot['packages']['x/1.0']['archiveSha512'])
        self.assertEqual(1,self.graph.verify_restored(self.repo,self.snapshot,self.cache)['packageArchives'])
    def test_package_version_drift(self):
        self.mutate_assets(lambda a:a['libraries'].update({'foreign/9.9':{'type':'package','path':'foreign/9.9','sha512':'foreign'}}))
        with self.assertRaises(ValueError):self.graph.verify_restored(self.repo,self.snapshot,self.cache)
    def test_framework_drift(self):
        self.mutate_assets(lambda a:a.update(targets={'net99.0':{}}))
        with self.assertRaises(ValueError):self.graph.verify_restored(self.repo,self.snapshot,self.cache)
    def test_semantic_content_hash_drift(self):
        self.mutate_assets(lambda a:a['libraries']['x/1.0'].update(sha512='foreign'))
        with self.assertRaises(ValueError):self.graph.verify_restored(self.repo,self.snapshot,self.cache)
    def test_archive_bytes_drift(self):
        self.package.write_bytes(b'changed')
        with self.assertRaises(ValueError):self.graph.verify_restored(self.repo,self.snapshot,self.cache)
    def test_foreign_cache_root(self):
        self.mutate_assets(lambda a:a.update(packageFolders={str(self.repo/'foreign'): {}}))
        with self.assertRaises(ValueError):self.graph.verify_restored(self.repo,self.snapshot,self.cache)
    def test_missing_graph(self):
        self.snapshot['projects'].pop(next(iter(self.snapshot['projects'])))
        with self.assertRaises(ValueError):self.graph.verify_restored(self.repo,self.snapshot,self.cache)
    def test_incomplete_closure(self):
        self.snapshot['packages']['missing/9.9']={}
        with self.assertRaises(ValueError):self.graph.verify_restored(self.repo,self.snapshot,self.cache)
    def test_foreign_project_path(self):
        self.snapshot['projects']['../outside.json']=self.snapshot['projects'].pop(next(iter(self.snapshot['projects'])))
        with self.assertRaises(ValueError):self.graph.verify_restored(self.repo,self.snapshot,self.cache)

class SdkIdentityControls(unittest.TestCase):
    def setUp(self):
        self.expected={mod.SDK_ROOT+'/'+name:'a'*64 for name in mod.SDK_RELATIVE}
        self.records=[{'outcome':'read','bytes':length,'sha256':'a'*64} for length in mod.SDK_LENGTHS]
        self.calls=[]
    def reader(self,path):
        self.calls.append(str(path));return dict(self.records[len(self.calls)-1])
    def baseline(self):
        result=mod.sdk_identity(self.expected,self.reader)
        self.assertTrue(result['allFiveMatch']);self.assertFalse(result['observedHashesAreAuthority']);self.calls=[]
    def test_five_fixed_identity_rows(self):
        self.baseline();result=mod.sdk_identity(self.expected,self.reader)
        self.assertEqual(list(range(5)),[r['index'] for r in result['files']])
        self.assertEqual(5,len(self.calls));self.assertNotIn('path',json.dumps(result))
    def test_hash_mismatch_does_not_become_authority(self):
        self.baseline();self.records[0]['sha256']='b'*64
        result=mod.sdk_identity(self.expected,self.reader)
        self.assertFalse(result['allFiveMatch']);self.assertEqual('hash-mismatch',result['files'][0]['outcome']);self.assertEqual('a'*64,result['files'][0]['expectedSha256'])
    def test_length_mismatch(self):
        self.baseline();self.records[1]['bytes']+=1
        self.assertEqual('length-mismatch',mod.sdk_identity(self.expected,self.reader)['files'][1]['outcome'])
    def test_typed_missing_and_unreadable(self):
        self.baseline();self.records[2]={'outcome':'missing','bytes':None,'sha256':None};self.records[3]={'outcome':'unreadable','bytes':None,'sha256':None}
        result=mod.sdk_identity(self.expected,self.reader)
        self.assertEqual('missing',result['files'][2]['outcome']);self.assertEqual('unreadable',result['files'][3]['outcome']);self.assertEqual(5,len(result['files']))
    def test_typed_oversized_and_symlink(self):
        self.baseline();self.records[2]={'outcome':'oversized','bytes':mod.SDK_FILE_QUOTA+1,'sha256':None};self.records[3]={'outcome':'symlink','bytes':None,'sha256':None}
        result=mod.sdk_identity(self.expected,self.reader);self.assertFalse(result['allFiveMatch']);self.assertEqual('oversized',result['files'][2]['outcome']);self.assertEqual('symlink',result['files'][3]['outcome'])
    def test_foreign_path_or_incomplete_map_refused_before_read(self):
        self.baseline();self.expected['foreign']=self.expected.pop(next(iter(self.expected)))
        with self.assertRaises(ValueError):mod.sdk_identity(self.expected,self.reader)
        self.assertEqual([],self.calls)
    def test_invalid_expected_hash_refused(self):
        self.baseline();self.expected[next(iter(self.expected))]='unexpected'
        with self.assertRaises(ValueError):mod.sdk_identity(self.expected,self.reader)
    def test_shared_image_is_diagnostic_only(self):
        self.baseline();result=mod.sdk_identity(self.expected,self.reader,shared_image=True)
        self.assertEqual('shared-image',result['source']);self.assertFalse(result['observedHashesAreAuthority']);self.assertTrue(all(p.startswith('C:/Program Files/dotnet/') for p in self.calls))

class SdkArchiveControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('sdk_bootstrap',ROOT/'hosted-sdk-bootstrap.py')
        cls.bootstrap=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.bootstrap)
    def archive(self,names):
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w') as z:
            for name,raw in names:z.writestr(name,raw)
        return zipfile.ZipFile(io.BytesIO(data.getvalue()))
    def test_fresh_canonical_archive_extracts(self):
        import tempfile,time
        with tempfile.TemporaryDirectory() as directory,self.archive([('sdk/one.dll',b'fixed')]) as archive:
            result=self.bootstrap.safe_extract(archive,Path(directory),time.monotonic()+5)
            self.assertTrue(result['canonicalInventoryVerified']);self.assertEqual(b'fixed',(Path(directory)/'sdk/one.dll').read_bytes())
    def test_parent_traversal_refused(self):
        with self.archive([('../escape.dll',b'fixed')]) as archive:
            with self.assertRaises(ValueError):self.bootstrap.inventory(archive)
    def test_absolute_path_refused(self):
        with self.archive([('/escape.dll',b'fixed')]) as archive:
            with self.assertRaises(ValueError):self.bootstrap.inventory(archive)
    def test_drive_path_refused(self):
        with self.archive([('C:/escape.dll',b'fixed')]) as archive:
            with self.assertRaises(ValueError):self.bootstrap.inventory(archive)
    def test_backslash_path_refused(self):
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w') as writer:writer.writestr('sdk/escape.dll',b'fixed')
        raw=data.getvalue().replace(b'sdk/escape.dll',b'sdk\\escape.dll')
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            with self.assertRaises(ValueError):self.bootstrap.inventory(archive)
    def test_case_ambiguous_members_refused(self):
        with self.archive([('sdk/one.dll',b'one'),('sdk/ONE.dll',b'two')]) as archive:
            with self.assertRaises(ValueError):self.bootstrap.inventory(archive)
    def test_duplicate_member_refused(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            with self.archive([('sdk/one.dll',b'one'),('sdk/one.dll',b'two')]) as archive:
                with self.assertRaises(ValueError):self.bootstrap.inventory(archive)
    def test_symlink_archive_member_refused(self):
        data=io.BytesIO();item=zipfile.ZipInfo('sdk/one.dll');item.external_attr=0o120777<<16
        with zipfile.ZipFile(data,'w') as z:z.writestr(item,b'target')
        with zipfile.ZipFile(io.BytesIO(data.getvalue())) as archive:
            with self.assertRaises(ValueError):self.bootstrap.inventory(archive)
    def test_existing_file_never_overwritten(self):
        import tempfile,time
        with tempfile.TemporaryDirectory() as directory,self.archive([('one.dll',b'new')]) as archive:
            path=Path(directory)/'one.dll';path.write_bytes(b'prior')
            with self.assertRaises(FileExistsError):self.bootstrap.safe_extract(archive,Path(directory),time.monotonic()+5)
            self.assertEqual(b'prior',path.read_bytes())
    def test_expired_extract_deadline_refused(self):
        import tempfile,time
        with tempfile.TemporaryDirectory() as directory,self.archive([('one.dll',b'new')]) as archive:
            with self.assertRaises(TimeoutError):self.bootstrap.safe_extract(archive,Path(directory),time.monotonic()-1)
    def test_archive_hash_and_length_positive_then_drift(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'archive.zip';path.write_bytes(b'fixed');expected=hashlib.sha512(b'fixed').hexdigest()
            self.assertTrue(self.bootstrap.verify_archive(path,5,expected)['officialArchiveMatched'])
            path.write_bytes(b'drift')
            with self.assertRaises(ValueError):self.bootstrap.verify_archive(path,5,expected)
            path.write_bytes(b'fixed')
            with self.assertRaises(ValueError):self.bootstrap.verify_archive(path,6,expected)

class SdkCleanupIdentityControls(unittest.TestCase):
    def setUp(self):
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        temporary=TemporaryDirectory(prefix='sdk-cleanup-identity-')
        self.addCleanup(temporary.cleanup)
        self.sdk_root=Path(temporary.name).resolve()
        binding=patch.object(mod,'SDK_ROOT',str(self.sdk_root))
        binding.start()
        self.addCleanup(binding.stop)
        self.permit={'leaseId':'synthetic-source-control','expiresUtc':'2000-01-01T00:00:00Z'}
        self.owner={'owner':mod.OWNER,**self.permit,'persistentData':False}
        mod.validate_sdk_cleanup(mod.SDK_ROOT,self.owner,self.permit)
    def test_fixture_root_is_absolute_on_current_platform(self):
        self.assertTrue(Path(mod.SDK_ROOT).is_absolute())
        self.assertEqual(Path(mod.SDK_ROOT),Path(mod.SDK_ROOT).resolve())
    def test_relative_provider_root_refused(self):
        from unittest.mock import patch
        with patch.object(mod,'SDK_ROOT','relative-sdk-cleanup-root'):
            with self.assertRaises(ValueError):mod.validate_sdk_cleanup(mod.SDK_ROOT,self.owner,self.permit)
    def test_symlink_marker_refused(self):
        from unittest.mock import patch
        with patch.object(Path,'is_symlink',return_value=True):
            with self.assertRaises(ValueError):mod.validate_sdk_cleanup(mod.SDK_ROOT,self.owner,self.permit)
    def test_exact_startup_lease_cleanup_without_renewal(self):
        before=dict(self.permit);mod.validate_sdk_cleanup(mod.SDK_ROOT,self.owner,self.permit);self.assertEqual(before,self.permit)
    def test_foreign_lease_refused(self):
        self.owner['leaseId']='foreign'
        with self.assertRaises(ValueError):mod.validate_sdk_cleanup(mod.SDK_ROOT,self.owner,self.permit)
    def test_foreign_root_refused(self):
        with self.assertRaises(ValueError):mod.validate_sdk_cleanup('C:/Program Files/dotnet',self.owner,self.permit)
    def test_persistent_data_marker_refused(self):
        self.owner['persistentData']=True
        with self.assertRaises(ValueError):mod.validate_sdk_cleanup(mod.SDK_ROOT,self.owner,self.permit)


class CheckoutByteIdentityControls(unittest.TestCase):
    def setUp(self):
        self.raw=b'fixed\npublic\n'
        self.pin=mod.digest(self.raw)
        self.baseline=mod.bootstrap_source_identity(self.raw,self.pin,len(self.raw))
        self.assertTrue(self.baseline['exactReviewedBytes'])
    def test_exact_source_observed_without_promoting_hash(self):
        self.assertEqual(self.pin,self.baseline['observedSha256'])
        self.assertFalse(self.baseline['observedHashesAreAuthority'])
    def test_crlf_conversion_rejected_with_physical_diagnostics(self):
        raw=self.raw.replace(b'\n',b'\r\n')
        row=mod.bootstrap_source_identity(raw,self.pin,len(self.raw))
        self.assertFalse(row['exactReviewedBytes']);self.assertEqual(2,row['crlfCount'])
        self.assertEqual(len(raw),row['observedBytes']);self.assertNotEqual(self.pin,row['observedSha256'])
    def test_same_length_content_drift_rejected(self):
        self.assertFalse(mod.bootstrap_source_identity(b'drift\npublic\n',self.pin,len(self.raw))['exactReviewedBytes'])
    def test_exact_hash_wrong_expected_length_rejected(self):
        self.assertFalse(mod.bootstrap_source_identity(self.raw,self.pin,len(self.raw)+1)['exactReviewedBytes'])
    def test_checkout_config_and_diagnostics_are_workflow_scoped(self):
        path=ROOT/'workflow.yml'
        if not path.exists():path=ROOT.parent/'.github/workflows/sealed-static.yml'
        workflow=path.read_text()
        for value in ("      GIT_CONFIG_COUNT: '1'",'      GIT_CONFIG_KEY_0: core.autocrlf',"      GIT_CONFIG_VALUE_0: 'false'",'outputs/sdk-bootstrap-source.json','outputs/sdk-bootstrap-source.bin'):
            self.assertIn(value,workflow)
        self.assertNotIn('git config --global core.autocrlf',workflow)


class CandidateGitNormalizationControls(unittest.TestCase):
    def test_candidate_birth_overrides_only_git_normalization(self):
        import ast
        tree=ast.parse((ROOT/'run-hosted-static.py').read_bytes())
        calls=[node for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='command' and node.args and isinstance(node.args[0],ast.Constant) and node.args[0].value=='candidate-checkout']
        self.assertEqual(1,len(calls))
        self.assertEqual(['git','-c','core.autocrlf=true','worktree','add','--detach'],[ast.literal_eval(node) for node in calls[0].args[1].elts[:6]])
    def test_candidate_scope_preserves_original_frozen_guard(self):
        import ast
        policy=json.loads((ROOT/'hosted-static-policy.json').read_bytes())
        data=real_kit()
        entries=mod.verified_entries(data,policy);raw=entries['outputs/hosted_static_core.py']
        tree=ast.parse(raw)
        calls=[node for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='run_owned' and node.args and isinstance(node.args[0],ast.List) and any(isinstance(value,ast.Constant) and value.value=='status' for value in node.args[0].elts)]
        self.assertEqual(1,len(calls))
        self.assertEqual(['git','-c','core.autocrlf=true','status','--porcelain=v1','--untracked-files=all'],ast.literal_eval(calls[0].args[0]))
        frozen=entries['outputs/workflows-gitleaks-toolchain-build-request-20261008-v3/scope-frozen.txt']
        self.assertEqual('56263288362806c71c9cf79fb8fbddb2ee4e8b62a49436e899284cf7e95c3e0d',mod.digest(frozen))
        self.assertEqual(3,len(frozen.splitlines()))
        self.assertIn(b'scope.stdout != expected_scope.read_bytes()',raw)
        self.assertIn(b"raise RuntimeError('Workflows owned or preserved source bytes changed')",raw)


class FreshQualificationPhaseControls(unittest.TestCase):
    def evidence(self):
        import ast, types, sys
        policy=json.loads((ROOT/'hosted-static-policy.json').read_bytes())
        data=real_kit()
        entries=mod.verified_entries(data,policy)
        tree=ast.parse(entries['outputs/hosted_static_core.py'])
        strict=types.ModuleType('artifact_pin_native_result_validation_v3')
        exec(compile(entries['outputs/artifact_pin_native_result_validation_v3.py'],'<sealed-strict>','exec'),strict.__dict__)
        previous=sys.modules.get(strict.__name__);sys.modules[strict.__name__]=strict
        association=types.ModuleType('sealed_association')
        try:exec(compile(entries['outputs/workflows_gitleaks_compiled_result_association_v1.py'],'<sealed-association>','exec'),association.__dict__)
        finally:
            if previous is None:sys.modules.pop(strict.__name__,None)
            else:sys.modules[strict.__name__]=previous
        return ast,entries,tree,association
    def branch(self,phase):
        ast,entries,tree,association=self.evidence()
        node=next(n for n in ast.walk(tree) if isinstance(n,ast.If) and isinstance(n.test,ast.Compare) and isinstance(n.test.left,ast.Name) and n.test.left.id=='current_phase' and len(n.test.comparators)==1 and isinstance(n.test.comparators[0],ast.Constant) and n.test.comparators[0].value==phase)
        return compile(ast.Module(body=node.body,type_ignores=[]),'<actual-phase-branch>','exec'),association
    def test_build_baseline_and_failures_use_actual_guard(self):
        from types import SimpleNamespace
        code,association=self.branch('build')
        baseline=b'Build succeeded.\n0 Warning(s)\n0 Error(s)\n'
        from unittest.mock import Mock
        capture=Mock(return_value='a'*64)
        state={'result':SimpleNamespace(stdout=baseline),'phase_receipts':{},'current_phase':'build','verify_built_assembly':capture,'verify_built_runtime':Mock(return_value={'deps':'d'*64,'runtimeconfig':'e'*64})}
        exec(code,state);self.assertEqual(0,state['phase_receipts']['build']['warnings']);self.assertEqual('a'*64,state['phase_receipts']['build']['builtAssemblySha256']);capture.assert_called_once_with()
        for raw in [baseline.replace(b'0 Warning',b'1 Warning'),baseline.replace(b'Build succeeded.',b'Build failed.'),b'Build succeeded.\n']:
            capture=Mock(side_effect=AssertionError('Failed build must not capture assembly'))
            with self.subTest(raw=raw),self.assertRaises(RuntimeError):exec(code,{'result':SimpleNamespace(stdout=raw),'phase_receipts':{},'current_phase':'build','verify_built_assembly':capture,'verify_built_runtime':Mock(return_value={'deps':'d'*64,'runtimeconfig':'e'*64})})
            capture.assert_not_called()
    def test_fresh_discovery_refuses_missing_duplicate_or_old_go_identity(self):
        from types import SimpleNamespace
        from tempfile import TemporaryDirectory
        code,association=self.branch('discovery')
        focus=association.focused_names([dict(method=m,arguments=None,executed=False) for m in association.METHODS])
        names=focus+[association.ASSEMBLY+'.Synthetic.Case'+str(i) for i in range(489)]
        for mutation in ['baseline','missing','duplicate','old-go','historical-assembly']:
            with self.subTest(mutation=mutation),TemporaryDirectory() as temporary:
                actual=names.copy()
                if mutation=='missing':actual.pop()
                if mutation=='duplicate':actual[-1]=actual[-2]
                assembly=str(Path(temporary)/'tests/Legacy.Maliev.Workflows.Tests/bin/Release/net10.0/Legacy.Maliev.Workflows.Tests.dll')
                data=[]
                for i,name in enumerate(actual):
                    class_name,method=name.split('(',1)[0].rsplit('.',1)
                    data.append(dict(Assembly=assembly,DisplayName=name,ID=hashlib.sha256(str(i).encode()).hexdigest(),Class=class_name,Method=method))
                text=json.dumps(data)
                if mutation=='old-go':text=text.replace('go1.26.9+auto','go1.26.8+auto')
                state=dict(result=SimpleNamespace(stdout=text.encode(),stderr=b''),REPO=Path(temporary),runroot=Path(temporary),CANDIDATE='a'*64,BASE='b'*40,association=association,json=json,current_phase='discovery',phase_receipts={},datetime=__import__('datetime').datetime,timezone=__import__('datetime').timezone,sha=lambda p:'e2278ee608bf879e73ba5f49955143d1a7613c959552be5c47b7e9abef08c74d' if mutation=='historical-assembly' else 'c'*64)
                if mutation=='baseline':exec(code,state);self.assertEqual(497,len(state['FRESH_INVENTORY']['names']))
                else:
                    with self.assertRaises((ValueError,RuntimeError)):exec(code,state)
    def test_tampered_assembly_after_discovery_uses_actual_guard(self):
        ast,entries,tree,association=self.evidence()
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='candidate_check')
        node=next(n for n in function.body if isinstance(n,ast.If) and isinstance(n.test,ast.Compare) and isinstance(n.test.left,ast.Name) and n.test.left.id=='FRESH_INVENTORY')
        code=compile(ast.Module(body=node.body,type_ignores=[]),'<actual-fresh-custody>','exec')
        state=dict(FRESH_INVENTORY={},REPO=Path('/modeled'),ASSEMBLY_HASH='a'*64,sha=lambda path:'b'*64)
        with self.assertRaises(RuntimeError):exec(code,state)
    def test_phase_order_and_no_old_receipt_acceptance(self):
        ast,entries,tree,association=self.evidence()
        main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        commands=next(n.value for n in main.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='commands' for t in n.targets))
        self.assertEqual(['restore','build','discovery','focused','suite','format','audit'],[n.value for n in commands.keys])
        self.assertFalse(any('/bin/' in name or 'build-b909' in name or 'validation-81cc' in name for name in entries))
        self.assertNotIn(b'RAW_BUILD_HASHES',entries['outputs/hosted_static_core.py'])
    def test_fixed_shared_deadline_and_resource_supervision(self):
        ast,entries,tree,association=self.evidence()
        core=entries['outputs/hosted_static_core.py'].decode()
        for text in ['timeout = min(600, remaining-25)','phase_deadline-time.monotonic()',"raise RuntimeError('Fixed remaining validation route deadline exceeded')",'supervisor.supervise(owned._quarantined, recover, slot, journal, checkpoint,','memory_limit=3 * 1024**3','cpu_rate=5000','output_limit=4 * 1024 * 1024']:
            self.assertIn(text,core)



class PhasePolicyMetadataControls(unittest.TestCase):
    def test_policy_phase_authority_matches_actual_core_and_historical_replay_semantics(self):
        import ast
        policy=json.loads((ROOT/'hosted-static-policy.json').read_bytes())
        data=real_kit()
        entries=mod.verified_entries(data,policy)
        main=next(n for n in ast.parse(entries['outputs/hosted_static_core.py']).body if isinstance(n,ast.FunctionDef) and n.name=='main')
        commands=next(n.value for n in main.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='commands' for t in n.targets))
        self.assertEqual([n.value for n in commands.keys],policy['nativePhases'])
        self.assertEqual(['restore','build','discovery','focused','suite','format','audit'],policy['nativePhases'])
        self.assertNotIn('buildOrTestReplayed',policy)
        self.assertIs(False,policy['historicalBuildOrTestsReplayed'])
        wrapper=(ROOT/'run-hosted-static.py').read_text()
        self.assertIn("'historicalBuildOrTestsReplayed':False",wrapper)
        self.assertNotIn('no builds or tests',wrapper)






class LinuxDiscoveryObservationControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.runtime=LinuxProviderControls().modules()['workflows_linux_runtime']
    def test_scalar_and_unlimited_limits(self):
        for name in self.runtime.COUNTER_FILES:
            if 'events' not in name: self.assertEqual(64,self.runtime.parse_discovery_counter(name,b'64\n'))
        for name in ('pids.max','memory.max'): self.assertEqual('max',self.runtime.parse_discovery_counter(name,b'max\n'))
    def test_closed_event_shape(self):
        self.assertEqual({'max':3},self.runtime.parse_discovery_counter('pids.events',b'max 3\n'))
        value=self.runtime.parse_discovery_counter('memory.events',b'low 0\nhigh 0\nmax 1\noom 1\noom_kill 0\noom_group_kill 0\n')
        self.assertEqual(1,value['oom'])
    def test_missing_counter_bytes_are_rejected(self):
        for raw in (None,b'',b'\n'):
            with self.subTest(raw=raw),self.assertRaises((RuntimeError,ValueError)): self.runtime.parse_discovery_counter('pids.current',raw)
    def test_malformed_counter_is_not_zero(self):
        for raw in (b'-1',b'01',b' 1',b'1 2',b'1\n\n',b'1.0',b'x',b'\xff',b'1'*4097):
            with self.subTest(raw=raw),self.assertRaises((RuntimeError,ValueError)): self.runtime.parse_discovery_counter('memory.current',raw)
    def test_max_only_allowed_for_limits(self):
        for name in ('pids.current','pids.peak','memory.current','memory.peak'):
            with self.subTest(name=name),self.assertRaises(RuntimeError): self.runtime.parse_discovery_counter(name,b'max')
    def test_foreign_counter_name_rejected(self):
        with self.assertRaises(RuntimeError): self.runtime.parse_discovery_counter('memory.swap.max',b'0')
    def test_duplicate_or_unknown_events_rejected(self):
        for raw in (b'max 0\nmax 1\n',b'max 0\nforeign 1\n',b'max  0\n',b'max -1\n'):
            with self.subTest(raw=raw),self.assertRaises(RuntimeError): self.runtime.parse_discovery_counter('pids.events',raw)
    def test_missing_memory_event_key_rejected(self):
        with self.assertRaises(RuntimeError): self.runtime.parse_discovery_counter('memory.events.local',b'low 0\nhigh 0\nmax 0\noom 0\n')
    def snapshot(self, *, malformed=False, missing=False, foreign=False, expired=False):
        import tempfile,types,time,json
        from unittest.mock import patch
        runtime=self.runtime
        with tempfile.TemporaryDirectory() as directory:
            root=Path('/sys/fs/cgroup/owned-fixture')
            def verify(group):
                if foreign: raise RuntimeError('foreign group')
            scope=types.SimpleNamespace(root=root,deadline=time.monotonic()+(-1 if expired else 10),verify=verify)
            def read(path,bound=4096):
                if path.name=='cgroup.procs':return b''
                if missing and path.name=='pids.peak':raise FileNotFoundError()
                if malformed and path.name=='pids.current':return b'corrupt'
                if path.name.startswith('memory.events'):return b'low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\n'
                if path.name=='pids.events':return b'max 0\n'
                return b'64\n'
            row={}
            with patch.object(runtime,'SCOPE',scope),patch.object(runtime,'observation_read',read):
                runtime.retain_discovery_observation(Path(directory)/'discovery.log','terminal',row)
            raw=(Path(directory)/'discovery-observation-terminal.json').read_bytes()
            self.assertLessEqual(len(raw),65536)
            self.assertEqual(len(raw),row['discoveryObservations']['terminal']['bytes'])
            self.assertFalse(json.loads(raw)['qualified'])
            return json.loads(raw)
    def test_missing_peak_is_explicitly_unavailable(self):
        self.assertEqual({'status':'unavailable','value':None,'reason':'FileNotFoundError'},self.snapshot(missing=True)['groups']['sdk']['pids.peak'])
    def test_malformed_observation_remains_unknown(self):
        self.assertIsNone(self.snapshot(malformed=True)['groups']['root']['pids.current']['value'])
    def test_foreign_group_never_enumerated(self):
        body=self.snapshot(foreign=True);self.assertEqual('incomplete',body['status']);self.assertEqual({},body['groups']);self.assertEqual([],body['processes'])
    def test_expired_budget_never_renewed(self):
        self.assertEqual('incomplete',self.snapshot(expired=True)['status'])
    def process(self, *, foreign=False, reused=False):
        import sys,types,stat
        from unittest.mock import patch
        runtime=self.runtime;expected='/owned/sdk'
        helper=types.SimpleNamespace(group_of=lambda pid:'/foreign' if foreign else expected)
        def read(path,bound=4096):
            if path.name=='status':return b'Name:\tdotnet\nThreads:\t3\n'
            if path.name=='0':return b'pos:\t0\nflags:\t0100000\n'
            if path.name=='limits':return b'Max processes             64                   64                   processes\nMax open files            1024                 4096                 files\nMax stack size            8388608              unlimited            bytes\nMax address space         unlimited            unlimited            bytes\n'
            raise AssertionError('Unexpected readonly process input')
        with patch.dict(sys.modules,{'workflows_linux_owned_scope_v1':helper}),patch.object(runtime,'start_ticks',side_effect=[17,18 if reused else 17]),patch.object(runtime,'observation_read',side_effect=read) as reads,patch.object(Path,'stat',return_value=types.SimpleNamespace(st_mode=stat.S_IFIFO)):
            if foreign:
                with self.assertRaises(RuntimeError):runtime.discovery_process(123,expected)
                reads.assert_not_called();return
            return runtime.discovery_process(123,expected)
    def test_exact_process_birth_thread_stdin_and_limits(self):
        body=self.process();self.assertEqual(17,body['startTicks']);self.assertEqual(3,body['threads'])
        self.assertEqual({'type':'pipe','flagsOctal':'0100000'},body['stdin'])
        self.assertEqual('64',body['limits']['Max processes']['hard'])
    def test_foreign_process_rejected_before_reading_descriptors(self):
        self.process(foreign=True)
    def test_process_birth_change_rejected(self):
        with self.assertRaises(RuntimeError):self.process(reused=True)
    def test_actual_crash_diagnostic_remains_rejected(self):
        from types import SimpleNamespace
        from tempfile import TemporaryDirectory
        from datetime import datetime,timezone
        code,association=FreshQualificationPhaseControls().branch('discovery')
        with TemporaryDirectory() as directory:
            # Modeled stderr oracle from the retained COMBINED crash text;
            # the failed run's separate stream bytes are unavailable.
            state=dict(result=SimpleNamespace(stdout=b'The following Tests are available:\n',
                stderr=b'Win32Exception (11): Resource temporarily unavailable\nOut of memory.\n'),
                REPO=Path(directory),runroot=Path(directory),CANDIDATE='a'*64,BASE='b'*40,
                association=association,json=json,datetime=datetime,timezone=timezone,sha=lambda p:'c'*64)
            with self.assertRaisesRegex(RuntimeError,'Compiled discovery stderr differs'):exec(code,state)
            self.assertNotIn('ASSEMBLY_HASH',state)
            self.assertFalse(json.loads((Path(directory)/'discovery-assembly-observation.json').read_bytes())['qualified'])
    def test_telemetry_precedes_teardown_and_crash_guard_is_retained(self):
        import inspect
        policy=json.loads((ROOT/'hosted-static-policy.json').read_bytes());entries=mod.verified_entries(real_kit(),policy)
        runtime=entries['outputs/workflows_linux_runtime.py'].decode();core=entries['outputs/hosted_static_core.py'].decode()
        self.assertLess(runtime.index('retain_discovery_observation(log_path,"terminal",row)'),runtime.index("SCOPE.stop_group('sdk',effective)"))
        self.assertIn('if result.stderr.strip(): raise RuntimeError(\'Compiled discovery stderr differs\')',core)
        self.assertLess(core.index("'discovery-assembly-observation.json'"),core.index("Compiled discovery stderr differs"))
        self.assertLess(core.index('Compiled discovery stderr differs'),core.index('ASSEMBLY_HASH = sha(assembly)'))


class LinuxSdkThreadPressureControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.runtime=LinuxProviderControls().modules()['workflows_linux_runtime']
    def test_fixed_child_controls_override_inherited_runtime_settings(self):
        result=self.runtime.sdk_child_environment({'DOTNET_EnableDiagnostics':'1','DOTNET_PROCESSOR_COUNT':'4096','MSBUILDDISABLENODEREUSE':'0','DOTNET_CLI_DO_NOT_USE_MSBUILD_SERVER':'0'},'/owned/docker.sock')
        self.assertEqual('0',result['DOTNET_EnableDiagnostics'])
        for key in ('DOTNET_PROCESSOR_COUNT','MSBUILDDISABLENODEREUSE','DOTNET_CLI_DO_NOT_USE_MSBUILD_SERVER'):self.assertEqual('1',result[key])
        self.assertEqual('unix:///owned/docker.sock',result['DOCKER_HOST'])
    def test_parent_environment_not_mutated(self):
        parent={'DOTNET_EnableDiagnostics':'1','CUSTOM':'retained'};original=parent.copy()
        child=self.runtime.sdk_child_environment(parent,'/owned/socket')
        self.assertEqual(original,parent);self.assertEqual('retained',child['CUSTOM']);self.assertIsNot(parent,child)
    def test_non_dictionary_or_non_string_environment_refused(self):
        for value in (None,[],{'DOTNET_EnableDiagnostics':True},{1:'bad'},{'BAD':0}):
            with self.subTest(value=value),self.assertRaises(RuntimeError):self.runtime.sdk_child_environment(value,'/owned/socket')
    def test_invalid_socket_shape_refused(self):
        for value in (None,'',[],False):
            with self.subTest(value=value),self.assertRaises(RuntimeError):self.runtime.sdk_child_environment({},value)
    def actual_path(self, cleanup_failure=False):
        import tempfile,types,time,stat,contextlib
        from unittest.mock import patch,Mock
        runtime=self.runtime
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();group=root/'sdk';group.mkdir();home=root/'home';home.mkdir();owner=home.stat()
            spawn=Mock(side_effect=RuntimeError('controlled spawn failure after environment capture'))
            stop=Mock(side_effect=RuntimeError('controlled cleanup failure') if cleanup_failure else None)
            scope=types.SimpleNamespace(root=root,closed=False,daemon_failure=None,deadline=time.monotonic()+10,
                handles={group:70},uid=owner.st_uid,gid=owner.st_gid,cli_home=home,front_parent=root,verify=lambda path:None,spawn=spawn,stop_group=stop)
            real_stat=Path.stat
            def metadata(path,*args,**kwargs):
                row=real_stat(path,*args,**kwargs)
                return types.SimpleNamespace(st_uid=row.st_uid,st_gid=row.st_gid,st_mode=stat.S_IFDIR|0o700) if path==home else row
            parent={'DOTNET_EnableDiagnostics':'1','GH_TOKEN':'fixture-removed','ROOT_STATIC_PERMIT':'fixture-removed'}
            with patch('shutil.which',return_value='/owned/dotnet'),patch.object(runtime,'SCOPE',scope),patch.object(runtime,'check_cli_home'),patch.object(Path,'stat',metadata),patch.object(runtime,'registration_window',contextlib.nullcontext),patch.object(runtime,'bind_executable',return_value={'fd':71,'resolved':'/owned/dotnet','sha256':'a'*64}),patch.object(runtime,'recheck_executable'),patch.object(runtime.os,'dup',return_value=72),patch.object(runtime.os,'set_inheritable'),patch.object(runtime.os,'fstat',return_value=types.SimpleNamespace(st_dev=1,st_ino=2)),patch.object(runtime.os,'pipe',side_effect=[(73,74),(75,76)]),patch.object(runtime.os,'close') as close:
                with self.assertRaisesRegex(RuntimeError,'controlled spawn failure') as raised:
                    runtime.run_owned(['/owned/dotnet','test','fixed.csproj','--list-tests'],env=parent,timeout=2)
                row=raised.exception.resource_row
                env=spawn.call_args.args[5]
                self.assertEqual('0',env['DOTNET_EnableDiagnostics']);self.assertEqual('1',parent['DOTNET_EnableDiagnostics'])
                self.assertNotIn('GH_TOKEN',env);self.assertNotIn('ROOT_STATIC_PERMIT',env)
                self.assertEqual(['test','fixed.csproj','--list-tests'],spawn.call_args.args[0][-3:])
                self.assertEqual('sdk',spawn.call_args.args[1]);self.assertEqual(owner.st_uid,spawn.call_args.args[2])
                stop.assert_called_once();self.assertEqual('sdk',stop.call_args.args[0])
                if cleanup_failure:
                    self.assertIn(row['job_lease'],runtime._quarantined)
                    stop.side_effect=None;runtime.recover_quarantined(row['job_lease'])
                    self.assertNotIn(row['job_lease'],runtime._quarantined)
                self.assertEqual(0,row['remaining_job_processes'])
                for key in ('terminal_state_verified','cleanup_verified','process_handle_closed','thread_handle_closed','job_handle_closed','pipe_handles_closed','readers_settled','attribute_list_disposed'):self.assertIs(True,row[key])
                self.assertGreaterEqual(close.call_count,7)
    def test_actual_owned_command_passes_controlled_child_environment_and_cleans(self):
        self.actual_path()
    def test_actual_cleanup_failure_preserves_primary_and_recovers_exact_lease(self):
        self.actual_path(cleanup_failure=True)


class LinuxSuiteObservationControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.runtime=LinuxProviderControls().modules()['workflows_linux_runtime']
    def test_fixed_phase_selection_excludes_other_commands(self):
        for phase in ('discovery','focused','suite'):self.assertEqual(phase,self.runtime.observed_phase(Path('/owned')/(phase+'.log')))
        for path in (None,'audit.log','suite.log.extra','SUITE.log','suite-stdout.log'):
            self.assertIsNone(self.runtime.observed_phase(path))
    def test_unknown_phase_counter_retention_refused(self):
        with self.assertRaises(RuntimeError):self.runtime.retain_discovery_observation('audit.log','before',{})
    def test_invalid_stage_cannot_select_another_artifact_path(self):
        for stage in ('../escape','live-0','live-9','unknown',True):
            with self.subTest(stage=stage),self.assertRaises(RuntimeError):self.runtime.retain_discovery_observation('suite.log',stage,{})
    def test_live_sampler_honors_tighter_command_boundary(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        runtime=self.runtime;scope=SimpleNamespace(deadline=100);state={'count':0,'nextAt':0}
        with patch.object(runtime,'SCOPE',scope),patch.object(runtime.time,'monotonic',return_value=2),patch.object(runtime,'retain_discovery_observation') as observer:
            runtime.sample_phase_observation('suite.log',state,{},deadline=2)
            observer.assert_not_called();self.assertEqual(0,state['count']);self.assertEqual(100,scope.deadline)
    def sample(self,state,clock=2,deadline=10,phase='suite.log'):
        from types import SimpleNamespace
        from unittest.mock import patch
        runtime=self.runtime
        with patch.object(runtime,'SCOPE',SimpleNamespace(deadline=deadline)),patch.object(runtime.time,'monotonic',return_value=clock),patch.object(runtime,'retain_discovery_observation') as observer:
            runtime.sample_phase_observation(phase,state,{})
            return observer.call_args_list
    def test_live_sampler_closed_shape_and_types(self):
        for state in ({},{'count':0,'nextAt':1,'foreign':True},{'count':True,'nextAt':1},{'count':9,'nextAt':1},{'count':0,'nextAt':float('nan')},{'count':0,'nextAt':float('inf')},{'count':0,'nextAt':-1}):
            with self.subTest(state=state),self.assertRaises(RuntimeError):self.sample(state)
    def test_live_sampler_never_exceeds_eight_or_renews_deadline(self):
        state={'count':0,'nextAt':0}
        for second in range(1,12):self.sample(state,clock=second,deadline=20)
        self.assertEqual(8,state['count']);self.assertEqual(9,state['nextAt'])
        expired={'count':0,'nextAt':0};self.assertEqual([],self.sample(expired,clock=10,deadline=10));self.assertEqual(0,expired['count'])
    def test_live_sampler_does_not_sample_before_interval(self):
        state={'count':0,'nextAt':3};self.assertEqual([],self.sample(state,clock=2));self.assertEqual(0,state['count'])
    def test_each_observed_phase_retains_same_closed_counters_with_own_prefix(self):
        import tempfile,types,time
        from unittest.mock import patch
        runtime=self.runtime
        def read(path,bound=4096):
            if path.name=='cgroup.procs':return b''
            if path.name.startswith('memory.events'):return b'low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\n'
            if path.name=='pids.events':return b'max 0\n'
            return b'64\n'
        with tempfile.TemporaryDirectory() as directory:
            root=Path('/sys/fs/cgroup/owned');scope=types.SimpleNamespace(root=root,deadline=time.monotonic()+10,verify=lambda path:None)
            for phase in ('discovery','focused','suite'):
                row={}
                with patch.object(runtime,'SCOPE',scope),patch.object(runtime,'observation_read',read):runtime.retain_discovery_observation(Path(directory)/(phase+'.log'),'terminal',row)
                path=Path(directory)/(phase+'-observation-terminal.json');body=json.loads(path.read_bytes())
                self.assertFalse(body['qualified']);self.assertEqual(set(runtime.COUNTER_FILES),set(body['groups']['sdk']))
                self.assertEqual(path.name,row['discoveryObservations']['terminal']['file'])
    def test_suite_streams_and_pre_teardown_sampling_use_actual_command_path(self):
        policy=json.loads((ROOT/'hosted-static-policy.json').read_bytes());entries=mod.verified_entries(real_kit(),policy);raw=entries['outputs/workflows_linux_runtime.py'].decode()
        self.assertIn('if discovery_observation: sample_phase_observation(log_path,observation_state,row,deadline=deadline)',raw)
        self.assertIn('with_name(observation_phase+"-stdout.log")',raw);self.assertIn('with_name(observation_phase+"-stderr.log")',raw)
        self.assertLess(raw.index('retain_discovery_observation(log_path,"terminal",row)'),raw.index("SCOPE.stop_group('sdk',effective)"))


class LinuxBuiltDllControls(unittest.TestCase):
    def source(self):
        import ast
        raw=sealed_source('hosted_static_core.py');return raw.decode(),ast.parse(raw)
    def commands(self):
        import ast
        text,tree=self.source();main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        node=next(n for n in main.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='commands' for t in n.targets))
        return node.value
    def guard(self,root):
        import ast,stat,types,hashlib
        text,tree=self.source();names={'verify_built_assembly','sha','TEST_ASSEMBLY_RELATIVE'}
        nodes=[n for n in tree.body if (isinstance(n,ast.FunctionDef) and n.name in names) or (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in names for t in n.targets))]
        state=dict(Path=Path,REPO=root,stat=stat,hashlib=hashlib)
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'<actual-built-assembly-guard>','exec'),state)
        return state
    def fixture(self,operation):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();state=self.guard(root);assembly=root/state['TEST_ASSEMBLY_RELATIVE'];assembly.parent.mkdir(parents=True);assembly.write_bytes(b'newly built source fixture')
            operation(state,assembly,root)
    def test_exact_three_dll_commands_and_no_project_options(self):
        import ast
        node=self.commands();state={'OUT':Path('/sealed')};commands=eval(compile(ast.Expression(body=node),'<actual-phase-argv>','eval'),state)
        sdk='/tmp/maliev-workflows-qualification/private-sdk/sdk/dotnet';dll='tests/Legacy.Maliev.Workflows.Tests/bin/Release/net10.0/Legacy.Maliev.Workflows.Tests.dll'
        self.assertEqual([sdk,'exec',dll,'-preEnumerateTheories','-noColor','-list','full/json'],commands['discovery'])
        self.assertEqual([sdk,'exec',dll,'-preEnumerateTheories','-method','Legacy.Maliev.Workflows.Tests.RepositoryContractTests.GitleaksInstallation_When*'],commands['focused'])
        self.assertEqual([sdk,'exec',dll,'-preEnumerateTheories'],commands['suite'])
        self.assertEqual(['restore','build','discovery','focused','suite','format','audit'],list(commands))
    def evaluated_commands(self):
        import ast
        from pathlib import PurePosixPath
        # A fixed POSIX source directory makes str(OUT / config) independent of
        # host path separators and ast.dump empty-field defaults.
        return eval(compile(ast.Expression(body=self.commands()),'<actual-command-contract>','eval'),{'OUT':PurePosixPath('/sealed')})
    def assert_non_test_command_contract(self,commands):
        expected={'restore': ['/tmp/maliev-workflows-qualification/private-sdk/sdk/dotnet', 'restore', 'Legacy.Maliev.Workflows.slnx', '--disable-parallel', '--configfile', '/sealed/hosted-nuget.config', '-m:1', '/nr:false'], 'build': ['/tmp/maliev-workflows-qualification/private-sdk/sdk/dotnet', 'build', 'Legacy.Maliev.Workflows.slnx', '-c', 'Release', '--no-restore', '--no-incremental', '--disable-build-servers', '-m:1', '/p:UseSharedCompilation=false', '/nr:false', '-warnaserror'], 'format': ['/tmp/maliev-workflows-qualification/private-sdk/sdk/dotnet', 'format', 'Legacy.Maliev.Workflows.slnx', '--verify-no-changes', '--no-restore', '--include', 'tests/Legacy.Maliev.Workflows.Tests/RepositoryContractTests.cs'], 'audit': ['/tmp/maliev-workflows-qualification/private-sdk/sdk/dotnet', 'package', 'list', '--project', 'Legacy.Maliev.Workflows.slnx', '--vulnerable', '--include-transitive', '--no-restore', '--format', 'json', '--output-version', '1', '--source', 'https://api.nuget.org/v3/index.json']}
        actual={k:v for k,v in commands.items() if k not in ('discovery','focused','suite')}
        self.assertEqual(expected,actual)
    def test_non_test_commands_exact_argv_contract_unchanged(self):
        self.assert_non_test_command_contract(self.evaluated_commands())
    def test_non_test_command_mutations_are_rejected(self):
        for phase in ('restore','build','format','audit'):
            with self.subTest(phase=phase):
                commands=self.evaluated_commands();commands[phase][1]='foreign-command'
                with self.assertRaises(AssertionError):self.assert_non_test_command_contract(commands)
        for mutation in ('restore-config','restore-parallelism','extra-phase','missing-phase'):
            with self.subTest(mutation=mutation):
                commands=self.evaluated_commands()
                if mutation=='restore-config':commands['restore'][commands['restore'].index('/sealed/hosted-nuget.config')]='/sealed/foreign.config'
                elif mutation=='restore-parallelism':commands['restore'][commands['restore'].index('-m:1')]='-m:2'
                elif mutation=='extra-phase':commands['foreign']=['foreign']
                else:commands.pop('audit')
                with self.assertRaises(AssertionError):self.assert_non_test_command_contract(commands)
    def test_build_captures_before_discovery_and_rechecks_before_owned_spawn(self):
        text,tree=self.source()
        self.assertLess(text.index("if 'Build succeeded.' not in text"),text.index('BUILT_ASSEMBLY_HASH = verify_built_assembly()'))
        start=text.index('for current_phase, arguments in commands.items():');loop=text[start:]
        self.assertLess(loop.index('verify_built_assembly(BUILT_ASSEMBLY_HASH)'),loop.index('result, row = owned.run_owned(arguments'))
        self.assertIn("if BUILT_ASSEMBLY_HASH is None or BUILT_RUNTIME_HASHES is None:",loop)
        self.assertIn("builtAssemblySha256=BUILT_ASSEMBLY_HASH",text)
    def test_regular_fresh_assembly_capture_and_recheck(self):
        def operation(s,a,r):
            value=s['verify_built_assembly']();self.assertEqual(hashlib.sha256(a.read_bytes()).hexdigest(),value);self.assertEqual(value,s['verify_built_assembly'](value))
        self.fixture(operation)
    def test_missing_assembly_refused(self):
        def operation(s,a,r):
            a.unlink()
            with self.assertRaises(OSError):s['verify_built_assembly']()
        self.fixture(operation)
    def test_nonregular_assembly_refused(self):
        def operation(s,a,r):
            a.unlink();a.mkdir()
            with self.assertRaises(RuntimeError):s['verify_built_assembly']()
        self.fixture(operation)
    def test_empty_assembly_refused(self):
        def operation(s,a,r):
            a.write_bytes(b'')
            with self.assertRaises(RuntimeError):s['verify_built_assembly']()
        self.fixture(operation)
    def test_changed_assembly_refused(self):
        def operation(s,a,r):
            value=s['verify_built_assembly']();a.write_bytes(b'changed')
            with self.assertRaises(RuntimeError):s['verify_built_assembly'](value)
        self.fixture(operation)
    def test_malformed_binding_refused(self):
        def operation(s,a,r):
            for value in (True,1,'','G'*64,'a'*63,b'a'*64):
                with self.subTest(value=value),self.assertRaises(RuntimeError):s['verify_built_assembly'](value)
        self.fixture(operation)
    def test_historical_assembly_refused(self):
        def operation(s,a,r):
            s['sha']=lambda path:'e2278ee608bf879e73ba5f49955143d1a7613c959552be5c47b7e9abef08c74d'
            with self.assertRaises(RuntimeError):s['verify_built_assembly']()
        self.fixture(operation)
    def test_changed_during_hash_refused(self):
        def operation(s,a,r):
            original=s['sha']
            def raced(path):value=original(path);a.write_bytes(b'raced replacement');return value
            s['sha']=raced
            with self.assertRaises(RuntimeError):s['verify_built_assembly']()
        self.fixture(operation)
    def test_assembly_symlink_refused(self):
        def operation(s,a,r):
            target=r/'foreign.dll';target.write_bytes(a.read_bytes());a.unlink();a.symlink_to(target)
            with self.assertRaises(RuntimeError):s['verify_built_assembly']()
        self.fixture(operation)
    def test_parent_symlink_refused(self):
        def operation(s,a,r):
            parent=a.parent;moved=parent.with_name('moved');parent.rename(moved);parent.symlink_to(moved,target_is_directory=True)
            with self.assertRaises(RuntimeError):s['verify_built_assembly']()
        self.fixture(operation)
    def test_result_filter_inventory_and_resource_acceptance_guards_preserved(self):
        text,tree=self.source()
        for token in ("len(FRESH_INVENTORY['names']) != 497","association.verify_native(trx.read_bytes(), FRESH_INVENTORY, current_phase, ASSEMBLY_HASH, CANDIDATE, BASE)","arguments = arguments + ['-trx', str(runroot / 'test-results' / current_phase / (current_phase + '.trx'))]","memory_limit=3 * 1024**3",'cpu_rate=5000','output_limit=4 * 1024 * 1024','phase_deadline-time.monotonic()'):self.assertIn(token,text)


class LinuxDirectXunitControls(unittest.TestCase):
    def evidence(self):
        return FreshQualificationPhaseControls().evidence()
    def rows(self):
        ast,entries,tree,a=self.evidence()
        forecast=[dict(method=m,arguments=None,executed=False) for m in a.METHODS]
        names=a.focused_names(forecast)+[a.ASSEMBLY+'.RepositoryContractTests.NativeControl'+str(i) for i in range(489)]
        assembly='/tmp/maliev-workflows-qualification/worktree/tests/Legacy.Maliev.Workflows.Tests/bin/Release/net10.0/'+a.ASSEMBLY+'.dll'
        rows=[]
        for i,name in enumerate(names):
            cls,method=name.split('(',1)[0].rsplit('.',1)
            rows.append(dict(Assembly=assembly,DisplayName=name,ID=hashlib.sha256(str(i).encode()).hexdigest(),Class=cls,Method=method))
        return a,forecast,assembly,rows
    def parse(self,raw=None,mutate=None):
        a,forecast,assembly,rows=self.rows()
        if mutate:mutate(rows)
        return a.native_discovery(json.dumps(rows).encode() if raw is None else raw,forecast,'a'*64,'b'*64,'c'*40,assembly)
    def reject(self,mutate=None,raw=None):
        with self.assertRaises(ValueError):self.parse(raw=raw,mutate=mutate)
    def test_actual_native_full_json_retains497_ids_names_and_focused8(self):
        value=self.parse();self.assertEqual(497,len(value['names']));self.assertEqual(497,len(set(value['nativeCaseIds'])));self.assertEqual(8,len(value['focusedNames']));self.assertFalse(value['dynamicExpansionAllowed']);self.assertEqual('xunit3.2.2/full-json',value['nativeFormat'])
    def test_exact_native_traits_shape_supported_without_losing_names(self):
        before=self.parse();after=self.parse(mutate=lambda r:r[0].update(Traits={'Category':['Unit']}));self.assertEqual(before['names'],after['names'])
    def test_legacy_vstest_text_is_not_native_discovery(self):
        self.reject(raw=b'The following Tests are available:\n    Legacy.Maliev.Workflows.Tests.Old.Test\n')
    def test_duplicate_top_level_and_nested_json_keys_refused(self):
        a,f,assembly,rows=self.rows();raw=json.dumps(rows).replace('"Assembly":','"Assembly":"private-foreign", "Assembly":',1).encode();self.reject(raw=raw)
        self.reject(raw=json.dumps(rows).replace('"ID":','"Traits":{"private":["value"],"private":["value"]},"ID":',1).encode())
    def test_missing_extra_and_unexpanded_rows_refused(self):
        for mode in ('missing','extra','unexpanded'):
            def change(r):
                if mode=='missing':r.pop()
                elif mode=='extra':r.append(dict(r[-1],ID='f'*64))
                else:r[0]['DisplayName']=r[0]['Class']+'.'+r[0]['Method']
            with self.subTest(mode=mode):self.reject(change)
    def test_duplicate_case_ids_and_unapproved_duplicate_displays_refused(self):
        self.reject(lambda r:r[-1].update(ID=r[-2]['ID']))
        self.reject(lambda r:r[-1].update(DisplayName=r[-2]['DisplayName'],Class=r[-2]['Class'],Method=r[-2]['Method']))
    def test_foreign_assembly_class_method_or_display_refused(self):
        for field,value in [('Assembly','/foreign.dll'),('Class','Foreign.Tests'),('Method','foreign-method'),('DisplayName','Foreign.Display')]:
            with self.subTest(field=field):self.reject(lambda r:r[0].update({field:value}))
    def test_missing_unknown_wrong_case_or_skipped_row_field_refused(self):
        for mode in ('missing','unknown','case','skip'):
            def change(r):
                if mode=='missing':r[0].pop('ID')
                elif mode=='unknown':r[0]['Unexpected']='private'
                elif mode=='case':r[0]['id']=r[0].pop('ID')
                else:r[0]['Skip']='private skip'
            with self.subTest(mode=mode):self.reject(change)
    def test_malformed_ids_fields_traits_and_unicode_refused(self):
        for field,value in [('ID','G'*64),('ID','a'*63),('Class',None),('Method',True),('DisplayName','\ud800'),('DisplayName','x'*16385),('Traits',{}),('Traits',{'k':'value'}),('Traits',{'k':[True]}),('Traits',{'k':['x']*65})]:
            with self.subTest(field=field,value=repr(value)[:40]):self.reject(lambda r:r[0].update({field:value}))
    def test_json_shape_encoding_nonfinite_depth_and_byte_bounds_refused(self):
        for raw in (b'',b'\xff',b'{}',b'null',b'NaN',b'['*2000+b']'*2000,b' '* (4*1024*1024+1)):
            with self.subTest(length=len(raw)):self.reject(raw=raw)
    def test_changed_go_focused_identity_and_additional_focus_refused(self):
        def changed(r):
            row=next(row for row in r if 'go1.26.9' in row['DisplayName'])
            row['DisplayName']=row['DisplayName'].replace('go1.26.9','go1.26.8')
        self.reject(changed)
        def extra(r):
            r[-1].update(DisplayName=r[0]['DisplayName']+'foreign',Class=r[0]['Class'],Method=r[0]['Method'])
        self.reject(extra)
    def native_trx(self,inventory,phase):
        import xml.etree.ElementTree as ET
        a=self.evidence()[3];strict=a.strict;ns=strict.NS
        names=inventory['focusedNames'] if phase=='focused' else inventory['names']
        root=ET.Element(ns+'TestRun');results=ET.SubElement(root,ns+'Results');definitions=ET.SubElement(root,ns+'TestDefinitions')
        summary=ET.SubElement(root,ns+'ResultSummary',outcome='Completed');counts={key:'0' for key in strict.COUNTERS}
        for key in ('total','executed','passed'):counts[key]=str(len(names))
        ET.SubElement(summary,ns+'Counters',counts)
        for name in names:
            uid=str(uuid.uuid4());cls,method=name.split('(',1)[0].rsplit('.',1)
            definition=ET.SubElement(definitions,ns+'UnitTest',id=uid,name=a.native_trx_display(name));ET.SubElement(definition,ns+'Execution',id=uid)
            ET.SubElement(definition,ns+'TestMethod',codeBase='/fresh/Legacy.Maliev.Workflows.Tests.dll',className=cls,name=method,adapterTypeName='executor://source-control/xunit.v3/3.2.2')
            ET.SubElement(results,ns+'UnitTestResult',testId=uid,executionId=uid,testName=a.native_trx_display(name),outcome='Passed')
        return a,root
    def test_native_discovery_retains_unchanged_strict8_and497_trx_association(self):
        import xml.etree.ElementTree as ET
        inventory=self.parse()
        for phase,total in (('focused',8),('suite',497)):
            with self.subTest(phase=phase):
                a,root=self.native_trx(inventory,phase);result=a.verify_native(ET.tostring(root),inventory,phase,'a'*64,'b'*64,'c'*40)
                self.assertEqual(total,result['total']);self.assertTrue(result['allExecutionAssociationsVerified'])
    def test_native_trx_missing_definition_foreign_dll_duplicate_id_and_fail_refused(self):
        import xml.etree.ElementTree as ET
        inventory=self.parse()
        for mode in ('missing','foreign-dll','duplicate','failed'):
            with self.subTest(mode=mode):
                a,root=self.native_trx(inventory,'focused');ns=a.strict.NS
                if mode=='missing':root.find(ns+'TestDefinitions').remove(root.find(ns+'TestDefinitions')[0])
                elif mode=='foreign-dll':root.find(ns+'TestDefinitions')[0].find(ns+'TestMethod').set('codeBase','Foreign.dll')
                elif mode=='duplicate':root.find(ns+'Results')[1].set('executionId',root.find(ns+'Results')[0].get('executionId'))
                else:root.find(ns+'Results')[0].set('outcome','Failed')
                with self.assertRaises(ValueError):a.verify_native(ET.tostring(root),inventory,'focused','a'*64,'b'*64,'c'*40)
    def runtime_guard(self,root):
        import ast,stat
        text=sealed_source('hosted_static_core.py');tree=ast.parse(text)
        names={'verify_built_runtime','sha','TEST_ASSEMBLY_RELATIVE','TEST_RUNTIME_RELATIVES'}
        nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in names for t in n.targets)]
        state=dict(Path=Path,REPO=root,stat=stat,hashlib=hashlib)
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'<actual-runtime-file-guard>','exec'),state)
        return state
    def runtime_fixture(self,operation):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            root=Path(directory).resolve();state=self.runtime_guard(root);paths={k:root/v for k,v in state['TEST_RUNTIME_RELATIVES'].items()}
            for path in paths.values():path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'{"source":"fresh build runtime control"}')
            operation(state,paths,root)
    def test_real_original_runtime_paths_capture_and_recheck(self):
        def op(s,p,r):
            hashes=s['verify_built_runtime']();self.assertEqual({k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in p.items()},hashes);self.assertEqual(hashes,s['verify_built_runtime'](hashes))
            self.assertTrue(all('tests/Legacy.Maliev.Workflows.Tests/bin/Release/net10.0' in v.as_posix() for v in p.values()))
        self.runtime_fixture(op)
    def test_changed_missing_empty_nonregular_and_oversized_runtime_refused(self):
        for name in ('deps','runtimeconfig'):
            for mode in ('changed','missing','empty','directory','oversized'):
                def op(s,p,r):
                    hashes=s['verify_built_runtime']();path=p[name]
                    if mode=='changed':path.write_bytes(b'changed runtime')
                    elif mode=='missing':path.unlink()
                    elif mode=='empty':path.write_bytes(b'')
                    elif mode=='directory':path.unlink();path.mkdir()
                    else:path.write_bytes(b'x'*(4*1024*1024+1))
                    with self.assertRaises((RuntimeError,OSError)):s['verify_built_runtime'](hashes)
                with self.subTest(name=name,mode=mode):self.runtime_fixture(op)
    def test_runtime_symlink_parent_symlink_and_hash_race_refused(self):
        for mode in ('file','parent','race'):
            def op(s,p,r):
                path=p['deps']
                if mode=='file':
                    foreign=r/'foreign.json';foreign.write_bytes(path.read_bytes());path.unlink();path.symlink_to(foreign)
                elif mode=='parent':
                    parent=path.parent;moved=parent.with_name('moved');parent.rename(moved);parent.symlink_to(moved,target_is_directory=True)
                else:
                    original=s['sha']
                    def raced(current):value=original(current);current.write_bytes(b'raced runtime');return value
                    s['sha']=raced
                with self.assertRaises(RuntimeError):s['verify_built_runtime']()
            with self.subTest(mode=mode):self.runtime_fixture(op)
    def test_malformed_runtime_hash_map_refused(self):
        def op(s,p,r):
            for binding in ({},{'deps':'a'*64},{'deps':'a'*64,'runtimeconfig':True},{'deps':'A'*64,'runtimeconfig':'b'*64},{'deps':'a'*64,'runtimeconfig':'b'*64,'foreign':'c'*64},True):
                with self.subTest(binding=binding),self.assertRaises(RuntimeError):s['verify_built_runtime'](binding)
        self.runtime_fixture(op)
    def test_build_runtime_capture_and_rechecks_precede_direct_spawn(self):
        text=sealed_source('hosted_static_core.py').decode()
        self.assertLess(text.index("if 'Build succeeded.' not in text"),text.index('BUILT_RUNTIME_HASHES = verify_built_runtime()'))
        loop=text[text.index('for current_phase, arguments in commands.items():'):]
        self.assertLess(loop.index('verify_built_runtime(BUILT_RUNTIME_HASHES)'),loop.index('result, row = owned.run_owned(arguments'))
        self.assertIn('builtRuntimeFilesSha256=BUILT_RUNTIME_HASHES',text)
        self.assertIn('association.native_discovery(result.stdout',text)
    def test_actual_phase_failure_or_stop_never_accepts_discovery_or_trx(self):
        import ast,time
        from types import SimpleNamespace
        from unittest.mock import Mock
        from tempfile import TemporaryDirectory
        ast,entries,tree,a=self.evidence();main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        loop=next(n for n in ast.walk(main) if isinstance(n,ast.For) and isinstance(n.target,ast.Tuple) and any(isinstance(t,ast.Name) and t.id=='current_phase' for t in n.target.elts))
        code=compile(ast.Module(body=[loop],type_ignores=[]),'<actual-phase-loop>','exec')
        for phase in ('restore','build','discovery','focused','suite','format','audit'):
            for mode in ('exit','stop'):
                with self.subTest(phase=phase,mode=mode),TemporaryDirectory() as directory:
                    owned=SimpleNamespace(verify_result_directory=Mock(),run_owned=Mock(return_value=(SimpleNamespace(returncode=1 if mode=='exit' else 0),{'stop_reason':None if mode=='exit' else 'timeout'})))
                    receipts={};verify_dll=Mock();verify_runtime=Mock()
                    state=dict(commands={phase:['exact-phase-control']},BUILT_ASSEMBLY_HASH='a'*64,BUILT_RUNTIME_HASHES={'deps':'b'*64,'runtimeconfig':'c'*64},verify_built_assembly=verify_dll,verify_built_runtime=verify_runtime,owned=owned,runroot=Path(directory),result_directories={'focused':{},'suite':{}},recheck=Mock(),time=time,phase_deadline=time.monotonic()+600,expiry=datetime.now(timezone.utc)+timedelta(minutes=15),datetime=datetime,timezone=timezone,REPO=Path(directory),phase_receipts=receipts,event=Mock(),phase_env={})
                    with self.assertRaisesRegex(RuntimeError,'Native '+phase+' failed or exceeded its bound'):exec(code,state)
                    self.assertEqual({},receipts);owned.run_owned.assert_called_once()
                    expected=['exact-phase-control']+(['-trx',str(Path(directory)/'test-results'/phase/(phase+'.trx'))] if phase in ('focused','suite') else [])
                    self.assertEqual(expected,owned.run_owned.call_args.args[0])
    def test_missing_runtime_binding_blocks_actual_loop_before_spawn(self):
        import ast
        from unittest.mock import Mock
        ast,entries,tree,a=self.evidence();loop=next(n for n in ast.walk(tree) if isinstance(n,ast.For) and isinstance(n.target,ast.Tuple) and any(isinstance(t,ast.Name) and t.id=='current_phase' for t in n.target.elts))
        code=compile(ast.Module(body=[loop],type_ignores=[]),'<actual-phase-loop>','exec')
        for phase in ('discovery','focused','suite'):
            with self.subTest(phase=phase),self.assertRaisesRegex(RuntimeError,'Successful fresh Release build required'):exec(code,dict(commands={phase:[]},BUILT_ASSEMBLY_HASH='a'*64,BUILT_RUNTIME_HASHES=None))


class LinuxNativeDiscoveryColorControls(unittest.TestCase):
    def raw(self):
        import zlib
        data=zlib.decompress(base64.b64decode('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'))
        self.assertEqual(264912,len(data));self.assertEqual('690ace86a2f1dd8298d6fab944f7ead1cb368c035c7868937c09ad89216598d7',hashlib.sha256(data).hexdigest())
        return data
    def parse(self,data):
        a=FreshQualificationPhaseControls().evidence()[3]
        forecast=[dict(method=m,arguments=None,executed=False) for m in a.METHODS]
        return a.native_discovery(data,forecast,'58886646bc8a00fe979653b60881ee3b32990614a10eaa018835d27ba1eaf894','1bc40306fb96fbd85e27ccec1eaa6d96ef0a1c0c6d15e177c334bd38c2159ec3','53892c362a30130f582c40da7525e44f11474e8e','/tmp/maliev-workflows-qualification/worktree/tests/Legacy.Maliev.Workflows.Tests/bin/Release/net10.0/Legacy.Maliev.Workflows.Tests.dll')
    def test_real_native_raw_output_with_terminal_reset_still_rejected(self):
        # Strict production parser must never strip ANSI or accept trailing non-JSON.
        with self.assertRaises(ValueError):self.parse(self.raw())
    def test_real497_json_payload_without_exact_terminal_reset_has_strict_membership(self):
        # Diagnostic regression fixture only; no runtime/native acceptance claim.
        raw=self.raw();self.assertTrue(raw.endswith(b'\n\x1b[0m'))
        parsed=self.parse(raw[:-4]);self.assertEqual(497,len(parsed['names']));self.assertEqual(497,len(set(parsed['nativeCaseIds'])));self.assertEqual(8,len(parsed['focusedNames']));self.assertFalse(parsed['dynamicExpansionAllowed'])
    def test_unexpected_ansi_prefix_suffix_and_extra_json_still_rejected(self):
        payload=self.raw()[:-4]
        for changed in (b'\x1b[0m'+payload,payload+b'\x1b[31m',payload+b'[]',payload+b'\x1b[0m\x1b[0m'):
            with self.subTest(tail=repr(changed[-12:])):
                with self.assertRaises(ValueError):self.parse(changed)


class LinuxNativeResultEncodingControls(unittest.TestCase):
    def evidence(self):
        return FreshQualificationPhaseControls().evidence()[3]
    def inventory(self):
        raw=LinuxNativeDiscoveryColorControls().raw()[:-4]
        self.assertEqual('c9b18e8f861b2320a05da23c3a4fc59af6ac08764c0204f38606e2a9569a6c96',hashlib.sha256(raw).hexdigest())
        a=self.evidence()
        return a.native_discovery(raw,[dict(method=m,arguments=None,executed=False) for m in a.METHODS],'58886646bc8a00fe979653b60881ee3b32990614a10eaa018835d27ba1eaf894','1bc40306fb96fbd85e27ccec1eaa6d96ef0a1c0c6d15e177c334bd38c2159ec3','53892c362a30130f582c40da7525e44f11474e8e','/tmp/maliev-workflows-qualification/worktree/tests/Legacy.Maliev.Workflows.Tests/bin/Release/net10.0/Legacy.Maliev.Workflows.Tests.dll')
    def trx(self):
        import zlib
        raw=zlib.decompress(base64.b64decode('eNrtW21v3DYS/t5fIeyHwx1arkSKr74kaOq6RYD0BYl7/XJAQJGUzYtWckTKif99R1rtJlmkLX1dI7voAv4g0TPkzPB5SGo4++jShfhiaDNvHy9MbSzWnKCSSINoXRZIFVQjbg1XUmGCdbXIWr1yjxd918Wvh/Z1271tM1IQjnCBCnWJ8VnBzzBdMsEUK/GXRXFWFIusH9pfguvXiovs3appw+PFdYw3Z3m+8qbvQlfHpelWeTDXbqVD/h8fBt28jIP1XX7p9Gq0NScFLhZPvsiyR5d+5UJmeqej79rHiwQr3gxu8O1VkmyIuo9JkrVvfbj+lChbFkQxhouNaL62HBx56WIEU8IcT+tqPTQQmXEiuKGWcSIRJtIiasoKaawp0lXJuaZMUW03fb1wAfTC+Axvv7Q+TlM6tWYRHn+c+n/urrS5W/6gG+9ul792/eu66d6G5Sgcli/cTRd87Pq7866NvTZx3f69j43Tr8OzFqLRNFOgX/167drLrmvMtfbtS9c4Mzaf6/bb3tfx1Qv3P2gJ59e6vXL2or31fdeuXBv/eaPj9Vn233+8Gbr4bz1phdx2sXUR3YJhVkeXr9uXd6tmFvwqA1BM5rmz7LIf3FfZaoiTKdvOVj4ECOb89q9F1g0RtMDvn3UIDoI1RuLy7gZacGmsUVYhaysGKB/jqoRFVnFmgALc0mot/9yH+AymQxoJYoqighqMKKEVUpJLxIQmlkqGNZ5HGKVxXRnHBUFGOgKTJyiqKFDJ8oKVVcUFQGeRuXfODKMP6SpjGIbo+vWEztxbZHboZwJMGIO/JWaSU8JmDI88+TSOhSikUmwDTtfa35dVpRJUlB8B+agAt7zy8Xqo8rcbU3ah93uY+0434dBBV9VCCSc5YrxWiEolkWalQWVBpbG8cpUWO6BLU0kHXVEQooj6U9AphhWhPA10jJZUihPoth1edXhJ+FJ9qYfYHQT0rGYWJtShunZwaoC1CiljoH9u6qknpc0O9NJU7gU9xgqRAD1KZSkToQeLY0FO0Hu/Yx8K4oSQXPBKIqFrOB4pwJDUokaVYLSgojKV2EVcmsp9EIdZSUkC4gRWMhVxUkh8xDvsXo90h7fQUSYrrLVFhJYaUcpAuoSRalPAuJo5XfId2KWp3At2WHGaADspJRFpsOPQKWcn2B3WIlcIYcpSl7AzUjieCSJQpeG0RpQoSiVdiRndQVuayr3QBoD5888IQBDBOBVtmLKSfy60Qaqjdf0Wc8/CT411/StITYSLd6D+9Fb7RleN+77bCu0LbZ8XTyV3Ck70DjmmQFrANigdd4gYIXCFK2vl7qaZpnI/PHGVsHrxssSEJOKJcthhjxdPf+2Y9pm/Oi0hpqwZwtTViDLouiIwCKFwjhdOw8nK7X51JqncC1NCyiIBUxQWwcRUB+fwoUA/ztnlHyTapgTet27M+02LwQ7o5pTe3yzl5pMTWQG81lcQoTyubvLVFB+0xT96A1lfX3szjTfxIvbO5SPoQv6HQc0r38I8QfyCy8FFDPj4Y42lbZrFevpgAi82SL2HM/lWe+zwBxevOwvhs+4bMOJgXMxMA6vDX1gCN3n/vcJzkWmrb4Dn43K1Nm69WHQ93AqkXEfk7wYg3fK2zMslWZL3G0C+IeORcPPhs5M+Oed3JPxMc+bEzxM/jyiR65PTo0fC0jRnTiw9sfTwc94+OZN8JORMc+ZEzhM5j+R6wCcn3Y+EoWnOnBh6Yuhh36T45PuJIyFmmjMnYp6I+bkvnXzyVc6RUC/NmRP1/n/0nai3v/s5n3zrdSx51yRnTvQ7fPo9yj9xkTnN1wW46N3mYnPTcneIZfH5Ho18sDLqfRr5YAW3+zTywWo092nkg1X07dPIBysE26eRD1ZdtFd2P1S5Sv5+Mf1g4ZxsHi39cBkd3+ctYy4oyX7sYubbTGfj/9bnhTS/8k/3+7Rpsuedts5m8xBzcYaiMPFcIMlKQAUhGp6sABA7Rx3mvLL6I1+2ts8/Mns5rFYaZmBbcXQOp53GRSg6mi0574YWtq2QxQ52QfBjE05np5ebqURpeqxh2xsfx2Kcvu/66SlCTQ70Pj3rquvjLOFb07WmGYK/dVPDuqNvhvG3i08/EGy7saUd99PN+8XWAHi3PkBPLXxwzg1vdd9Ovwgs1lVHkzvzmD/33VXvQliPCCVDG8GPKoLmqDz5Yh00GP7Jb4PX86w='))
        self.assertEqual(14678,len(raw));self.assertEqual('183cbd5602b40191d602f9a6365a6ce55350ad9c293a6d3006734318d94a65b7',hashlib.sha256(raw).hexdigest())
        return raw
    def verify(self,raw=None,inventory=None,phase='focused'):
        return self.evidence().verify_native(self.trx() if raw is None else raw,self.inventory() if inventory is None else inventory,phase,'58886646bc8a00fe979653b60881ee3b32990614a10eaa018835d27ba1eaf894','1bc40306fb96fbd85e27ccec1eaa6d96ef0a1c0c6d15e177c334bd38c2159ec3','53892c362a30130f582c40da7525e44f11474e8e')
    def test_actual_frozen8trx_and497compiled_inventory_exact_forward_join(self):
        value=self.verify();self.assertEqual(8,value['total']);self.assertTrue(value['allExecutionAssociationsVerified']);self.assertEqual('xunit3.2.2/ExecutionSink.XmlEscape',value['nativeDisplayEncoding'])
    def test_original_legacy_verifier_still_rejects_native_escaped_fixture(self):
        a=self.evidence()
        with self.assertRaises(ValueError):a.verify(self.trx(),self.inventory(),'focused','58886646bc8a00fe979653b60881ee3b32990614a10eaa018835d27ba1eaf894','1bc40306fb96fbd85e27ccec1eaa6d96ef0a1c0c6d15e177c334bd38c2159ec3','53892c362a30130f582c40da7525e44f11474e8e')
    def test_forward_encoder_exact_quotes_slashes_controls_and_unicode(self):
        a=self.evidence();cases=[('"',r'\"'),('\\',r'\\'),('\x00',r'\0'),('\x07',r'\a'),('\b',r'\b'),('\f',r'\f'),('\n',r'\n'),('\r',r'\r'),('\t',r'\t'),('\v',r'\v'),('\x01',r'\x01'),('\x1f',r'\x1f'),('\ufffe',r'\xfffe'),('\uffff',r'\xffff'),('ไทย😊','ไทย😊')]
        for value,expected in cases:
            with self.subTest(value=repr(value)):self.assertEqual(expected,a.native_trx_display(value))
        for value in (None,'',True,'x'*16385):
            with self.subTest(value=repr(value)[:20]),self.assertRaises(ValueError):a.native_trx_display(value)
        with self.assertRaises(UnicodeError):a.native_trx_display('\ud800')
    def test_real497_inventory_and_synthetic_fulltrx_preserve_reviewed_duplicate(self):
        import xml.etree.ElementTree as ET
        inventory=self.inventory();a,root=LinuxDirectXunitControls().native_trx(inventory,'suite')
        self.assertEqual({a.ALLOWED_DUPLICATE:2},inventory['displayMultiplicity'])
        value=self.verify(ET.tostring(root),inventory,'suite');self.assertEqual(497,value['total'])
    def mutation(self,change):
        import xml.etree.ElementTree as ET
        root=ET.fromstring(self.trx());change(root,self.evidence().strict.NS)
        return ET.tostring(root)
    def test_actual_trx_missing_definition_duplicate_ids_and_failed_result_refused(self):
        for mode in ('missing-definition','duplicate-id','failed'):
            def change(root,ns):
                definitions=root.find(ns+'TestDefinitions');results=root.find(ns+'Results')
                if mode=='missing-definition':definitions.remove(definitions[-1])
                elif mode=='duplicate-id':results[-1].set('testId',results[0].get('testId'))
                else:results[0].set('outcome','Failed')
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.verify(self.mutation(change))
    def test_actual_trx_foreign_dll_class_or_method_refused(self):
        for key,value in [('codeBase','/foreign.dll'),('className','Foreign.Tests'),('name','ForeignMethod')]:
            def change(root,ns):root.find(ns+'TestDefinitions')[0].find(ns+'TestMethod').set(key,value)
            with self.subTest(key=key),self.assertRaises(ValueError):self.verify(self.mutation(change))
    def test_unescaped_double_encoded_and_foreign_names_refused_without_normalization(self):
        for mode in ('unescaped','double','foreign'):
            def change(root,ns):
                result=root.find(ns+'Results')[0];definition=root.find(ns+'TestDefinitions')[0];name=definition.get('name')
                value=name.replace('\\"','"') if mode=='unescaped' else self.evidence().native_trx_display(name) if mode=='double' else name+'foreign'
                definition.set('name',value);result.set('testName',value)
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.verify(self.mutation(change))
    def test_native_inventory_unknown_format_shape_and_changed_bindings_refused(self):
        import copy
        for mode in ('format','extra','assembly','candidate','base','schema','ids','missing-name','foreign-focus'):
            inventory=copy.deepcopy(self.inventory())
            if mode=='format':inventory['nativeFormat']='foreign'
            elif mode=='extra':inventory['foreign']=True
            elif mode=='assembly':inventory['assemblySha256']='a'*64
            elif mode=='candidate':inventory['candidateSha256']='a'*64
            elif mode=='base':inventory['baseSha']='a'*40
            elif mode=='schema':inventory['schemaVersion']=True
            elif mode=='ids':inventory['nativeCaseIds'][-1]=inventory['nativeCaseIds'][0]
            elif mode=='missing-name':inventory['names'].pop()
            else:inventory['focusedNames'][0]+='foreign'
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.verify(inventory=inventory)
    def test_extra_missing_and_unauthorized_duplicate_full_membership_refused(self):
        import xml.etree.ElementTree as ET
        inventory=self.inventory()
        for mode in ('extra','missing','duplicate'):
            a,root=LinuxDirectXunitControls().native_trx(inventory,'suite');ns=a.strict.NS
            results=root.find(ns+'Results');definitions=root.find(ns+'TestDefinitions')
            if mode=='missing':results.remove(results[-1]);definitions.remove(definitions[-1])
            elif mode=='extra':root.find(ns+'ResultSummary').find(ns+'Counters').set('total','498')
            else:
                name=definitions[0].get('name');definitions[-1].set('name',name);results[-1].set('testName',name)
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.verify(ET.tostring(root),inventory,'suite')
    def test_core_routes_only_native_trx_join_and_keeps_owned_trx_and_caps(self):
        source=sealed_source('hosted_static_core.py')
        self.assertEqual(1,source.count(b'association.verify_native(trx.read_bytes(), FRESH_INVENTORY, current_phase, ASSEMBLY_HASH, CANDIDATE, BASE)'))
        self.assertNotIn(b'association.verify(trx.read_bytes()',source)
        self.assertIn(b"arguments = arguments + ['-trx', str(runroot / 'test-results' / current_phase / (current_phase + '.trx'))]",source)
        self.assertIn(b'memory_limit=3 * 1024**3',source);self.assertIn(b'cpu_rate=5000',source);self.assertIn(b'output_limit=4 * 1024 * 1024',source)


class LinuxProviderControls(unittest.TestCase):
    def modules(self):
        import tempfile, types, sys
        policy=json.loads((ROOT/'hosted-static-policy.json').read_bytes())
        entries=mod.verified_entries(real_kit(),policy)
        names=['workflows_linux_trust','hosted_linux_entry','workflows_cleanup_supervisor_v1','workflows_linux_owned_scope_v1','workflows_private_docker_proxy_v1','workflows_linux_runtime','hosted_linux_sdk_bootstrap']
        previous={n:sys.modules.get(n) for n in names};loaded={}
        try:
            for name in names:
                module=types.ModuleType(name);module.__file__='<sealed-'+name+'>';sys.modules[name]=module
                exec(compile(entries['outputs/'+name+'.py'],module.__file__,'exec'),module.__dict__);loaded[name]=module
            return loaded
        finally:
            for name,value in previous.items():
                if value is None:sys.modules.pop(name,None)
                else:sys.modules[name]=value
    def capability(self,platform='linux',memory=5120,tools=('bash','docker','dockerd'),controllers=('cpu','memory','pids'),competing=()):
        return self.modules()['workflows_linux_runtime'].capabilities(platform,memory,tools,controllers,competing)
    def test_linux_capability_requires_all_fixed_prerequisites(self):
        self.assertTrue(self.capability()['linuxDockerAndBashRequired'])
    def test_windows_platform_refused_before_sdk(self):
        with self.assertRaises(RuntimeError):self.capability(platform='win32')
    def test_below_initial_memory_floor_refused(self):
        with self.assertRaises(RuntimeError):self.capability(memory=5119)
    def test_missing_bash_refused(self):
        with self.assertRaises(RuntimeError):self.capability(tools=('docker','dockerd'))
    def test_missing_linux_daemon_refused(self):
        with self.assertRaises(RuntimeError):self.capability(tools=('bash','docker'))
    def test_missing_pids_controller_refused(self):
        with self.assertRaises(RuntimeError):self.capability(controllers=('cpu','memory'))
    def test_competing_sdk_refused(self):
        with self.assertRaises(RuntimeError):self.capability(competing=(123,))
    def test_cap_or_timeout_widening_refused(self):
        import time
        runtime=self.modules()['workflows_linux_runtime']
        for timeout,memory,cpu,output in [(601,256*1024**2,5000,1024),(1,3*1024**3+1,5000,1024),(1,256*1024**2,5001,1024),(1,256*1024**2,5000,4*1024**2+1)]:
            with self.subTest(timeout=timeout,memory=memory,cpu=cpu,output=output),self.assertRaises(RuntimeError):runtime.command_budget(timeout,memory,cpu,output,time.monotonic()+1)
    def test_expired_remaining_deadline_refused(self):
        import time
        with self.assertRaises(RuntimeError):self.modules()['workflows_linux_runtime'].command_budget(1,256*1024**2,5000,1024,time.monotonic()-1)
    def test_sdk_archive_traversal_link_and_writable_members_refused(self):
        import tarfile
        bootstrap=self.modules()['hosted_linux_sdk_bootstrap']
        for name,kind,mode in [('../escape',tarfile.REGTYPE,0o755),('dotnet',tarfile.SYMTYPE,0o755),('dotnet',tarfile.REGTYPE,0o777)]:
            member=tarfile.TarInfo(name);member.type=kind;member.mode=mode;member.size=1
            with self.subTest(name=name,kind=kind,mode=mode),self.assertRaises(ValueError):bootstrap.archive_plan([member])
    def test_sdk_archive_duplicate_and_file_directory_collision_refused(self):
        import tarfile
        bootstrap=self.modules()['hosted_linux_sdk_bootstrap'];host=tarfile.TarInfo('dotnet');host.mode=0o755;host.size=1
        child=tarfile.TarInfo('dotnet/child');child.mode=0o755;child.size=1
        for members in ([host,host],[host,child]):
            with self.assertRaises(ValueError):bootstrap.archive_plan(members)
    def test_linux_route_retains_all497_and_exact_three_business_files(self):
        policy=json.loads((ROOT/'hosted-static-policy.json').read_bytes());entries=mod.verified_entries(real_kit(),policy)
        candidate=json.loads(entries['outputs/workflows-go1269-hosted-candidate/candidate-manifest.json'])
        self.assertEqual(3,len(candidate['files']));self.assertEqual(130,len([n for n in entries if n.startswith('worktree/')]))
        self.assertIn(b"len(FRESH_INVENTORY['names']) != 497",entries['outputs/hosted_static_core.py'])
        self.assertIn(b"group ==",entries['outputs/workflows_private_docker_proxy_v1.py'].replace(b'group==',b'group =='))
        for phase in ['restore','build','discovery','focused','suite','format','audit']:self.assertIn(phase,policy['nativePhases'])
    def test_private_daemon_windows_os_refused(self):
        import time
        from unittest.mock import Mock,patch
        runtime=self.modules()['workflows_linux_runtime'];client=Mock();client.recv.side_effect=[b'HTTP/1.0 200 OK\r\n\r\n{"Os":"windows"}',b'']
        context=Mock();context.__enter__=Mock(return_value=client);context.__exit__=Mock(return_value=False)
        with patch.object(runtime.socket,'socket',return_value=context),patch.object(runtime.socket,'AF_UNIX',1,create=True),self.assertRaises(RuntimeError):runtime.private_daemon_version(Path('/private/backend.sock'),time.monotonic()+1)

class LinuxDockerdSizeControls(unittest.TestCase):
    observed_size=83666424
    def fixture(self, size, operation):
        import tempfile,os,types,stat
        from unittest.mock import patch
        trust=LinuxProviderControls().modules()['workflows_linux_trust']
        with tempfile.TemporaryDirectory(prefix='dockerd-size-control-') as directory:
            root=Path(directory).resolve();target=root/'dockerd'
            with target.open('wb') as stream:stream.truncate(size)
            target.chmod(0o444)
            real_stat=Path.stat;real_fstat=os.fstat
            def observed(row):
                return types.SimpleNamespace(st_mode=stat.S_IFREG|0o755,st_uid=0,st_gid=0,
                    st_dev=row.st_dev,st_ino=row.st_ino,st_size=row.st_size,st_mtime_ns=row.st_mtime_ns)
            def metadata(path,*args,**kwargs):
                row=real_stat(path,*args,**kwargs)
                return observed(row) if path==target else row
            try:
                with patch.object(Path,'stat',metadata),patch.object(trust.os,'fstat',side_effect=lambda fd:observed(real_fstat(fd))):
                    operation(trust,root,target)
            finally:target.chmod(0o666)
    def test_actual_observed_daemon_size_refused_by_default(self):
        def operation(trust,root,target):
            with self.assertRaises(RuntimeError):trust.bind_executable(target,[root],0)
        self.fixture(self.observed_size,operation)
    def test_actual_observed_daemon_size_accepted_with_explicit_bounded_ceiling(self):
        import os
        def operation(trust,root,target):
            binding=trust.bind_executable(target,[root],0,maximum_bytes=96*1024**2)
            try:
                self.assertEqual(self.observed_size,binding['bytes']);self.assertEqual(96*1024**2,binding['maximumBytes'])
                self.assertTrue(trust.recheck_executable(binding))
            finally:os.close(binding['fd'])
        self.fixture(self.observed_size,operation)
    def test_daemon_above96MiB_refused_before_hashing(self):
        def operation(trust,root,target):
            with self.assertRaises(RuntimeError):trust.bind_executable(target,[root],0,maximum_bytes=96*1024**2)
        self.fixture(96*1024**2+1,operation)
    def test_daemon_growth_above96MiB_refused_on_recheck(self):
        import os
        def operation(trust,root,target):
            binding=trust.bind_executable(target,[root],0,maximum_bytes=96*1024**2)
            try:
                target.chmod(0o666)
                with target.open('r+b') as stream:stream.truncate(96*1024**2+1)
                target.chmod(0o444)
                with self.assertRaises(RuntimeError):trust.recheck_executable(binding)
            finally:os.close(binding['fd'])
        self.fixture(self.observed_size,operation)
    def test_explicit_ceiling_cannot_be_widened_or_used_for_other_executables(self):
        def operation(trust,root,target):
            for limit in (96*1024**2+1,128*1024**2,True):
                with self.subTest(limit=limit),self.assertRaises(RuntimeError):trust.bind_executable(target,[root],0,maximum_bytes=limit)
            other=root/'python3';other.write_bytes(b'interpreter');other.chmod(0o444)
            try:
                with self.assertRaises(RuntimeError):trust.bind_executable(other,[root],other.stat().st_uid,maximum_bytes=96*1024**2)
            finally:other.chmod(0o666)
        self.fixture(16,operation)
    def test_explicit_daemon_ceiling_preserves_foreign_uid_refusal(self):
        def operation(trust,root,target):
            with self.assertRaises(RuntimeError):trust.bind_executable(target,[root],1,maximum_bytes=96*1024**2)
        self.fixture(self.observed_size,operation)
    def test_explicit_daemon_ceiling_preserves_unsafe_mode_refusal(self):
        from unittest.mock import patch
        def operation(trust,root,target):
            original=trust.os.fstat
            def unsafe(fd):
                row=original(fd);row.st_mode=0o100777;return row
            with patch.object(trust.os,'fstat',side_effect=unsafe),self.assertRaises(RuntimeError):
                trust.bind_executable(target,[root],0,maximum_bytes=96*1024**2)
        self.fixture(16,operation)
    def test_explicit_daemon_ceiling_preserves_symlink_escape_refusal(self):
        import tempfile
        def operation(trust,root,target):
            with tempfile.TemporaryDirectory(prefix='foreign-daemon-control-') as directory:
                other=Path(directory).resolve()/'dockerd';other.write_bytes(b'foreign')
                alias=root/'alias';alias.mkdir();link=alias/'dockerd';link.symlink_to(other)
                with self.assertRaises(RuntimeError):trust.bind_executable(link,[root],0,maximum_bytes=96*1024**2)
        self.fixture(16,operation)
    def test_explicit_daemon_ceiling_preserves_symlink_substitution_refusal(self):
        import os
        def operation(trust,root,target):
            alias=root/'alias';alias.mkdir();link=alias/'dockerd';link.symlink_to(target)
            binding=trust.bind_executable(link,[root],0,maximum_bytes=96*1024**2)
            try:
                replacement=root/'replacement';replacement.mkdir();other=replacement/'dockerd';other.write_bytes(b'foreign')
                link.unlink();link.symlink_to(other)
                with self.assertRaises(RuntimeError):trust.recheck_executable(binding)
                self.assertEqual(target.stat().st_ino,os.fstat(binding['fd']).st_ino)
            finally:os.close(binding['fd'])
        self.fixture(16,operation)
    def test_only_real_daemon_caller_selects96MiB_and_root_uid(self):
        import ast
        calls=[n for n in ast.walk(ast.parse(sealed_source('workflows_linux_runtime.py'))) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='bind_executable']
        explicit=[n for n in calls if any(k.arg=='maximum_bytes' for k in n.keywords)]
        self.assertEqual(1,len(explicit));call=explicit[0]
        self.assertEqual("executables['dockerd']",ast.unparse(call.args[0]));self.assertEqual(0,call.args[2].value)
        self.assertEqual('96 * 1024 ** 2',ast.unparse(next(k.value for k in call.keywords if k.arg=='maximum_bytes')))
    def test_daemon_binding_cannot_widen_recorded_ceiling_on_recheck(self):
        import os
        def operation(trust,root,target):
            binding=trust.bind_executable(target,[root],0,maximum_bytes=96*1024**2)
            try:
                binding['maximumBytes']=128*1024**2
                with self.assertRaises(RuntimeError):trust.recheck_executable(binding)
            finally:os.close(binding['fd'])
        self.fixture(16,operation)


class LinuxTrustCorrections(unittest.TestCase):
    def modules(self):return LinuxProviderControls().modules()
    def fixture(self, operation):
        import tempfile,os
        with tempfile.TemporaryDirectory(prefix='workflows-trust-control-') as directory:
            root=Path(directory).resolve();target=root/'python3.12';target.write_bytes(b'fixed interpreter postimage');target.chmod(0o444)
            try:operation(root,target)
            finally:
                for path in root.iterdir():
                    if path.is_file() and not path.is_symlink():path.chmod(0o666)
    def test_real_symlink_to_regular_target_retains_real_descriptor(self):
        import os
        trust=self.modules()['workflows_linux_trust']
        def operation(root,target):
            link=root/'python3';link.symlink_to(target)
            self.assertTrue(link.is_symlink());binding=trust.bind_executable(link,[root],target.stat().st_uid)
            try:
                self.assertEqual(str(target),binding['resolved']);self.assertEqual(target.stat().st_ino,os.fstat(binding['fd']).st_ino)
                self.assertTrue(trust.recheck_executable(binding));self.assertEqual(target.read_bytes(),os.read(binding['fd'],1024))
            finally:os.close(binding['fd'])
        self.fixture(operation)
    def test_real_symlink_substitution_refused_with_original_descriptor_retained(self):
        import os
        trust=self.modules()['workflows_linux_trust']
        def operation(root,target):
            link=root/'python3';link.symlink_to(target);binding=trust.bind_executable(link,[root],target.stat().st_uid)
            try:
                other=root/'replacement';other.write_bytes(b'foreign');link.unlink();link.symlink_to(other)
                with self.assertRaises(RuntimeError):trust.recheck_executable(binding)
                self.assertEqual(target.stat().st_ino,os.fstat(binding['fd']).st_ino)
            finally:os.close(binding['fd'])
        self.fixture(operation)
    def test_real_target_mode_or_content_substitution_refused(self):
        import os
        trust=self.modules()['workflows_linux_trust']
        def operation(root,target):
            binding=trust.bind_executable(target,[root],target.stat().st_uid)
            try:
                target.chmod(0o666)
                with self.assertRaises(RuntimeError):trust.recheck_executable(binding)
                target.write_bytes(b'replaced interpreter');target.chmod(0o444)
                with self.assertRaises(RuntimeError):trust.recheck_executable(binding)
            finally:os.close(binding['fd'])
        self.fixture(operation)
    def test_wrong_owner_or_digest_and_escape_refused(self):
        trust=self.modules()['workflows_linux_trust']
        def operation(root,target):
            for uid,sha in [(target.stat().st_uid+1,None),(target.stat().st_uid,'0'*64)]:
                with self.assertRaises(RuntimeError):trust.bind_executable(target,[root],uid,sha)
            child=root/'allowed';child.mkdir()
            with self.assertRaises(RuntimeError):trust.bind_executable(target,[child],target.stat().st_uid)
        self.fixture(operation)
    def test_entry_can_execute_before_helper_materialization(self):
        import sys,types
        entries=mod.verified_entries(real_kit(),json.loads((ROOT/'hosted-static-policy.json').read_bytes()))
        previous=sys.modules.pop('workflows_linux_trust',None)
        try:
            module=types.ModuleType('unmaterialized_entry');exec(compile(entries['outputs/hosted_linux_entry.py'],'<entry>','exec'),module.__dict__)
            self.assertTrue(callable(module.main))
        finally:
            if previous is not None:sys.modules['workflows_linux_trust']=previous
    def test_sdk_marker_failures_preserve_primary_and_emit_receipt(self):
        import tempfile,time,sys
        modules=self.modules();entry=modules['hosted_linux_entry'];trust=modules['workflows_linux_trust']
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory,patch.dict(sys.modules,{'workflows_linux_trust':trust}):
            root=Path(directory).resolve();parent=root/'sdk-parent';parent.mkdir();sdk=parent/'sdk';sdk.mkdir();row=parent.stat();identity=(row.st_dev,row.st_ino,row.st_uid)
            permit=dict(owner='task',leaseId='lease',expiresUtc='expiry');primary=RuntimeError('original build failure')
            for malformed in [None,b'{',b'{"owner":"foreign"}']:
                marker=sdk/'.codex-sdk-owner.json'
                if malformed is None:
                    if marker.exists():marker.unlink()
                else:marker.write_bytes(malformed)
                receipt=root/'receipt.json'
                with self.assertRaises(RuntimeError) as error:
                    mod.preserve_first_failure(primary,lambda:entry.cleanup_sdk_namespace(sdk,permit,identity,time.monotonic()+2),lambda state,errors:entry.emit_bounded_receipt(receipt,dict(cleanupFailureTypes=errors)))
                self.assertIs(primary,error.exception);self.assertTrue(sdk.exists());self.assertTrue(json.loads(receipt.read_bytes())['cleanupFailureTypes'])
    def test_sdk_namespace_success_and_shared_deadline_refusal(self):
        import tempfile,time,sys
        from unittest.mock import patch
        modules=self.modules();entry=modules['hosted_linux_entry'];trust=modules['workflows_linux_trust']
        with tempfile.TemporaryDirectory() as directory,patch.dict(sys.modules,{'workflows_linux_trust':trust}):
            root=Path(directory).resolve();parent=root/'private-sdk';parent.mkdir();sdk=parent/'sdk';sdk.mkdir();row=parent.stat();identity=(row.st_dev,row.st_ino,row.st_uid)
            permit=dict(owner='task',leaseId='lease',expiresUtc='expiry');(sdk/'.codex-sdk-owner.json').write_text(json.dumps(dict(permit,persistentData=False)))
            with self.assertRaises(TimeoutError):entry.cleanup_sdk_namespace(sdk,permit,identity,time.monotonic()-1)
            self.assertTrue(sdk.exists());self.assertTrue(entry.cleanup_sdk_namespace(sdk,permit,identity,time.monotonic()+2));self.assertFalse(parent.exists())
    def test_sdk_parent_identity_substitution_refuses_deletion(self):
        import tempfile,time,sys
        from unittest.mock import patch
        modules=self.modules();entry=modules['hosted_linux_entry'];trust=modules['workflows_linux_trust']
        with tempfile.TemporaryDirectory() as directory,patch.dict(sys.modules,{'workflows_linux_trust':trust}):
            parent=Path(directory).resolve()/'parent';parent.mkdir();sdk=parent/'sdk';sdk.mkdir();permit=dict(owner='task',leaseId='lease',expiresUtc='expiry')
            (sdk/'.codex-sdk-owner.json').write_text(json.dumps(dict(permit,persistentData=False)))
            with self.assertRaises(ValueError):entry.cleanup_sdk_namespace(sdk,permit,(0,0,0),time.monotonic()+2)
            self.assertTrue(sdk.exists())
    def test_graceful_retained_child_precedes_group_force(self):
        import time
        from unittest.mock import patch
        scope=self.modules()['workflows_linux_owned_scope_v1'];owner=object.__new__(scope.LinuxOwnedScope);owner.root=Path('/owned');owner.verify=lambda path:None
        owner.children={123:dict(group=str(owner.root/'daemon'),reaped=False,pidfd=7,pid=123)};events=[]
        with patch.object(scope.select,'select',return_value=([],[],[])),patch.object(scope.signal,'pidfd_send_signal',side_effect=lambda *args:events.append('term'),create=True),patch.object(scope,'populated',side_effect=[False,True,False]),patch.object(scope.Path,'write_text',side_effect=lambda *args:events.append('force')),patch.object(scope.os,'waitpid',return_value=(123,0),create=True),patch.object(scope.os,'WNOHANG',1,create=True):
            owner.stop_group('daemon',time.monotonic()+2)
        self.assertEqual(['term','force'],events);self.assertTrue(owner.children[123]['reaped'])
    def test_expired_shared_deadline_prevents_signals_and_force(self):
        import time
        from unittest.mock import Mock,patch
        scope=self.modules()['workflows_linux_owned_scope_v1'];owner=object.__new__(scope.LinuxOwnedScope);owner.root=Path('/owned');owner.verify=Mock();owner.children={}
        with patch.object(scope.Path,'write_text') as force,self.assertRaises(RuntimeError):owner.stop_group('daemon',time.monotonic()-1)
        force.assert_not_called()
    def test_registration_mask_restored_after_acquisition_failure(self):
        from unittest.mock import patch
        scope=self.modules()['workflows_linux_owned_scope_v1']
        with patch.object(scope.signal,'pthread_sigmask',return_value={1},create=True) as mask,patch.object(scope.signal,'SIG_BLOCK',0,create=True),patch.object(scope.signal,'SIG_SETMASK',2,create=True):
            with self.assertRaises(ValueError),scope.registration_window():raise ValueError('controlled failure')
            self.assertEqual((2,{1}),mask.call_args.args)
    def test_parent_death_guard_refuses_wrong_parent(self):
        from unittest.mock import Mock,patch
        scope=self.modules()['workflows_linux_owned_scope_v1'];libc=Mock();libc.prctl.return_value=0
        with patch.object(scope.os,'getppid',return_value=999),patch.object(scope.signal,'SIGKILL',9,create=True),self.assertRaises(RuntimeError):scope.child_guard(123,libc)
        libc.prctl.assert_called_once()

    def test_cli_home_replaces_root_home_and_clears_authority_environment(self):
        import tempfile,types,stat
        from unittest.mock import patch
        runtime=self.modules()['workflows_linux_runtime']
        with tempfile.TemporaryDirectory() as directory:
            home=Path(directory).resolve();observed=home.stat();real_stat=Path.stat
            def metadata(path,*args,**kwargs):
                row=real_stat(path,*args,**kwargs)
                if path==home:return types.SimpleNamespace(st_uid=row.st_uid,st_gid=row.st_gid,st_mode=stat.S_IFDIR|0o700)
                return row
            with patch.object(Path,'stat',metadata):
                result=runtime.runtime_environment(dict(HOME='/root',GH_TOKEN='redacted-fixture',ROOT_STATIC_PERMIT='fixture'),home,observed.st_uid,observed.st_gid)
            self.assertEqual(str(home),result['HOME']);self.assertEqual(str(home),result['DOTNET_CLI_HOME'])
            self.assertNotIn('GH_TOKEN',result);self.assertNotIn('ROOT_STATIC_PERMIT',result)
            for key in ['XDG_CACHE_HOME','XDG_CONFIG_HOME','XDG_DATA_HOME','TMPDIR']:self.assertTrue(Path(result[key]).is_relative_to(home))
    def test_cli_home_real_symlink_refused(self):
        import tempfile
        runtime=self.modules()['workflows_linux_runtime']
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();home=root/'home';home.mkdir();link=root/'link';link.symlink_to(home,target_is_directory=True);row=home.stat()
            with self.assertRaises(RuntimeError):runtime.runtime_environment({'HOME':'/root'},link,row.st_uid,row.st_gid)
    def test_bounded_receipt_file_failure_keeps_stdout_evidence_and_primary(self):
        import io
        from unittest.mock import patch
        entry=self.modules()['hosted_linux_entry'];primary=RuntimeError('original')
        output=io.StringIO()
        with patch.object(Path,'open',side_effect=PermissionError('controlled receipt refusal')),patch('sys.stdout',output),self.assertRaises(RuntimeError) as error:
            mod.preserve_first_failure(primary,lambda:None,lambda state,errors:entry.emit_bounded_receipt(Path('unused'),dict(cleanupFailures=['PermissionError'])))
        self.assertIs(primary,error.exception);self.assertEqual(['PermissionError'],json.loads(output.getvalue())['cleanupFailures']);self.assertTrue(primary.__notes__)

    def test_unadmitted_child_is_stopped_by_exact_handle_without_resume(self):
        from unittest.mock import patch
        scope=self.modules()['workflows_linux_owned_scope_v1'];owner=object.__new__(scope.LinuxOwnedScope);owner.root=Path('/owned');owner.verify=lambda path:None
        owner.children={123:dict(group=str(owner.root/'sdk'),reaped=False,pidfd=7,pid=123,admitted=False)};signals=[]
        with patch.object(scope.time,'monotonic',side_effect=[0,0,2,2,2]),patch.object(scope.select,'select',return_value=([],[],[])),patch.object(scope.signal,'pidfd_send_signal',side_effect=lambda fd,number:signals.append((fd,number)),create=True),patch.object(scope.signal,'SIGKILL',9,create=True),patch.object(scope,'populated',return_value=False),patch.object(scope.os,'waitpid',side_effect=[(0,0),(123,0)],create=True),patch.object(scope.os,'WNOHANG',1,create=True):
            owner.stop_group('sdk',10)
        self.assertEqual([(7,scope.signal.SIGTERM),(7,9)],signals);self.assertTrue(owner.children[123]['reaped'])
    def test_sdk_rmdir_failure_preserves_primary_and_receipt(self):
        import tempfile,time,sys
        from unittest.mock import patch
        modules=self.modules();entry=modules['hosted_linux_entry'];trust=modules['workflows_linux_trust']
        with tempfile.TemporaryDirectory() as directory,patch.dict(sys.modules,{'workflows_linux_trust':trust}):
            root=Path(directory).resolve();parent=root/'private-sdk';parent.mkdir();sdk=parent/'sdk';sdk.mkdir();row=parent.stat();identity=(row.st_dev,row.st_ino,row.st_uid)
            permit=dict(owner='task',leaseId='lease',expiresUtc='expiry');(sdk/'.codex-sdk-owner.json').write_text(json.dumps(dict(permit,persistentData=False)))
            primary=RuntimeError('original phase');receipt=root/'receipt.json'
            with patch.object(Path,'rmdir',side_effect=PermissionError('controlled deletion failure')),self.assertRaises(RuntimeError) as error:
                mod.preserve_first_failure(primary,lambda:entry.cleanup_sdk_namespace(sdk,permit,identity,time.monotonic()+2),lambda state,errors:entry.emit_bounded_receipt(receipt,dict(cleanupFailureTypes=errors)))
            self.assertIs(primary,error.exception);self.assertTrue(sdk.exists());self.assertEqual(['PermissionError'],json.loads(receipt.read_bytes())['cleanupFailureTypes'])

class LinuxFiniteCleanupControls(unittest.TestCase):
    def modules(self):return LinuxProviderControls().modules()
    class Clock:
        def __init__(self):self.now=0
        def read(self):return self.now
        def wait(self,seconds):self.now+=seconds
    def test_permanent_quarantine_stops_at_fixed_boundary_with_custody(self):
        from unittest.mock import Mock
        supervisor=self.modules()['workflows_cleanup_supervisor_v1'];clock=self.Clock();resources={'stuck':True};events=[];slot=Mock(released=False,partial_creation=False);journal=Mock(closed=False)
        journal.close.side_effect=lambda:setattr(journal,'closed',True)
        recover=Mock(side_effect=RuntimeError('permanent observation refusal'))
        result=supervisor.supervise(resources,recover,slot,journal,lambda kind,state:events.append((kind,state)),absolute_deadline=.25,monotonic=clock.read,wait=clock.wait)
        self.assertLessEqual(clock.now,.25);self.assertEqual(1,result['attempts']);self.assertTrue(result['fixedDeadlineExpired']);self.assertFalse(result['cleanupVerified']);self.assertFalse(result['slotReleased']);self.assertTrue(result['journalClosed']);slot.close.assert_not_called();self.assertEqual({'stuck':True},resources)
        self.assertEqual('cleanup-expired-checkpoint',events[-1][0]);self.assertEqual(['stuck'],events[-1][1]['ownedLeases'])
    def test_already_expired_boundary_never_attempts_recovery_or_claim_release(self):
        from unittest.mock import Mock
        supervisor=self.modules()['workflows_cleanup_supervisor_v1'];resources={'stuck':True};recover=Mock();slot=Mock(released=False);journal=Mock(closed=False);journal.close.side_effect=lambda:setattr(journal,'closed',True)
        state=supervisor.supervise(resources,recover,slot,journal,lambda *args:None,absolute_deadline=0,monotonic=lambda:1,wait=Mock())
        recover.assert_not_called();slot.close.assert_not_called();self.assertEqual(0,state['attempts']);self.assertTrue(state['custodyRetained'])
    def test_legacy_without_fixed_deadline_keeps_accepted_renewal(self):
        supervisor=self.modules()['workflows_cleanup_supervisor_v1'];clock=self.Clock();resources={'owned':True};calls=[]
        def recover(lease):
            calls.append(lease)
            if len(calls)<5:raise RuntimeError('temporary observation failure')
            del resources[lease]
        state=supervisor.supervise(resources,recover,None,None,lambda *args:None,attempt_seconds=.1,attention_seconds=.2,monotonic=clock.read,wait=clock.wait)
        self.assertTrue(state['cleanupVerified']);self.assertGreater(state['attempts'],1);self.assertGreater(state['attentionCount'],0);self.assertEqual(5,len(calls))
    def test_cleanup_boundary_never_renews_frozen_scope_deadline(self):
        from unittest.mock import patch
        import types
        runtime=self.modules()['workflows_linux_runtime'];runtime.SCOPE=types.SimpleNamespace(deadline=100,cleanup_deadline=12)
        with patch.object(runtime.time,'monotonic',return_value=80):self.assertEqual(12,runtime.cleanup_boundary())
    def test_actual_core_final_receipt_after_permanent_quarantine(self):
        import types,sys,tempfile,subprocess
        from unittest.mock import Mock,patch
        modules=self.modules();supervisor=modules['workflows_cleanup_supervisor_v1'];clock=self.Clock();slot=Mock(released=False,partial_creation=False)
        admission=types.ModuleType('workflows_native_admission_v3');admission.read_json=lambda path:({},b'fixture');admission.validate=lambda *args:datetime.now(timezone.utc)+timedelta(hours=1);admission.owner_identity=lambda:{'owner':'source-fixture'};admission.preflight=lambda *args:{};admission.Lease=lambda *args:slot
        owned=types.ModuleType('workflows_linux_runtime');owned._quarantined={'stuck':(None,{'job_lease':'stuck','cleanup_verified':False})};owned.prepare_result_directories=lambda path:{};owned.result_permission_arguments=lambda *args:['permission-probe'];owned.SCOPE=types.SimpleNamespace(uid=1001,gid=100);owned.cleanup_boundary=lambda:.25;owned.supervision_boundary=lambda:.25;owned.recover_quarantined=Mock(side_effect=RuntimeError('permanent resource refusal'))
        injected={'workflows_linux_runtime':owned,'workflows_native_admission_v3':admission,'workflows_cleanup_supervisor_v1':supervisor}
        for name in ['artifact_pin_native_result_validation_v3','workflows_gitleaks_compiled_result_association_v1','hosted_package_graph']:injected[name]=types.ModuleType(name)
        with tempfile.TemporaryDirectory() as directory,patch.dict(sys.modules,injected):
            core_path=Path(directory)/'source-core.py';core_path.write_bytes(sealed_source('hosted_static_core.py'));core=types.ModuleType('source_core');core.__file__=str(core_path);exec(compile(core_path.read_bytes(),core.__file__,'exec'),core.__dict__)
            core.OUT=Path(directory).resolve();core.candidate_check=lambda:None
            expected=core.OUT/'workflows-gitleaks-toolchain-build-request-20261008-v3/scope-frozen.txt';expected.parent.mkdir();expected.write_bytes(b'exact fixture scope')
            original_sha=core.sha;core.sha=lambda path:core.SCOPE_HASH if path==expected else original_sha(path)
            failure=RuntimeError('original phase failure');failure.resource_row={'job_lease':'stuck'}
            owned.run_owned=Mock(side_effect=[(subprocess.CompletedProcess([],0,(core.BASE+'\n').encode(),b''),{}),(subprocess.CompletedProcess([],0,expected.read_bytes(),b''),{}),failure])
            original_supervise=supervisor.supervise
            def finite(*args,**kwargs):return original_supervise(*args,**kwargs,monotonic=clock.read,wait=clock.wait)
            with patch.object(supervisor,'supervise',finite),patch.object(sys,'argv',['core','hosted-qualification','permit']),patch('sys.stdout',io.StringIO()),self.assertRaises(SystemExit) as error:core.main()
            self.assertEqual(1,error.exception.code);receipts=list(core.OUT.glob('*/receipt.json'));self.assertEqual(1,len(receipts));receipt=json.loads(receipts[0].read_bytes())
            self.assertIn('original phase failure',receipt['failure']);self.assertEqual(1,receipt['quarantineCount']);self.assertFalse(receipt['claimReleased']);self.assertTrue(receipt['cleanupSupervision']['fixedDeadlineExpired']);self.assertTrue(receipt['cleanupSupervision']['journalClosed']);self.assertLessEqual(clock.now,.25);slot.close.assert_not_called()

class LinuxResultsOwnershipControls(unittest.TestCase):
    def fixture(self,operation):
        import tempfile,types,stat
        from unittest.mock import patch
        runtime=LinuxProviderControls().modules()['workflows_linux_runtime'];runtime.SCOPE=types.SimpleNamespace(uid=1001,gid=100)
        with tempfile.TemporaryDirectory() as directory:
            runroot=Path(directory).resolve()/'run';runroot.mkdir();owners={};modes={};actual_stat=Path.stat
            def metadata(path,*args,**kwargs):
                row=actual_stat(path,*args,**kwargs);uid,gid=owners.get(path,(0,0))
                return types.SimpleNamespace(st_dev=row.st_dev,st_ino=row.st_ino,st_uid=uid,st_gid=gid,st_mode=(row.st_mode & ~0o777)|modes.get(path,row.st_mode & 0o777))
            with patch.object(runtime.os,'chown',side_effect=lambda path,uid,gid:owners.update({Path(path):(uid,gid)}),create=True),patch.object(runtime.os,'chmod',side_effect=lambda path,mode:modes.update({Path(path):mode})),patch.object(runtime,'registration_window',__import__('contextlib').nullcontext),patch.object(Path,'stat',metadata):
                proof=runtime.prepare_result_directories(runroot);operation(runtime,runroot,proof,owners,modes)
    def test_only_phase_directories_receive_sdk_uid_and_gid(self):
        def operation(runtime,runroot,proof,owners,modes):
            self.assertEqual({runroot/'test-results/focused',runroot/'test-results/suite'},set(owners));self.assertEqual(0o755,modes[runroot]);self.assertEqual(0o755,modes[runroot/'test-results'])
            for phase in ('focused','suite'):self.assertTrue(runtime.verify_result_directory(runroot,phase,proof[phase]));self.assertEqual((1001,100),owners[runroot/'test-results'/phase])
        self.fixture(operation)
    def test_foreign_owner_or_writable_authority_parent_refused(self):
        def operation(runtime,runroot,proof,owners,modes):
            target=runroot/'test-results/focused';owners[target]=(9999,100)
            with self.assertRaises(RuntimeError):runtime.verify_result_directory(runroot,'focused',proof['focused'])
            owners[target]=(1001,100);modes[runroot]=0o777
            with self.assertRaises(RuntimeError):runtime.verify_result_directory(runroot,'focused',proof['focused'])
        self.fixture(operation)
    def test_real_directory_substitution_refused_by_recorded_inode(self):
        def operation(runtime,runroot,proof,owners,modes):
            target=runroot/'test-results/focused';target.rename(target.parent/'original');target.mkdir()
            with self.assertRaises(RuntimeError):runtime.verify_result_directory(runroot,'focused',proof['focused'])
        self.fixture(operation)
    def test_bootstrap_writes_stay_outside_controller_authority_directory(self):
        entry=sealed_source('hosted_linux_entry.py').decode();bootstrap=sealed_source('hosted_linux_sdk_bootstrap.py').decode()
        self.assertNotIn('os.chown(outputs, uid, gid)',entry);self.assertIn("archive = SDK_ROOT.parent/'official-linux-sdk.tar.gz'",bootstrap);self.assertIn("(SDK_ROOT.parent/'sdk-bootstrap-record.json')",bootstrap)

    def test_real_permission_probe_uses_existing_uid_drop_before_sdk_phases(self):
        import types
        runtime=LinuxProviderControls().modules()['workflows_linux_runtime'];runtime.SCOPE=types.SimpleNamespace(uid=1001,gid=100)
        args=runtime.result_permission_arguments(Path('/owned/run'),Path('/owned/permit'))
        self.assertEqual(['-I','-B','-c'],args[1:4]);compile(args[4],'<permission-probe>','exec')
        self.assertIn('os.getuid()==os.geteuid()==uid',args[4]);self.assertIn("target.open('xb')",args[4]);self.assertIn('target.unlink()',args[4]);self.assertIn('not os.access(path,os.W_OK)',args[4])
        core=sealed_source('hosted_static_core.py').decode();self.assertLess(core.index('permissions,row=owned.run_owned'),core.index('for current_phase, arguments in commands.items()'))
        self.assertIn('results-permission.json',core)

class LinuxReaderContainmentControls(unittest.TestCase):
    def modules(self):return LinuxProviderControls().modules()
    def test_actual_subprocess_exits_with_non_daemon_reader_and_pipe_writer_open(self):
        import subprocess,sys,time
        entries=mod.verified_entries(real_kit(),json.loads((ROOT/'hosted-static-policy.json').read_bytes()))
        names=['workflows_linux_trust','workflows_linux_owned_scope_v1','workflows_private_docker_proxy_v1','workflows_linux_runtime','hosted_linux_entry']
        sources={name:entries['outputs/'+name+'.py'].decode() for name in names}
        code="import types,sys,json,io,os,time,threading,tempfile\nfrom pathlib import Path\n"
        code+='sources='+repr(sources)+'\n'
        code+="for name,source in sources.items():\n module=types.ModuleType(name);module.__file__='<sealed-'+name+'>';sys.modules[name]=module;exec(compile(source,module.__file__,'exec'),module.__dict__)\n"
        code+="""runtime=sys.modules['workflows_linux_runtime'];entry=sys.modules['hosted_linux_entry']
read,write=os.pipe();os.set_blocking(read,False)
scope=types.SimpleNamespace(deadline=time.monotonic()+1,cleanup_deadline=time.monotonic()+1,daemon_reader_stop=threading.Event(),daemon_pipes=[read,write],daemon_reader_receipt=None,daemon_failure=None,proxy=None,root=Path('/not-a-real-kernel-group'),births={})
runtime.SCOPE=scope;runtime._quarantined['retained']=(None,{'cleanup_verified':False})
scope.daemon_reader=threading.Thread(target=runtime.retain_daemon_output,args=(scope,read,io.BytesIO()),daemon=False);scope.daemon_reader.start()
actual_birth=None
if os.name=='nt':
 import ctypes
 class FileTime(ctypes.Structure):_fields_=[('low',ctypes.c_uint32),('high',ctypes.c_uint32)]
 api=ctypes.WinDLL('kernel32',use_last_error=True);api.GetProcessTimes.argtypes=[ctypes.c_void_p,*([ctypes.POINTER(FileTime)]*4)];api.GetProcessTimes.restype=ctypes.c_int
 created,ended,kernel,user=FileTime(),FileTime(),FileTime(),FileTime()
 assert api.GetProcessTimes(ctypes.c_void_p(-1),ctypes.byref(created),ctypes.byref(ended),ctypes.byref(kernel),ctypes.byref(user))
 actual_birth=(created.high<<32)|created.low
else:
 raw=Path('/proc/self/stat').read_text();actual_birth=int(raw[raw.rfind(')')+2:].split()[19])
primary=RuntimeError('original validation failure');cleanup_error=None
try:runtime.finish(scope.cleanup_deadline)
except RuntimeError as error:cleanup_error=type(error).__name__
assert not scope.daemon_reader.is_alive() and scope.daemon_reader.daemon is False
assert scope.controller_reader_cleanup['joined'] and scope.controller_reader_cleanup['reader']['pipeClosed']
assert runtime._quarantined and scope.quarantine_containment['custodyRetained']
os.fstat(write) # Writer deliberately stays open through final receipt and process exit.
with tempfile.TemporaryDirectory() as directory:
 receipt=Path(directory)/'wrapper-receipt.json'
 entry.emit_bounded_receipt(receipt,dict(pid=os.getpid(),actualStart=actual_birth,executable=sys.executable,timeoutSeconds=3,persistentData=False,originalFailure=str(primary),cleanupError=cleanup_error,quarantineCount=len(runtime._quarantined),writerStillOpen=True,readerJoined=True,readerDaemon=False,claimReleased=False,fullCleanupVerified=False))
 print(receipt.read_text(),flush=True)
# No EOF or writer close is used to settle the reader. OS closes writer on exit.
"""
        started=time.monotonic();result=subprocess.run([sys.executable,'-I','-B','-'],input=code.encode(),capture_output=True,timeout=3)
        self.assertEqual(0,result.returncode,result.stderr.decode());proof=json.loads(result.stdout)
        self.assertLess(time.monotonic()-started,3);self.assertTrue(proof['writerStillOpen']);self.assertTrue(proof['readerJoined']);self.assertFalse(proof['readerDaemon']);self.assertFalse(proof['claimReleased']);self.assertFalse(proof['fullCleanupVerified']);self.assertEqual(1,proof['quarantineCount']);self.assertGreater(proof['actualStart'],0);self.assertIn('original validation failure',proof['originalFailure'])
        print('Actual bounded controller exit fixture: '+json.dumps(proof))
    def test_reader_self_expires_without_controller_stop_or_pipe_eof(self):
        import os,types,threading
        runtime=self.modules()['workflows_linux_runtime'];read,write=os.pipe();os.set_blocking(read,False)
        scope=types.SimpleNamespace(deadline=0,cleanup_deadline=1,daemon_reader_stop=threading.Event(),daemon_pipes=[read,write],daemon_reader_receipt=None,daemon_failure=None)
        try:
            runtime.retain_daemon_output(scope,read,io.BytesIO(),monotonic=lambda:2)
            self.assertEqual('fixed-deadline',scope.daemon_reader_receipt['stopReason']);self.assertTrue(scope.daemon_reader_receipt['pipeClosed']);self.assertNotIn(read,scope.daemon_pipes);os.fstat(write)
        finally:os.close(write)
    def test_controller_reserve_is_inside_original_boundary_and_never_renews(self):
        import types
        runtime=self.modules()['workflows_linux_runtime'];runtime.SCOPE=types.SimpleNamespace(deadline=100,cleanup_deadline=12)
        self.assertEqual(10,runtime.supervision_boundary());self.assertEqual(12,runtime.cleanup_boundary())
    def test_quarantine_unsettled_proxy_keeps_daemon_and_kernel_custody(self):
        import types,time
        from unittest.mock import Mock,patch
        runtime=self.modules()['workflows_linux_runtime'];root=Path('/owned');proxy=Mock();proxy.stop.side_effect=RuntimeError('unsettled retained client')
        runtime.SCOPE=types.SimpleNamespace(proxy=proxy,root=root,births={root/'docker':(1,2),root/'daemon':(1,3)},stop_group=Mock())
        with patch.object(runtime,'settle_controller_reader',return_value={'joined':True}):state=runtime.contain_quarantined_controller(time.monotonic()+1)
        runtime.SCOPE.stop_group.assert_not_called();self.assertTrue(state['custodyRetained']);self.assertFalse(state['claimReleaseAuthorized']);self.assertFalse(state['daemonStopped']);self.assertIn('RuntimeError',state['errors'])
    def test_quarantine_controller_stop_uses_same_deadline_and_preserves_sdk(self):
        import types,time
        from unittest.mock import Mock,patch
        runtime=self.modules()['workflows_linux_runtime'];root=Path('/owned');proxy=Mock();proxy.stop.return_value=dict(admissionFenced=True,activeClients=0,workersJoined=True)
        runtime.SCOPE=types.SimpleNamespace(proxy=proxy,root=root,births={root/'docker':(1,2),root/'daemon':(1,3),root/'sdk':(1,4)},stop_group=Mock());deadline=time.monotonic()+1
        with patch.object(runtime,'settle_controller_reader',return_value={'joined':True}):state=runtime.contain_quarantined_controller(deadline)
        self.assertEqual([('docker',deadline),('daemon',deadline)],[call.args for call in runtime.SCOPE.stop_group.call_args_list]);self.assertTrue(state['daemonStopped']);self.assertTrue(state['custodyRetained']);self.assertFalse(state['claimReleaseAuthorized'])
    def test_release_failure_still_settles_reader_and_preserves_first_error(self):
        import types,time
        from unittest.mock import Mock,patch
        runtime=self.modules()['workflows_linux_runtime'];primary=RuntimeError('original release refusal');runtime.SCOPE=types.SimpleNamespace(cleanup_deadline=None,release=Mock(side_effect=primary))
        with patch.object(runtime,'settle_controller_reader',side_effect=TimeoutError('reader refusal')) as settle,self.assertRaises(RuntimeError) as error:runtime.finish(time.monotonic()+1)
        settle.assert_called_once();self.assertIs(primary,error.exception);self.assertIn('Secondary controller',primary.__notes__[0])

    def test_expired_quarantine_still_fences_proxy_without_join_or_force(self):
        import types,time
        from unittest.mock import Mock,patch
        runtime=self.modules()['workflows_linux_runtime'];root=Path('/owned');proxy=Mock()
        runtime.SCOPE=types.SimpleNamespace(proxy=proxy,root=root,births={root/'daemon':(1,2)},stop_group=Mock())
        with patch.object(runtime,'settle_controller_reader',return_value={'joined':True}):state=runtime.contain_quarantined_controller(time.monotonic()-1)
        proxy.request_fence.assert_called_once();proxy.stop.assert_not_called();runtime.SCOPE.stop_group.assert_not_called();self.assertFalse(state['daemonStopped']);self.assertTrue(state['custodyRetained']);self.assertIn('TimeoutError',state['errors'])
    def test_proxy_cancellation_closes_only_retained_streams_without_waiting(self):
        import types,threading
        from unittest.mock import Mock
        proxy=self.modules()['workflows_private_docker_proxy_v1'];owner=object.__new__(proxy.PrivateDockerProxy);owner.closed=threading.Event();owner.lock=threading.RLock();owner.listener=Mock();stream=Mock();owner.sockets={1:[stream]};owner.listener_thread=Mock()
        owner.request_fence();self.assertTrue(owner.closed.is_set());owner.listener.close.assert_called_once();stream.shutdown.assert_called_once();owner.listener_thread.join.assert_not_called()

class LinuxRecoveryReserveControls(unittest.TestCase):
    def modules(self):return LinuxProviderControls().modules()
    def test_real_command_cleanup_closure_honors_sdk_and_recovery_deadlines(self):
        import tempfile,os,sys,contextlib,inspect
        from unittest.mock import patch
        modules=self.modules();runtime=modules['workflows_linux_runtime'];scope=modules['workflows_linux_owned_scope_v1']
        class Clock:
            now=0.0
            def read(self):return self.now
            def wait(self,seconds):self.now=round(self.now+seconds,6)
        clock=Clock();first=[True]
        def populated(path):
            if first[0]:first[0]=False;raise RuntimeError('controlled first SDK observation refusal')
            return True
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();sdk=root/'sdk';sdk.mkdir();holder=root/'held-file';holder.write_bytes(b'owned fixture descriptor')
            with holder.open('rb') as held:
                owner=object.__new__(scope.LinuxOwnedScope);owner.root=root;owner.deadline=100;owner.closed=False;owner.daemon_failure=None;owner.cleanup_deadline=None;owner.handles={sdk:held.fileno()};owner.children={};owner.verify=lambda path:None;owner.cli_home=root;owner.uid=1001;owner.gid=100;owner.front_parent=root
                actual_stop=owner.stop_group;deadlines=[]
                def record_stop(name,deadline):deadlines.append((name,deadline));return actual_stop(name,deadline)
                owner.stop_group=record_stop;runtime.SCOPE=owner
                with patch.object(runtime,'check_cli_home'),patch.object(runtime,'runtime_environment',return_value={}),patch.object(runtime,'registration_window',contextlib.nullcontext),patch.object(runtime,'bind_executable',side_effect=RuntimeError('controlled executable refusal')),patch.object(scope,'populated',populated),patch.object(scope.time,'monotonic',clock.read),patch.object(scope.time,'sleep',clock.wait):
                    with self.assertRaises(RuntimeError) as original:runtime.run_owned([sys.executable],timeout=1)
                    lease=original.exception.resource_row['job_lease'];cleanup,row=runtime._quarantined[lease];descriptors=inspect.getclosurevars(cleanup).nonlocals['descriptors']
                    try:
                        self.assertEqual(25,owner.cleanup_deadline);self.assertEqual(('sdk',23),deadlines[0]);clock.now=21
                        with self.assertRaises(RuntimeError):runtime.recover_quarantined(lease,deadline=22.5)
                        self.assertEqual(('sdk',22.5),deadlines[-1]);self.assertLessEqual(clock.now,22.52);self.assertGreaterEqual(owner.cleanup_deadline-clock.now,2.48)
                        self.assertIn(lease,runtime._quarantined);self.assertFalse(row.get('cleanup_verified',False));self.assertEqual(25,owner.cleanup_deadline)
                        clock.now=21
                        with self.assertRaises(RuntimeError):runtime.recover_quarantined(lease)
                        self.assertEqual(('sdk',23),deadlines[-1]);self.assertLessEqual(clock.now,23.02);self.assertGreaterEqual(owner.cleanup_deadline-clock.now,1.98)
                    finally:
                        for descriptor in list(descriptors):os.close(descriptor);descriptors.remove(descriptor)
                        runtime._quarantined.clear()
    def release_fixture(self,expired):
        import tempfile,os,time,threading,sys
        from unittest.mock import Mock,patch
        modules=self.modules();runtime=modules['workflows_linux_runtime'];scope=modules['workflows_linux_owned_scope_v1'];proxy_module=modules['workflows_private_docker_proxy_v1']
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();sdk=root/'sdk';sdk.mkdir();read,write=os.pipe();os.set_blocking(read,False)
            owner=object.__new__(scope.LinuxOwnedScope);owner.root=root;owner.deadline=time.monotonic()+100;owner.cleanup_deadline=time.monotonic()+.75;owner.closed=False;owner.births={sdk:(1,2)};owner.handles={};owner.children={};owner.entered=False
            proxy=object.__new__(proxy_module.PrivateDockerProxy);proxy.closed=threading.Event();proxy.lock=threading.RLock();proxy.sockets={};proxy.workers={};proxy.bytes=0;proxy.failure=None;proxy.identity=None;proxy.deadline=owner.deadline
            def accept():
                if proxy.closed.wait(.02):raise OSError('cancelled listener')
                raise proxy_module.socket.timeout()
            proxy.listener=Mock();proxy.listener.accept.side_effect=accept;proxy.listener_thread=threading.Thread(target=proxy._accept,daemon=False);proxy.listener_thread.start();owner.proxy=proxy
            owner.daemon_reader_stop=threading.Event();owner.daemon_pipes=[read,write];owner.daemon_reader_receipt=None;owner.daemon_failure=None;owner.daemon_reader=threading.Thread(target=runtime.retain_daemon_output,args=(owner,read,io.BytesIO()),daemon=False);owner.daemon_reader.start();runtime.SCOPE=owner
            try:
                deadline=time.monotonic()-1 if expired else owner.cleanup_deadline
                with patch.dict(sys.modules,{'workflows_linux_trust':modules['workflows_linux_trust']}),self.assertRaises(TimeoutError if expired else RuntimeError) as failure:runtime.finish(deadline)
                if not expired:self.assertIn('Linux owned scope refused',str(failure.exception))
                self.assertTrue(proxy.closed.is_set());self.assertFalse(owner.closed);self.assertEqual({},runtime._quarantined);self.assertTrue(owner.quarantine_containment['custodyRetained']);self.assertFalse(owner.quarantine_containment['claimReleaseAuthorized']);self.assertFalse(owner.quarantine_containment['daemonStopped'])
                self.assertEqual({sdk:(1,2)},owner.births)
            finally:
                proxy.request_fence();owner.daemon_reader_stop.set();proxy.listener_thread.join(.5);owner.daemon_reader.join(.5);os.close(write)
                self.assertFalse(proxy.listener_thread.is_alive());self.assertFalse(owner.daemon_reader.is_alive())
    def test_real_scope_sdk_custody_refusal_always_fences_real_proxy_thread(self):self.release_fixture(False)
    def test_real_scope_expired_remaining_always_cancels_real_proxy_thread(self):self.release_fixture(True)

if __name__=='__main__':unittest.main()
