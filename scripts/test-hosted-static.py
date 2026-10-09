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
        policy=json.loads((ROOT/'hosted-static-policy.json').read_bytes());data=(ROOT/'sealed-static-kit.zip').read_bytes() if (ROOT/'sealed-static-kit.zip').is_file() else mod.fetch(policy)
        files=mod.verified_entries(data,policy)
        self.assertEqual(168,len(files));self.assertEqual(policy['kitSha256'],mod.digest(data))
        core=files['outputs/hosted_static_core.py'];self.assertEqual(policy['coreSha256'],mod.digest(core))
        self.assertEqual(5120,policy['initialMemoryFloorMiB']);self.assertEqual(4096,policy['runtimeMemoryFloorMiB'])
    def test_native_fixed_commands(self):
        policy=json.loads((ROOT/'hosted-static-policy.json').read_bytes());data=(ROOT/'sealed-static-kit.zip').read_bytes() if (ROOT/'sealed-static-kit.zip').is_file() else mod.fetch(policy)
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
        data=(ROOT/'sealed-static-kit.zip').read_bytes() if (ROOT/'sealed-static-kit.zip').is_file() else mod.fetch(policy)
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
        self.permit={'leaseId':'synthetic-source-control','expiresUtc':'2000-01-01T00:00:00Z'}
        self.owner={'owner':mod.OWNER,**self.permit,'persistentData':False}
        mod.validate_sdk_cleanup(mod.SDK_ROOT,self.owner,self.permit)
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
        data=(ROOT/'sealed-static-kit.zip').read_bytes() if (ROOT/'sealed-static-kit.zip').is_file() else mod.fetch(policy)
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
        data=(ROOT/'sealed-static-kit.zip').read_bytes() if (ROOT/'sealed-static-kit.zip').is_file() else mod.fetch(policy)
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
                state=dict(result=SimpleNamespace(stdout=text.encode(),stderr=b''),REPO=Path(temporary),runroot=Path(temporary),CANDIDATE='a'*64,BASE='b'*40,association=association,json=json,current_phase='discovery',phase_receipts={},sha=lambda p:'e2278ee608bf879e73ba5f49955143d1a7613c959552be5c47b7e9abef08c74d' if mutation=='historical-assembly' else 'c'*64)
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
        for text in ['timeout = min(600, remaining-25)','phase_deadline-time.monotonic()',"raise RuntimeError('Fixed remaining validation route deadline exceeded')",'supervisor.supervise(owned._quarantined, recover, slot, journal, checkpoint)','memory_limit=3 * 1024**3','cpu_rate=5000','output_limit=4 * 1024 * 1024']:
            self.assertIn(text,core)



class PhasePolicyMetadataControls(unittest.TestCase):
    def test_policy_phase_authority_matches_actual_core_and_historical_replay_semantics(self):
        import ast
        policy=json.loads((ROOT/'hosted-static-policy.json').read_bytes())
        data=(ROOT/'sealed-static-kit.zip').read_bytes() if (ROOT/'sealed-static-kit.zip').is_file() else mod.fetch(policy)
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

if __name__=='__main__':unittest.main()
