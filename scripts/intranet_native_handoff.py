"""Current Intranet native selector/drain binding for the accepted handoff policy.

No CLI or default executor. Native is the owned stdout-only command interface;
proof/source/image/capacity operations remain explicitly caller-owned interfaces.
"""
import hashlib
import importlib.util
import json
import re
import tempfile
from pathlib import Path

PINS = {
    'application_handoff_policy.py': '03b80a61ffc19b9eb3286783934902ed413157edccedfd8ab46ebce2f153e5e2',
    'green_metadata.py': '137f2fa0c9e03dee1229ecc1652dd28f2f526a207e99ce7bbc964ef4dab1f77d',
}
ROLES = {
    'compatibility': ('legacy-maliev-intranet', 'intranet'),
    'bff': ('legacy-maliev-intranet-bff', 'intranet-bff'),
}
ROUTES = frozenset({'ROUTE_GREEN', 'ROUTE_CANONICAL', 'ROLLBACK_SELECTOR', 'FALLBACK_SELECTOR'})
UID = re.compile(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}')


class NativeBindingRejected(RuntimeError):
    def __init__(self, step, exit_code=1):
        super().__init__('Intranet native binding rejected at ' + step)
        self.step, self.exit_code = step, exit_code


def require(value, step):
    if not value:
        raise NativeBindingRejected(step)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def load_policy(scripts_root):
    root = Path(scripts_root).resolve()
    for name, digest in PINS.items():
        require(hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, 'PRODUCER_PIN')
    spec = importlib.util.spec_from_file_location('intranet_pinned_handoff', root / 'application_handoff_policy.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NativeSelectorDrain:
    """Real command/readback adapter, without copying the policy's phase logic."""
    def __init__(self, role, native, observations):
        require(role in ROLES and callable(native) and callable(observations), 'BINDING')
        self.deployment, self.container = ROLES[role]
        self.native, self.observations = native, observations
        self.namespace = 'maliev-legacy'

    def command(self, step, arguments):
        failed = False
        try:
            result = self.native('kubectl', ['-n', self.namespace] + arguments, step)
        except Exception:
            failed = True
        if failed:
            raise NativeBindingRejected(step)
        require(type(result) is dict and set(result) == {'exitCode', 'stdout'}, step)
        code = result['exitCode']
        require(type(code) is int and 0 <= code <= 2147483647, step)
        if code:
            raise NativeBindingRejected(step, code)
        value = result['stdout']
        require(type(value) is str and len(value.encode('utf-8')) <= 16384, step)
        return value

    def field(self, step, kind, name, field, *, structured=False):
        require(kind in ('service', 'deployment') and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,62}', name), step)
        value = self.command(step, ['get', kind, name, '-o', 'jsonpath={' + field + '}'])
        if not structured:
            return value
        failed = False
        try:
            def unique(pairs):
                output = {}
                for key, child in pairs:
                    if key in output:
                        raise ValueError()
                    output[key] = child
                return output
            value = json.loads(value, object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except Exception:
            failed = True
        if failed:
            raise NativeBindingRejected(step)
        return value

    def service(self, step):
        uid = self.field(step, 'service', self.deployment, '.metadata.uid')
        rv = self.field(step, 'service', self.deployment, '.metadata.resourceVersion')
        selector = self.field(step, 'service', self.deployment, '.spec.selector', structured=True)
        ports = self.field(step, 'service', self.deployment, '.spec.ports', structured=True)
        kind = self.field(step, 'service', self.deployment, '.spec.type')
        require(UID.fullmatch(uid) and re.fullmatch('[1-9][0-9]*', rv), step)
        require(type(selector) is dict and set(selector) in ({'app.kubernetes.io/name'}, {'app.kubernetes.io/name', 'maliev.com/observability-handoff'}), step)
        require(type(ports) is list and len(ports) == 1 and kind == 'ClusterIP', step)
        require(ports[0].get('port') == 80 and ports[0].get('targetPort') == 'http' and ports[0].get('protocol') == 'TCP', step)
        return dict(uid=uid, resourceVersion=rv, selector=selector, ports=ports, portsSignature=canonical(ports))

    def green_name(self, request):
        run = request.get('runId')
        require(type(run) is str and re.fullmatch('[0-9a-f]{32}', run), 'GREEN_IDENTITY')
        return self.deployment + '-bg-' + run[:8]

    def owned_green(self, step, request, expected_uid):
        name = self.green_name(request)
        uid = self.field(step, 'deployment', name, '.metadata.uid')
        rv = self.field(step, 'deployment', name, '.metadata.resourceVersion')
        run = self.field(step, 'deployment', name, '.metadata.labels.maliev\\.com/observability-handoff')
        require(uid == expected_uid and UID.fullmatch(uid) and run == request['runId'] and re.fullmatch('[1-9][0-9]*', rv), step)
        return name, rv

    def observation(self, step, request):
        failed = False
        try:
            response = self.observations(step, request)
        except Exception:
            failed = True
        if failed:
            raise NativeBindingRejected(step)
        require(type(response) is dict and set(response) == {'exitCode', 'receipt'}, step)
        code = response['exitCode']
        require(type(code) is int and 0 <= code <= 2147483647, step)
        if code:
            raise NativeBindingRejected(step, code)
        receipt = response['receipt']
        require(type(receipt) is dict and set(receipt) == {'greenUid', 'runId', 'remainingProcesses'}, step)
        # This exact flat receipt is bounded before any serialization or parser use.
        require(type(receipt['greenUid']) is str and UID.fullmatch(receipt['greenUid']) and
                type(receipt['runId']) is str and re.fullmatch('[0-9a-f]{32}', receipt['runId']) and
                type(receipt['remainingProcesses']) is int and 0 <= receipt['remainingProcesses'] <= 2147483647, step)
        return dict(receipt)

    def route(self, step, request):
        current = self.service(step)
        expected = request['service']
        require(current['uid'] == expected['uid'] and current['resourceVersion'] == expected['resourceVersion'] and current['portsSignature'] == expected['portsSignature'], step)
        if expected['selector'] == 'original':
            expected_selector = {'app.kubernetes.io/name': self.deployment}
        else:
            expected_selector = {'app.kubernetes.io/name': self.green_name(request), 'maliev.com/observability-handoff': request['runId']}
        require(current['selector'] == expected_selector, step)
        # Fence the backend selected by the actual Service BEFORE changing traffic.
        # A recreated original/green Deployment can retain the same selector labels.
        selected_uid = expected.get('selectorUid')
        require(type(selected_uid) is str and UID.fullmatch(selected_uid), step)
        if expected['selector'] == 'green':
            self.owned_green(step, request, selected_uid)
        else:
            require(self.field(step, 'deployment', self.deployment, '.metadata.uid') == selected_uid, step)
        target = request['targetDeploymentUid']
        name = self.green_name(request) if request['selector'] == 'green' else self.deployment
        if request['selector'] == 'green':
            self.owned_green(step, request, target)
            selected = {'app.kubernetes.io/name': name, 'maliev.com/observability-handoff': request['runId']}
        else:
            require(self.field(step, 'deployment', name, '.metadata.uid') == target, step)
            selected = {'app.kubernetes.io/name': name}
        patch = [dict(op='test', path='/metadata/uid', value=current['uid']),
                 dict(op='test', path='/metadata/resourceVersion', value=current['resourceVersion']),
                 dict(op='test', path='/spec/ports', value=current['ports']),
                 dict(op='test', path='/spec/selector', value=current['selector']),
                 dict(op='replace', path='/spec/selector', value=selected)]
        self.command(step, ['patch', 'service', self.deployment, '--type=json', '-p', canonical(patch)])
        after = self.service(step)
        require(after['uid'] == current['uid'] and after['ports'] == current['ports'] and after['selector'] == selected, step)
        require((len(after['resourceVersion']), after['resourceVersion']) > (len(current['resourceVersion']), current['resourceVersion']), step)
        require(self.field(step, 'deployment', name, '.metadata.uid') == target, step)
        return dict(uid=after['uid'], resourceVersion=after['resourceVersion'], selector=request['selector'], selectorUid=target, portsSignature=after['portsSignature'])

    def drain(self, request):
        step = 'DRAIN_GREEN'
        name, rv = self.owned_green(step, request, request['greenUid'])
        replicas = self.field(step, 'deployment', name, '.spec.replicas')
        require(re.fullmatch('[1-9][0-9]*', replicas), step)
        patch = [dict(op='test', path='/metadata/uid', value=request['greenUid']),
                 dict(op='test', path='/metadata/resourceVersion', value=rv),
                 dict(op='test', path='/spec/replicas', value=int(replicas)),
                 dict(op='replace', path='/spec/replicas', value=0)]
        self.command(step, ['patch', 'deployment', name, '--type=json', '-p', canonical(patch)])
        # The existing process observer must prove settled processes; an empty-looking
        # Deployment or successful scale patch is not a drain receipt.
        proof = self.observation('DRAIN_PROCESS_PROOF', dict(request, deployment=name))
        require(type(proof) is dict and proof.get('greenUid') == request['greenUid'] and proof.get('runId') == request['runId'] and type(proof.get('remainingProcesses')) is int and proof['remainingProcesses'] == 0, step)
        name, rv = self.owned_green(step, request, request['greenUid'])
        require(self.field(step, 'deployment', name, '.spec.replicas') == '0', step)
        pods = self.command(step, ['get', 'pods', '-l', 'app.kubernetes.io/name=' + name + ',maliev.com/observability-handoff=' + request['runId'], '-o', 'jsonpath={.items[*].metadata.uid}'])
        require(not pods.strip(), step)
        options = dict(apiVersion='v1', kind='DeleteOptions', propagationPolicy='Foreground', preconditions=dict(uid=request['greenUid'], resourceVersion=rv))
        with tempfile.TemporaryDirectory(prefix='owned-intranet-delete-') as temporary:
            path = Path(temporary) / 'delete-options.json'
            path.write_text(canonical(options), encoding='utf-8')
            self.command(step, ['delete', '--raw', '/apis/apps/v1/namespaces/' + self.namespace + '/deployments/' + name, '-f', str(path)])
        absent = self.command(step, ['get', 'deployment', name, '--ignore-not-found', '-o', 'jsonpath={.metadata.uid}'])
        require(not absent, step)
        return dict(greenUid=request['greenUid'], remainingProcesses=0, ownedDeleted=True)


def run_current_handoff(role, source_commit, image_digest, native, application_tool, scripts_root):
    """Consume the existing accepted policy; never duplicate its fallback algorithm.

    application_tool owns source/image/capacity/proof, selected deployment metadata,
    green creation and canonical mutation. Those interfaces are not synthesized here.
    """
    policy = load_policy(scripts_root)
    adapter = NativeSelectorDrain(role, native, application_tool)
    def tool(step, request):
        try:
            if step in ROUTES:
                return dict(exitCode=0, receipt=adapter.route(step, request))
            if step == 'DRAIN_GREEN':
                return dict(exitCode=0, receipt=adapter.drain(request))
        except NativeBindingRejected as failure:
            return dict(exitCode=failure.exit_code, receipt={})
        return application_tool(step, request)
    contract = dict(source_sha='3fd301fe85cd8ca61434569eccb67a369eda47a4', target_application='Legacy.Maliev.Intranet',
                    artifact='maliev-intranet', container=ROLES[role][1], namespace='maliev-legacy')
    return policy.run_handoff('Legacy.Maliev.Intranet', source_commit, image_digest, tool, green_contract=contract)


def invoke_public_release(*args, **kwargs):
    raise NativeBindingRejected('ACTIVATION_NOT_APPROVED')
