"""Download and extract one pinned official SDK into a fresh task-owned root."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import time
import urllib.request
import zipfile

SDK_ROOT=Path('D:/codex-temp/2026-10-09/workflows-hosted-sdk-10.0.401')
OUT=Path('D:/codex-temp/2026-10-03/legacy-code-workflows-20261003/outputs')
URL='https://builds.dotnet.microsoft.com/dotnet/Sdk/10.0.401/dotnet-sdk-10.0.401-win-x64.zip'
ARCHIVE_BYTES=300608304
ARCHIVE_SHA512='24b670ad3d923bfcf47df6c3b034152398b42f6dbc388e10d783aee1cfb5e5817d399fc0ae2a12cfa822a55e61d34830ccb15c50ef6efee437ab874bb7c79430'
MAX_UNPACKED=2*1024**3
MAX_MEMBER=128*1024**2

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args):raise ValueError('Official SDK redirect refused')

def verify_archive(path,expected_bytes=ARCHIVE_BYTES,expected_sha512=ARCHIVE_SHA512):
    size=0;sha=hashlib.sha512()
    with Path(path).open('rb') as stream:
        while block:=stream.read(1024**2):size+=len(block);sha.update(block)
    if size!=expected_bytes or sha.hexdigest()!=expected_sha512:raise ValueError('Pinned official SDK archive differs')
    return {'bytes':size,'sha512':sha.hexdigest(),'officialArchiveMatched':True}

def inventory(archive):
    entries=[];seen=set();total=0
    if len(archive.infolist())>100000:raise ValueError('SDK inventory quota')
    for item in archive.infolist():
        if item.orig_filename!=item.filename:raise ValueError('Normalized SDK member refused')
        name=item.filename.rstrip('/') if item.is_dir() else item.filename
        if not name or '\\' in name or ':' in name or any(part in ('','.','..') for part in name.split('/')) or PurePosixPath(name).is_absolute():raise ValueError('Noncanonical SDK member')
        if name.casefold() in seen or ((item.external_attr>>16)&0o170000)==0o120000:raise ValueError('Ambiguous or symlink SDK member')
        if item.file_size<0 or item.file_size>MAX_MEMBER:raise ValueError('SDK member quota')
        seen.add(name.casefold());total+=item.file_size;entries.append((item,name))
    if total>MAX_UNPACKED:raise ValueError('SDK unpacked quota')
    return entries,total

def safe_extract(archive,root,deadline):
    root=Path(root).resolve(strict=True)
    entries,total=inventory(archive)
    for item,name in entries:
        if time.monotonic()>=deadline:raise TimeoutError('SDK extraction deadline')
        target=root/name
        if not target.resolve().is_relative_to(root):raise ValueError('SDK extraction escape')
        current=target
        while current!=root.parent:
            if current.is_symlink():raise ValueError('SDK symlink destination')
            current=current.parent
        if item.is_dir():target.mkdir(parents=True,exist_ok=True);continue
        target.parent.mkdir(parents=True,exist_ok=True)
        copied=0
        with archive.open(item) as source,target.open('xb') as output:
            while block:=source.read(1024**2):
                if time.monotonic()>=deadline:raise TimeoutError('SDK extraction deadline')
                copied+=len(block)
                if copied>item.file_size:raise ValueError('SDK extraction quota')
                output.write(block)
        if copied!=item.file_size:raise ValueError('SDK extraction length differs')
    return {'members':len(entries),'unpackedBytes':total,'canonicalInventoryVerified':True,'freshFileWritesOnly':True}

def main():
    if sys.platform!='win32' or len(sys.argv)!=1:raise ValueError('Fixed Windows SDK bootstrap only')
    parent=Path('D:/codex-temp/2026-10-09').resolve()
    if SDK_ROOT.resolve()!=SDK_ROOT.absolute() or SDK_ROOT.resolve().parent!=parent or SDK_ROOT.exists() or SDK_ROOT.is_symlink():raise ValueError('Fresh fixed task-owned SDK root required')
    cache=OUT/'sdk-bootstrap-official-archive.zip';owned_cache=False;owned_root=False;success=False
    permit=json.loads(os.environ['ROOT_STATIC_PERMIT'])
    receipt={'sdkExecuted':False,'archiveSha512Expected':ARCHIVE_SHA512,'owner':'01a1009c-83f6-7010-9a59-df89ecbb1b1f','leaseId':permit['leaseId'],'expiresUtc':permit['expiresUtc'],'persistentData':False}
    deadline=time.monotonic()+280
    try:
        size=0;sha=hashlib.sha512()
        with cache.open('xb') as output:
            owned_cache=True
            with urllib.request.build_opener(NoRedirect()).open(URL,timeout=30) as response:
                while block:=response.read(1024**2):
                    if time.monotonic()>=deadline:raise TimeoutError('SDK bootstrap deadline')
                    size+=len(block)
                    if size>ARCHIVE_BYTES:raise ValueError('SDK download quota')
                    output.write(block);sha.update(block)
        if size!=ARCHIVE_BYTES or sha.hexdigest()!=ARCHIVE_SHA512:raise ValueError('Pinned official SDK download differs')
        receipt['archive']=verify_archive(cache)
        SDK_ROOT.mkdir(parents=True,exist_ok=False);owned_root=True
        (SDK_ROOT/'.codex-sdk-owner.json').write_text(json.dumps({'owner':receipt['owner'],'leaseId':receipt['leaseId'],'expiresUtc':receipt['expiresUtc'],'persistentData':False}))
        with zipfile.ZipFile(cache) as archive:receipt['extraction']=safe_extract(archive,SDK_ROOT,deadline)
        receipt.update(completedUtc=datetime.now(timezone.utc).isoformat(),installedFreshTaskRoot=True)
        success=True
    finally:
        if owned_cache:cache.unlink()
        receipt['downloadCacheRemoved']=not cache.exists()
        if owned_root and not success:
            # Only this fresh root was created by this invocation. Verify exact
            # absolute scope immediately before removing partial disposable data.
            if SDK_ROOT.resolve()!=SDK_ROOT.absolute() or SDK_ROOT.resolve().parent!=parent or SDK_ROOT.resolve()!=parent/'workflows-hosted-sdk-10.0.401' or SDK_ROOT.is_symlink():raise ValueError('Owned SDK cleanup scope changed')
            shutil.rmtree(SDK_ROOT)
        receipt['partialInstallRemoved']=not owned_root or success or not SDK_ROOT.exists()
        (OUT/'sdk-bootstrap-record.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt))

if __name__=='__main__':main()
