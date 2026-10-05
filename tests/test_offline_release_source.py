import importlib.util
import pathlib
import subprocess
import tempfile
import unittest
from unittest import mock
import sys
import os

MODULE = pathlib.Path(__file__).resolve().parents[1] / 'scripts/offline_release_source.py'


class SourceGuardTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temporary.name)
        self.origin = self.root / 'origin.git'
        self.repo = self.root / 'checkout with spaces'
        self.git('init', '--bare', '--initial-branch=main', str(self.origin))
        self.git('init', '--initial-branch=main', str(self.repo))
        self.git('-C', str(self.repo), 'config', 'user.name', 'Source Fixture')
        self.git('-C', str(self.repo), 'config', 'user.email', 'fixture@example.invalid')
        (self.repo / 'source.txt').write_text('reviewed source\n', encoding='utf-8')
        self.git('-C', str(self.repo), 'add', 'source.txt')
        self.git('-C', str(self.repo), 'commit', '-m', 'Fixture source')
        self.sha = self.git('-C', str(self.repo), 'rev-parse', 'HEAD').strip()
        self.url = self.origin.as_uri()
        self.git('-C', str(self.repo), 'remote', 'add', 'origin', self.url)
        self.git('-C', str(self.repo), 'push', 'origin', 'main')
        self.addCleanup(self.temporary.cleanup)

    def git(self, *args):
        return subprocess.check_output(['git', *args], stderr=subprocess.DEVNULL, text=True)

    def module(self):
        self.assertTrue(MODULE.is_file(), 'Missing actual source guard API')
        spec = importlib.util.spec_from_file_location('offline_release_source', MODULE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_actual_clean_head_and_remote_main_observation_is_offline(self):
        proof = self.module().verify_release_source(str(self.repo), self.sha, self.url, allow_fixture_origin=True)
        self.assertEqual(self.sha, proof['sourceCommit'])
        self.assertTrue(proof['cleanObserved'])
        self.assertTrue(proof['remoteMainObserved'])
        self.assertFalse(proof['deploymentAllowed'])
        self.assertFalse(proof['liveAccepted'])
        self.assertNotIn(str(self.root), repr(proof))
        self.assertEqual('', self.git('-C', str(self.repo), 'status', '--porcelain'))

    def assert_rejected(self, step, **overrides):
        module = self.module()
        arguments = dict(repository_root=str(self.repo), expected_commit=self.sha, expected_origin=self.url, allow_fixture_origin=True)
        arguments.update(overrides)
        with self.assertRaises(module.SourceFailure) as failure:
            module.verify_release_source(**arguments)
        self.assertEqual(step, failure.exception.step)
        self.assertNotIn(str(self.root), str(failure.exception))
        return failure.exception

    def test_tracked_dirty_source_rejected(self):
        (self.repo / 'source.txt').write_text('changed\n')
        self.assert_rejected('CLEAN')

    def test_untracked_source_rejected(self):
        (self.repo / 'private-canary.txt').write_text('private-canary-value\n')
        self.assert_rejected('CLEAN')

    def test_staged_source_rejected(self):
        (self.repo / 'source.txt').write_text('changed\n')
        self.git('-C', str(self.repo), 'add', 'source.txt')
        self.assert_rejected('CLEAN')

    def test_wrong_head_rejected(self):
        self.assert_rejected('HEAD', expected_commit='a' * 40)

    def test_wrong_origin_rejected(self):
        self.assert_rejected('ORIGIN', expected_origin=(self.root / 'foreign.git').as_uri())

    def test_local_remote_requires_explicit_fixture_mode(self):
        self.assert_rejected('INPUT', allow_fixture_origin=False)

    def test_nested_directory_is_not_isolated_checkout_root(self):
        folder = self.repo / 'nested'
        folder.mkdir()
        self.assert_rejected('REPOSITORY', repository_root=str(folder))

    def test_changed_remote_between_distinct_stage_observations_rejected(self):
        module = self.module()
        module.verify_release_source(str(self.repo), self.sha, self.url, allow_fixture_origin=True)
        other = self.root / 'other'
        self.git('clone', str(self.origin), str(other))
        self.git('-C', str(other), 'config', 'user.name', 'Other Fixture')
        self.git('-C', str(other), 'config', 'user.email', 'other@example.invalid')
        (other / 'next.txt').write_text('next source\n')
        self.git('-C', str(other), 'add', 'next.txt')
        self.git('-C', str(other), 'commit', '-m', 'Remote changed')
        self.git('-C', str(other), 'push', 'origin', 'main')
        self.assert_rejected('REMOTE_MAIN')

    def test_read_after_image_builder_detects_local_change(self):
        module = self.module()
        module.verify_release_source(str(self.repo), self.sha, self.url, allow_fixture_origin=True)
        (self.repo / 'source.txt').write_text('builder changed checkout\n')
        self.assert_rejected('CLEAN')

    def test_second_origin_url_is_ambiguous(self):
        self.git('-C', str(self.repo), 'config', '--add', 'remote.origin.url', self.url)
        self.assert_rejected('REPOSITORY')

    def test_missing_remote_main_preserves_native_exit_without_raw_output(self):
        self.git('-C', str(self.origin), 'config', 'receive.denyDeleteCurrent', 'ignore')
        self.git('-C', str(self.repo), 'push', 'origin', '--delete', 'main')
        failure = self.assert_rejected('REMOTE_MAIN')
        self.assertEqual(2, failure.exit_code)

    def test_streaming_read_rejects_oversized_provider_output_without_capture(self):
        module = self.module()
        self.assertTrue(hasattr(module, 'read_git_output'), 'Missing bounded native stream reader')
        # At the native stream boundary only; actual Git source controls above
        # exercise real isolated checkouts and bare origins.
        with self.assertRaises(module.SourceFailure):
            module.read_git_output([sys.executable, '-c', 'import sys;sys.stdout.write("private-canary"*10000)'],
                                   self.root, {}, 2, 'REMOTE_MAIN')

    def test_native_timeout_is_bounded_and_redacted(self):
        module = self.module()
        self.assertTrue(hasattr(module, 'read_git_output'), 'Missing bounded native timeout reader')
        with self.assertRaises(module.SourceFailure) as failure:
            module.read_git_output([sys.executable, '-c', 'import time;time.sleep(5)'], self.root, {}, 0.2, 'REMOTE_MAIN')
        self.assertEqual('REMOTE_MAIN', failure.exception.step)
        self.assertNotIn('sleep', str(failure.exception))

    def test_remote_duplicate_lines_are_not_accepted_as_first_sha(self):
        module = self.module()
        original = module.read_git_output
        def provider(command, *arguments):
            value = original(command, *arguments)
            return value + value if 'ls-remote' in command else value
        with mock.patch.object(module, 'read_git_output', side_effect=provider):
            with self.assertRaises(module.SourceFailure) as failure:
                module.verify_release_source(str(self.repo), self.sha, self.url, allow_fixture_origin=True)
        self.assertEqual('REMOTE_MAIN', failure.exception.step)

    def test_checkout_changed_during_remote_read_is_reobserved(self):
        module = self.module()
        original = module.read_git_output
        def provider(command, *arguments):
            value = original(command, *arguments)
            if 'ls-remote' in command:
                (self.repo / 'source.txt').write_text('changed during observation\n')
            return value
        with mock.patch.object(module, 'read_git_output', side_effect=provider):
            with self.assertRaises(module.SourceFailure) as failure:
                module.verify_release_source(str(self.repo), self.sha, self.url, allow_fixture_origin=True)
        self.assertEqual('CLEAN', failure.exception.step)

    def test_cli_actual_source_observation_returns_one_bounded_receipt(self):
        request = dict(repositoryRoot=str(self.repo), expectedCommit=self.sha, expectedOrigin=self.url, allowFixtureOrigin=True)
        import json
        result = subprocess.run([sys.executable, '-B', str(MODULE)], input=json.dumps(request),
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(0, result.returncode)
        self.assertNotEqual('', result.stdout, 'Missing actual JSON source-guard consumer entry')
        self.assertTrue(json.loads(result.stdout)['cleanObserved'])
        self.assertEqual('', result.stderr)

    def test_powershell_actual_consumer_bridge_reads_same_git_fixture(self):
        script = MODULE.with_name('Assert-OfflineReleaseSource.ps1')
        self.assertTrue(script.is_file(), 'Missing shared PowerShell consumer API')
        import json
        harness = pathlib.Path(__file__).with_name('Invoke-OfflineSourceGuardFixture.ps1')
        result = subprocess.run(['pwsh', '-NoProfile', '-File', str(harness), '-SourceGuardScriptPath', str(script),
                                 '-RepositoryRoot', str(self.repo), '-ExpectedSourceCommit', self.sha, '-ApprovedSourceRepository', self.url],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(0, result.returncode, result.stderr)
        proof = json.loads(result.stdout)
        self.assertEqual(self.sha, proof['sourceCommit'])
        self.assertFalse(proof['deploymentAllowed'])
        self.assertFalse(proof['liveAccepted'])

    def test_oversized_stderr_is_bounded_and_redacted(self):
        module = self.module()
        with self.assertRaises(module.SourceFailure) as failure:
            module.read_git_output([sys.executable, '-c', 'import sys;sys.stderr.write("private-canary"*10000)'],
                                   self.root, {}, 2, 'HEAD')
        self.assertNotIn('private-canary', str(failure.exception))

    def test_remote_reference_and_full_sha_are_not_prefix_or_case_matches(self):
        module = self.module()
        original = module.read_git_output
        for response in (self.sha + '\trefs/heads/main-extra\n', self.sha.upper() + '\trefs/heads/main\n',
                         self.sha + ' refs/heads/main\n', self.sha + '\trefs/heads/main\n\n'):
            with self.subTest(response=response):
                def provider(command, *arguments):
                    return response if 'ls-remote' in command else original(command, *arguments)
                with mock.patch.object(module, 'read_git_output', side_effect=provider):
                    with self.assertRaises(module.SourceFailure):
                        module.verify_release_source(str(self.repo), self.sha, self.url, allow_fixture_origin=True)

    def test_cli_duplicate_input_and_private_data_return_opaque_rejection(self):
        payload = '{"repositoryRoot":"private-canary","repositoryRoot":"other"}'
        result = subprocess.run([sys.executable, '-B', str(MODULE)], input=payload, capture_output=True, text=True, timeout=5)
        self.assertEqual(1, result.returncode)
        self.assertNotIn('private-canary', result.stdout + result.stderr)
        self.assertEqual('', result.stderr)

    def test_nonapproved_repository_and_invalid_commit_fail_without_git(self):
        self.assert_rejected('INPUT', expected_origin='https://github.com/foreign/Legacy.Maliev.FileService.git')
        self.assert_rejected('INPUT', expected_commit='A' * 40)
        self.assert_rejected('INPUT', allow_fixture_origin='true')

    def test_ambient_repository_selectors_cannot_hide_changed_actual_head(self):
        foreign = self.root / 'foreign-checkout'
        self.git('clone', str(self.origin), str(foreign))
        self.git('-C', str(foreign), 'remote', 'set-url', 'origin', self.url)
        self.git('-C', str(self.repo), 'commit', '--allow-empty', '-m', 'Actual head changed')
        with mock.patch.dict(os.environ, {'GIT_DIR': str(foreign / '.git'), 'GIT_WORK_TREE': str(self.repo)}):
            self.assert_rejected('HEAD')

    def test_ambient_config_injection_cannot_hide_actual_foreign_origin(self):
        foreign_url = (self.root / 'foreign.git').as_uri()
        self.git('-C', str(self.repo), 'remote', 'set-url', 'origin', foreign_url)
        injected = {'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'url.' + self.url + '.insteadOf', 'GIT_CONFIG_VALUE_0': foreign_url}
        with mock.patch.dict(os.environ, injected):
            self.assert_rejected('ORIGIN')


if __name__ == '__main__':
    unittest.main()
