"""Protected-main sealed Windows build-first qualification; historical build/test evidence is never replayed."""
import base64
from datetime import datetime, timezone
import hashlib
import importlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import time
import urllib.request
import zipfile

MAX_KIT = 64 * 1024 * 1024
MAX_RESPONSE = 128 * 1024 * 1024
REPOSITORY = 'MALIEV-Co-Ltd/Legacy.Maliev.Workflows'
ROOT = '019fc21e-50f0-7112-834f-9fb3b35b9dfe'
OWNER = '01a1009c-83f6-7010-9a59-df89ecbb1b1f'

def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError('Duplicate JSON key')
        result[key] = value
    return result

def digest(raw): return hashlib.sha256(raw).hexdigest()

def validate_context(context, head):
    expected = {'repository': REPOSITORY, 'ref': 'refs/heads/main', 'eventName': 'workflow_dispatch', 'sha': head}
    job = context.get('job') if type(context) is dict else None
    identity = {k:v for k,v in context.items() if k != 'job'} if type(context) is dict else {}
    if identity != expected or type(job) is not dict or job.get('workflow_repository') != REPOSITORY or job.get('workflow_sha') != head or not re.fullmatch('[0-9a-f]{40}', head):
        raise ValueError('Trusted protected-main workflow identity required')

def validate_permit(raw, policy, now=None):
    if type(raw) is not bytes or not 0 < len(raw) <= 4096: raise ValueError('Permit bound')
    permit = json.loads(raw, object_pairs_hook=unique)
    required = {'issuedBy','owner','phase','leaseId','issuedUtc','expiresUtc','worktree','baseSha','candidateSha'}
    if set(permit) != required or any(type(v) is not str for v in permit.values()): raise ValueError('Permit shape')
    fixed = {'issuedBy':ROOT,'owner':OWNER,'phase':'hosted-qualification','worktree':policy['worktree'],'baseSha':policy['baseSha'],'candidateSha':policy['candidateSha']}
    if any(permit[k] != v for k,v in fixed.items()): raise ValueError('Permit association')
    import uuid
    if str(uuid.UUID(permit['leaseId'])) != permit['leaseId']: raise ValueError('Lease identity')
    issued=datetime.fromisoformat(permit['issuedUtc']); expiry=datetime.fromisoformat(permit['expiresUtc'])
    now=now or datetime.now(timezone.utc)
    if issued.utcoffset() is None or expiry.utcoffset() is None or not issued <= now < expiry or not 0 < (expiry-issued).total_seconds() <= 900:
        raise ValueError('Finite current permit required')
    return permit

def decode_blob(raw, policy):
    if len(raw) > MAX_RESPONSE: raise ValueError('Response quota')
    item=json.loads(raw,object_pairs_hook=unique)
    if item.get('sha') != policy['kitGitBlob'] or item.get('encoding') != 'base64' or type(item.get('size')) is not int:
        raise ValueError('Immutable blob identity')
    data=base64.b64decode(item['content'].replace('\n',''),validate=True)
    if item['size'] != len(data) or len(data) != policy['kitBytes'] or len(data)>MAX_KIT or digest(data)!=policy['kitSha256']:
        raise ValueError('Immutable blob size/hash')
    if hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()!=policy['kitGitBlob']:
        raise ValueError('Git object identity')
    return data

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args): raise ValueError('Redirect refused')

def fetch(policy):
    headers={'Accept':'application/vnd.github+json','User-Agent':'reviewed-workflows-static-transport'}
    token=os.environ.get('GH_TOKEN')
    if token: headers['Authorization']='Bearer '+token
    request=urllib.request.Request('https://api.github.com/repos/'+REPOSITORY+'/git/blobs/'+policy['kitGitBlob'],headers=headers)
    with urllib.request.build_opener(NoRedirect()).open(request,timeout=30) as response:
        deadline=time.monotonic()+30; blocks=[]; size=0
        while True:
            if time.monotonic()>=deadline: raise TimeoutError('Finite blob deadline')
            block=response.read1(min(65536,MAX_RESPONSE-size+1))
            if not block: break
            blocks.append(block); size+=len(block)
            if size>MAX_RESPONSE: raise ValueError('Response quota')
        raw=b''.join(blocks)
    return decode_blob(raw,policy)

