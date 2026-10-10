import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/'scripts/intranet_native_handoff.py'
spec=importlib.util.spec_from_file_location('native_handoff',PATH)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
SERVICE='11111111-1111-1111-1111-111111111111'
BASE='22222222-2222-2222-2222-222222222222'
GREEN='33333333-3333-3333-3333-333333333333'
RUN='a'*32

class NativeState:
    def __init__(self, role, scenario='success'):
        self.name=m.ROLES[role][0];self.green=self.name+'-bg-'+RUN[:8];self.scenario=scenario
        self.canonical_uid=BASE;self.green_uid=GREEN;self.run=RUN
        self.service=dict(uid=SERVICE,rv='7',selector={'app.kubernetes.io/name':self.name},ports=[dict(name='http',port=80,targetPort='http',protocol='TCP')])
        self.replicas=2;self.green_rv='10';self.deleted=False;self.calls=[];self.options=None
    def __call__(self, command, arguments, step):
        self.calls.append((command,copy.deepcopy(arguments),step))
        assert command=='kubectl' and arguments[:2]==['-n','maliev-legacy']
        args=arguments[2:];value=''
        if args[:2]==['get','service']:
            field=args[-1].removeprefix('jsonpath={').removesuffix('}')
            table={'.metadata.uid':self.service['uid'],'.metadata.resourceVersion':self.service['rv'],'.spec.selector':json.dumps(self.service['selector']),'.spec.ports':json.dumps(self.service['ports']),'.spec.type':'ClusterIP'}
            value=table[field]
        elif args[:2]==['get','deployment']:
            field=args[-1].removeprefix('jsonpath={').removesuffix('}')
            name=args[2]
            if '--ignore-not-found' in args and self.deleted:value=''
            elif field=='.metadata.uid':value=self.green_uid if name==self.green else self.canonical_uid
            elif field=='.metadata.resourceVersion':value=self.green_rv
            elif field=='.metadata.labels.maliev\\.com/observability-handoff':value='b'*32 if self.scenario=='foreign-run' else self.run
            elif field=='.spec.replicas':value=str(self.replicas)
            else:raise AssertionError('Unexpected selected field')
        elif args[:2]==['patch','service']:
            patch=json.loads(args[-1]);self.service_patch=patch
            if self.scenario=='server-cas-race':return dict(exitCode=29,stdout='PRIVATE_PROVIDER_SENTINEL')
            assert patch[0]['value']==self.service['uid'] and patch[1]['value']==self.service['rv']
            assert patch[2]['value']==self.service['ports'] and patch[3]['value']==self.service['selector']
            self.service['selector']=patch[4]['value'];self.service['rv']=str(int(self.service['rv'])+1)
            if self.scenario=='readback-uid':self.service['uid']=BASE
        elif args[:2]==['patch','deployment']:
            self.scale_patch=json.loads(args[-1])
            assert self.scale_patch[0]['value']==GREEN and self.scale_patch[1]['value']==self.green_rv
            self.replicas=0;self.green_rv='11'
        elif args[:2]==['get','pods']:
            value=GREEN if self.scenario=='remaining-pods' else ''
        elif args[:2]==['delete','--raw']:
            self.options=json.loads(Path(args[-1]).read_text(encoding='utf-8'))
            self.options_path=args[-1]
            assert self.options['preconditions']==dict(uid=GREEN,resourceVersion='11')
            if self.scenario=='delete-race':return dict(exitCode=31,stdout='PRIVATE_PROVIDER_SENTINEL')
            self.deleted=True
        else:raise AssertionError('No executable fallback')
        return dict(exitCode=0,stdout=value)

