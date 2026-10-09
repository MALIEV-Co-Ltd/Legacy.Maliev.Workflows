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
        state={'result':SimpleNamespace(stdout=baseline),'phase_receipts':{},'current_phase':'build'}
        exec(code,state);self.assertEqual(0,state['phase_receipts']['build']['warnings'])
        for raw in [baseline.replace(b'0 Warning',b'1 Warning'),baseline.replace(b'Build succeeded.',b'Build failed.'),b'Build succeeded.\n']:
            with self.subTest(raw=raw),self.assertRaises(RuntimeError):exec(code,{'result':SimpleNamespace(stdout=raw),'phase_receipts':{},'current_phase':'build'})
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
                text='The following Tests are available:\n'+''.join('    '+n+'\n' for n in actual)
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