def verified_entries(data, policy):
    result={}; expected=policy['entries']
    if sum(row['bytes'] for row in expected.values())>64*1024*1024: raise ValueError('Total materialization quota')
    with io.BytesIO(data) as memory, zipfile.ZipFile(memory) as archive:
        names=archive.namelist()
        if len(names)!=len(set(names)) or set(names)!=set(expected): raise ValueError('Exact sealed inventory')
        for entry in archive.infolist():
            name=entry.filename
            if '\\' in name or ':' in name or any(x in ('','.','..') for x in name.split('/')) or PurePosixPath(name).as_posix()!=name or name.split('/')[0] not in ('outputs','worktree'):
                raise ValueError('Noncanonical member')
            if entry.is_dir() or ((entry.external_attr>>16)&0o170000)==0o120000: raise ValueError('Nonfile member')
            row=expected[name]
            if type(row['bytes']) is not int or not 0<row['bytes']<=16*1024*1024 or entry.file_size!=row['bytes']: raise ValueError('Member quota')
            raw=archive.read(entry)
            if len(raw)!=row['bytes'] or digest(raw)!=row['sha256']: raise ValueError('Member postimage')
            result[name]=raw
    return result

def safe_write(root,relative,raw):
    root=Path(root); target=root/relative
    if not target.resolve().is_relative_to(root.resolve()): raise ValueError('Target escape')
    current=target
    while current!=root.parent:
        if current.is_symlink(): raise ValueError('Symlink destination')
        current=current.parent
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(raw)

def preparation_command(run_owned, ledger, arguments, **kwargs):
    def event(name,row): ledger.append(dict(row))
    try:
        result,row=run_owned(arguments,on_event=event,**kwargs)
    except BaseException as error:
        row=getattr(error,'resource_row',None)
        if isinstance(row,dict): ledger.append(dict(row))
        raise
    ledger.append(dict(row))
    flags=('terminal_state_verified','job_caps_readback_verified','cleanup_verified','process_handle_closed','thread_handle_closed','job_handle_closed','pipe_handles_closed','readers_settled','attribute_list_disposed')
    if result.returncode or type(row.get('remaining_job_processes')) is not int or row['remaining_job_processes']!=0 or any(row.get(flag) is not True for flag in flags):
        raise RuntimeError('Owned preparation failed or cleanup not verified')
    return result.stdout

def preserve_first_failure(primary, cleanup, receipt):
    state=None;errors=[]
    try: state=cleanup()
    except BaseException as error:
        errors.append(type(error).__name__)
        if primary is None: primary=error
    try: receipt(state,errors)
    except BaseException as error:
        if primary is None: primary=error
        else: primary.add_note('Secondary receipt failure: '+type(error).__name__)
    if primary is not None: raise primary


SDK_ROOT = 'D:/codex-temp/2026-10-09/workflows-hosted-sdk-10.0.401'
SDK_RELATIVE = ('dotnet.exe','sdk/10.0.401/dotnet.dll','sdk/10.0.401/.version','sdk/10.0.401/NuGet.ProjectModel.dll','sdk/10.0.401/NuGet.Packaging.dll')
SDK_LENGTHS = (167208,3520296,101,628520,1718056)
SDK_FILE_QUOTA = 16 * 1024 * 1024

def read_sdk_file(path):
    path=Path(path)
    if path.is_symlink(): return {'outcome':'symlink','bytes':None,'sha256':None}
    try:
        with path.open('rb') as stream: raw=stream.read(SDK_FILE_QUOTA+1)
    except FileNotFoundError: return {'outcome':'missing','bytes':None,'sha256':None}
    except OSError: return {'outcome':'unreadable','bytes':None,'sha256':None}
    if len(raw)>SDK_FILE_QUOTA: return {'outcome':'oversized','bytes':len(raw),'sha256':None}
    return {'outcome':'read','bytes':len(raw),'sha256':digest(raw)}

