"""Retain one actual journal adapter roster; never certify journal runtime parity."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import preserve_validation_evidence as producer
from fdm_validation_guards import read_file

CLASS = 'Legacy.Maliev.Workflows.Tests.FdmJournalEvidenceTests'
METHOD = 'ActualJournalConsumer_PreservesAllTwentyDiagnosticCases'

def require(condition):
    if not condition:
        raise ValueError('Focused journal evidence unavailable')

def transform(raw):
    doc=producer.parse_xml(raw)
    tag=lambda node: node.tag.rsplit('}',1)[-1]
    definitions=[n for n in doc.iter() if tag(n)=='UnitTest']
    results=[n for n in doc.iter() if tag(n)=='UnitTestResult']
    entries=[n for n in doc.iter() if tag(n)=='TestEntry']
    counters=[n for n in doc.iter() if tag(n)=='Counters']
    summaries=[n for n in doc.iter() if tag(n)=='ResultSummary']
    require(len(definitions)==len(results)==len(entries)==len(counters)==1)
    require(len(summaries)==1 and summaries[0].get('outcome')=='Completed')
    require(not any(tag(n) in ('ErrorInfo','RunInfo') for n in doc.iter()))
    # This one-Fact producer has no RunInfo diagnostics. Unknown/benign-labelled
    # messages are not inferred safe; retain them upstream and refuse here.
    known={'total','executed','passed','failed','error','timeout','aborted','inconclusive',
           'passedButRunAborted','notRunnable','notExecuted','disconnected','warning',
           'completed','inProgress','pending'}
    require(set(counters[0].attrib)==known)
    require(counters[0] in list(summaries[0]))
    definition,result,entry=definitions[0],results[0],entries[0]
    methods=[n for n in definition if tag(n)=='TestMethod'];executions=[n for n in definition if tag(n)=='Execution']
    require(len(methods)==len(executions)==1)
    require(methods[0].get('className')==CLASS and methods[0].get('name')==METHOD)
    require(result.get('outcome')=='Passed' and definition.get('id')==result.get('testId')==entry.get('testId'))
    require(executions[0].get('id')==result.get('executionId')==entry.get('executionId'))
    require(all(counters[0].get(k)=='1' for k in ('total','executed','passed')))
    require(all(counters[0].get(k)=='0' for k in ('failed','notExecuted')))
    require(all(value=='0' for key,value in counters[0].attrib.items() if key not in ('total','executed','passed')))
    # The accepted exporter validates GUIDs, display hashes and counter shape.
    data=producer.outcome_trx(raw)
    require(producer.parse_xml(data).get('evidenceSchema')==producer.TRX_ROSTER_SCHEMA)
    return data

def main():
    target=None
    metadata=None
    try:
        root=Path(os.environ['GITHUB_WORKSPACE']).resolve()
        expected=os.environ['EXPECTED_SOURCE_HEAD'];require(re.fullmatch('[0-9a-f]{40}',expected) is not None)
        def git(*args):
            r=subprocess.run(['git','-C',str(root),*args],capture_output=True,timeout=10,env=dict(os.environ,GIT_OPTIONAL_LOCKS='0',GIT_TERMINAL_PROMPT='0'))
            require(r.returncode==0 and len(r.stdout)<=1024*1024);return r.stdout.decode().strip()
        require(git('rev-parse','HEAD')==expected)
        require(not git('status','--porcelain','--untracked-files=no'))
        run=os.environ['GITHUB_RUN_ID'];attempt=os.environ['GITHUB_RUN_ATTEMPT'];workflow=os.environ['GITHUB_WORKFLOW_SHA']
        require(re.fullmatch('[0-9]+',run) and re.fullmatch('[0-9]+',attempt) and re.fullmatch('[0-9a-f]{40}',workflow))
        target=root/'TestResults/journal-focused/retained';require(not target.exists());target.mkdir(parents=True)
        metadata=dict(schema='workflows-journal-focused/v1',expectedHead=expected,observedHead=expected,workflowSha=workflow,runId=run,runAttempt=attempt,files=[],actualFocusedPassed=None,python20RawDiagnosticsAvailable=False,coverageAvailable=False,acceptanceCertified=False,runtimeAcceptance=False,activationPermitted=False)
        raw,info=read_file(root,'TestResults/journal-focused/raw/journal-focused.trx',16*1024**2)
        data=transform(raw);(target/'journal-focused.trx').write_bytes(data)
        metadata['files']=[dict(path='journal-focused.trx',bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),originalSha256=hashlib.sha256(raw).hexdigest(),transform=producer.TRX_ROSTER_SCHEMA)]
        metadata['actualFocusedPassed']=1
        pins=[]
        for name in ('.github/workflows/validate.yml','scripts/retain_fdm_journal_focused.py','scripts/fdm_journal_evidence.py','tests/test_fdm_journal_evidence.py','tests/Legacy.Maliev.Workflows.Tests/FdmJournalEvidenceTests.cs','scripts/preserve_validation_evidence.py','tests/test_focused_retention.py','tests/fixtures/journal-focused-native-shape.trx'):
            value,_=read_file(root,name,1024*1024);pins.append(dict(path=name,bytes=len(value),sha256=hashlib.sha256(value).hexdigest()))
        metadata['sourcePins']=pins
        require(git('rev-parse','HEAD')==expected)
        (target/'source-binding.json').write_text(json.dumps(metadata,sort_keys=True)+'\n')
        return 0
    except (ValueError,OSError,KeyError,subprocess.SubprocessError):
        if target is not None and metadata is not None:
            metadata.update(actualFocusedPassed=None,observedHead=None,unavailableReason='focused-validation-not-observed-or-binding-rejected')
            (target/'source-binding.json').write_text(json.dumps(metadata,sort_keys=True)+'\n')
        print('Focused journal evidence unavailable',file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main())
