import copy
import hashlib
import importlib.util
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('roster_evidence',ROOT/'scripts/preserve_validation_evidence.py')
evidence=importlib.util.module_from_spec(spec);spec.loader.exec_module(evidence)
SCHEMA='privacy-safe-test-roster-trx/v2'

def fixture(names=('Synthetic.Method(value: private-canary)',)):
    root=ET.Element('TestRun', {'user':'private-canary'})
    definitions=ET.SubElement(root,'TestDefinitions');entries=ET.SubElement(root,'TestEntries');results=ET.SubElement(root,'Results')
    for index,name in enumerate(names):
        test_id='test-'+str(index);execution_id='execution-'+str(index)
        definition=ET.SubElement(definitions,'UnitTest',{'id':test_id,'name':name,'storage':'private-canary'})
        ET.SubElement(definition,'Execution',{'id':execution_id})
        ET.SubElement(definition,'TestMethod',{'className':'Legacy.Maliev.AuthService.Tests.SyntheticTests','name':'Method','codeBase':'private-canary','adapterTypeName':'private-canary'})
        ET.SubElement(entries,'TestEntry',{'testId':test_id,'executionId':execution_id,'testListId':'list-1'})
        result=ET.SubElement(results,'UnitTestResult',{'testId':test_id,'executionId':execution_id,'testName':name,'outcome':'Passed','computerName':'private-canary'})
        ET.SubElement(ET.SubElement(result,'Output'),'StdOut').text='private-canary'
    ET.SubElement(ET.SubElement(root,'ResultSummary'),'Counters',{'total':str(len(names)),'passed':str(len(names)),'failed':'0'})
    return root

def export(root):return evidence.outcome_trx(ET.tostring(root,encoding='utf-8'))

