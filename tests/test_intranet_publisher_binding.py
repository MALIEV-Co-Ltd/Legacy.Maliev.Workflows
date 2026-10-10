import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
import datetime
from unittest.mock import patch
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
namespace={'__name__':'source_fixture'}
workflow=(ROOT/'.github/workflows/publish-image.yml').read_text()
block=workflow.split('      - name: Verify packaged Intranet assets and source revision\n',1)[1].split('      - name: Verify packaged Web assets',1)[0]
program='\n'.join(line.removeprefix('          ') for line in block.split('        run: |\n',1)[1].splitlines()).rstrip()
exec(compile(program,'actual_intranet_publisher_step','exec'),namespace)
REV='a'*40;IMAGE_ID='sha256:'+'b'*64;CONTAINER='c'*64

class LimitState:
    RLIMIT_FSIZE=1;RLIM_INFINITY=-1
    def __init__(self):self.limits=(-1,-1);self.history=[]
    def getrlimit(self,key):return self.limits
    def setrlimit(self,key,value):self.limits=value;self.history.append(value)
limits=LimitState();namespace['resource']=limits

class DockerState:
    def __init__(self,role='compatibility',fault=None):
        self.role,self.fault=role,fault;self.calls=[];self.present=False;self.exports=[];self.records=None
    def native(self,args):
        self.calls.append(args)
        if args[:2]==['image','inspect']:
            if args[3]=='{{json .Config.Volumes}}':return '{"/data":{}}' if self.fault=='image-volume' else 'null'
            if args[3]=='{{.Id}}':
                if self.fault=='tag-race' and self.present:return 'sha256:'+'d'*64
                return IMAGE_ID
            return 'e'*40 if self.fault=='revision' else REV
        if args[0]=='create':
            if self.fault=='create-pending':raise TimeoutError('PRIVATE_PENDING_CREATE')
            self.present=True
            name=args[args.index('--name')+1];labels={}
            for i,a in enumerate(args):
                if a=='--label':key,value=args[i+1].split('=',1);labels[key]=value
            self.records=[dict(Id=CONTAINER,Name='/'+name,Image=IMAGE_ID,Created=datetime.datetime.now(datetime.timezone.utc).isoformat(),Mounts=[],Config=dict(Labels=labels),State=dict(Running=False,Status='created',StartedAt='0001-01-01T00:00:00Z'))]
            if self.fault=='foreign-owner':self.records[0]['Config']['Labels']['maliev.codex.artifact-owner']='foreign'
            if self.fault=='old-created':self.records[0]['Created']='2000-01-01T00:00:00+00:00'
            if self.fault=='started-stopped':self.records[0]['State'].update(Status='exited',StartedAt=datetime.datetime.now(datetime.timezone.utc).isoformat())
            if self.fault=='create-timeout':raise TimeoutError('PRIVATE_DOCKER_TIMEOUT')
            if self.fault=='malformed-create':return 'PRIVATE_INVALID_ID'
            return CONTAINER
        if args[:2]==['container','inspect']:return json.dumps(self.records)
        if args[:2]==['container','export']:
            assert limits.limits[0]<=namespace['ARCHIVE_LIMIT'] and limits.limits[0]>0
            archive=Path(args[args.index('--output')+1]);self.exports.append(archive)
            if self.fault=='export-file-limit':archive.write_bytes(b'PARTIAL_SYNTHETIC_EXPORT');raise OSError('PRIVATE_EFBIG')
            assembly,assets=namespace['ROLE_ARTIFACTS'][self.role]
            files={assembly+'.dll':b'SYNTHETIC_IMAGE_FIXTURE',assembly+'.deps.json':json.dumps(dict(libraries={assembly+'/1.0':{}})).encode(),assembly+'.runtimeconfig.json':json.dumps(dict(runtimeOptions=dict(tfm='net10.0'))).encode()}
            files.update({asset:b'SYNTHETIC_ASSET' for asset in assets})
            with tarfile.open(archive,'w') as output:
                for relative,data in files.items():
                    if self.fault=='missing' and relative==assembly+'.dll':continue
                    entry=tarfile.TarInfo('app/'+relative);entry.size=len(data)
                    if self.fault=='link' and relative==assembly+'.dll':entry.type=tarfile.SYMTYPE;entry.linkname='/private';entry.size=0
                    output.addfile(entry,io.BytesIO(data))
                    if self.fault=='duplicate' and relative==assembly+'.dll':output.addfile(entry,io.BytesIO(data))
            return ''
        if args[:2]==['container','rm']:
            if self.fault=='cleanup':raise ValueError('PRIVATE_PROVIDER_TEXT')
            self.present=False;return CONTAINER
        if args[:2]==['container','ls']:return CONTAINER if self.present else ''
        raise AssertionError(args)

