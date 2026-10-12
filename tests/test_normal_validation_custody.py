"""Provider-free source controls; no SDK/controller/OS qualification."""
import base64
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import sys
import os
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('normal_validation_custody', ROOT/'scripts/normal_validation_custody.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
sys.modules['normal_validation_custody']=module


class SourceControls(unittest.TestCase):
    def setUp(self):
        module.EVIDENCE_QUOTA=module.EvidenceQuota()
    def test_modes_and_exact_request(self):
        self.assertIsNone(module.request(b'', 'disabled'))
        good = {'schema':'normal-validation-custody-request-v1','profile':module.MODE,
                'deadlineRecord':'/caller/clock.json','resultRoot':'/caller/results'}
        self.assertEqual(module.request(json.dumps(good).encode(), module.MODE), good)
        for mode, raw in [('other', b''), ('disabled', b'x'), (module.MODE,b'{}')]:
            with self.subTest(mode=mode), self.assertRaises(ValueError): module.request(raw, mode)

    def test_duplicate_unknown_and_nonfinite_json(self):
        for raw in [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}']:
            with self.assertRaises(ValueError): module.parse(raw)
        with self.assertRaises(ValueError): module.keys({'a':1,'extra':2}, ('a',))

    def test_strict_number_types(self):
        for value in [True, 1.0, '1']:
            with self.assertRaises(ValueError): module.integer(value)
        for value in [True, float('inf'), float('nan'), -1]:
            with self.assertRaises(ValueError): module.number(value)

    def test_original_order_and_logger_only_in_test(self):
        commands = [module.native_arguments(p, 's.sln', '/run/normal-trx') for p in module.PHASES]
        self.assertEqual([x[1] for x in commands], ['restore','build','format','test','list'])
        self.assertEqual(commands[3], ['dotnet','test','s.sln','--configuration','Release','--no-build','--no-restore',
                                      '--logger','trx;LogFileName=normal-validation.trx','--results-directory','/run/normal-trx'])
        self.assertFalse(any('--filter' in x for x in commands))
        self.assertEqual(commands[2], ['dotnet','format','s.sln','--verify-no-changes','--no-restore'])

    def test_existing_env_semantics_not_serialized(self):
        env = {'PATH':'existing','DOTNET_ROOT':'existing','GITHUB_ACTIONS':'true','PRIVATE_TEST_SETTING':'kept'}
        self.assertEqual(module.native_environment(env, 'false'), env)
        expected = dict(env, GITHUB_ACTIONS='false')
        self.assertEqual(module.native_environment(env, 'true'), expected)
        self.assertEqual(env['GITHUB_ACTIONS'], 'true')
        with self.assertRaises(ValueError): module.native_environment(env, 'TRUE')

    def fixture(self, tmp):
        package = Path(tmp)/'package'; action = package/'actions/dotnet-validate'; action.mkdir(parents=True)
        (package/'scripts').mkdir()
        tree, blobs = [], {}
        for name in module.FILES:
            raw = (ROOT/name).read_bytes()
            with (package/name).open('wb') as stream:
                stream.write(raw);stream.flush();os.fsync(stream.fileno())
            sha = hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
            tree.append({'path':name,'type':'blob','mode':'100644','sha':sha})
            blobs[sha] = {'sha':sha,'encoding':'base64','size':len(raw),'content':base64.b64encode(raw).decode()}
        producer, tree_sha = 'a'*40, 'b'*40
        env = {'NORMAL_CUSTODY_ACTION_REPOSITORY':module.REPOSITORY,'NORMAL_CUSTODY_ACTION_REF':producer,
               'NORMAL_CUSTODY_ACTION_PATH':str(action),'GITHUB_ACTION_PATH':str(action),'GITHUB_REPOSITORY':module.CALLER}
        def get(endpoint, deadline):
            if endpoint.startswith('git/commits/'):return {'sha':producer,'tree':{'sha':tree_sha}}
            if endpoint.startswith('git/trees/'):return {'sha':tree_sha,'tree':tree,'truncated':False}
            return blobs[endpoint.rsplit('/',1)[1]]
        return env, get, tree, blobs, package

    def test_fake_metadata_control_binds_every_physical_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            env, get, _, _, _ = self.fixture(tmp)
            result = module.authenticate(env, get=get, now=lambda:1)
            self.assertEqual(len(result['pins']), 5)
            self.assertEqual(result['producer'], 'a'*40)

    def test_context_foreign_repository_tag_localpath(self):
        with tempfile.TemporaryDirectory() as tmp:
            env, get, _, _, _ = self.fixture(tmp)
            for key, value in [('NORMAL_CUSTODY_ACTION_REPOSITORY','foreign/repo'),
                               ('NORMAL_CUSTODY_ACTION_REF','main'),('GITHUB_REPOSITORY','foreign/repo')]:
                with self.subTest(key=key), self.assertRaises(ValueError):module.authenticate(dict(env, **{key:value}), get=get, now=lambda:1)

    def test_immutable_object_and_physical_tamper_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            env, get, _, _, package = self.fixture(tmp)
            (package/module.FILES[1]).write_text('changed')
            with self.assertRaises(ValueError):module.authenticate(env, get=get, now=lambda:1)
        with tempfile.TemporaryDirectory() as tmp:
            env, get, tree, _, _ = self.fixture(tmp);tree[0]['mode']='120000'
            with self.assertRaises(ValueError):module.authenticate(env, get=get, now=lambda:1)

    def test_truncated_or_duplicate_tree_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            env, get, tree, _, _ = self.fixture(tmp)
            def truncated(endpoint, deadline):
                value=get(endpoint,deadline)
                return dict(value,truncated=True) if endpoint.startswith('git/trees/') else value
            with self.assertRaises(ValueError):module.authenticate(env,get=truncated,now=lambda:1)
            tree.append(dict(tree[0]))
            with self.assertRaises(ValueError):module.authenticate(env,get=get,now=lambda:1)

    def test_source_api_identity_and_size_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            env, get, _, blobs, _ = self.fixture(tmp)
            first=next(iter(blobs.values()));first['size']+=1
            with self.assertRaises(ValueError):module.authenticate(env,get=get,now=lambda:1)

    def test_redirect_and_endpoint_no_auth_fallback(self):
        with self.assertRaises(ValueError):module.DenyRedirect().redirect_request(None,None,302,None,None,'https://elsewhere')
        with self.assertRaises(ValueError):module.public_get('../private',100)

    def test_original_clock_bounds_and_reserve(self):
        env={'GITHUB_RUN_ID':'1','GITHUB_RUN_ATTEMPT':'2','GITHUB_SHA':'a'*40,'RUNNER_NAME':'runner'}
        boot='11111111-1111-1111-1111-111111111111'
        record={'schema':'n62-job-deadline-v1','run':1,'attempt':2,'job':3,'head':'a'*40,'runner':'runner',
                'startedUtc':'2026-10-12T00:00:00Z','sampleWall':dt.datetime(2026,10,12,tzinfo=dt.timezone.utc).timestamp()+10,
                'sampleMono':1000,'boot':boot,'deadlineMono':3690,'reserve':300}
        self.assertEqual(module.budget(record,env,record['sampleWall']+10,1010,boot),3690)
        for change in [{'reserve':299},{'deadlineMono':3700},{'run':True},{'job':1.0}]:
            with self.subTest(change=change),self.assertRaises(ValueError):module.budget(dict(record,**change),env,record['sampleWall']+10,1010,boot)
        with self.assertRaises(ValueError):module.budget(record,env,record['sampleWall']+10,3391,boot)

    def test_current_root_single_trx_and_relative_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);trx=root/'normal-validation.trx';trx.write_bytes(b'<actual-test-fixture/>')
            self.assertEqual(module.discover_trx(root),trx)
            self.assertEqual(module.artifact(root,trx)['path'],'normal-validation.trx')
            (root/'other.trx').write_bytes(b'<other/>')
            with self.assertRaises(ValueError):module.discover_trx(root)

    def test_empty_or_outside_trx_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'empty.trx').write_bytes(b'')
            with self.assertRaises(ValueError):module.discover_trx(root)
            with self.assertRaises(ValueError):module.artifact(root,ROOT/'scripts/normal_validation_custody.py')

    def test_unreleased_lifecycle_never_claims_pass_or_native(self):
        self.assertIs(module.RELEASED_LIFECYCLE,False)
        source=(ROOT/'scripts/normal_validation_custody.py').read_text()
        self.assertLess(source.index('require(RELEASED_LIFECYCLE,'),source.index("if args.operation == 'prepare':"))

    def test_trx_incremental_entry_quota(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for i in range(1025):(root/str(i)).touch()
            with self.assertRaisesRegex(ValueError,'entry quota'):module.discover_trx(root)

    def test_trx_exact_filename_and_nested_ambiguity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'other.trx').write_bytes(b'x')
            with self.assertRaises(ValueError):module.discover_trx(root)
            (root/'other.trx').unlink();(root/'nested').mkdir()
            (root/'nested/normal-validation.trx').write_bytes(b'x')
            with self.assertRaises(ValueError):module.discover_trx(root)

    def test_memory_loader_ignores_changed_physical_sibling_and_shadow_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            env,get,_,_,package=self.fixture(tmp)
            module.authenticate(env,get=get,now=lambda:1)
            (package/'scripts/normal_validation_controller.py').write_text("raise RuntimeError('tamper')")
            with mock.patch.dict(sys.modules,{'normal_validation_controller':object()}):
                loaded=module.load_authenticated_modules(package)
                self.assertIs(loaded.RELEASED_LIFECYCLE,False)
                self.assertEqual(sys.modules['normal_validation_controller'].Controller.gate_digest(),
                    hashlib.sha256(module.AUTHENTICATED_BYTES['scripts/normal_validation_exec_gate.py']).hexdigest())
        sys.modules['normal_validation_custody']=module

    def test_authenticated_deadline_cannot_be_restarted(self):
        with tempfile.TemporaryDirectory() as tmp:
            env,get,_,_,_=self.fixture(tmp);observed=[]
            def bounded(endpoint,deadline):observed.append(deadline);return get(endpoint,deadline)
            module.authenticate(env,get=bounded,now=lambda:10,absolute_deadline=12)
            self.assertEqual(set(observed),{12})
            with self.assertRaises(ValueError):module.authenticate(env,get=bounded,now=lambda:13,absolute_deadline=12)

    def test_native_environment_strips_only_custody_controls(self):
        self.assertEqual(module.native_environment({'NORMAL_CUSTODY_JOB_API_TOKEN':'private','PATH':'kept'},'false'),{'PATH':'kept'})

    def test_job_metadata_fixed_current_attempt_and_existing_token_only(self):
        env={'GITHUB_RUN_ID':'1','GITHUB_RUN_ATTEMPT':'2','NORMAL_CUSTODY_JOB_API_TOKEN':'synthetic'}
        with mock.patch.object(module,'owned_http',return_value={'total_count':0,'jobs':[]}) as transport:
            module.job_metadata(env,module.time.monotonic()+20)
            url,headers,deadline=transport.call_args.args
            self.assertIn('/runs/1/attempts/2/jobs?per_page=100',url)
            self.assertEqual(headers['Authorization'],'Bearer synthetic')
        for value in ({'total_count':101,'jobs':[]},{'total_count':True,'jobs':[]},{'total_count':1,'jobs':[]}):
            with mock.patch.object(module,'owned_http',return_value=value),self.assertRaises(ValueError):
                module.job_metadata(env,module.time.monotonic()+20)

    def test_gate_environment_and_vectors_bounded_without_exec(self):
        spec=importlib.util.spec_from_file_location('source_gate',ROOT/'scripts/normal_validation_exec_gate.py')
        gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
        good={'argv':[str(ROOT/'synthetic-dotnet'),'test'],'executableSha256':'a'*64,'environment':{'PATH':'existing'}}
        self.assertEqual(gate.payload(json.dumps(good).encode()),good)
        for change in ({'argv':['dotnet']},{'environment':{'BAD=KEY':'x'}},{'environment':{'x':'a'*49152}},
                       {'argv':['/dotnet']*33},{'environment':{'PATH':True}}):
            with self.subTest(change=list(change)),self.assertRaises(ValueError):gate.payload(json.dumps(dict(good,**change)).encode())

    def test_exclusive_receipt_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'receipt.json';module.write_exclusive(path,{'terminal':'fixture'})
            with self.assertRaises(FileExistsError):module.write_exclusive(path,{'terminal':'changed'})
            self.assertEqual(json.loads(path.read_bytes()),{'terminal':'fixture'})

    def test_no_lifecycle_success_for_missing_kernel_flags(self):
        for key in ('scopeAbsent','nativeExitVerified','unitTerminal','wrapperExitVerified','wrapperPidfdExited'):
            raw=dict(exitCode=0,scopeAbsent=True,nativeExitVerified=True,unitTerminal=True,wrapperExitVerified=True,wrapperPidfdExited=True)
            raw[key]=False
            with self.subTest(key=key),self.assertRaises(ValueError):module.stage_wire(raw,{},ROOT)

    def test_stage_wire_matches_reviewed_lifecycle_reader(self):
        from test_normal_validation_lifecycle import LifecycleControls
        value,shared,command,controller=LifecycleControls().fixture()
        raw=dict(stage='restore',startedMono=1,expiryMono=10,exitCode=0,scopeAbsent=True,
                 nativeExitVerified=True,unitTerminal=True,wrapperExitVerified=True,wrapperPidfdExited=True,
                 unit=controller['unit'],invocation=controller['invocation'],scope=controller['scope'],
                 namespace=controller['namespace'],helper=value['preExec']['helper'],native=value['preExec']['sdk'],
                 wrapper=dict(pid=11,birthTicks=21,executable='/systemd-run',executableSha256='f'*64),
                 wrapperExitedAtMono=4,removalObservedAtMono=4,preExecObservedAtMono=2,
                 managerPreExec=value['preExec']['manager'],terminalBeforeStop=value['terminal'])
        with tempfile.TemporaryDirectory() as tmp,mock.patch.object(module.time,'monotonic',return_value=5):
            emitted=module.stage_wire(raw,shared,Path(tmp))
            self.assertEqual(emitted['phase'],'restore')
            self.assertEqual([m['role'] for m in emitted['members']],['sdk','wrapper'])
            self.assertEqual(json.loads((Path(tmp)/emitted['lifecycle']['path']).read_bytes()),value)

    def test_actual_job_identity_fault_matrix(self):
        env={'GITHUB_RUN_ID':'1','GITHUB_RUN_ATTEMPT':'2','GITHUB_SHA':'a'*40,'RUNNER_NAME':'runner',
             'GITHUB_REPOSITORY':module.CALLER,'GITHUB_ACTIONS':'true'}
        boot='11111111-1111-1111-1111-111111111111';wall=dt.datetime(2026,10,12,tzinfo=dt.timezone.utc).timestamp()+10
        record=dict(schema='n62-job-deadline-v1',run=1,attempt=2,job=3,head='a'*40,runner='runner',
                    startedUtc='2026-10-12T00:00:00Z',sampleWall=wall,sampleMono=1000,boot=boot,deadlineMono=3690,reserve=300)
        job=dict(id=3,run_id=1,run_attempt=2,head_sha='a'*40,runner_name='runner',started_at=record['startedUtc'],status='in_progress',name='validate / validate')
        self.assertEqual(module.admit_record(record,env,{'jobs':[job]},wall+10,1010,boot),3690)
        for key,replacement in [('id',4),('run_id',2),('run_attempt',3),('head_sha','b'*40),('runner_name','foreign'),
                                ('started_at','2026-10-12T00:00:01Z'),('status','completed'),('name','different')]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                module.admit_record(record,env,{'jobs':[dict(job,**{key:replacement})]},wall+10,1010,boot)
        with self.assertRaises(ValueError):module.admit_record(record,env,{'jobs':[job,job]},wall+10,1010,boot)

    def test_main_runtime_guard_prevents_controller_admission(self):
        value={'schema':'normal-validation-custody-request-v1','profile':module.MODE,'deadlineRecord':'synthetic','resultRoot':'synthetic'}
        with mock.patch.object(sys,'argv',['source','prepare','--mode',module.MODE,'--request','fixture','--solution','s.sln']),\
             mock.patch.object(module,'trusted_interpreter'),mock.patch.object(module,'stable_read',side_effect=[json.dumps(value).encode(),b'{}']),\
             mock.patch.object(module,'budget',return_value=10000),mock.patch.object(module,'authenticate'),\
             mock.patch.object(module,'original_deadline_path',return_value=Path('synthetic')),\
             mock.patch.object(module.Path,'read_text',return_value='synthetic'),mock.patch.object(module,'admission') as admission:
            with self.assertRaisesRegex(ValueError,'kernel qualification unavailable'):module.main()
            admission.assert_not_called()

    def test_external_original_deadline_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);workspace=root/'workspace';workspace.mkdir();runner=root/'runner-temp';runner.mkdir()
            clock=runner/'n62-deadline.json';clock.write_bytes(b'{"original":true}')
            value={'deadlineRecord':str(clock)}
            self.assertEqual(module.original_deadline_path(value,{'RUNNER_TEMP':str(runner)}),clock)
            self.assertFalse(clock.is_relative_to(workspace))
            with self.assertRaises(ValueError):module.original_deadline_path({'deadlineRecord':str(workspace/'n62-deadline.json')},{'RUNNER_TEMP':str(runner)})
            self.assertEqual(clock.read_bytes(),b'{"original":true}')

    def test_proposed_results_parent_may_be_missing_without_caller_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace=Path(tmp);record=dict(run=1,attempt=2,job=3)
            root=workspace/'runner-results'/('normal-1-2-3-'+'a'*32)
            self.assertEqual(module.proposed_result_root({'resultRoot':str(root)},record,workspace),(root,'a'*32))
            self.assertFalse(root.parent.exists())
            root.parent.mkdir();self.assertEqual(module.proposed_result_root({'resultRoot':str(root)},record,workspace)[0],root)
            root.mkdir()
            with self.assertRaises(ValueError):module.proposed_result_root({'resultRoot':str(root)},record,workspace)

    def test_proposed_results_rejects_foreign_parent_and_nonce(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace=Path(tmp);record=dict(run=1,attempt=2,job=3)
            for path in (workspace/'foreign'/('normal-1-2-3-'+'a'*32),workspace/'runner-results/normal-1-2-4-bad'):
                with self.assertRaises(ValueError):module.proposed_result_root({'resultRoot':str(path)},record,workspace)

    def test_v7_artifact_and_cumulative_quotas(self):
        self.assertEqual((module.TRX_LIMIT,module.LOG_LIMIT,module.RECEIPT_LIMIT),(16*1024**2,4*1024**2,1024**2))
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name,limit in [('normal-validation.trx',module.TRX_LIMIT),('test.log',module.LOG_LIMIT)]:
                path=root/name
                with path.open('wb') as stream:stream.truncate(limit+1)
                with self.assertRaises(ValueError):module.artifact(root,path)
        quota=module.EvidenceQuota();quota.consume(64*1024**2)
        with self.assertRaises(ValueError):quota.read(1)
        quota=module.EvidenceQuota()
        for _ in range(128):quota.read(0)
        with self.assertRaises(ValueError):quota.read(0)
        quota=module.EvidenceQuota()
        with self.assertRaises(ValueError):quota.entry('a'*(1024**2+1))

    def test_sole_trx_covers_entire_result_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'normal-trx').mkdir();trx=root/'normal-trx/normal-validation.trx';trx.write_bytes(b'fixture')
            self.assertEqual(module.discover_trx(root,trx),trx)
            (root/'borrowed.trx').write_bytes(b'fixture')
            with self.assertRaises(ValueError):module.discover_trx(root,trx)

    def test_proof_timestamp_source_precedes_release_transition_is_separate(self):
        source=(ROOT/'scripts/normal_validation_controller.py').read_text()
        self.assertLess(source.index("receipt['preExecObservedAtMono']=time.monotonic()"),source.index('peer.send(payload)'))
        self.assertLess(source.index('peer.send(payload)'),source.index('receipt["transitionObservedAtMono"] = time.monotonic()'))
        self.assertEqual(source.count('preExecObservedAtMono'),1)

    def test_lifecycle_exact_64k_write_and_artifact_read_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'lifecycle-restore.json'
            value={'p':'x'*(65536-8)}
            self.assertEqual(len(json.dumps(value,separators=(',',':')).encode()),65536)
            module.write_exclusive(path,value,maximum=module.LIFECYCLE_LIMIT)
            emitted=module.artifact(root,path,maximum=module.LIFECYCLE_LIMIT)
            self.assertEqual(emitted['sha256'],hashlib.sha256(path.read_bytes()).hexdigest())

    def test_lifecycle_64k_plus_one_rejected_at_writer_and_artifact_reader(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'lifecycle-restore.json';value={'p':'x'*(65537-8)}
            with self.assertRaises(ValueError):module.write_exclusive(path,value,maximum=module.LIFECYCLE_LIMIT)
            self.assertFalse(path.exists())
            path.write_bytes(json.dumps(value,separators=(',',':')).encode())
            with self.assertRaises(ValueError):module.artifact(root,path,maximum=module.LIFECYCLE_LIMIT)


if __name__=='__main__':unittest.main(verbosity=2)
