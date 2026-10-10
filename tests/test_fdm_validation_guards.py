"""Synthetic-only guard negatives; never imports archived tools or Web runtime."""
import copy
import hashlib
import importlib.util
import json
import io
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fdm_guards', ROOT / 'scripts/fdm_validation_guards.py')
guard = importlib.util.module_from_spec(spec); spec.loader.exec_module(guard)
HEAD = '1' * 40
FULL = '2' * 40


class FdmGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='fdm-guard-controls-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'caller'; self.root.mkdir()
        self.now = time.time()
        self.manifest = dict(schemaVersion=1, sourceSha=guard.SOURCE_SHA,
                             sourceParent=guard.SOURCE_PARENT, phases=[])
        for phase in guard.PHASES:
            method = 'Synthetic_' + phase.replace('-', '_')
            display = 'Demo.Tests.GuardCases.' + method
            self.manifest['phases'].append(dict(id=phase, filter='FullyQualifiedName~' + method,
                expectedPassingRows=[dict(**{'class': 'Demo.Tests.GuardCases'}, method=method,
                                          displaySha256=guard.sha(b'trx-display/v1\0' + display.encode()))]))
        self.write(guard.PHASE_MANIFEST, json.dumps(self.manifest).encode())
        attrs = b'* text=auto eol=lf\nLegacy.Maliev.Web.Application/Pricing/Profiles/Sources/*.json -text\nLegacy.Maliev.Web.Application/Pricing/Profiles/Resolved/*.json -text\n'
        self.write('.gitattributes', attrs)
        for group in ('Sources', 'Resolved'):
            self.write('Legacy.Maliev.Web.Application/Pricing/Profiles/' + group + '/demo.json', b'{"synthetic":true}\r\n')
        self.worker = 'Legacy.Maliev.Web/wwwroot/demo-worker.js'
        self.reference = 'Legacy.Maliev.Web/demo-policy.cs'
        self.write(self.worker, b'// synthetic worker\n')
        digest = guard.sha((self.root / self.worker).read_bytes())
        self.write(self.reference, ('WorkerPin = "' + digest[:16] + '";\n').encode())
        for path in guard.COVERAGE_PINS:
            self.write(path, (ROOT / 'tests/fixtures/fdm-coverage' / Path(path).name).read_bytes())
        self.write(guard.STARTUP_PROOF, b'# Synthetic inert startup-proof fixture; never executed.\n')
        paths = ['.gitattributes', guard.PHASE_MANIFEST, guard.STARTUP_PROOF, self.worker, self.reference,
                 *['Legacy.Maliev.Web.Application/Pricing/Profiles/' + group + '/demo.json' for group in ('Sources', 'Resolved')]]
        for path in ('Legacy.Maliev.Web.Application/Pricing/PricingEngine.cs',
                     'Legacy.Maliev.Web.Application/Pricing/PricingCatalog.cs',
                     'Legacy.Maliev.Web.Tests/FdmQuantityMarginTests.cs',
                     'Legacy.Maliev.Web.Tests/AdditiveQuoteTicketServiceTests.cs'):
            self.write(path, b'// synthetic source custody fixture only\n'); paths.append(path)
        files = [dict(path=path, bytes=(self.root / path).stat().st_size,
                      sha256=guard.sha((self.root / path).read_bytes()),
                      checkoutPolicy='opaque' if path.endswith('demo.json') else 'lf') for path in paths]
        self.source = dict(schemaVersion=1, sourceSha=guard.SOURCE_SHA, sourceParent=guard.SOURCE_PARENT,
                           fullWorkflowSha=FULL, files=files,
                           worker=dict(path=self.worker, referencePath=self.reference, sha256=digest, pin=digest[:16]))
        self.write(guard.SOURCE_MANIFEST, json.dumps(self.source).encode())
        self.prepare('margin')

    def write(self, path, data):
        file = self.root / path; file.parent.mkdir(parents=True, exist_ok=True); file.write_bytes(data)

    def prepare(self, phase):
        self.phase = phase
        self.trx = 'TestResults/fdm/' + phase + '/' + phase + '.trx'
        receipt = guard.admission(phase, HEAD, HEAD, 4 * 1024 ** 3, [], self.now - 1)
        receipt['phaseManifestSha256'] = guard.sha((self.root / guard.PHASE_MANIFEST).read_bytes())
        self.receipt = receipt
        self.write('TestResults/fdm/' + phase + '/admission.json', json.dumps(receipt).encode())
        method = 'Synthetic_' + phase.replace('-', '_')
        display = 'Demo.Tests.GuardCases.' + method
        tid, eid = str(uuid.uuid4()), str(uuid.uuid4())
        root = ET.Element('TestRun')
        definitions = ET.SubElement(root, 'TestDefinitions')
        test = ET.SubElement(definitions, 'UnitTest', id=tid, name=display)
        ET.SubElement(test, 'Execution', id=eid)
        ET.SubElement(test, 'TestMethod', className='Demo.Tests.GuardCases', name=method)
        entries = ET.SubElement(root, 'TestEntries'); ET.SubElement(entries, 'TestEntry', testId=tid, executionId=eid)
        results = ET.SubElement(root, 'Results'); ET.SubElement(results, 'UnitTestResult', testId=tid, executionId=eid, testName=display, outcome='Passed')
        summary = ET.SubElement(root, 'ResultSummary', outcome='Completed')
        ET.SubElement(summary, 'Counters', total='1', executed='1', passed='1', failed='0', notExecuted='0')
        self.xml = root; self.write(self.trx, ET.tostring(root)); os.utime(self.root / self.trx, (self.now, self.now))

    def validate(self, **changes):
        args = dict(root=self.root, phase=self.phase, name=self.trx, expected_head=HEAD, observed_head=HEAD, now=self.now + 1)
        args.update(changes); return guard.validate_trx(**args)

    def rewrite_xml(self):
        self.write(self.trx, ET.tostring(self.xml)); os.utime(self.root / self.trx, (self.now, self.now))

    def test_valid_source_and_single_exact_phase_are_accepted_without_runtime_claim(self):
        result = guard.source_custody(self.root, HEAD, HEAD, True, FULL)
        self.assertFalse(result['runtimeAcceptance']); self.assertEqual(14, result['phases'])
        self.assertEqual(1, self.validate()['passingRows'])

    def test_unknown_phase_is_refused(self):
        with self.assertRaises(guard.GuardError): self.validate(phase='foreign')
        with self.assertRaises(guard.GuardError): guard.admission('foreign', HEAD, HEAD, 4 * 1024 ** 3, [], self.now)

    def test_missing_and_zero_trx_are_refused(self):
        file = self.root / self.trx; file.unlink()
        with self.assertRaises(OSError): self.validate()
        self.write(self.trx, b'')
        with self.assertRaises(guard.GuardError): self.validate()

    def test_stale_head_is_refused_in_all_interfaces(self):
        with self.assertRaises(guard.GuardError): self.validate(observed_head='3' * 40)
        with self.assertRaises(guard.GuardError): guard.source_custody(self.root, HEAD, '3' * 40, True, FULL)
        with self.assertRaises(guard.GuardError): guard.admission('build', HEAD, '3' * 40, 4 * 1024 ** 3, [], self.now)

    def test_path_escape_or_foreign_trx_location_is_refused(self):
        for path in ('../outside.trx', '/outside.trx', 'C:/outside.trx', 'TestResults/fdm/endpoint/endpoint.trx'):
            with self.assertRaises(guard.GuardError): self.validate(name=path)

    def test_duplicate_result_case_is_refused(self):
        original = copy.deepcopy(self.xml)
        results = self.xml.find('Results'); results.append(copy.deepcopy(results[0])); self.rewrite_xml()
        with self.assertRaises(guard.GuardError): self.validate()
        self.xml = original
        definition = copy.deepcopy(self.xml.find('TestDefinitions')[0])
        tid, eid = str(uuid.uuid4()), str(uuid.uuid4())
        definition.set('id', tid); definition.find('Execution').set('id', eid)
        self.xml.find('TestDefinitions').append(definition)
        ET.SubElement(self.xml.find('TestEntries'), 'TestEntry', testId=tid, executionId=eid)
        result = copy.deepcopy(self.xml.find('Results')[0])
        result.set('testId', tid); result.set('executionId', eid); self.xml.find('Results').append(result)
        for field in ('total', 'executed', 'passed'): self.xml.find('ResultSummary/Counters').set(field, '2')
        self.rewrite_xml()
        with self.assertRaises(guard.GuardError): self.validate()

    def test_foreign_phase_roster_is_refused(self):
        foreign = self.manifest['phases'][1]['expectedPassingRows'][0]
        test = self.xml.find('TestDefinitions')[0]
        display = foreign['class'] + '.' + foreign['method']
        test.set('name', display); test.find('TestMethod').set('name', foreign['method'])
        self.xml.find('Results')[0].set('testName', display); self.rewrite_xml()
        with self.assertRaises(guard.GuardError): self.validate()

    def test_late_artifact_and_preexisting_artifact_custody_are_refused(self):
        with self.assertRaises(guard.GuardError): self.validate(now=self.receipt['expiresEpoch'] + 1)
        os.utime(self.root / self.trx, (self.receipt['observedEpoch'] - 1,) * 2)
        with self.assertRaises(guard.GuardError): self.validate()
        with self.assertRaises(guard.GuardError): guard.write_receipt(self.root, 'margin', self.receipt)

    def test_admission_refuses_low_memory_and_foreign_dotnet(self):
        with self.assertRaises(guard.GuardError): guard.admission('build', HEAD, HEAD, 3072 * 1024 ** 2 - 1, [], self.now)
        with self.assertRaises(guard.GuardError): guard.admission('build', HEAD, HEAD, 4 * 1024 ** 3, [{'pid': 1}], self.now)

    def test_swapped_display_execution_and_entry_joins_are_refused(self):
        original = copy.deepcopy(self.xml)
        for field, value in [('testName', 'Demo.Tests.GuardCases.Synthetic_other'), ('executionId', str(uuid.uuid4())), ('testId', str(uuid.uuid4()))]:
            self.xml = copy.deepcopy(original); self.xml.find('Results')[0].set(field, value); self.rewrite_xml()
            with self.assertRaises(guard.GuardError): self.validate()

    def test_failed_skipped_error_and_bad_counters_are_refused(self):
        original = copy.deepcopy(self.xml)
        for outcome in ('Failed', 'NotExecuted', 'Skipped'):
            self.xml = copy.deepcopy(original); self.xml.find('Results')[0].set('outcome', outcome); self.rewrite_xml()
            with self.assertRaises(guard.GuardError): self.validate()
        self.xml = copy.deepcopy(original); ET.SubElement(self.xml.find('Results')[0], 'ErrorInfo'); self.rewrite_xml()
        with self.assertRaises(guard.GuardError): self.validate()
        self.xml = copy.deepcopy(original); self.xml.find('ResultSummary/Counters').set('total', '2'); self.rewrite_xml()
        with self.assertRaises(guard.GuardError): self.validate()

    def test_empty_duplicate_unknown_manifest_phase_and_duplicate_case_are_refused(self):
        original = copy.deepcopy(self.manifest)
        for change in (lambda m:m['phases'][0].update(id='foreign'),
                       lambda m:m['phases'][0].update(expectedPassingRows=[]),
                       lambda m:m['phases'][0]['expectedPassingRows'].append(copy.deepcopy(m['phases'][0]['expectedPassingRows'][0])),
                       lambda m:m['phases'].__setitem__(1, copy.deepcopy(m['phases'][0]))):
            manifest = copy.deepcopy(original); change(manifest); self.write(guard.PHASE_MANIFEST, json.dumps(manifest).encode())
            with self.assertRaises(guard.GuardError): guard.phase_manifest(self.root)

    def test_manifest_changed_after_admission_is_refused(self):
        self.manifest['phases'][0]['filter'] += '|FullyQualifiedName~Synthetic_extra'
        self.write(guard.PHASE_MANIFEST, json.dumps(self.manifest).encode())
        with self.assertRaises(guard.GuardError): self.validate()

    def test_source_byte_pin_worker_pin_or_coverage_tampering_is_refused(self):
        for path in (self.worker, self.reference, next(iter(guard.COVERAGE_PINS))):
            file = self.root / path; original = file.read_bytes(); file.write_bytes(original + b'changed')
            with self.assertRaises(guard.GuardError): guard.source_custody(self.root, HEAD, HEAD, True, FULL)
            file.write_bytes(original)

    def test_old_full_baseline_and_dirty_source_are_refused(self):
        with self.assertRaises(guard.GuardError): guard.source_custody(self.root, HEAD, HEAD, True, guard.BASELINE_FULL_WORKFLOW)
        with self.assertRaises(guard.GuardError): guard.source_custody(self.root, HEAD, HEAD, False, FULL)

    def test_symlink_artifact_is_refused_without_external_read(self):
        file = self.root / self.trx; outside = Path(self.temp.name) / 'outside.trx'
        outside.write_bytes(file.read_bytes()); file.unlink(); file.symlink_to(outside)
        with self.assertRaises(guard.GuardError): self.validate()

    def test_source_path_escape_is_refused(self):
        self.source['files'][0]['path'] = '../outside'
        self.write(guard.SOURCE_MANIFEST, json.dumps(self.source).encode())
        with self.assertRaises(guard.GuardError): guard.source_custody(self.root, HEAD, HEAD, True, FULL)

    def test_duplicate_json_keys_are_refused(self):
        data = (self.root / guard.PHASE_MANIFEST).read_bytes()
        self.write(guard.PHASE_MANIFEST, data.replace(b'"schemaVersion": 1', b'"schemaVersion": 1, "schemaVersion": 1'))
        with self.assertRaises(guard.GuardError): guard.phase_manifest(self.root)

    def refuses_before_native_admission(self):
        arguments = ['fdm_validation_guards.py', 'admission', '--root', str(self.root),
                     '--expected-head', HEAD, '--phase', 'build', '--full-workflow-sha', FULL]
        with mock.patch('sys.argv', arguments), mock.patch.object(guard, 'observe_git', return_value=(HEAD, True)), \
                mock.patch.object(guard, 'observe_linux') as memory_probe, mock.patch('sys.stderr', new_callable=io.StringIO) as error:
            self.assertEqual(2, guard.main())
            self.assertEqual('FDM validation proof rejected\n', error.getvalue())
            memory_probe.assert_not_called()
        self.assertFalse((self.root / 'TestResults/fdm/build/admission.json').exists())

    def test_missing_startup_proof_file_refuses_before_native_admission(self):
        (self.root / guard.STARTUP_PROOF).unlink()
        self.refuses_before_native_admission()

    def test_unpinned_existing_startup_proof_refuses_before_native_admission(self):
        self.source['files'] = [entry for entry in self.source['files'] if entry['path'] != guard.STARTUP_PROOF]
        self.write(guard.SOURCE_MANIFEST, json.dumps(self.source).encode())
        self.refuses_before_native_admission()

    def test_tampered_startup_proof_refuses_before_native_admission(self):
        file = self.root / guard.STARTUP_PROOF; file.write_bytes(file.read_bytes() + b'# changed\n')
        self.refuses_before_native_admission()

    def test_wrong_startup_proof_checkout_policy_refuses_before_native_admission(self):
        entry = next(entry for entry in self.source['files'] if entry['path'] == guard.STARTUP_PROOF)
        entry['checkoutPolicy'] = 'opaque'
        self.write(guard.SOURCE_MANIFEST, json.dumps(self.source).encode())
        self.refuses_before_native_admission()

    def test_empty_pinned_startup_proof_refuses_before_native_admission(self):
        self.write(guard.STARTUP_PROOF, b'')
        entry = next(entry for entry in self.source['files'] if entry['path'] == guard.STARTUP_PROOF)
        entry.update(bytes=0, sha256=guard.sha(b''))
        self.write(guard.SOURCE_MANIFEST, json.dumps(self.source).encode())
        self.refuses_before_native_admission()

    def test_other_script_path_is_not_admitted_by_startup_exception(self):
        path = 'scripts/OtherStartupProof.ps1'; data = b'# Synthetic inert extra fixture\n'
        self.write(path, data)
        self.source['files'].append(dict(path=path, bytes=len(data), sha256=guard.sha(data), checkoutPolicy='lf'))
        self.write(guard.SOURCE_MANIFEST, json.dumps(self.source).encode())
        self.refuses_before_native_admission()


if __name__ == '__main__':
    unittest.main(verbosity=2)
