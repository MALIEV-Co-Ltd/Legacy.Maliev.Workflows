import copy
import importlib.util
import json
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT/'scripts/intranet_deployment_binding.py'
spec=importlib.util.spec_from_file_location('deployment_binding',MODULE)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
SCRIPTS=ROOT/'scripts'
UID='11111111-1111-1111-1111-111111111111';GREEN='22222222-2222-2222-2222-222222222222';SERVICE='33333333-3333-3333-3333-333333333333'
RUN='a'*32;OLD='sha256:'+'b'*64;NEW='sha256:'+'c'*64
ROLLOUT=dict(minReadySeconds=90,drainSeconds=60,terminationGracePeriodSeconds=90,maxSurge=1,maxUnavailable=0)

class KubernetesState:
    def __init__(self,role,replicas=2):
        self.role=role;self.name,self.container=m.base.ROLES[role]
        artifact='legacy-maliev-intranet-compatibility' if role=='compatibility' else 'legacy-maliev-intranet-bff'
        self.repository='registry.example.invalid/project/repository/'+artifact
        self.calls=[];self.files=[];self.deleted=False;self.created=None;self.fail=None
        readiness='/intranet/readiness' if role=='compatibility' else '/intranet-bff/readiness'
        liveness='/intranet/liveness' if role=='compatibility' else '/intranet-bff/liveness'
        pod=dict(serviceAccountName='legacy-maliev-intranet',automountServiceAccountToken=False,terminationGracePeriodSeconds=30,
            containers=[dict(name=self.container,image=self.repository+'@'+OLD,
                env=[dict(name='DOTNET_ENVIRONMENT',value='Production')],
                envFrom=[dict(secretRef=dict(name='legacy-maliev-intranet-runtime'))],
                readinessProbe=dict(httpGet=dict(path=readiness,port='http')),livenessProbe=dict(httpGet=dict(path=liveness,port='http')),
                startupProbe=None,ports=[dict(name='http',containerPort=8080)],
                resources=dict(requests=dict(cpu='50m',memory='96Mi')),securityContext=dict(readOnlyRootFilesystem=True))])
        self.deployments={self.name:dict(metadata=dict(name=self.name,uid=UID,resourceVersion='7',labels={}),
            spec=dict(replicas=replicas,strategy=dict(type='RollingUpdate',rollingUpdate=dict(maxSurge=1,maxUnavailable=1)),template=dict(spec=pod)),
            status=dict(readyReplicas=replicas,availableReplicas=replicas))}
        self.service=dict(metadata=dict(uid=SERVICE,resourceVersion='9'),spec=dict(type='ClusterIP',selector={'app.kubernetes.io/name':self.name},ports=[dict(name='http',port=80,targetPort='http',protocol='TCP')]))
    def lookup(self,object,path):
        if path=='.spec.template.spec.containers[*].name':return ' '.join(c['name'] for c in object['spec']['template']['spec']['containers'])
        if path=='.metadata.labels.maliev\\.com/observability-handoff':return object['metadata']['labels'].get('maliev.com/observability-handoff','')
        match=re.fullmatch(r'\.spec\.template\.spec\.containers\[0\]\.env\[\?\(@\.name=="([^"]+)"\)\]\.(value|valueFrom)',path)
        if match:
            values=[v.get(match[2],'') for v in object['spec']['template']['spec']['containers'][0].get('env',[]) if v['name']==match[1]]
            return values[0] if len(values)==1 else ''
        keys=path.removeprefix('.').replace('[0]','.0').split('.')
        value=object
        for key in keys:
            if type(value) is list:value=value[int(key)]
            elif type(value) is dict:value=value.get(key,'')
            else:return ''
        return value
    def __call__(self,command,args,step):
        self.calls.append((command,copy.deepcopy(args),step))
        assert command=='kubectl' and args[:2]==['-n','maliev-legacy']
        args=args[2:];value=''
        if args[0]=='get':
            kind,name=args[1:3]
            if kind=='service':obj=self.service
            elif kind=='deployment':obj=self.deployments.get(name)
            elif kind=='pods':return dict(exitCode=0,stdout='')
            else:raise AssertionError('Unknown resource')
            if obj is None and '--ignore-not-found' in args:return dict(exitCode=0,stdout='')
            query=args[-1]
            if query.startswith('jsonpath='):
                value=self.lookup(obj,query.removeprefix('jsonpath={').removesuffix('}'))
            elif 'range $key,$value :=' in query:
                field=re.search('if eq \\$key "([^"]+)"',query)[1]
                parent=obj['spec']['template']['spec']
                if 'index .spec.template.spec.containers 0' in query:parent=parent['containers'][0]
                value='present' if field in parent else ''
            elif '.initContainers' in query:
                pod=obj['spec']['template']['spec'];container=pod['containers'][0]
                value='unsafe' if pod.get('initContainers') or pod.get('volumes') or any(container.get(k) for k in ('command','args','volumeMounts')) or any(container.get(p) and (container[p].get('exec') or container[p].get('httpGet',{}).get('httpHeaders')) for p in ('readinessProbe','livenessProbe','startupProbe')) else ''
            elif '{{range .env}}' in query:
                value='\n'.join(v['name']+'|'+('reference' if 'valueFrom' in v else 'literal') for v in obj['spec']['template']['spec']['containers'][0].get('env',[]))
            else:raise AssertionError('Unknown native template')
            if value is None:value=''
            elif type(value) in (dict,list,bool):value=json.dumps(value,separators=(',',':'))
            else:value=str(value)
        elif args[0]=='create':
            self.files.append(args[-1]);document=json.loads(Path(args[-1]).read_text())
            self.created=copy.deepcopy(document);name=document['metadata']['name']
            document['metadata'].update(uid=GREEN,resourceVersion='11');document['status']=dict(readyReplicas=document['spec']['replicas'],availableReplicas=document['spec']['replicas'])
            self.deployments[name]=document
        elif args[0]=='patch':
            kind,name=args[1:3];patch=json.loads(args[-1])
            if self.fail=='canonical-server-cas' and kind=='deployment' and name==self.name:return dict(exitCode=29,stdout='PRIVATE_PROVIDER_SENTINEL')
            obj=self.service if kind=='service' else self.deployments[name]
            for operation in patch:
                parts=operation['path'].strip('/').split('/');parent=obj
                for key in parts[:-1]:parent=parent[int(key)] if type(parent) is list else parent[key]
                key=int(parts[-1]) if type(parent) is list else parts[-1]
                if operation['op']=='test':assert parent[key]==operation['value'],'API CAS precondition mismatch'
                else:parent[key]=operation['value']
            obj['metadata']['resourceVersion']=str(int(obj['metadata']['resourceVersion'])+1)
            if kind=='deployment' and name==self.name and self.fail and self.fail.startswith('post-'):
                fault=self.fail.removeprefix('post-');spec=obj['spec'];pod=spec['template']['spec'];container=pod['containers'][0]
                if fault=='uid':obj['metadata']['uid']=GREEN
                elif fault=='image':container['image']=self.repository+'@'+OLD
                elif fault=='replicas':spec['replicas']=1
                elif fault=='metadata':container['resources']['requests']['cpu']='60m'
                elif fault=='minimum':spec['minReadySeconds']=0
                elif fault=='grace':pod['terminationGracePeriodSeconds']=30
                elif fault=='surge':spec['strategy']['rollingUpdate']['maxSurge']=2
                elif fault=='unavailable':spec['strategy']['rollingUpdate']['maxUnavailable']=1
                elif fault=='lifecycle':container['lifecycle']['preStop']['exec']['command'][-1]='sleep 30'
                else:raise AssertionError('Unknown post-patch drift')
        elif args[:2]==['delete','--raw']:
            self.files.append(args[-1]);options=json.loads(Path(args[-1]).read_text())
            name=args[2].rsplit('/',1)[1]
            assert options['preconditions']=={k:self.deployments[name]['metadata'][{'uid':'uid','resourceVersion':'resourceVersion'}[k]] for k in ('uid','resourceVersion')}
            del self.deployments[name];self.deleted=True
        else:raise AssertionError('No native executable fallback')
        return dict(exitCode=0,stdout=value)