def sdk_identity(expected, reader=read_sdk_file, *, shared_image=False):
    fixed=tuple(SDK_ROOT+'/'+name for name in SDK_RELATIVE)
    keys=tuple(str(path).replace('\\','/') for path in expected)
    if keys!=fixed or any(type(pin) is not str or not re.fullmatch('[0-9a-f]{64}',pin) for pin in expected.values()):
        raise ValueError('Exact five fixed SDK identities required')
    rows=[]
    for index,(key,pin) in enumerate(expected.items()):
        path='C:/Program Files/dotnet/'+SDK_RELATIVE[index] if shared_image else key
        actual=reader(path)
        if actual['outcome']=='read':
            outcome='matched' if actual['sha256']==pin and actual['bytes']==SDK_LENGTHS[index] else 'hash-mismatch' if actual['sha256']!=pin else 'length-mismatch'
        else: outcome=actual['outcome']
        rows.append({'index':index,'expectedSha256':pin,'expectedBytes':SDK_LENGTHS[index],'observedSha256':actual['sha256'],'observedBytes':actual['bytes'],'outcome':outcome})
    return {'schemaVersion':1,'source':'shared-image' if shared_image else 'isolated-task-sdk','files':rows,'allFiveMatch':all(row['outcome']=='matched' for row in rows),'observedHashesAreAuthority':False}

def bootstrap_source_identity(raw, expected_sha256, expected_bytes):
    return {'schemaVersion':1,'expectedSha256':expected_sha256,'expectedBytes':expected_bytes,
            'observedSha256':digest(raw),'observedBytes':len(raw),
            'lfCount':raw.count(b'\n'),'crlfCount':raw.count(b'\r\n'),
            'exactReviewedBytes':len(raw)==expected_bytes and digest(raw)==expected_sha256,
            'observedHashesAreAuthority':False}

def validate_sdk_cleanup(root,owner,validated_permit):
    root=Path(root)
    if root.resolve()!=root.absolute() or root.resolve()!=Path(SDK_ROOT) or root.is_symlink() or owner!={'owner':OWNER,'leaseId':validated_permit['leaseId'],'expiresUtc':validated_permit['expiresUtc'],'persistentData':False}:
        raise ValueError('Exact task-owned SDK cleanup identity required')

