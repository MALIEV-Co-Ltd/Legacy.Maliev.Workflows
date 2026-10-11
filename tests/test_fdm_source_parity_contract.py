"""Authored synthetic contract controls; no Web host, native worker or qualification."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('parity',ROOT/'scripts/fdm_source_parity_contract.py')
parity=importlib.util.module_from_spec(spec);spec.loader.exec_module(parity)
HEAD='1'*40
FULL='2'*40


def synthetic_contract():
    """Only a source shape fixture; not a real consumer, passing TRX or native proof."""
    targets={source:source.replace('Maliev.Web','Legacy.Maliev.Web',1) for source in parity.PATHS}
    return dict(schema='fdm-source-parity/v1',sourceSha=parity.SOURCE,sourceParent=parity.PARENT,
        candidateHead=HEAD,fullRecipeHead=FULL,
        sourcePaths=[dict(sourcePath=source,targetFiles=[dict(path=target,bytes=1,sha256='3'*64)]) for source,target in targets.items()],
        journals=[dict(sourcePath=source,sourceLine=line,name=name,kind=kind,targetPath=targets[source],targetPhase=name,
            scenario='setup-failure' if name.startswith('failed_setup_cleanup_') else 'normal') for source,line,name,kind in parity.JOURNALS],
        behaviors=[dict(id=identity,sourceSelector=selector,targetFilter='FullyQualifiedName~Synthetic_'+identity.replace('-','_'),
            expectedPassingRows=[{'class':'Demo.SyntheticTests','method':'Synthetic_'+identity.replace('-','_'),'displaySha256':'4'*64}]) for identity,selector in parity.BEHAVIORS],
        startup=dict(environment='Development',expectedHead=HEAD,proofPath='tests/synthetic-startup-proof.json',liveness=True,quotation=True,finallyCleanup=True),
        candidateHeadInterface=dict(name='candidate_head',required=True,callerPassesExactHead=True,calleeChecksActualHead=True))


class FdmSourceParityContractTests(unittest.TestCase):
    def setUp(self):
        self.document=synthetic_contract()

    def refused(self, document=None, **heads):
        with self.assertRaises(parity.ContractError) as raised:
            parity.validate(self.document if document is None else document,heads.get('head',HEAD),heads.get('full',FULL))
        self.assertEqual('FDM source parity contract rejected',str(raised.exception))

    def test_counts_are_source_paths_journals_and_execution_groups_separately(self):
        result=parity.validate(self.document,HEAD,FULL)
        self.assertEqual((6,14,18,1,14),(result['source551Paths'],result['source552Paths'],result['fixedJournalObligations'],result['dynamicJournalPrefixes'],result['behaviorExecutionGroups']))
        self.assertFalse(result['runtimeAcceptance']);self.assertFalse(result['activationPermitted'])

    def test_absent_reviewed_consumer_head_is_refused(self):
        self.document['candidateHead']=None;self.refused()

    def test_baseline_head_or_full_recipe_is_refused(self):
        self.refused(head=parity.BASELINE);self.refused(full=parity.BASELINE)

    def test_source_sha_or_parent_drift_is_refused(self):
        for key in ['sourceSha','sourceParent']:
            document=copy.deepcopy(self.document);document[key]='5'*40;self.refused(document)

    def test_source_path_missing_duplicate_or_renamed_is_refused(self):
        for action in ['missing','duplicate','renamed']:
            document=copy.deepcopy(self.document)
            if action=='missing':document['sourcePaths'].pop()
            elif action=='duplicate':document['sourcePaths'][-1]=document['sourcePaths'][0]
            else:document['sourcePaths'][-1]['sourcePath']='private-customer-source'
            self.refused(document)

    def test_empty_unhashed_or_conflicting_target_source_is_refused(self):
        for action in ['empty','unhashed','conflicting']:
            document=copy.deepcopy(self.document)
            if action=='empty':document['sourcePaths'][0]['targetFiles']=[]
            elif action=='unhashed':document['sourcePaths'][0]['targetFiles'][0]['sha256']=''
            else:
                target=copy.deepcopy(document['sourcePaths'][0]['targetFiles'][0]);target['sha256']='5'*64;document['sourcePaths'][1]['targetFiles']=[target]
            self.refused(document)

    def test_traversal_and_foreign_target_path_are_refused(self):
        for path in ['../outside.cs','scripts/../outside.cs','C:/secret.cs','tools/security/scanner.py']:
            document=copy.deepcopy(self.document);document['sourcePaths'][0]['targetFiles'][0]['path']=path;self.refused(document)

    def test_seven_candidate_phases_do_not_replace_eighteen_original_events(self):
        self.document['journals']=self.document['journals'][:7];self.refused()

    def test_dynamic_http_prefix_cannot_be_dropped_or_changed(self):
        for action in ['drop','change']:
            document=copy.deepcopy(self.document)
            if action=='drop':document['journals']=[row for row in document['journals'] if row['kind']!='dynamic-prefix']
            else:next(row for row in document['journals'] if row['kind']=='dynamic-prefix')['targetPhase']='other_'
            self.refused(document)

    def test_journal_provenance_duplicate_and_unbound_target_are_refused(self):
        for action in ['line','duplicate','unbound']:
            document=copy.deepcopy(self.document)
            if action=='line':document['journals'][0]['sourceLine']+=1
            elif action=='duplicate':document['journals'][-1]=document['journals'][0]
            else:document['journals'][0]['targetPath']='Legacy.Maliev.Web.Tests/Unbound.cs'
            self.refused(document)

    def test_cleanup_failure_obligations_cannot_be_relabelled_normal(self):
        next(row for row in self.document['journals'] if row['scenario']=='setup-failure')['scenario']='normal';self.refused()

    def test_journal_cannot_redirect_to_another_admitted_source_obligation(self):
        foreign=self.document['sourcePaths'][-1]['targetFiles'][0]['path']
        self.document['journals'][0]['targetPath']=foreign;self.refused()

    def test_all_eight_readiness_selectors_are_required(self):
        self.document['behaviors']=[row for row in self.document['behaviors'] if row['id']!='readiness-selected-material'];self.refused()

    def test_renamed_or_duplicate_original_behavior_is_refused(self):
        for action in ['renamed','duplicate']:
            document=copy.deepcopy(self.document)
            if action=='renamed':document['behaviors'][0]['sourceSelector']='private-customer-selector'
            else:document['behaviors'][-1]=document['behaviors'][0]
            self.refused(document)

    def test_empty_or_duplicate_expected_passing_identity_is_refused(self):
        for action in ['empty','duplicate']:
            document=copy.deepcopy(self.document)
            if action=='empty':document['behaviors'][0]['expectedPassingRows']=[]
            else:document['behaviors'][0]['expectedPassingRows']*=2
            self.refused(document)

    def test_optional_maps_testing_host_is_not_development_startup(self):
        self.document['startup']['environment']='Testing';self.refused()

    def test_single_generic_filter_for_every_behavior_is_refused(self):
        for row in self.document['behaviors']:row['targetFilter']='FullyQualifiedName~Demo'
        self.refused()

    def test_single_generic_case_for_every_behavior_is_refused(self):
        generic=copy.deepcopy(self.document['behaviors'][0]['expectedPassingRows'])
        for row in self.document['behaviors']:row['expectedPassingRows']=copy.deepcopy(generic)
        self.refused()

    def test_partial_reviewable_behavior_overlap_is_not_assumed_disjoint(self):
        first=self.document['behaviors'][0];second=self.document['behaviors'][1]
        second['targetFilter']=first['targetFilter'];second['expectedPassingRows']=copy.deepcopy(first['expectedPassingRows'])
        result=parity.validate(self.document,HEAD,FULL)
        self.assertTrue(result['sourceContractValidated']);self.assertFalse(result['runtimeAcceptance'])

    def test_missing_liveness_quotation_or_finally_cleanup_is_refused(self):
        for key in ['liveness','quotation','finallyCleanup']:
            document=copy.deepcopy(self.document);document['startup'][key]=False;self.refused(document)

    def test_startup_head_must_match_exact_consumer(self):
        self.document['startup']['expectedHead']='5'*40;self.refused()

    def test_caller_and_callee_must_require_exact_candidate_head(self):
        for key in ['required','callerPassesExactHead','calleeChecksActualHead']:
            document=copy.deepcopy(self.document);document['candidateHeadInterface'][key]=False;self.refused(document)

    def test_unknown_and_duplicate_json_fields_are_refused(self):
        self.document['unexpected']='private-customer-value';self.refused()
        with self.assertRaises(parity.ContractError):json.loads('{"schema":1,"schema":2}',object_pairs_hook=parity.pairs)


if __name__=='__main__':
    unittest.main(verbosity=2)