class BindingTests(unittest.TestCase):
    def route(self, role, scenario='success', selector='green', phase='ROUTE_GREEN'):
        state=NativeState(role,scenario)
        adapter=m.NativeSelectorDrain(role,state,lambda *_: {})
        expected=dict(uid=SERVICE,resourceVersion='7',selector='original',selectorUid=BASE,portsSignature=m.canonical(state.service['ports']))
        if selector=='original':
            state.service['selector']={'app.kubernetes.io/name':state.green,'maliev.com/observability-handoff':RUN}
            expected.update(selector='green',selectorUid=GREEN)
        request=dict(runId=RUN,service=expected,selector=selector,targetDeploymentUid=GREEN if selector=='green' else BASE)
        return state,adapter,request
    def test_current_roles_all_policy_selector_and_fallback_phases(self):
        for role in m.ROLES:
            for phase,selector in [('ROUTE_GREEN','green'),('ROUTE_CANONICAL','original'),('FALLBACK_SELECTOR','green'),('ROLLBACK_SELECTOR','original')]:
                with self.subTest(role=role,phase=phase):
                    state,adapter,request=self.route(role,selector=selector,phase=phase)
                    receipt=adapter.route(phase,request)
                    self.assertEqual(request['targetDeploymentUid'],receipt['selectorUid'])
                    self.assertEqual('8',receipt['resourceVersion'])
                    self.assertEqual(['/metadata/uid','/metadata/resourceVersion','/spec/ports','/spec/selector','/spec/selector'],[op['path'] for op in state.service_patch])
    def test_preflight_uid_rv_ports_selector_races_never_patch(self):
        for role in m.ROLES:
            for field in ('uid','rv','ports','selector'):
                with self.subTest(role=role,field=field):
                    state,adapter,request=self.route(role)
                    state.service[field]={'uid':BASE,'rv':'9','ports':[dict(port=81,targetPort='http',protocol='TCP')],'selector':{'app.kubernetes.io/name':'foreign'}}[field]
                    with self.assertRaises(m.NativeBindingRejected):adapter.route('ROUTE_GREEN',request)
                    self.assertFalse(any(args[2]=='patch' for _,args,_ in state.calls))
    def test_server_cas_native_exit_and_after_readback_rejection(self):
        for scenario in ('server-cas-race','readback-uid','foreign-run'):
            with self.subTest(scenario=scenario):
                state,adapter,request=self.route('compatibility',scenario)
                with self.assertRaises(m.NativeBindingRejected) as caught:adapter.route('ROUTE_GREEN',request)
                if scenario=='server-cas-race':self.assertEqual(29,caught.exception.exit_code)
                self.assertNotIn('PRIVATE_PROVIDER_SENTINEL',str(caught.exception))
    def test_selected_backend_uid_and_green_run_fenced_before_all_route_phases(self):
        for role in m.ROLES:
            for phase,selector in [('ROUTE_GREEN','green'),('FALLBACK_SELECTOR','green'),('ROUTE_CANONICAL','original'),('ROLLBACK_SELECTOR','original')]:
                faults=('selected-uid',) if selector=='green' else ('selected-uid','selected-run')
                for fault in faults:
                    with self.subTest(role=role,phase=phase,fault=fault):
                        state,adapter,request=self.route(role,selector=selector,phase=phase)
                        if selector=='green':state.canonical_uid=GREEN
                        elif fault=='selected-uid':state.green_uid=BASE
                        else:state.scenario='foreign-run'
                        with self.assertRaises(m.NativeBindingRejected):adapter.route(phase,request)
                        self.assertFalse(any(args[2]=='patch' for _,args,_ in state.calls))
    def test_current_roles_owned_drain_and_atomic_delete(self):
        for role in m.ROLES:
            with self.subTest(role=role):
                state=NativeState(role)
                adapter=m.NativeSelectorDrain(role,state,lambda step,request:dict(exitCode=0,receipt=dict(greenUid=GREEN,runId=RUN,remainingProcesses=0)))
                result=adapter.drain(dict(runId=RUN,greenUid=GREEN))
                self.assertTrue(result['ownedDeleted'])
                self.assertEqual('test',state.scale_patch[0]['op'])
                self.assertEqual(GREEN,state.scale_patch[0]['value'])
                self.assertFalse(Path(state.options_path).exists())
    def test_process_pod_run_and_delete_races_reject_deletion(self):
        for scenario in ('remaining-process','remaining-pods','foreign-run','delete-race'):
            with self.subTest(scenario=scenario):
                state=NativeState('bff',scenario)
                adapter=m.NativeSelectorDrain('bff',state,lambda *_:dict(exitCode=0,receipt=dict(greenUid=GREEN,runId=RUN,remainingProcesses=1 if scenario=='remaining-process' else 0)))
                with self.assertRaises(m.NativeBindingRejected) as caught:adapter.drain(dict(runId=RUN,greenUid=GREEN))
                self.assertFalse(state.deleted)
                if scenario=='delete-race':
                    self.assertEqual(31,caught.exception.exit_code)
                    self.assertFalse(Path(state.options_path).exists())
    def test_actual_pinned_producer_loader_and_public_refusal(self):
        root=ROOT/'scripts'
        self.assertTrue(callable(m.load_policy(root).run_handoff))
        with tempfile.TemporaryDirectory(prefix='owned-pin-negative-') as temporary:
            for name in m.PINS:(Path(temporary)/name).write_text('changed',encoding='utf-8')
            with self.assertRaises(m.NativeBindingRejected):m.load_policy(temporary)
        with self.assertRaises(m.NativeBindingRejected):m.invoke_public_release()
    def test_joined_existing_policy_selected_json_native_routes_and_owned_drain(self):
        helper_path=ROOT/'tests/test_application_handoff_policy.py'
        helper_spec=importlib.util.spec_from_file_location('frozen_policy_test_helper',helper_path)
        helper=importlib.util.module_from_spec(helper_spec);helper_spec.loader.exec_module(helper)
        scripts=ROOT/'scripts'
        for role in m.ROLES:
            for fail in (None,'GREEN_HEALTH','CANONICAL_HEALTH'):
                with self.subTest(role=role,fail=fail):
                    model=helper.FakeTools(fail=fail,replicas=2)
                    state=NativeState(role)
                    state.canonical_uid=model.deployment['uid'];state.service['uid']=model.service['uid']
                    model.service['resourceVersion']='7';model.service['portsSignature']=m.canonical(state.service['ports'])
                    metadata=dict(containerNames=[m.ROLES[role][1]],unsafeFields=[],environment=[],
                        containerMetadata=dict(readinessProbe=dict(httpGet=dict(path='/intranet/readiness' if role=='compatibility' else '/intranet-bff/readiness',port='http')),livenessProbe=dict(httpGet=dict(path='/intranet/liveness' if role=='compatibility' else '/intranet-bff/liveness',port='http')),envFrom=[dict(secretRef=dict(name='legacy-maliev-intranet-runtime'))]),
                        podMetadata=dict(serviceAccountName='legacy-maliev-intranet',automountServiceAccountToken=False))
                    model.deployment['greenMetadata']=json.dumps(metadata)
                    def application_tool(step,request):
                        state.run=request['runId'];state.green=state.name+'-bg-'+state.run[:8]
                        if step=='DRAIN_PROCESS_PROOF':
                            self.assertEqual(0,state.replicas)
                            return dict(exitCode=0,receipt=dict(greenUid=helper.GREEN,runId=state.run,remainingProcesses=0))
                        response=model(step,request)
                        if step=='CREATE_GREEN':
                            model.green['greenMetadataPlan']=copy.deepcopy(request['greenMetadataPlan'])
                            response['receipt']['greenMetadataPlan']=copy.deepcopy(request['greenMetadataPlan'])
                        return response
                    def native(command,args,step):
                        answer=state(command,args,step)
                        if args[2:4]==['patch','service'] and answer['exitCode']==0:
                            selected='original' if state.service['selector']['app.kubernetes.io/name']==state.name else 'green'
                            model.service.update(resourceVersion=state.service['rv'],selector=selected,selectorUid=model.deployment['uid'] if selected=='original' else helper.GREEN)
                        if args[2:4]==['delete','--raw'] and answer['exitCode']==0:model.green=None
                        return answer
                    if fail:
                        with self.assertRaises(Exception) as caught:m.run_current_handoff(role,helper.COMMIT,helper.DIGEST,native,application_tool,scripts)
                        self.assertEqual(fail=='CANONICAL_HEALTH',caught.exception.canonical_mutation_started)
                        self.assertFalse(caught.exception.fallback_blocked)
                        self.assertEqual('green' if fail=='CANONICAL_HEALTH' else 'original',model.service['selector'])
                    else:
                        result=m.run_current_handoff(role,helper.COMMIT,helper.DIGEST,native,application_tool,scripts)
                        self.assertFalse(result['runtimeAccepted'])
                        self.assertTrue(state.deleted)
                        self.assertIsNone(model.green)
                    self.assertTrue(any(args[2:4]==['patch','service'] for _,args,_ in state.calls))
    def joined_negative(self,role,*,selected_uid_race=False,proof_fault=None):
        helper_spec=importlib.util.spec_from_file_location('frozen_negative_helper',ROOT/'tests/test_application_handoff_policy.py')
        helper=importlib.util.module_from_spec(helper_spec);helper_spec.loader.exec_module(helper)
        scripts=ROOT/'scripts'
        model=helper.FakeTools(replicas=2)
        state=NativeState(role);state.canonical_uid=model.deployment['uid'];state.service['uid']=model.service['uid']
        model.service['resourceVersion']='7';model.service['portsSignature']=m.canonical(state.service['ports'])
        probe=dict(httpGet=dict(path='/intranet/readiness' if role=='compatibility' else '/intranet-bff/readiness',port='http'))
        model.deployment['greenMetadata']=json.dumps(dict(containerNames=[m.ROLES[role][1]],unsafeFields=[],environment=[],containerMetadata=dict(readinessProbe=probe,livenessProbe=probe),podMetadata=dict(automountServiceAccountToken=False)))
        def application_tool(step,request):
            state.run=request['runId'];state.green=state.name+'-bg-'+state.run[:8]
            if step=='DRAIN_PROCESS_PROOF':
                self.assertEqual(0,state.replicas)
                return proof_fault(dict(exitCode=0,receipt=dict(greenUid=helper.GREEN,runId=state.run,remainingProcesses=0)))
            response=model(step,request)
            if step=='CREATE_GREEN':
                model.green['greenMetadataPlan']=copy.deepcopy(request['greenMetadataPlan'])
                response['receipt']['greenMetadataPlan']=copy.deepcopy(request['greenMetadataPlan'])
            return response
        def native(command,args,step):
            if selected_uid_race and step=='ROUTE_GREEN':state.canonical_uid=helper.GREEN
            answer=state(command,args,step)
            if args[2:4]==['patch','service'] and answer['exitCode']==0:
                selected='original' if state.service['selector']['app.kubernetes.io/name']==state.name else 'green'
                model.service.update(resourceVersion=state.service['rv'],selector=selected,selectorUid=model.deployment['uid'] if selected=='original' else helper.GREEN)
            if args[2:4]==['patch','deployment'] and answer['exitCode']==0:
                # Independent selected Deployment/process proof must reflect the actual scale.
                model.green.update(replicas=0,ready=0,available=0)
            if args[2:4]==['delete','--raw'] and answer['exitCode']==0:model.green=None
            return answer
        with self.assertRaises(Exception) as caught:m.run_current_handoff(role,helper.COMMIT,helper.DIGEST,native,application_tool,scripts)
        return state,caught.exception
    def test_joined_policy_selected_backend_recreation_rejects_traffic_patch(self):
        for role in m.ROLES:
            with self.subTest(role=role):
                state,failure=self.joined_negative(role,selected_uid_race=True)
                self.assertEqual('ROUTE_GREEN',failure.step)
                self.assertFalse(failure.canonical_mutation_started)
                self.assertFalse(any(args[2]=='patch' for _,args,_ in state.calls))
                self.assertFalse(state.deleted)
    def test_joined_policy_nonzero_malformed_extra_observer_receipts_never_delete(self):
        faults={
            'nonzero':lambda good:dict(good,exitCode=29),
            'boolean-exit':lambda good:dict(good,exitCode=True),
            'string-exit':lambda good:dict(good,exitCode='29'),
            'negative-exit':lambda good:dict(good,exitCode=-1),
            'response-extra':lambda good:dict(good,PRIVATE_PROVIDER_SENTINEL='private'),
            'missing-receipt':lambda good:dict(exitCode=0),
            'receipt-not-dict':lambda good:dict(exitCode=0,receipt='PRIVATE_PROVIDER_SENTINEL'),
            'receipt-extra':lambda good:dict(exitCode=0,receipt=dict(good['receipt'],private='PRIVATE_PROVIDER_SENTINEL')),
            'wrong-uid':lambda good:dict(exitCode=0,receipt=dict(good['receipt'],greenUid=BASE)),
            'wrong-run':lambda good:dict(exitCode=0,receipt=dict(good['receipt'],runId='b'*32)),
            'boolean-remaining':lambda good:dict(exitCode=0,receipt=dict(good['receipt'],remainingProcesses=False)),
            'unbounded-remaining':lambda good:dict(exitCode=0,receipt=dict(good['receipt'],remainingProcesses=2**31)),
            'unbounded-run':lambda good:dict(exitCode=0,receipt=dict(good['receipt'],runId='a'*16385)),
        }
        for role in m.ROLES:
            for label,fault in faults.items():
                with self.subTest(role=role,fault=label):
                    state,failure=self.joined_negative(role,proof_fault=fault)
                    self.assertEqual('DRAIN_GREEN',failure.step)
                    self.assertEqual(29 if label=='nonzero' else 1,failure.exit_code)
                    self.assertTrue(failure.canonical_mutation_started)
                    self.assertTrue(failure.fallback_blocked)
                    self.assertFalse(state.deleted)
                    self.assertFalse(any(args[2:4]==['delete','--raw'] for _,args,_ in state.calls))
                    self.assertNotIn('PRIVATE_PROVIDER_SENTINEL',str(failure))

if __name__=='__main__':unittest.main(verbosity=2)
