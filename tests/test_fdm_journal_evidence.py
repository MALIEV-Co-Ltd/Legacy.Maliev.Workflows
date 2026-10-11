import importlib.util
import json
from pathlib import Path
import unittest
import contextlib
import io
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))

spec = importlib.util.spec_from_file_location('journal', Path(__file__).parents[1] / 'scripts/fdm_journal_evidence.py')
journal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(journal)

class OriginalJournalTests(unittest.TestCase):
    def row(self, phase, parts=1, at='2026-10-11T01:00:01.1234567+00:00'):
        return {'atUtc': at, 'phase': phase, 'parts': parts}

    def consume(self, rows):
        return journal.consume(('\n'.join(json.dumps(row) for row in rows)+'\n').encode(), '2026-10-11T01:00:00Z', '2026-10-11T01:01:00Z')

    def test_original_dotnet_wire_and_dynamic_handler_are_consumed(self):
        rows=self.consume([self.row('fdm_quote_request_start'), self.row('http_GetOrderTotal_response_200'), self.row('fdm_quote_request_complete')])
        result=journal.assess(rows,['fdm_quote_request_start','fdm_quote_request_complete'],'normal')
        self.assertTrue(result['fixedOperationsComplete'])
        self.assertFalse(result['journalOperationsComplete'])
        self.assertEqual(result['networkDiagnostics'],'unknown')
        self.assertFalse(result['runtimeAcceptance'])
        self.assertFalse(result['headCustodyVerified'])

    def test_seven_event_substitution_cannot_cover_original_required_labels(self):
        with self.assertRaises(journal.JournalError):
            journal.assess(self.consume([self.row('pdf_case_start')]),['fdm_quote_request_complete'],'normal')

    def test_completion_without_start_is_rejected(self):
        with self.assertRaises(journal.JournalError):
            journal.assess(self.consume([self.row('fdm_quote_request_complete')]),['fdm_quote_request_complete'],'normal')

    def test_interrupted_operation_is_retained_but_cannot_complete(self):
        with self.assertRaises(journal.JournalError):
            journal.assess(self.consume([self.row('fdm_quote_request_start')]),['fdm_quote_request_start'],'normal')

    def test_boolean_parts_and_unknown_dynamic_handlers_are_rejected(self):
        for row in [self.row('pdf_case_start',True),self.row('http_CustomerEmail_response_200')]:
            with self.subTest(row=row),self.assertRaises(journal.JournalError):self.consume([row])

    def test_customer_fields_and_duplicate_json_keys_are_rejected(self):
        with self.assertRaises(journal.JournalError):self.consume([{**self.row('pdf_case_start'),'customer':'synthetic'}])
        with self.assertRaises(journal.JournalError):journal.consume(b'{"atUtc":"2026-10-11T01:00:01Z","phase":"pdf_case_start","parts":1,"parts":2}', '2026-10-11T01:00:00Z','2026-10-11T01:01:00Z')

    def test_seventh_tick_outside_interval_is_rejected(self):
        with self.assertRaises(journal.JournalError):
            journal.consume(json.dumps(self.row('pdf_case_start',at='2026-10-11T01:00:01.1234568Z')).encode(),'2026-10-11T01:00:00Z','2026-10-11T01:00:01.1234567Z')

    def test_failed_setup_cleanup_is_diagnostic_not_success(self):
        rows=self.consume([self.row('loaded_setup_start'),self.row('failed_setup_cleanup_start'),self.row('failed_setup_cleanup_failed')])
        result=journal.assess(rows,['failed_setup_cleanup_start','failed_setup_cleanup_failed'],'setup-failure')
        self.assertFalse(result['journalOperationsComplete'])
        self.assertFalse(result['activationPermitted'])

    def test_cleanup_both_outcomes_or_wrong_order_are_rejected(self):
        for phases in [('failed_setup_cleanup_start','failed_setup_cleanup_complete','failed_setup_cleanup_failed'),('failed_setup_cleanup_complete','failed_setup_cleanup_start')]:
            with self.subTest(phases=phases),self.assertRaises(journal.JournalError):journal.assess(self.consume([self.row(p) for p in phases]),['failed_setup_cleanup_start'],'setup-failure')

    def test_cleanup_exact_same_part_attempt_completes_fixed_operation(self):
        rows=self.consume([self.row('failed_setup_cleanup_start',2),self.row('failed_setup_cleanup_complete',2)])
        result=journal.assess(rows,['failed_setup_cleanup_start','failed_setup_cleanup_complete'],'setup-failure')
        self.assertTrue(result['fixedOperationsComplete'])
        self.assertFalse(result['journalOperationsComplete'])

    def test_cleanup_mismatched_part_outcome_is_rejected(self):
        rows=self.consume([self.row('failed_setup_cleanup_start',1),self.row('failed_setup_cleanup_complete',2)])
        with self.assertRaises(journal.JournalError):journal.assess(rows,['failed_setup_cleanup_start'],'setup-failure')

    def test_cleanup_duplicate_outcome_or_overlapping_start_is_rejected(self):
        for phases in [('failed_setup_cleanup_start','failed_setup_cleanup_complete','failed_setup_cleanup_complete'),('failed_setup_cleanup_start','failed_setup_cleanup_start','failed_setup_cleanup_complete')]:
            with self.subTest(phases=phases),self.assertRaises(journal.JournalError):journal.assess(self.consume([self.row(p) for p in phases]),['failed_setup_cleanup_start'],'setup-failure')

    def test_cleanup_multiple_same_part_sequential_attempts_are_supported(self):
        phases=['failed_setup_cleanup_start','failed_setup_cleanup_complete']*2
        result=journal.assess(self.consume([self.row(p) for p in phases]),['failed_setup_cleanup_start','failed_setup_cleanup_complete'],'setup-failure')
        self.assertTrue(result['fixedOperationsComplete'])

    def test_cleanup_mixed_outcomes_across_valid_attempts_are_diagnostic_failure(self):
        rows=self.consume([self.row('failed_setup_cleanup_start',1),self.row('failed_setup_cleanup_start',2),self.row('failed_setup_cleanup_complete',1),self.row('failed_setup_cleanup_failed',2)])
        result=journal.assess(rows,['failed_setup_cleanup_start','failed_setup_cleanup_complete','failed_setup_cleanup_failed'],'setup-failure')
        self.assertFalse(result['fixedOperationsComplete'])
        self.assertFalse(result['journalOperationsComplete'])
        self.assertFalse(result['runtimeAcceptance'])

    def test_http_failed_or_error_response_is_adverse_without_pairing(self):
        for phase in ['http_GetEstimate_failed','http_GetEstimate_response_500','http_UploadFile_response_404']:
            rows=self.consume([self.row('pdf_case_start'),self.row(phase)])
            result=journal.assess(rows,['pdf_case_start'],'normal')
            self.assertEqual(result['networkDiagnostics'],'adverse')
            self.assertFalse(result['journalOperationsComplete'])

    def test_capped_http_requests_do_not_require_unemitted_response(self):
        rows=self.consume([self.row('pdf_case_start')]+[self.row('http_GetEstimate_request')]*32)
        result=journal.assess(rows,['pdf_case_start'],'normal')
        self.assertEqual(result['networkDiagnostics'],'unknown')
        self.assertFalse(result['journalOperationsComplete'])
        self.assertFalse(result['runtimeAcceptance'])

    def test_missing_http_observations_remain_unknown(self):
        result=journal.assess(self.consume([self.row('pdf_case_start')]),['pdf_case_start'],'normal')
        self.assertEqual(result['networkDiagnostics'],'unknown')
        self.assertFalse(result['journalOperationsComplete'])

    def test_public_diagnostic_contract_keeps_custody_and_acceptance_false(self):
        data=(json.dumps(self.row('pdf_case_start'))+'\n').encode()
        result=journal.diagnose(data,'2026-10-11T01:00:00Z','2026-10-11T01:01:00Z',['pdf_case_start'],'normal')
        self.assertEqual(set(result),{'schema','journalSha256','journalBytes','fixedOperationsComplete','journalOperationsComplete','networkDiagnostics','networkCompleteness','observations','headCustodyVerified','runtimeAcceptance','activationPermitted'})
        self.assertEqual(result['schema'],'fdm-journal-diagnostic/v1')
        self.assertEqual(result['journalBytes'],len(data))
        self.assertFalse(result['headCustodyVerified'])
        self.assertFalse(result['runtimeAcceptance'])
        self.assertFalse(result['activationPermitted'])

    def test_cli_consumes_retained_original_journal_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'TestResults/readiness/pipeline-progress.jsonl'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(self.row('pdf_case_start'))+'\n',encoding='utf-8')
            out,error=io.StringIO(),io.StringIO()
            with contextlib.redirect_stdout(out),contextlib.redirect_stderr(error):
                code=journal.main(['--root',directory,'--journal','TestResults/readiness/pipeline-progress.jsonl','--started-utc','2026-10-11T01:00:00Z','--finished-utc','2026-10-11T01:01:00Z','--required-fixed','pdf_case_start','--scenario','normal'])
            self.assertEqual(code,0)
            self.assertEqual(error.getvalue(),'')
            self.assertFalse(json.loads(out.getvalue())['journalOperationsComplete'])

    def test_cli_argument_failure_is_generic_and_does_not_echo_values(self):
        out,error=io.StringIO(),io.StringIO()
        with contextlib.redirect_stdout(out),contextlib.redirect_stderr(error):
            code=journal.main(['--synthetic-private-value'])
        self.assertEqual(code,2)
        self.assertEqual(out.getvalue(),'')
        self.assertEqual(error.getvalue(),'FDM journal evidence rejected\n')

if __name__ == '__main__': unittest.main(verbosity=2)