def main():
    if sys.platform!='win32': raise ValueError('Qualified Windows provider required')
    trusted=Path(__file__).resolve().parent
    policy=json.loads((trusted/'hosted-static-policy.json').read_bytes(),object_pairs_hook=unique)
    permit_raw=os.environ['ROOT_STATIC_PERMIT'].encode('utf-8')
    validated_permit=validate_permit(permit_raw,policy)
    context=json.loads(os.environ['TRUSTED_WORKFLOW_CONTEXT'],object_pairs_hook=unique)
    # The checkout action supplies the trusted control tree. Verify its actual
    # HEAD with the qualified provider after verifying that provider's bytes.
    entries=verified_entries(fetch(policy),policy)
    outputs=Path(policy['outputsRoot']); worktree=Path(policy['worktree'])
    if outputs.exists() or worktree.exists(): raise ValueError('Fresh hosted roots required')
    for name,raw in entries.items():
        if name.startswith('outputs/'): safe_write(outputs,name[len('outputs/'):],raw)
    provider=outputs/'workflows_owned_command_auth_job_accounting_v2.py'
    if digest(provider.read_bytes())!=policy['qualifiedProviderSha256']: raise ValueError('Qualified provider pin')
    sys.path.insert(0,str(outputs))
    owned=importlib.import_module('workflows_owned_command_auth_job_accounting_v2')
    admission=importlib.import_module('workflows_native_admission_v3')
    supervisor=importlib.import_module('workflows_cleanup_supervisor_v1')
    ledger=[]; failure=None
    def command(name,args,cwd,timeout=30):
        return preparation_command(owned.run_owned,ledger,args,cwd=cwd,timeout=timeout,memory_limit=256*1024**2,output_limit=4*1024**2,log_path=outputs/(name+'.log'))
    try:
        head=command('trusted-head',['git','rev-parse','HEAD'],trusted.parent).decode().strip()
        validate_context(context,head)
        preflight=admission.preflight()
        if preflight['freeMiB']<policy['initialMemoryFloorMiB'] or admission.SLOT.exists(): raise RuntimeError('Additional initial headroom required')
        command('candidate-checkout',['git','-c','core.autocrlf=true','worktree','add','--detach',str(worktree),policy['baseSha']],trusted.parent)
        for name,raw in entries.items():
            if name.startswith('worktree/'): safe_write(worktree,name[len('worktree/'):],raw)
        del entries  # Release sealed archive buffers before any native phase.
        permit_path=outputs/'root-hosted-static-permit.json';permit_path.write_bytes(permit_raw)
        core=outputs/'hosted_static_core.py'
        if digest(core.read_bytes())!=policy['coreSha256']: raise ValueError('Reviewed native core pin')
        module=importlib.import_module('hosted_static_core')
        identity={'sharedImage':sdk_identity(module.SDK_FILES,shared_image=True)}
        (outputs/'sdk-identity.json').write_text(json.dumps(identity,indent=2))
        remaining=(datetime.fromisoformat(validate_permit(permit_raw,policy)['expiresUtc'])-datetime.now(timezone.utc)).total_seconds()-25
        if remaining<=0: raise RuntimeError('Insufficient current bootstrap lease')
        bootstrap=trusted/'hosted-sdk-bootstrap.py'
        # Retain the fixed public control file's physical checkout bytes before
        # checking identity. This observation never changes the reviewed pin.
        with bootstrap.open('rb') as stream: bootstrap_raw=stream.read(64*1024+1)
        source_identity=bootstrap_source_identity(bootstrap_raw,policy['sdkBootstrapSha256'],6249)
        source_identity['captureComplete']=len(bootstrap_raw)<=64*1024
        (outputs/'sdk-bootstrap-source.json').write_text(json.dumps(source_identity,indent=2))
        (outputs/'sdk-bootstrap-source.bin').write_bytes(bootstrap_raw)
        print(json.dumps({'sdkBootstrapSource':source_identity}),flush=True)
        if not source_identity['captureComplete'] or not source_identity['exactReviewedBytes']: raise ValueError('Reviewed SDK bootstrap pin')
        command('sdk-bootstrap',[sys.executable,'-B',str(bootstrap)],trusted.parent,timeout=min(300,remaining))
        identity['isolated']=sdk_identity(module.SDK_FILES)
        (outputs/'sdk-identity.json').write_text(json.dumps(identity,indent=2))
        module.candidate_check()
        sys.argv=[str(core),'hosted-qualification',str(permit_path)]
        module.main()
    except BaseException as error:
        failure=error
    finally:
        def checkpoint(kind,state):
            (outputs/'wrapper-cleanup.json').write_text(json.dumps({'kind':kind,'state':state},indent=2))
        def recover(lease): ledger.append(owned.recover_quarantined(lease))
        def cleanup():
            while True:
                try:
                    state=supervisor.supervise(owned._quarantined,recover,None,None,checkpoint)
                    sdk=Path(SDK_ROOT)
                    if sdk.exists():
                        owner=json.loads((sdk/'.codex-sdk-owner.json').read_bytes(),object_pairs_hook=unique)
                        # Cleanup uses the identity admitted at startup; it does
                        # not renew a permit or authorize another command.
                        validate_sdk_cleanup(sdk,owner,validated_permit)
                        shutil.rmtree(sdk)
                    state['sdkRootRemoved']=not sdk.exists()
                    return state
                except BaseException:
                    if owned._quarantined: continue  # Retain and supervise exact owned handles.
                    raise
        def receipt(state,errors):
            (outputs/'wrapper-receipt.json').write_text(json.dumps({'owner':OWNER,'leaseId':validated_permit['leaseId'],'leaseExpiresUtc':validated_permit['expiresUtc'],'failureType':type(failure).__name__ if failure else None,'resources':ledger,'cleanup':state,'cleanupFailureTypes':errors,'historicalBuildOrTestsReplayed':False},indent=2))
        preserve_first_failure(failure,cleanup,receipt)


if __name__=='__main__': main()
