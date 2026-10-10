"""Pure profile/capsule controls; no hosted resource allocation."""
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('native_profile_transport',HERE/'run-hosted-static.py')
transport=importlib.util.module_from_spec(spec);spec.loader.exec_module(transport)


class PublicProfileTests(unittest.TestCase):
    def test_fixed_selection_and_inventory_default(self):
        with patch.dict(transport.os.environ,{},clear=True):
            self.assertEqual(transport.selected_policy_path(HERE),HERE/'hosted-static-policy.json')
        with patch.object(transport.sys,'platform','linux'),patch.dict(transport.os.environ,{'HOSTED_STATIC_PROFILE':'auth-program-child-c-component-v1'},clear=True):
            self.assertEqual(transport.selected_policy_path(HERE),HERE/'hosted-native-program-policy.json')
        for platform,profile in [('win32','auth-program-child-c-component-v1'),('linux','../custom'),('linux',''),('linux','native')]:
            with self.subTest(platform=platform,profile=profile),patch.object(transport.sys,'platform',platform),patch.dict(transport.os.environ,{'HOSTED_STATIC_PROFILE':profile},clear=True),self.assertRaises(ValueError):
                transport.selected_policy_path(HERE)

    def test_complete_sealed_capsule_and_fixed_permit_join(self):
        policy=json.loads((HERE/'hosted-native-program-policy.json').read_bytes())
        entries=transport.verified_entries((HERE/'sealed-native-program-kit.zip').read_bytes(),policy)
        self.assertEqual(set(entries),set(policy['entries']))
        self.assertIn('worktree/tools/native-program-child/program_child.c',entries)
        self.assertEqual(transport.digest(entries['outputs/hosted_native_program_core.py']),policy['coreSha256'])
        now=datetime.now(timezone.utc)
        permit=dict(issuedBy=transport.ROOT,owner=transport.OWNER,phase='hosted-qualification',
            leaseId='cfd607a0-a070-41e3-9395-0a3084c98c35',issuedUtc=now.isoformat(),
            expiresUtc=(now+timedelta(seconds=900)).isoformat(),worktree=policy['worktree'],
            baseSha=policy['baseSha'],candidateSha=policy['candidateSha'])
        self.assertEqual(transport.validate_permit(json.dumps(permit).encode(),policy,now=now),permit)
        for key,value in [('candidateSha','c01d8789b9b38b95a2b73e68ba294591713eb53dff652a41c0314d78bedbbf2e'),
                          ('baseSha','69135d56050470d59384a69357eca4ff7248e6a0'),('phase','native'),('extra','value')]:
            bad=dict(permit);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):transport.validate_permit(json.dumps(bad).encode(),policy,now=now)


if __name__=='__main__':unittest.main(verbosity=2)
