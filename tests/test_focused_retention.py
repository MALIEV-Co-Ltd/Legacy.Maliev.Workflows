import copy,importlib.util,sys,unittest,xml.etree.ElementTree as ET
from pathlib import Path
base=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(base/'scripts'))
path=base/'scripts/retain_fdm_journal_focused.py'
spec=importlib.util.spec_from_file_location('focused',path);focused=importlib.util.module_from_spec(spec);spec.loader.exec_module(focused)
raw=(base/'tests/fixtures/journal-focused-native-shape.trx').read_bytes()
ns={'t':'http://microsoft.com/schemas/VisualStudio/TeamTest/2010'}
class FocusedRetentionTests(unittest.TestCase):
    def test_actual_one_fact_roster_transforms_and_preserves_identity(self):
        data=focused.transform(raw);doc=ET.fromstring(data)
        self.assertEqual(doc.attrib['evidenceSchema'],'privacy-safe-test-roster-trx/v2')
        self.assertEqual(len(list(doc.find('Results'))),1)
        self.assertEqual(doc.find('TestDefinitions/UnitTest/TestMethod').attrib['className'],focused.CLASS)

    def test_extra_or_duplicate_definition_is_rejected(self):
        doc=ET.fromstring(raw);defs=doc.find('t:TestDefinitions',ns);defs.append(copy.deepcopy(list(defs)[0]))
        with self.assertRaises(ValueError):focused.transform(ET.tostring(doc))

    def test_execution_join_mismatch_is_rejected(self):
        doc=ET.fromstring(raw);doc.find('t:TestEntries/t:TestEntry',ns).set('executionId','00000000-0000-0000-0000-000000000001')
        with self.assertRaises(ValueError):focused.transform(ET.tostring(doc))

    def test_nonpassing_result_or_false_counter_is_rejected(self):
        for failure in ('outcome','counter'):
            doc=ET.fromstring(raw)
            if failure=='outcome':doc.find('t:Results/t:UnitTestResult',ns).set('outcome','Failed')
            else:doc.find('t:ResultSummary/t:Counters',ns).set('passed','0')
            with self.subTest(failure=failure),self.assertRaises(ValueError):focused.transform(ET.tostring(doc))

    def test_unrelated_fact_cannot_supply_journal_focused_evidence(self):
        doc=ET.fromstring(raw);doc.find('t:TestDefinitions/t:UnitTest/t:TestMethod',ns).set('name','DifferentFact')
        with self.assertRaises(ValueError):focused.transform(ET.tostring(doc))

    def test_private_output_is_not_exported_in_success_roster(self):
        doc=ET.fromstring(raw);result=doc.find('t:Results/t:UnitTestResult',ns);output=ET.SubElement(result,'{'+ns['t']+'}Output');ET.SubElement(output,'{'+ns['t']+'}StdOut').text='SYNTHETIC-PRIVATE-NOT-EXPORTABLE'
        self.assertNotIn(b'SYNTHETIC-PRIVATE-NOT-EXPORTABLE',focused.transform(ET.tostring(doc)))

    def test_passed_fact_with_failed_run_summary_is_rejected(self):
        for outcome in ('Failed','Error','Aborted','InProgress','Warning',''):
            doc=ET.fromstring(raw);doc.find('t:ResultSummary',ns).set('outcome',outcome)
            with self.subTest(outcome=outcome),self.assertRaises(ValueError):focused.transform(ET.tostring(doc))

    def test_summary_error_info_cannot_be_stripped_into_success(self):
        doc=ET.fromstring(raw);ET.SubElement(doc.find('t:ResultSummary',ns),'{'+ns['t']+'}ErrorInfo')
        with self.assertRaises(ValueError):focused.transform(ET.tostring(doc))

    def test_run_diagnostics_adverse_or_unknown_are_rejected(self):
        for outcome in ('Error','Warning','Aborted','Passed','Information',''):
            doc=ET.fromstring(raw);infos=ET.SubElement(doc.find('t:ResultSummary',ns),'{'+ns['t']+'}RunInfos');ET.SubElement(infos,'{'+ns['t']+'}RunInfo',{'outcome':outcome})
            with self.subTest(outcome=outcome),self.assertRaises(ValueError):focused.transform(ET.tostring(doc))

    def test_missing_unknown_or_nonzero_adverse_counters_are_rejected(self):
        for kind in ('missing','unknown','adverse'):
            doc=ET.fromstring(raw);counter=doc.find('t:ResultSummary/t:Counters',ns)
            if kind=='missing':del counter.attrib['error']
            elif kind=='unknown':counter.set('inventedCounter','0')
            else:counter.set('error','1')
            with self.subTest(kind=kind),self.assertRaises(ValueError):focused.transform(ET.tostring(doc))
if __name__=='__main__':unittest.main(verbosity=2)
