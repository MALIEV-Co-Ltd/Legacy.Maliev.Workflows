"""Protected-main sealed Windows static validation; no builds or tests."""
import base64
from datetime import datetime, timezone
import hashlib
import importlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
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
    fixed = {'issuedBy':ROOT,'owner':OWNER,'phase':'hosted-static','worktree':policy['worktree'],'baseSha':policy['baseSha'],'candidateSha':policy['candidateSha']}
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


def main():
    if sys.platform!='win32': raise ValueError('Qualified Windows provider required')
    trusted=Path(__file__).resolve().parent
    policy=json.loads((trusted/'hosted-static-policy.json').read_bytes(),object_pairs_hook=unique)
    permit_raw=os.environ['ROOT_STATIC_PERMIT'].encode('utf-8')
    validate_permit(permit_raw,policy)
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
    def command(name,args,cwd):
        return preparation_command(owned.run_owned,ledger,args,cwd=cwd,timeout=30,memory_limit=256*1024**2,output_limit=4*1024**2,log_path=outputs/(name+'.log'))
    try:
        head=command('trusted-head',['git','rev-parse','HEAD'],trusted.parent).decode().strip()
        validate_context(context,head)
        preflight=admission.preflight()
        if preflight['freeMiB']<policy['initialMemoryFloorMiB'] or admission.SLOT.exists(): raise RuntimeError('Additional initial headroom required')
        command('candidate-checkout',['git','worktree','add','--detach',str(worktree),policy['baseSha']],trusted.parent)
        for name,raw in entries.items():
            if name.startswith('worktree/'): safe_write(worktree,name[len('worktree/'):],raw)
        del entries  # Release sealed archive buffers before any native phase.
        permit_path=outputs/'root-hosted-static-permit.json';permit_path.write_bytes(permit_raw)
        core=outputs/'hosted_static_core.py'
        if digest(core.read_bytes())!=policy['coreSha256']: raise ValueError('Reviewed native core pin')
        module=importlib.import_module('hosted_static_core')
        module.candidate_check()
        sys.argv=[str(core),'hosted-static',str(permit_path)]
        module.main()
    except BaseException as error:
        failure=error
    finally:
        def checkpoint(kind,state):
            (outputs/'wrapper-cleanup.json').write_text(json.dumps({'kind':kind,'state':state},indent=2))
        def recover(lease): ledger.append(owned.recover_quarantined(lease))
        def cleanup():
            while True:
                try: return supervisor.supervise(owned._quarantined,recover,None,None,checkpoint)
                except BaseException:
                    if owned._quarantined: continue  # Retain and supervise exact owned handles.
                    raise
        def receipt(state,errors):
            (outputs/'wrapper-receipt.json').write_text(json.dumps({'failureType':type(failure).__name__ if failure else None,'resources':ledger,'cleanup':state,'cleanupFailureTypes':errors,'buildOrTestsReplayed':False},indent=2))
        preserve_first_failure(failure,cleanup,receipt)


if __name__=='__main__': main()