class DeploymentTests(unittest.TestCase):
    def setup_state(self,role='compatibility'):
        state=KubernetesState(role)
        adapter=m.NativeDeploymentBinding(role,state.repository,state,lambda *_:{},SCRIPTS)
        request=dict(runId=RUN,imageDigest=NEW,sourceCommit='d'*40)
        return state,adapter,request
    def prepared_state(self,role='compatibility'):
        state,adapter,request=self.setup_state(role)
        baseline=adapter.current('SNAPSHOT',request)
        metadata=adapter.metadata.decode_green_metadata(baseline['deployment']['greenMetadata'])
        plan=adapter.metadata.plan_green_metadata(adapter.contract,metadata,NEW)
        create=dict(request,replicas=2,standby=True,greenMetadataPlan=plan,rollout=ROLLOUT)
        green=adapter.create(create)
        route=dict(request,service=baseline['service'],selector='green',targetDeploymentUid=green['uid'])
        adapter.route('ROUTE_GREEN',route)
        latest=adapter.current('READ_CURRENT',request)
        mutation=dict(request,deploymentUid=UID,expectedImage=OLD,rollout=ROLLOUT,service=latest['service'],greenDeploymentUid=GREEN,
            expectedGreenMetadataPlan=plan,expectedCanonicalMetadata=metadata,expectedCanonicalReplicas=2,expectedGreenReplicas=2)
        return state,adapter,mutation
    def test_actual_selected_projection_roles_null_array_reference_preservation(self):
        for role in m.base.ROLES:
            with self.subTest(role=role):
                state,adapter,request=self.setup_state(role);current=adapter.current('SNAPSHOT',request)
                metadata=adapter.metadata.decode_green_metadata(current['deployment']['greenMetadata'])
                self.assertIsNone(metadata['containerMetadata']['startupProbe'])
                self.assertEqual(1,len(metadata['containerMetadata']['envFrom']))
                self.assertFalse(metadata['podMetadata']['automountServiceAccountToken'])
                self.assertEqual(UID,current['service']['selectorUid'])
                self.assertEqual(2,current['deployment']['replicas'])
                self.assertTrue(all('-o' in args and args[-1]!='json' for _,args,_ in state.calls))
    def test_unknown_environment_and_probe_headers_refused_without_value_fetch(self):
        for fault in ('literal','headers','command'):
            with self.subTest(fault=fault):
                state,adapter,request=self.setup_state()
                container=state.deployments[state.name]['spec']['template']['spec']['containers'][0]
                if fault=='literal':container['env'].append(dict(name='PRIVATE_ENV',value='PRIVATE_PROVIDER_SENTINEL'))
                elif fault=='headers':container['readinessProbe']['httpGet']['httpHeaders']=[dict(name='Authorization',value='PRIVATE_PROVIDER_SENTINEL')]
                else:container['command']=['PRIVATE_PROVIDER_SENTINEL']
                with self.assertRaises(Exception):adapter.current('SNAPSHOT',request)
                self.assertFalse(any('PRIVATE_ENV' in args[-1] and '.value' in args[-1] for _,args,_ in state.calls))
                if fault=='headers':self.assertFalse(any(args[-1]=='jsonpath={.spec.template.spec.containers[0].readinessProbe}' for _,args,_ in state.calls))
    def test_actual_native_create_mutate_roles_and_owned_files_settle(self):
        for role in m.base.ROLES:
            with self.subTest(role=role):
                state,adapter,request=self.prepared_state(role)
                created=state.created
                self.assertEqual(2,created['spec']['replicas'])
                self.assertEqual(state.repository+'@'+NEW,created['spec']['template']['spec']['containers'][0]['image'])
                self.assertNotIn('imageDigest',created['spec']['template']['spec']['containers'][0])
                result=adapter.mutate(request)
                self.assertEqual(NEW,result['imageDigest'])
                self.assertEqual(UID,result['uid'])
                current=adapter.read_deployment('VERIFY_CANONICAL',state.name)
                self.assertEqual(90,current['rolloutSettings']['minReadySeconds'])
                self.assertTrue(all(not Path(path).exists() for path in state.files))
    def test_fresh_uid_replicas_metadata_service_green_races_never_canonical_patch(self):
        for fault in ('uid','replicas','canonical-meta','rollout-settings','service','green-run','green-uid','green-ready','green-standby','green-meta'):
            with self.subTest(fault=fault):
                state,adapter,request=self.prepared_state()
                current=state.deployments[state.name];green=state.deployments[adapter.green_name(request)]
                if fault=='uid':current['metadata']['uid']=GREEN
                elif fault=='replicas':current['spec']['replicas']=1
                elif fault=='canonical-meta':current['spec']['template']['spec']['containers'][0]['resources']['requests']['cpu']='60m'
                elif fault=='rollout-settings':current['spec']['strategy']['rollingUpdate']['maxUnavailable']=0
                elif fault=='service':state.service['metadata']['resourceVersion']='100'
                elif fault=='green-run':green['metadata']['labels']['maliev.com/observability-handoff']='e'*32
                elif fault=='green-uid':green['metadata']['uid']=UID
                elif fault=='green-ready':green['status']['readyReplicas']=0
                elif fault=='green-standby':green['spec']['template']['spec']['containers'][0]['env'][-1]['value']='false'
                else:green['spec']['template']['spec']['containers'][0]['envFrom']=[dict(secretRef=dict(name='foreign'))]
                before=len(state.calls)
                with self.assertRaises(Exception):adapter.mutate(request)
                self.assertFalse(any(args[2:5]==['patch','deployment',state.name] for _,args,_ in state.calls[before:]))
    def test_source_rollout_admission_preserves_owned_hooks_and_nullable_minimum(self):
        owned=dict(preStop=dict(exec=dict(command=['/bin/sh','-c','sleep 60'])))
        for role in m.base.ROLES:
            for minimum in (None,0):
                for lifecycle in (None,owned):
                    with self.subTest(role=role,minimum=minimum,lifecycle=lifecycle):
                        state,adapter,request=self.setup_state(role)
                        spec=state.deployments[state.name]['spec']
                        if minimum is not None:spec['minReadySeconds']=minimum
                        if lifecycle is not None:spec['template']['spec']['containers'][0]['lifecycle']=copy.deepcopy(lifecycle)
                        current=adapter.current('SNAPSHOT',request)
                        self.assertEqual(minimum,current['deployment']['rolloutSettings']['minReadySeconds'])
                        self.assertEqual(lifecycle,current['deployment']['rolloutSettings']['lifecycle'])
            for fault in ('strategy','postStart','extra-hook','changed-sleep','malformed','null-hook','empty-hook'):
                with self.subTest(role=role,fault=fault):
                    state,adapter,request=self.setup_state(role);owner_calls=[]
                    spec=state.deployments[state.name]['spec'];container=spec['template']['spec']['containers'][0]
                    if fault=='strategy':spec['strategy']=dict(type='Recreate')
                    elif fault=='postStart':container['lifecycle']=dict(postStart=dict(exec=dict(command=['foreign'])))
                    elif fault=='extra-hook':container['lifecycle']=dict(owned,postStart=dict(exec=dict(command=['foreign'])))
                    elif fault=='changed-sleep':container['lifecycle']=dict(preStop=dict(exec=dict(command=['/bin/sh','-c','sleep 30'])))
                    elif fault=='malformed':container['lifecycle']=['foreign']
                    elif fault=='null-hook':container['lifecycle']=None
                    else:container['lifecycle']={}
                    with self.assertRaises(Exception) as caught:
                        m.run_bound_handoff(role,state.repository,'d'*40,NEW,state,lambda step,request:owner_calls.append(step),SCRIPTS)
                    self.assertEqual('SNAPSHOT',caught.exception.step)
                    self.assertEqual([],owner_calls)
                    self.assertFalse(any(args[2] in ('create','patch','delete') for _,args,_ in state.calls))

    def test_absent_to_explicit_zero_settings_drift_stops_before_patch(self):
        for role in m.base.ROLES:
            with self.subTest(role=role):
                state,adapter,request=self.prepared_state(role)
                state.deployments[state.name]['spec']['minReadySeconds']=0
                before=len(state.calls)
                with self.assertRaises(m.base.NativeBindingRejected):adapter.mutate(request)
                self.assertFalse(any(args[2:5]==['patch','deployment',state.name] for _,args,_ in state.calls[before:]))

    def test_actual_post_patch_settings_identity_and_metadata_must_match(self):
        for role in m.base.ROLES:
            for fault in ('uid','image','replicas','metadata','minimum','grace','surge','unavailable','lifecycle'):
                with self.subTest(role=role,fault=fault):
                    state,adapter,request=self.prepared_state(role);state.fail='post-'+fault
                    with self.assertRaises((m.base.NativeBindingRejected,adapter.metadata.MetadataRejected)) as caught:adapter.mutate(request)
                    if fault!='metadata':self.assertEqual('MUTATE_CANONICAL',caught.exception.step)
                    self.assertEqual(NEW,state.created['spec']['template']['spec']['containers'][0]['image'].rsplit('@',1)[1])
                    self.assertFalse(state.deleted)
                    self.assertTrue(all(not Path(path).exists() for path in state.files))

    def test_actual_canonical_native_cas_exit_preserves_private_output(self):
        state,adapter,request=self.prepared_state();state.fail='canonical-server-cas'
        with self.assertRaises(m.base.NativeBindingRejected) as caught:adapter.mutate(request)
        self.assertEqual(29,caught.exception.exit_code)
        self.assertNotIn('PRIVATE_PROVIDER_SENTINEL',str(caught.exception))
        self.assertEqual(OLD,adapter.image('VERIFY',state.name)[1])
    def test_public_dispatch_consumes_real_native_policy_roles_replicas_and_route_proofs(self):
        for role,replicas in ((role,count) for role in m.base.ROLES for count in (1,3,10)):
            for failure in (None,'canonical-server-cas','green-process-proof','post-grace') + tuple(phase+':'+fault for phase in ('GREEN_HEALTH','BEFORE_CANONICAL_SELECTOR','CANONICAL_HEALTH','FINAL_HEALTH') for fault in ('missing','false','string','foreign','short')):
                with self.subTest(role=role,replicas=replicas,failure=failure):
                    state=KubernetesState(role,replicas);state.fail=failure
                    owner_calls=[];owner_requests=[];reservation='44444444-4444-4444-4444-444444444444';reserved=0
                    def owner(step,request):
                        nonlocal reserved
                        owner_calls.append(step);owner_requests.append((step,copy.deepcopy(request)))
                        receipt={}
                        if step=='VERIFY_SOURCE':receipt=dict(sourceCommit=request['sourceCommit'])
                        elif step=='VERIFY_IMAGE':receipt=dict(sourceCommit=request['sourceCommit'],imageDigest=request['imageDigest'],immutable=True)
                        elif step in ('RESERVE_CAPACITY','RECHECK_CAPACITY'):
                            if step=='RESERVE_CAPACITY':reserved=request['additionalSlots']
                            receipt=dict(availableSlots=replicas+1,reservedSlots=reserved,reservationId=reservation)
                        elif step in ('VERIFY_GREEN','VERIFY_CANONICAL','VERIFY_FALLBACK'):
                            # Test-only runtime observer: identities/settings come from
                            # independently stored native workload state, not request claims.
                            target=next(obj for obj in state.deployments.values() if obj['metadata']['uid']==request['deploymentUid'])
                            spec=target['spec'];pod=spec['template']['spec'];container=pod['containers'][0]
                            standby=any(v.get('name')=='MALIEV_OBSERVABILITY_STANDBY' and v.get('value')=='true' for v in container.get('env',[]))
                            receipt=dict(uid=target['metadata']['uid'],imageDigest=container['image'].rsplit('@',1)[1],replicas=spec['replicas'],ready=target['status']['readyReplicas'],available=target['status']['availableReplicas'],
                                rollout=dict(minReadySeconds=spec.get('minReadySeconds',0),drainSeconds=int(container['lifecycle']['preStop']['exec']['command'][-1].split()[-1]),terminationGracePeriodSeconds=pod['terminationGracePeriodSeconds'],maxSurge=spec['strategy']['rollingUpdate']['maxSurge'],maxUnavailable=spec['strategy']['rollingUpdate']['maxUnavailable']),
                                processVerified=not(failure=='green-process-proof' and step=='VERIFY_GREEN'),standbyVerified=standby)
                            if standby:
                                receipt['runId']=target['metadata']['labels']['maliev.com/observability-handoff']
                                adapter=m.NativeDeploymentBinding(role,state.repository,state,owner,SCRIPTS)
                                receipt['greenMetadataPlan']=adapter.actual_plan(step,target['metadata']['name'],request)
                        elif step in ('BEFORE_FIRST_SELECTOR','BEFORE_CANONICAL_SELECTOR'):
                            target=next(obj for obj in state.deployments.values() if obj['metadata']['uid']==request['deploymentUid'])
                            self.assertNotEqual(target['metadata']['name'],state.service['spec']['selector']['app.kubernetes.io/name'])
                            receipt=dict(imageDigest=target['spec']['template']['spec']['containers'][0]['image'].rsplit('@',1)[1],deploymentUid=target['metadata']['uid'],continuousPublicHealthy=True,endpointsVerified=True,observedSeconds=0,processRouteVerified=False)
                            if step=='BEFORE_CANONICAL_SELECTOR':receipt['processRouteVerified']=True
                        elif step in ('GREEN_HEALTH','CANONICAL_HEALTH','FINAL_HEALTH'):
                            selected=state.service['spec']['selector']['app.kubernetes.io/name'];target=state.deployments[selected]
                            receipt=dict(imageDigest=target['spec']['template']['spec']['containers'][0]['image'].rsplit('@',1)[1],deploymentUid=target['metadata']['uid'],publicHealthy=True,endpointsVerified=True,processRouteVerified=True,observedSeconds=180)
                        elif step=='DRAIN_PROCESS_PROOF':
                            green=next(obj for obj in state.deployments.values() if obj['metadata']['uid']==request['greenUid'])
                            receipt=dict(greenUid=green['metadata']['uid'],runId=green['metadata']['labels']['maliev.com/observability-handoff'],remainingProcesses=green['spec']['replicas'])
                        elif step=='RELEASE_CAPACITY':
                            reserved=0;receipt=dict(reservationId=reservation,released=True)
                        else:raise AssertionError('No invented application executor')
                        if failure and ':' in failure:
                            phase,fault=failure.split(':')
                            if step==phase:
                                if fault=='missing':receipt.pop('processRouteVerified',None)
                                elif fault=='false':receipt['processRouteVerified']=False
                                elif fault=='string':receipt['processRouteVerified']='true'
                                elif fault=='foreign':receipt['deploymentUid']=SERVICE
                                elif fault=='short':receipt['observedSeconds']=-1 if phase=='BEFORE_CANONICAL_SELECTOR' else 179
                        return dict(exitCode=0,receipt=receipt)
                    if failure:
                        with self.assertRaises(Exception) as caught:m.invoke_public_release(role,state.repository,'d'*40,NEW,native=state,application_tool=owner)
                        expected=failure.split(':')[0] if ':' in failure else ('MUTATE_CANONICAL' if failure in ('canonical-server-cas','post-grace') else 'VERIFY_GREEN')
                        self.assertEqual(expected,caught.exception.step)
                        if failure=='post-grace':
                            self.assertNotIn('BEFORE_CANONICAL_SELECTOR',owner_calls)
                            self.assertNotIn('RELEASE_CAPACITY',owner_calls)
                            self.assertEqual(state.created['metadata']['name'],state.service['spec']['selector']['app.kubernetes.io/name'])
                        if failure=='canonical-server-cas':self.assertEqual(29,caught.exception.exit_code)
                        self.assertEqual(failure.startswith('FINAL_HEALTH:'),state.deleted)
                    else:
                        result=m.invoke_public_release(role,state.repository,'d'*40,NEW,native=state,application_tool=owner)
                        self.assertFalse(result['runtimeAccepted']);self.assertFalse(result['consumerAdoptionAccepted'])
                        self.assertEqual(replicas,state.created['spec']['replicas'])
                        reservation_request=next(request for step,request in owner_requests if step=='RESERVE_CAPACITY')
                        self.assertEqual(replicas+1,reservation_request['additionalSlots'])
                        self.assertEqual(2*replicas+1,reservation_request['peakReplicas'])
                        self.assertTrue(state.deleted);self.assertEqual(0,reserved)
                    # These operations MUST come from real selected native producer code;
                    # the test runtime observer cannot fabricate their receipts.
                    self.assertTrue(all(step not in owner_calls for step in ('SNAPSHOT','READ_CURRENT','CREATE_GREEN','MUTATE_CANONICAL')))
                    self.assertTrue(all(not Path(path).exists() for path in state.files))

    def test_public_no_default_executor_and_missing_boundaries_refuse_before_io(self):
        with self.assertRaises(m.base.NativeBindingRejected) as caught:m.invoke_public_release()
        self.assertEqual('ACTIVATION_NOT_APPROVED',caught.exception.step)
        boundary_calls=[]
        boundary=lambda *args:boundary_calls.append(args)
        for native,observer in ((None,None),(boundary,None),(None,boundary),(True,boundary),(boundary,True)):
            with self.subTest(native_callable=callable(native),observer_callable=callable(observer)):
                state=KubernetesState('compatibility')
                with self.assertRaises(m.base.NativeBindingRejected) as caught:
                    m.invoke_public_release('compatibility',state.repository,'d'*40,NEW,native=native,application_tool=observer)
                self.assertEqual('PUBLIC_BINDING',caught.exception.step)
                self.assertEqual([],state.calls)
                self.assertEqual([],boundary_calls)

    def test_public_invalid_identity_and_arguments_refuse_before_transport(self):
        state=KubernetesState('compatibility');observer_calls=[]
        valid=dict(role='compatibility',image_repository=state.repository,source_commit='d'*40,image_digest=NEW,native=state,application_tool=lambda *args:observer_calls.append(args))
        for field,value in (('role',[]),('role','Compatibility'),('role','foreign'),('image_repository',state.repository+':latest'),
                            ('image_repository',state.repository.replace('-compatibility','-bff')),('source_commit','D'*40),
                            ('source_commit','d'*39),('image_digest','sha256:'+'C'*64),('image_digest',True)):
            with self.subTest(field=field,value=value):
                with self.assertRaises(m.base.NativeBindingRejected) as caught:m.invoke_public_release(**dict(valid,**{field:value}))
                self.assertEqual('PUBLIC_REQUEST',caught.exception.step)
        for unknown in ('approved','scripts_root','namespace'):
            with self.subTest(unknown=unknown):
                with self.assertRaises(TypeError):m.invoke_public_release(**dict(valid,**{unknown:True}))
        self.assertEqual([],state.calls);self.assertEqual([],observer_calls)

    def test_public_unhealthy_or_out_of_range_baseline_rejects_before_mutation(self):
        for role in m.base.ROLES:
            for replicas,ready in ((0,0),(11,11),(3,2)):
                with self.subTest(role=role,replicas=replicas,ready=ready):
                    state=KubernetesState(role,replicas);owner_calls=[]
                    state.deployments[state.name]['status']['readyReplicas']=ready
                    with self.assertRaises(Exception) as caught:
                        m.invoke_public_release(role,state.repository,'d'*40,NEW,native=state,application_tool=lambda step,request:owner_calls.append(step))
                    self.assertEqual('SNAPSHOT',caught.exception.step)
                    self.assertEqual([],owner_calls)
                    self.assertFalse(any(args[2] in ('create','patch','delete') for _,args,_ in state.calls))

if __name__=='__main__':unittest.main(verbosity=2)
