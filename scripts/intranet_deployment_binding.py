"""Current-role Deployment projection/create/CAS binding; no default executor."""
import copy
import hashlib
import importlib.util
import json
import re
import tempfile
from pathlib import Path

NATIVE_PIN='8c6685b02b2aceb3644d7f1f3550a6a3aa2652ee3ef4f8df7f42ab458c49103f'
native_path=Path(__file__).resolve().with_name('intranet_native_handoff.py')
if hashlib.sha256(native_path.read_bytes()).hexdigest()!=NATIVE_PIN:
    raise RuntimeError('Intranet native producer pin rejected.')
spec=importlib.util.spec_from_file_location('intranet_reviewed_native',native_path)
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
require=base.require

def metadata_module(scripts_root):
    path=Path(scripts_root).resolve()/'green_metadata.py'
    require(hashlib.sha256(path.read_bytes()).hexdigest()==base.PINS['green_metadata.py'],'PRODUCER_PIN')
    spec=importlib.util.spec_from_file_location('intranet_reviewed_metadata',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class NativeDeploymentBinding(base.NativeSelectorDrain):
    def __init__(self,role,image_repository,native,observations,scripts_root):
        super().__init__(role,native,observations)
        artifact='legacy-maliev-intranet-compatibility' if role=='compatibility' else 'legacy-maliev-intranet-bff'
        require(type(image_repository) is str and re.fullmatch(r'[a-z0-9][a-z0-9.-]*(?:/[a-z0-9][a-z0-9._-]*)+',image_repository) and image_repository.endswith('/'+artifact),'IMAGE_REPOSITORY')
        self.image_repository=image_repository
        self.baseline_snapshot=None
        self.metadata=metadata_module(scripts_root)
        self.contract=dict(source_sha='3fd301fe85cd8ca61434569eccb67a369eda47a4',target_application='Legacy.Maliev.Intranet',artifact='maliev-intranet',container=self.container,namespace=self.namespace)

    def integer(self,step,name,field,empty=None):
        value=self.field(step,'deployment',name,field)
        if not value and empty is not None:return empty
        require(re.fullmatch(r'0|[1-9][0-9]*',value) and len(value)<=10,step)
        number=int(value);require(number<=2147483647,step)
        return number

    def optional(self,step,name,field,scope,kind):
        # Presence is read independently: null and absent must not collapse.
        parent='.spec.template.spec' if scope=='pod' else '(index .spec.template.spec.containers 0)'
        query='go-template={{range $key,$value := '+parent+'}}{{if eq $key "'+field+'"}}present{{end}}{{end}}'
        present=self.command(step,['get','deployment',name,'-o',query])
        require(present in ('','present'),step)
        if not present:return False,None
        path='.spec.template.spec.'+field if scope=='pod' else '.spec.template.spec.containers[0].'+field
        raw=self.field(step,'deployment',name,path)
        if not raw:return True,None
        if kind=='string':return True,raw
        return True,self.field(step,'deployment',name,path,structured=True)

    def selected_metadata(self,step,name):
        names=self.field(step,'deployment',name,'.spec.template.spec.containers[*].name').split()
        require(names==[self.container],step)
        probes=''.join('{{with .'+probe+'}}{{if .exec}}probe{{end}}{{with .httpGet}}{{if .httpHeaders}}headers{{end}}{{end}}{{end}}' for probe in ('readinessProbe','livenessProbe','startupProbe'))
        unsafe=self.command(step,['get','deployment',name,'-o','go-template={{if .spec.template.spec.initContainers}}init{{end}}{{if .spec.template.spec.volumes}}volume{{end}}{{range .spec.template.spec.containers}}{{if .command}}command{{end}}{{if .args}}args{{end}}{{if .volumeMounts}}mount{{end}}'+probes+'{{end}}'])
        require(not unsafe,step)
        shape=self.command(step,['get','deployment',name,'-o','go-template={{range .spec.template.spec.containers}}{{range .env}}{{.name}}{{"|"}}{{if .valueFrom}}reference{{else}}literal{{end}}{{"\n"}}{{end}}{{end}}'])
        environment=[];lines=shape.splitlines();seen=set()
        require(len(lines)<=128,step)
        for line in lines:
            parts=line.split('|')
            require(len(parts)==2 and re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,127}',parts[0]) and parts[0] not in seen,step)
            key,source=parts
            seen.add(key)
            path='.spec.template.spec.containers[0].env[?(@.name=="'+key+'")].'
            if source=='reference':
                environment.append(dict(name=key,valueFrom=self.field(step,'deployment',name,path+'valueFrom',structured=True)))
            else:
                require(source=='literal' and key in self.metadata.FLAGS,step)
                # Never read the value of an unknown literal environment variable.
                environment.append(dict(name=key,value=self.field(step,'deployment',name,path+'value')))
        container={};pod={}
        for field in sorted(self.metadata.CONTAINER_FIELDS):
            present,value=self.optional(step,name,field,'container','string' if field=='imagePullPolicy' else 'json')
            if present:container[field]=value
        for field in sorted(self.metadata.POD_FIELDS):
            present,value=self.optional(step,name,field,'pod','string' if field in ('serviceAccountName','dnsPolicy','restartPolicy','schedulerName') else 'json')
            if present:pod[field]=value
        return self.metadata.decode_green_metadata(dict(containerNames=names,unsafeFields=[],environment=environment,containerMetadata=container,podMetadata=pod))

    def image(self,step,name):
        image=self.field(step,'deployment',name,'.spec.template.spec.containers[0].image')
        require(re.fullmatch(re.escape(self.image_repository)+r'@sha256:[0-9a-f]{64}',image),step)
        return image,image.rsplit('@',1)[1]

    def read_deployment(self,step,name):
        uid=self.field(step,'deployment',name,'.metadata.uid')
        rv=self.field(step,'deployment',name,'.metadata.resourceVersion')
        require(base.UID.fullmatch(uid) and re.fullmatch('[1-9][0-9]*',rv),step)
        image,digest=self.image(step,name)
        metadata=self.selected_metadata(step,name)
        _,lifecycle=self.optional(step,name,'lifecycle','container','json')
        rollout=dict(strategy=self.field(step,'deployment',name,'.spec.strategy',structured=True),
                     minReadySeconds=self.integer(step,name,'.spec.minReadySeconds',0),
                     terminationGracePeriodSeconds=self.integer(step,name,'.spec.template.spec.terminationGracePeriodSeconds'),
                     lifecycle=lifecycle)
        return dict(uid=uid,resourceVersion=rv,image=image,imageDigest=digest,
                    replicas=self.integer(step,name,'.spec.replicas'),
                    ready=self.integer(step,name,'.status.readyReplicas',0),available=self.integer(step,name,'.status.availableReplicas',0),
                    settingsSignature=base.canonical(rollout),greenMetadata=json.dumps(metadata,ensure_ascii=False),rolloutSettings=rollout)

    def current(self,step,request):
        deployment=self.read_deployment(step,self.deployment)
        service=self.service(step)
        original={'app.kubernetes.io/name':self.deployment}
        green={'app.kubernetes.io/name':self.green_name(request),'maliev.com/observability-handoff':request['runId']}
        if service['selector']==original:
            selector='original';selected_uid=deployment['uid']
        else:
            require(service['selector']==green,step)
            selected_uid=self.field(step,'deployment',self.green_name(request),'.metadata.uid')
            self.owned_green(step,request,selected_uid);selector='green'
        receipt=dict(uid=service['uid'],resourceVersion=service['resourceVersion'],selector=selector,selectorUid=selected_uid,portsSignature=service['portsSignature'])
        if step=='SNAPSHOT':self.baseline_snapshot=copy.deepcopy(deployment)
        return dict(deployment=deployment,service=receipt)

    def document_command(self,step,verb,document):
        with tempfile.TemporaryDirectory(prefix='owned-intranet-manifest-') as directory:
            path=Path(directory)/'manifest.json'
            path.write_text(base.canonical(document),encoding='utf-8')
            return self.command(step,[verb,'-f',str(path)])

    def actual_plan(self,step,name,request):
        selected=self.selected_metadata(step,name)
        _,digest=self.image(step,name)
        container={key:copy.deepcopy(value) for key,value in selected['containerMetadata'].items() if value is not None}
        # Read ACTUAL standby/environment/lifecycle; do not run the planner to
        # overwrite a bad readback with the desired settings.
        container.update(name=self.container,imageDigest=digest,env=selected['environment'],
                         lifecycle=self.field(step,'deployment',name,'.spec.template.spec.containers[0].lifecycle',structured=True))
        pod={key:copy.deepcopy(value) for key,value in selected['podMetadata'].items() if value is not None}
        pod.update(containers=[container],terminationGracePeriodSeconds=self.integer(step,name,'.spec.template.spec.terminationGracePeriodSeconds'))
        return self.metadata.bounded(dict(namespace=self.namespace,pod=pod))

    def create(self,request):
        step='CREATE_GREEN';name=self.green_name(request)
        plan=request.get('greenMetadataPlan');require(type(plan) is dict and plan.get('namespace')==self.namespace,step)
        plan=self.metadata.bounded(plan)
        pod=copy.deepcopy(plan['pod']);containers=pod.get('containers')
        require(type(containers) is list and len(containers)==1 and containers[0].get('name')==self.container and containers[0].get('imageDigest')==request['imageDigest'],step)
        digest=containers[0].pop('imageDigest');require(re.fullmatch('sha256:[a-f0-9]{64}',digest),step)
        containers[0]['image']=self.image_repository+'@'+digest
        labels={'app.kubernetes.io/name':name,'maliev.com/observability-handoff':request['runId']}
        require(type(request['replicas']) is int and 1<=request['replicas']<=10 and request['standby'] is True,step)
        document=dict(apiVersion='apps/v1',kind='Deployment',metadata=dict(name=name,namespace=self.namespace,labels=labels),
            spec=dict(replicas=request['replicas'],minReadySeconds=90,selector=dict(matchLabels=labels),
            strategy=dict(type='RollingUpdate',rollingUpdate=dict(maxSurge=1,maxUnavailable=0)),template=dict(metadata=dict(labels=labels),spec=pod)))
        self.document_command(step,'create',document)
        uid=self.field(step,'deployment',name,'.metadata.uid');self.owned_green(step,request,uid)
        require(self.integer(step,name,'.spec.replicas')==request['replicas'],step)
        observed=self.actual_plan(step,name,request)
        self.metadata.verify_green_metadata(plan,observed)
        return dict(uid=uid,runId=request['runId'],imageDigest=digest,greenMetadataPlan=observed)

    def mutate(self,request):
        step='MUTATE_CANONICAL'
        # Both native identities and selected metadata are re-read at the actual
        # mutation boundary; a source-only receipt cannot replace this readback.
        observed=self.current(step,request);current=observed['deployment'];service=observed['service']
        require(self.baseline_snapshot is not None and current['settingsSignature']==self.baseline_snapshot['settingsSignature'],step)
        require(current['uid']==request['deploymentUid'] and current['imageDigest']==request['expectedImage'] and
                current['replicas']==request['expectedCanonicalReplicas'] and current['ready']==current['replicas'] and current['available']==current['replicas'],step)
        require(service==request['service'] and service['selector']=='green' and service['selectorUid']==request['greenDeploymentUid'],step)
        self.metadata.verify_green_metadata(request['expectedCanonicalMetadata'],self.metadata.decode_green_metadata(current['greenMetadata']))
        green=self.green_name(request);self.owned_green(step,request,request['greenDeploymentUid'])
        require(self.integer(step,green,'.spec.replicas')==request['expectedGreenReplicas'] and
                self.integer(step,green,'.status.readyReplicas',0)==request['expectedGreenReplicas'] and
                self.integer(step,green,'.status.availableReplicas',0)==request['expectedGreenReplicas'],step)
        self.metadata.verify_green_metadata(request['expectedGreenMetadataPlan'],self.actual_plan(step,green,request))
        require(request['rollout']==dict(minReadySeconds=90,drainSeconds=60,terminationGracePeriodSeconds=90,maxSurge=1,maxUnavailable=0),step)
        patch=[dict(op='test',path='/metadata/uid',value=current['uid']),dict(op='test',path='/metadata/resourceVersion',value=current['resourceVersion']),
               dict(op='test',path='/spec/replicas',value=current['replicas']),
               dict(op='test',path='/spec/template/spec/containers/0/name',value=self.container),
               dict(op='test',path='/spec/template/spec/containers/0/image',value=current['image']),
               dict(op='add',path='/spec/minReadySeconds',value=90),
               dict(op='add',path='/spec/strategy',value=dict(type='RollingUpdate',rollingUpdate=dict(maxSurge=1,maxUnavailable=0))),
               dict(op='add',path='/spec/template/spec/terminationGracePeriodSeconds',value=90),
               dict(op='add',path='/spec/template/spec/containers/0/lifecycle',value=dict(preStop=dict(exec=dict(command=['/bin/sh','-c','sleep 60'])))),
               dict(op='replace',path='/spec/template/spec/containers/0/image',value=self.image_repository+'@'+request['imageDigest'])]
        self.command(step,['patch','deployment',self.deployment,'--type=json','-p',base.canonical(patch)])
        after_uid=self.field(step,'deployment',self.deployment,'.metadata.uid')
        _,after_digest=self.image(step,self.deployment)
        require(after_uid==current['uid'] and after_digest==request['imageDigest'],step)
        return dict(uid=after_uid,imageDigest=after_digest)


def run_bound_handoff(role,image_repository,source_commit,image_digest,native,application_tool,scripts_root):
    policy=base.load_policy(scripts_root)
    adapter=NativeDeploymentBinding(role,image_repository,native,application_tool,scripts_root)
    def tool(step,request):
        try:
            if step in ('SNAPSHOT','READ_CURRENT'):receipt=adapter.current(step,request)
            elif step=='CREATE_GREEN':receipt=adapter.create(request)
            elif step=='MUTATE_CANONICAL':receipt=adapter.mutate(request)
            elif step in base.ROUTES:receipt=adapter.route(step,request)
            elif step=='DRAIN_GREEN':receipt=adapter.drain(request)
            else:return application_tool(step,request)
            return dict(exitCode=0,receipt=receipt)
        except base.NativeBindingRejected as error:
            return dict(exitCode=error.exit_code,receipt={})
    return policy.run_handoff('Legacy.Maliev.Intranet',source_commit,image_digest,tool,green_contract=adapter.contract)


def invoke_public_release(*args,**kwargs):
    raise base.NativeBindingRejected('ACTIVATION_NOT_APPROVED')