class PublisherTests(unittest.TestCase):
    def invoke(self,state,dockerfile=None):
        dockerfile=dockerfile or ('Legacy.Maliev.Intranet'+('.Bff' if state.role=='bff' else '')+'/Dockerfile')
        return namespace['inspect_intranet_image']('MALIEV-Co-Ltd/Legacy.Maliev.Intranet',dockerfile,'registry.example/project/legacy-maliev-intranet-'+state.role+':'+REV,REV,state.native)
    def test_actual_embedded_both_role_corpora_revision_and_cleanup(self):
        for role in ['compatibility','bff']:
            state=DockerState(role);result=self.invoke(state)
            self.assertEqual(9 if role=='compatibility' else 3,len(result['files']))
            self.assertEqual(IMAGE_ID,result['imageId']);self.assertFalse(result['runtimeAccepted'])
            self.assertFalse(state.present);self.assertTrue(all(not p.parent.exists() for p in state.exports))
            create=next(c for c in state.calls if c[0]=='create');self.assertIn('--memory',create);self.assertIn('--cpus',create)
            self.assertFalse(any(c[0] in ['start','run','push','build'] for c in state.calls))
    def test_missing_duplicate_and_link_refuse_and_remove_owned_resource(self):
        for fault in ['missing','duplicate','link']:
            state=DockerState(fault=fault)
            with self.assertRaises(ValueError):self.invoke(state)
            self.assertFalse(state.present);self.assertTrue(all(not p.parent.exists() for p in state.exports))
    def test_revision_mismatch_allocates_no_container(self):
        state=DockerState(fault='revision')
        with self.assertRaises(ValueError):self.invoke(state)
        self.assertFalse(any(c[0]=='create' for c in state.calls))
    def test_retag_after_inspection_refuses_and_cleans(self):
        state=DockerState(fault='tag-race')
        with self.assertRaises(ValueError):self.invoke(state)
        self.assertFalse(state.present)
    def test_foreign_resource_never_removed_or_exported(self):
        state=DockerState(fault='foreign-owner')
        with self.assertRaises(ValueError):self.invoke(state)
        self.assertFalse(any(c[:2] in [['container','rm'],['container','export']] for c in state.calls))
        # Recovery is explicitly retained; a label is not an automatic expiry.
        with self.assertRaises(namespace['ImageRecoveryRequired']) as caught:self.invoke(DockerState(fault='foreign-owner'))
        self.assertFalse(caught.exception.recovery_receipt['expiryIsAutomaticCleanup'])
        # Test model only: no actual container exists.
    def test_cleanup_failure_cannot_return_success(self):
        state=DockerState(fault='cleanup')
        with self.assertRaises(ValueError):self.invoke(state)
        self.assertTrue(all(not p.parent.exists() for p in state.exports))
    def test_created_but_timeout_or_invalid_stdout_is_recovered_by_exact_owner(self):
        for fault in ['create-timeout','malformed-create']:
            state=DockerState(fault=fault)
            with self.assertRaises((TimeoutError,ValueError)):self.invoke(state)
            self.assertFalse(state.present)
            self.assertTrue(any(c[:2]==['container','inspect'] and c[2].startswith('legacy-intranet-artifact-') for c in state.calls))
            self.assertEqual([CONTAINER],[c[2] for c in state.calls if c[:2]==['container','rm']])
    def test_created_identity_outside_current_attempt_is_preserved_with_recovery_receipt(self):
        state=DockerState(fault='old-created')
        with self.assertRaises(namespace['ImageRecoveryRequired']) as caught:self.invoke(state)
        self.assertFalse(any(c[:2]==['container','rm'] for c in state.calls))
        self.assertFalse(caught.exception.recovery_receipt['cleanupVerified'])
    def test_empty_listing_after_interrupted_create_retains_pending_lease(self):
        state=DockerState(fault='create-pending')
        with self.assertRaises(namespace['ImageRecoveryRequired']) as caught:self.invoke(state)
        self.assertTrue(caught.exception.recovery_receipt['createMayBeInFlight'])
        self.assertIsNone(caught.exception.recovery_receipt['containerId'])
        self.assertFalse(any(c[:2]==['container','rm'] for c in state.calls))
    def test_export_write_cap_is_inherited_and_restored_on_failure(self):
        state=DockerState(fault='export-file-limit')
        with self.assertRaises(OSError):self.invoke(state)
        self.assertEqual((-1,-1),limits.limits);self.assertFalse(state.present)
        self.assertTrue(all(not p.parent.exists() for p in state.exports))
    def test_failed_disk_admission_never_exports_and_cleans_owned_container(self):
        state=DockerState()
        with patch.object(namespace['shutil'],'disk_usage',return_value=SimpleNamespace(free=1)):
            with self.assertRaises(ValueError):self.invoke(state)
        self.assertFalse(state.present);self.assertFalse(any(c[:2]==['container','export'] for c in state.calls))
    def test_volume_image_refuses_before_creation(self):
        state=DockerState(fault='image-volume')
        with self.assertRaises(ValueError):self.invoke(state)
        self.assertFalse(any(c[0]=='create' for c in state.calls))
    def test_started_then_stopped_container_is_preserved_with_receipt(self):
        state=DockerState(fault='started-stopped')
        with self.assertRaises(namespace['ImageRecoveryRequired']):self.invoke(state)
        self.assertFalse(any(c[:2] in [['container','rm'],['container','export']] for c in state.calls))
    def test_unknown_current_role_refuses_and_other_repository_is_unchanged(self):
        state=DockerState()
        with self.assertRaises(ValueError):self.invoke(state,'Legacy.Maliev.Intranet.Client/Dockerfile')
        self.assertEqual([],state.calls)
        self.assertEqual({'status':'not-applicable'},namespace['inspect_intranet_image']('MALIEV-Co-Ltd/Legacy.Maliev.Other','','','',state.native))
    def test_workflow_binds_verified_image_to_scan_and_preserves_refusals(self):
        self.assertIn('image-ref: ${{ steps.intranet-artifacts.outputs.imageId || env.COMMIT_TAG }}',workflow)
        self.assertLess(workflow.index('test "$(docker image inspect'),workflow.index('docker push "$COMMIT_TAG"'))
        self.assertIn('expiryIsAutomaticCleanup=False',program)
        self.assertIn('timeout=120',program)
        self.assertIn('[intranet-image-recovery]',program)
        self.assertIn('GITHUB_STEP_SUMMARY',program)

if __name__=='__main__':unittest.main(verbosity=2)
