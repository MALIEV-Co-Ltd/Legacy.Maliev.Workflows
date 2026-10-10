"""Synthetic-only privacy and custody controls; no SDK, git or native workers."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('retainer', ROOT/'scripts/retain_workflows_test_evidence.py')
retainer = importlib.util.module_from_spec(spec); spec.loader.exec_module(retainer)
NAMES = {'test_case_' + str(i) for i in range(24)}


def diagnostics():
    rows = [name + ' (__main__.FdmGuardTests.' + name + ') ... ok' for name in sorted(NAMES)]
    return '\n'.join(rows + ['', '-'*70, 'Ran 24 tests in 0.1s', '', 'OK', ''])


def trx(value, outcome='Passed'):
    root = ET.Element('TestRun'); definitions = ET.SubElement(root, 'TestDefinitions')
    test = ET.SubElement(definitions, 'UnitTest', id='case-a', name='synthetic display')
    ET.SubElement(test, 'Execution', id='exec-a')
    ET.SubElement(test, 'TestMethod', className=retainer.CLASS, name=retainer.METHOD)
    entries = ET.SubElement(root, 'TestEntries'); ET.SubElement(entries, 'TestEntry', testId='case-a', executionId='exec-a')
    results = ET.SubElement(root, 'Results'); result = ET.SubElement(results, 'UnitTestResult', testId='case-a', executionId='exec-a', testName='synthetic display', outcome=outcome)
    output = ET.SubElement(result, 'Output'); ET.SubElement(output, 'StdOut').text = 'fdm-python/v1 begin\n' + value + 'fdm-python/v1 end'
    summary = ET.SubElement(root, 'ResultSummary', outcome='Completed')
    ET.SubElement(summary, 'Counters', total='1', executed='1', passed='1', failed='0', error='0', timeout='0', aborted='0', inconclusive='0', passedButRunAborted='0', notRunnable='0', notExecuted='0', disconnected='0', warning='0', completed='1', inProgress='0', pending='0')
    return ET.tostring(root)


class RetentionTests(unittest.TestCase):
    def test_actual_all24_diagnostics_are_retained_verbatim(self):
        value = diagnostics(); self.assertEqual(value.encode(), retainer.python_diagnostics(trx(value), NAMES))

    def test_arbitrary_payload_after_valid_summary_is_refused(self):
        with self.assertRaises(ValueError): retainer.python_diagnostics(trx(diagnostics() + 'private-payload\n'), NAMES)

    def test_missing_case_is_refused(self):
        value = diagnostics().split('\n', 1)[1]
        with self.assertRaises(ValueError): retainer.python_diagnostics(trx(value), NAMES)

    def test_duplicate_case_is_refused(self):
        value = diagnostics(); value = value.split('\n', 1)[0] + '\n' + value
        with self.assertRaises(ValueError): retainer.python_diagnostics(trx(value), NAMES)

    def test_unknown_case_is_refused(self):
        value = diagnostics().replace('test_case_0 ', 'test_foreign_case ', 1)
        with self.assertRaises(ValueError): retainer.python_diagnostics(trx(value), NAMES)

    def test_mismatched_descriptor_case_identity_is_refused(self):
        value = diagnostics().replace('FdmGuardTests.test_case_0)', 'FdmGuardTests.private_sentinel)', 1)
        with self.assertRaises(ValueError): retainer.python_diagnostics(trx(value), NAMES)

    def test_skipped_case_is_refused(self):
        value = diagnostics().replace(' ... ok', " ... skipped 'fixture'", 1)
        with self.assertRaises(ValueError): retainer.python_diagnostics(trx(value), NAMES)

    def test_failed_adapter_cannot_certify_successful_diagnostics(self):
        with self.assertRaises(ValueError): retainer.python_diagnostics(trx(diagnostics(), 'Failed'), NAMES)

    def test_wrong_count_summary_is_refused(self):
        with self.assertRaises(ValueError): retainer.python_diagnostics(trx(diagnostics().replace('Ran 24', 'Ran 23')), NAMES)

    def test_multiple_diagnostic_blocks_are_refused(self):
        xml = ET.fromstring(trx(diagnostics())); node = next(n for n in xml.iter() if n.tag == 'StdOut'); node.text *= 2
        with self.assertRaises(ValueError): retainer.python_diagnostics(ET.tostring(xml), NAMES)

    def test_oversized_output_is_refused(self):
        with self.assertRaises(ValueError): retainer.python_diagnostics(trx('x'*300000), NAMES)

    def test_private_output_is_removed_from_actual_roster_retention(self):
        raw = trx(diagnostics()); kept = retainer.producer.outcome_trx(raw)
        self.assertNotIn(b'fdm-python/v1', kept)
        self.assertNotIn(b'synthetic display', kept)
        self.assertIn(b'privacy-safe-test-roster-trx/v2', kept)
        self.assertIn(b'case-a', kept)
        self.assertIn(b'exec-a', kept)

    def test_source_path_escape_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError): retainer.read(Path(temp), '../outside')

    def test_source_link_is_refused_without_reading_payload(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root/'source').write_bytes(b'private-payload')
            with mock.patch.object(Path, 'is_symlink', return_value=True):
                with self.assertRaises(ValueError): retainer.read(root, 'source')

    def test_wrong_observed_head_refuses_before_writing(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(retainer, 'head', return_value='3'*40):
            root = Path(temp)
            with self.assertRaises(ValueError): retainer.retain(root, '1'*40, '2'*40, '1', '1', '4'*40)
            self.assertFalse((root/retainer.RETAINED).exists())

    def test_absent_baseline_reports_are_explicitly_unavailable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); controls = root/retainer.CONTROL_PATH; controls.mkdir()
            for path in ('.github/workflows/validate.yml', '.github/workflows/dotnet-validate.yml', 'actions/dotnet-validate/action.yml'):
                target = root/path; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(b'# synthetic gate input\n')
            with mock.patch.object(retainer, '__file__', str(controls/'scripts/retain_workflows_test_evidence.py')), \
                    mock.patch.object(retainer, 'head', side_effect=lambda p: retainer.BASELINE if p == root else '2'*40):
                result = retainer.retain(root,retainer.BASELINE,'2'*40,'1','1','4'*40)
            self.assertFalse(result['trxAvailable'])
            self.assertFalse(result['coverageAvailable'])
            self.assertFalse(result['coverageGateAvailable'])
            self.assertFalse(result['acceptanceCertified'])

    def test_existing_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); controls = root/retainer.CONTROL_PATH; controls.mkdir()
            target = root/retainer.RETAINED; target.mkdir(parents=True); marker = target/'preserved'; marker.write_bytes(b'own evidence')
            with mock.patch.object(retainer, '__file__', str(controls/'scripts/retain_workflows_test_evidence.py')), \
                    mock.patch.object(retainer, 'head', side_effect=lambda p: retainer.BASELINE if p == root else '2'*40):
                with self.assertRaises(ValueError): retainer.retain(root,retainer.BASELINE,'2'*40,'1','1','4'*40)
            self.assertEqual(b'own evidence',marker.read_bytes())


if __name__ == '__main__':
    unittest.main(verbosity=2)