class RosterIdentityTests(unittest.TestCase):
    def test_full_roster_preserves_method_and_exact_three_way_join_without_private_values(self):
        root=fixture();raw=export(root);output=ET.fromstring(raw)
        self.assertEqual(SCHEMA,output.get('evidenceSchema'))
        definition=output.find('TestDefinitions/UnitTest');entry=output.find('TestEntries/TestEntry');result=output.find('Results/UnitTestResult')
        self.assertEqual('test-0',definition.get('id'));self.assertEqual(definition.get('id'),entry.get('testId'));self.assertEqual(entry.get('testId'),result.get('testId'))
        self.assertEqual(definition.find('Execution').get('id'),entry.get('executionId'));self.assertEqual(entry.get('executionId'),result.get('executionId'))
        self.assertEqual('Method',definition.find('TestMethod').get('name'));self.assertEqual('Legacy.Maliev.AuthService.Tests.SyntheticTests',definition.find('TestMethod').get('className'))
        expected=hashlib.sha256(b'trx-display/v1\0Synthetic.Method(value: private-canary)').hexdigest()
        self.assertEqual(expected,definition.get('displayNameSha256'));self.assertEqual(expected,result.get('displayNameSha256'))
        self.assertNotIn(b'private-canary',raw);self.assertNotIn(b'testName=',raw);self.assertNotIn(b'codeBase=',raw);self.assertNotIn(b'Output',raw)
    def test_same_method_theory_rows_keep_distinct_case_hashes(self):
        output=ET.fromstring(export(fixture(('Method(value: one)','Method(value: two)'))))
        definitions=output.findall('TestDefinitions/UnitTest');self.assertEqual(2,len(definitions))
        self.assertNotEqual(definitions[0].get('displayNameSha256'),definitions[1].get('displayNameSha256'))
        self.assertEqual([d.get('displayNameSha256') for d in definitions],[r.get('displayNameSha256') for r in output.findall('Results/UnitTestResult')])
    def test_namespaced_trx_keeps_roster(self):
        root=fixture()
        for node in root.iter():node.tag='{http://microsoft.com/schemas/VisualStudio/TeamTest/2010}'+node.tag
        self.assertEqual(SCHEMA,ET.fromstring(export(root)).get('evidenceSchema'))
    def test_each_missing_roster_fails_closed(self):
        for section in ('TestDefinitions','TestEntries'):
            root=fixture();root.remove(root.find(section))
            with self.subTest(section=section),self.assertRaises(evidence.EvidenceFailure):export(root)
    def test_duplicate_definition_entry_result_or_section_fails_closed(self):
        for path in ('TestDefinitions/UnitTest','TestEntries/TestEntry','Results/UnitTestResult'):
            root=fixture();node=root.find(path);root.find(path.split('/')[0]).append(copy.deepcopy(node))
            with self.subTest(path=path),self.assertRaises(evidence.EvidenceFailure):export(root)
        for section in ('TestDefinitions','TestEntries','Results'):
            root=fixture();root.append(copy.deepcopy(root.find(section)))
            with self.subTest(section=section),self.assertRaises(evidence.EvidenceFailure):export(root)
    def test_missing_or_foreign_join_members_fail_closed(self):
        for path,attribute in (('TestDefinitions/UnitTest','id'),('TestDefinitions/UnitTest/Execution','id'),('TestEntries/TestEntry','testId'),('TestEntries/TestEntry','executionId'),('Results/UnitTestResult','testId'),('Results/UnitTestResult','executionId')):
            for replacement in (None,'unknown'):
                root=fixture();node=root.find(path)
                if replacement is None:node.attrib.pop(attribute)
                else:node.set(attribute,replacement)
                with self.subTest(path=path,attribute=attribute,replacement=replacement),self.assertRaises(evidence.EvidenceFailure):export(root)
    def test_orphan_definition_or_entry_fails_closed(self):
        for section in ('TestDefinitions','TestEntries'):
            root=fixture(('Method(one)','Method(two)'));node=root.find(section);node.remove(node[-1])
            with self.subTest(section=section),self.assertRaises(evidence.EvidenceFailure):export(root)
    def test_swapped_same_method_theory_result_pairs_fail_closed(self):
        root=fixture(('Method(value: one)','Method(value: two)'));results=root.findall('Results/UnitTestResult')
        for attribute in ('testId','executionId'):
            first,second=results[0].get(attribute),results[1].get(attribute);results[0].set(attribute,second);results[1].set(attribute,first)
        with self.assertRaises(evidence.EvidenceFailure):export(root)
    def test_display_identity_is_mandatory_and_exact_ordinal(self):
        for value in (None,'synthetic.method(value: private-canary)','Synthetic.Method(value: private-canary) '):
            root=fixture();node=root.find('Results/UnitTestResult')
            if value is None:node.attrib.pop('testName')
            else:node.set('testName',value)
            with self.subTest(value=value),self.assertRaises(evidence.EvidenceFailure):export(root)
    def test_static_method_identity_rejects_parameters_paths_and_unbounded_values(self):
        for key,value in (('className','Customer(address: private-canary)'),('className','C:/private-canary'),('name','Method(value: private-canary)'),('name','private-canary'),('name','a'*513)):
            root=fixture();root.find('TestDefinitions/UnitTest/TestMethod').set(key,value)
            with self.subTest(key=key,value=value),self.assertRaises(evidence.EvidenceFailure):export(root)
    def test_duplicate_or_missing_method_execution_nodes_fail_closed(self):
        for child in ('TestMethod','Execution'):
            for duplicate in (False,True):
                root=fixture();definition=root.find('TestDefinitions/UnitTest');node=definition.find(child)
                if duplicate:definition.append(copy.deepcopy(node))
                else:definition.remove(node)
                with self.subTest(child=child,duplicate=duplicate),self.assertRaises(evidence.EvidenceFailure):export(root)
    def test_counter_mismatch_and_unexpected_counters_fail_closed(self):
        for attribute,value in (('total','2'),('passed','0'),('failed','1'),('private','private-canary')):
            root=fixture();root.find('ResultSummary/Counters').set(attribute,value)
            with self.subTest(attribute=attribute),self.assertRaises(evidence.EvidenceFailure):export(root)
    def test_nested_result_smuggling_fails_closed(self):
        root=fixture();result=root.find('Results/UnitTestResult');ET.SubElement(result,'InnerResults').append(copy.deepcopy(result))
        with self.assertRaises(evidence.EvidenceFailure):export(root)
    def test_nested_roster_sections_cannot_downgrade_to_legacy(self):
        root=fixture();settings=ET.SubElement(root,'TestSettings')
        for section in ('TestDefinitions','TestEntries'):
            node=root.find(section);root.remove(node);settings.append(node)
        with self.assertRaises(evidence.EvidenceFailure):export(root)
    def test_staged_manifest_marks_versioned_roster_and_both_actual_hashes(self):
        import json
        import test_preserve_validation_evidence as existing
        fixture_case=existing.RetentionTests();fixture_case.setUp()
        try:
            original=ET.tostring(fixture(),encoding='utf-8');fixture_case.write('TestResults/fixture/roster.trx',original)
            stage,complete=fixture_case.prepare();self.assertTrue(complete)
            manifest=json.loads((stage/'availability.json').read_text());record=next(r for r in manifest['files'] if r['path'].endswith('.trx'))
            self.assertEqual(SCHEMA,record['transform']);self.assertEqual(evidence.digest(original),record['originalSha256'])
            retained=(stage/record['path']).read_bytes();self.assertEqual(evidence.digest(retained),record['sha256']);self.assertNotIn(b'private-canary',retained)
            self.assertFalse(manifest['generatedInclusiveCertified']);self.assertFalse(manifest['sourceMapAttestation'])
        finally:fixture_case.doCleanups()
    def test_legacy_outcomes_without_rosters_still_export_without_roster_claim(self):
        root=fixture();root.remove(root.find('TestDefinitions'));root.remove(root.find('TestEntries'));raw=export(root);output=ET.fromstring(raw)
        self.assertIsNone(output.get('evidenceSchema'));self.assertIsNone(output.find('TestDefinitions'));self.assertIsNone(output.find('TestEntries'))
        self.assertEqual('Passed',output.find('Results/UnitTestResult').get('outcome'));self.assertNotIn(b'private-canary',raw)
    def test_xml_and_file_limits_fail_closed_without_echo(self):
        for data in (b'<!DOCTYPE TestRun><TestRun/>',b'<!ENTITY private "private-canary"><TestRun/>',b'<TestRun>'):
            with self.subTest(data=data),self.assertRaises(evidence.EvidenceFailure) as error:evidence.outcome_trx(data)
            self.assertNotIn('private-canary',str(error.exception))
        from unittest.mock import patch
        with patch.object(evidence,'MAX_FILE',20),self.assertRaises(evidence.EvidenceFailure):export(fixture())

if __name__=='__main__':unittest.main(verbosity=2)
