import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('evidence', ROOT / 'scripts/preserve_validation_evidence.py')
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='evidence-fixture-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'workspace'
        self.stage = Path(self.temporary.name) / 'runner'
        self.root.mkdir()
        self.stage.mkdir()
        self.project = 'Legacy.Maliev.Intranet.Bff'
        self.write(self.project + '/Program.cs', b'// synthetic production source\n')
        subprocess.run(['git','init','--quiet',str(self.root)], check=True, capture_output=True)
        subprocess.run(['git','-C',str(self.root),'add','.'], check=True, capture_output=True)
        subprocess.run(['git','-C',str(self.root),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','--quiet','-m','Synthetic source'], check=True, capture_output=True)
        self.sha = subprocess.check_output(['git','-C',str(self.root),'rev-parse','HEAD'], text=True).strip()
        self.write('TestResults/fixture/coverage.cobertura.xml', b'<coverage><packages><package name="Synthetic" line-rate="0.8"/></packages></coverage>')
        self.write(self.project + '/bin/Release/net10.0/' + self.project + '.dll', b'MZ synthetic opaque production assembly')
        self.write(self.project + '/bin/Release/net10.0/' + self.project + '.pdb', b'BSJB synthetic opaque portable symbols')
        self.write('coverage.runsettings', b'<RunSettings><ExcludeByFile>**/obj/**</ExcludeByFile></RunSettings>')

    def write(self, path, data):
        file = self.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(data)

    def prepare(self, **overrides):
        args = dict(workspace=self.root, runner_temp=self.stage, repository='MALIEV-Co-Ltd/Legacy.Maliev.Intranet',
                    source_revision=self.sha, results_directory='TestResults', production_projects=[self.project])
        args.update(overrides)
        return evidence.prepare(**args)

    def test_actual_existing_bytes_hashes_and_settings_preserved_without_coverage_relabel(self):
        stage, complete = self.prepare()
        manifest = json.loads((stage/'availability.json').read_text())
        self.assertTrue(complete)
        self.assertFalse(manifest['trxAvailable'])
        self.assertFalse(manifest['generatedInclusiveCertified'])
        self.assertFalse(manifest['sourceMapAttestation'])
        self.assertEqual(self.sha, manifest['sourceRevision'])
        self.assertEqual((self.root/'coverage.runsettings').read_bytes(), (stage/'coverage.runsettings').read_bytes())
        for record in manifest['files']:
            self.assertEqual(record['sha256'], evidence.digest((stage/record['path']).read_bytes()))

    def test_missing_coverage_or_symbols_is_explicit_partial_and_does_not_pass(self):
        for missing in ('TestResults/fixture/coverage.cobertura.xml', self.project+'/bin/Release/net10.0/'+self.project+'.pdb'):
            data = (self.root/missing).read_bytes()
            (self.root/missing).unlink()
            stage, complete = self.prepare()
            self.assertFalse(complete)
            self.assertFalse(json.loads((stage/'availability.json').read_text())['complete'])
            self.write(missing, data)

    def test_trx_outcomes_preserved_while_private_output_arguments_and_machine_paths_are_omitted(self):
        trx = b'<TestRun><Results><UnitTestResult testId="one" outcome="Passed" testName="private-canary"><Output><StdOut>private-canary</StdOut></Output></UnitTestResult></Results><ResultSummary><Counters total="1" passed="1" failed="0"/></ResultSummary><TestSettings><Deployment root="private-canary"/></TestSettings></TestRun>'
        self.write('TestResults/fixture/actual.trx', trx)
        stage, complete = self.prepare()
        self.assertTrue(complete)
        result = (stage/'TestResults/fixture/actual.trx').read_bytes()
        self.assertNotIn(b'private-canary', result)
        self.assertIn(b'outcome="Passed"', result)
        manifest = json.loads((stage/'availability.json').read_text())
        self.assertTrue(manifest['trxAvailable'])
        retained = next(r for r in manifest['files'] if r['path'].endswith('.trx'))
        self.assertEqual('outcome-only-trx/v1', retained['transform'])
        self.assertEqual(evidence.digest(trx), retained['originalSha256'])

    def test_whole_repo_configuration_logs_and_private_git_are_not_selected(self):
        for file in ('appsettings.Production.json','TestResults/private.log','TestResults/private.env', self.project+'/secret.json'):
            self.write(file, b'private-canary')
        stage, _ = self.prepare()
        self.assertFalse(any(b'private-canary' in p.read_bytes() for p in stage.rglob('*') if p.is_file()))
        source_map = json.loads((stage/'source-map.json').read_text())
        self.assertEqual([self.project+'/Program.cs'], [p['path'] for p in source_map['files']])

    def test_traversal_foreign_tests_projects_and_wrong_head_are_refused(self):
        for overrides in (dict(results_directory='../secret'), dict(results_directory=str(self.root)),
                          dict(production_projects=['Legacy.Maliev.AuthService.Api']),
                          dict(production_projects=['Legacy.Maliev.Intranet.Tests']), dict(source_revision='b'*40),
                          dict(production_projects=[self.project,self.project])):
            with self.subTest(overrides=overrides):
                with self.assertRaises(evidence.EvidenceFailure): self.prepare(**overrides)

    def test_oversized_xml_and_entity_or_unexpected_payload_are_refused(self):
        for data in (b'x'*(evidence.MAX_FILE+1), b'<!DOCTYPE coverage><coverage/>',
                     b'<coverage><private>private-canary</private></coverage>'):
            self.write('TestResults/fixture/coverage.cobertura.xml', data)
            with self.assertRaises(evidence.EvidenceFailure): self.prepare()

    def test_symlinked_results_cannot_escape_the_workspace(self):
        outside = self.stage/'outside.xml'
        outside.write_bytes(b'<coverage/>')
        target = self.root/'TestResults/fixture/coverage.cobertura.xml'
        target.unlink()
        try:
            target.symlink_to(outside)
        except OSError:
            self.skipTest('Windows symlink permission unavailable; mandatory hosted Linux control')
        with self.assertRaises(evidence.EvidenceFailure): self.prepare()

    def test_action_is_separate_final_caller_step_and_uploads_partial_manifest_after_prepare_failure(self):
        action = (ROOT/'actions/preserve-validation-evidence/action.yml').read_text()
        self.assertIn("if: always() && steps.prepare.outputs.artifact-path != ''", action)
        self.assertIn('actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02', action)
        self.assertNotIn('dotnet test', action)
        self.assertNotIn('continue-on-error', action)
        self.assertIn('if-no-files-found: error', action)

    def test_actual_cli_retains_partial_manifest_but_exits_nonzero_with_opaque_output(self):
        missing = self.root/self.project/'bin/Release/net10.0'/f'{self.project}.pdb'
        missing.unlink()
        output = self.stage/'action-output.txt'
        environment = dict(os.environ, GITHUB_WORKSPACE=str(self.root), RUNNER_TEMP=str(self.stage),
            GITHUB_REPOSITORY='MALIEV-Co-Ltd/Legacy.Maliev.Intranet', GITHUB_SHA=self.sha,
            RESULTS_DIRECTORY='TestResults', PRODUCTION_PROJECTS=self.project, GITHUB_OUTPUT=str(output))
        result = subprocess.run([os.environ.get('PYTHON','python'),'-B',str(ROOT/'scripts/preserve_validation_evidence.py')],
            env=environment, capture_output=True, text=True, timeout=15)
        self.assertEqual(2, result.returncode)
        self.assertEqual('', result.stdout)
        self.assertNotIn(str(self.root), result.stderr)
        retained = Path(output.read_text().strip().split('=',1)[1])
        self.assertFalse(json.loads((retained/'availability.json').read_text())['complete'])

    def test_source_map_never_claims_compiled_membership_and_ambient_git_redirect_is_ignored(self):
        old = os.environ.get('GIT_DIR')
        os.environ['GIT_DIR'] = str(self.stage/'private-canary')
        try:
            stage, _ = self.prepare()
            self.assertFalse(json.loads((stage/'source-map.json').read_text())['compiledMembershipCertified'])
        finally:
            if old is None: os.environ.pop('GIT_DIR',None)
            else: os.environ['GIT_DIR'] = old

    def test_each_requested_production_project_requires_its_own_source_inventory(self):
        second = 'Legacy.Maliev.Intranet.Server'
        for extension in ('dll','pdb'):
            self.write(second+'/bin/Release/net10.0/'+second+'.'+extension, b'synthetic opaque binary')
        stage, complete = self.prepare(production_projects=[self.project,second])
        self.assertFalse(complete)

    def test_total_retention_and_file_count_limits_fail_before_staging(self):
        for name in ('MAX_TOTAL','MAX_FILES'):
            with patch.object(evidence,name,1):
                with self.assertRaises(evidence.EvidenceFailure): self.prepare()
        self.assertFalse(any(self.stage.glob('validation-evidence-*')))

    def test_runsettings_cannot_smuggle_an_environment_dump_into_the_retained_artifact(self):
        self.write('coverage.runsettings', b'<RunSettings><RunConfiguration><EnvironmentVariables><PRIVATE>private-canary</PRIVATE></EnvironmentVariables></RunConfiguration></RunSettings>')
        with self.assertRaises(evidence.EvidenceFailure): self.prepare()

    def test_actual_sdk_generated_source_filename_retains_hash_and_partial_evidence(self):
        name = self.project + '/obj/Release/net10.0/.NETCoreApp,Version=v10.0.AssemblyAttributes.cs'
        payload = b'// synthetic SDK generated target framework attribute\n'
        self.write(name, payload)
        (self.root/'TestResults/fixture/coverage.cobertura.xml').unlink()
        stage, complete = self.prepare()
        self.assertFalse(complete)
        mapping = json.loads((stage/'source-map.json').read_text())
        self.assertIn(name, json.dumps(mapping))
        self.assertIn(evidence.digest(payload), json.dumps(mapping))
        self.assertFalse(mapping['compiledMembershipCertified'])
        self.assertFalse((stage/name).exists())

    def test_sdk_source_exception_never_allows_arbitrary_punctuation_inputs_or_links(self):
        filename = '.NETCoreApp,Version=v10.0.AssemblyAttributes.cs'
        for path in ('../obj/'+filename, '/obj/'+filename, 'obj//'+filename,
                     'obj/'+filename+'/private', 'obj/private,environment=canary.cs',
                     'src/'+filename, 'obj/.NETCoreApp,Version=v10.0.AssemblyAttributes.cs:secret',
                     'obj/.NETCoreApp,Version=v10.0.AssemblyAttributes.cs\\private'):
            with self.subTest(path=path), self.assertRaises(evidence.EvidenceFailure):
                evidence.relative_source_name(path)
        with self.assertRaises(evidence.EvidenceFailure): evidence.relative_name('obj/'+filename)
        name = self.project+'/obj/Release/net10.0/'+filename
        path = self.root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        target = self.stage/'outside.cs'
        target.write_bytes(b'private-canary')
        try:
            path.symlink_to(target)
        except OSError:
            # Existing symlink control exercises the same filesystem preflight;
            # this direct control must fail rather than silently skip.
            self.fail('SDK filename symlink control unavailable')
        with self.assertRaises(evidence.EvidenceFailure): self.prepare()
        self.assertFalse(any(self.stage.glob('validation-evidence-*')))


if __name__ == '__main__':
    unittest.main(verbosity=2)
