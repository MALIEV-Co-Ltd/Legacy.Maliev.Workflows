"""Own-repository test evidence only; no native SDK or arbitrary output export."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

spec = importlib.util.spec_from_file_location('reviewed_evidence', Path(__file__).with_name('preserve_validation_evidence.py'))
producer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(producer)
BASELINE = 'a08d488e64071cc97bd5a4b270808b5ff28f10a3'
CLASS = 'Legacy.Maliev.Workflows.Tests.FdmValidationGuardTests'
METHOD = 'PythonControls_RequireAllTwentyFourCasesWithoutSkips'
RAW = 'TestResults/raw-evidence'
RETAINED = 'TestResults/workflows-retained'
CONTROL_PATH = '.maliev-evidence-controls'
MAX_REPORT = 32 * 1024 * 1024


def require(value):
    if not value:
        raise ValueError('own test evidence unavailable')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def head(path):
    return producer.source_head(path)


def read(root, relative, limit=MAX_REPORT):
    require(not Path(relative).is_absolute() and '..' not in Path(relative).parts)
    path = root / relative
    require(path.resolve().is_relative_to(root.resolve()) and path.is_file())
    for current in [path, *path.parents]:
        if current == root:
            break
        require(not current.is_symlink() and not current.is_junction())
    require(path.stat().st_size <= limit)
    return path.read_bytes()


def python_diagnostics(raw, names):
    require(len(names) == 24)
    xml = producer.parse_xml(raw)
    tag = lambda node: node.tag.rsplit('}', 1)[-1]
    definitions = {}
    for node in xml.iter():
        if tag(node) == 'UnitTest':
            methods = [n for n in node if tag(n) == 'TestMethod']
            if len(methods) == 1 and methods[0].get('className') == CLASS and methods[0].get('name') == METHOD:
                require(node.get('id') not in definitions)
                definitions[node.get('id')] = True
    require(len(definitions) == 1)
    results = [n for n in xml.iter() if tag(n) == 'UnitTestResult' and n.get('testId') in definitions]
    require(len(results) == 1 and results[0].get('outcome') == 'Passed')
    text = '\n'.join(n.text or '' for n in results[0].iter() if tag(n) == 'StdOut')
    require(len(text.encode()) <= 256 * 1024)
    begin, end = 'fdm-python/v1 begin\n', 'fdm-python/v1 end'
    require(text.count(begin) == text.count(end) == 1)
    value = text.split(begin, 1)[1].split(end, 1)[0]
    seen = set(); summary = 0; terminal = 0
    for line in value.splitlines():
        match = re.fullmatch(r'(test_[A-Za-z0-9_]+) \(__main__\.FdmGuardTests(?:\.\1)?\) \.\.\. ok', line)
        if match:
            name = match.group(1); require(name in names and name not in seen); seen.add(name)
        elif re.fullmatch(r'Ran 24 tests in [0-9]+(?:\.[0-9]+)?s', line):
            summary += 1
        elif line == 'OK':
            terminal += 1
        else:
            require(line in ('', '-' * 70))
    require(seen == names and summary == terminal == 1 and value.rstrip().endswith('OK'))
    return value.encode()


def retain(root, expected, control_head, run_id, attempt, workflow_sha):
    root = root.resolve(); controls = root / CONTROL_PATH
    require(all(re.fullmatch('[0-9a-f]{40}', x) for x in (expected, control_head, workflow_sha)))
    require(re.fullmatch('[0-9]+', run_id) and re.fullmatch('[0-9]+', attempt))
    require(head(root) == expected and head(controls) == control_head)
    require(Path(__file__).resolve().is_relative_to(controls.resolve()))
    target = root / RETAINED; require(not target.exists() and target.resolve().is_relative_to(root))
    for parent in target.parents:
        if parent == root:
            break
        require(not parent.is_symlink() and not parent.is_junction())
    target.mkdir(parents=True)
    files = []; total = 0; diagnostics = False; reports = 0
    raw_root = root / RAW
    if raw_root.exists():
        require(raw_root.is_dir() and not raw_root.is_symlink() and not raw_root.is_junction())
        for path in sorted(raw_root.rglob('*')):
            if not path.is_file() or (path.suffix != '.trx' and path.name != 'coverage.cobertura.xml'):
                continue
            require(reports < 64); reports += 1
            relative = path.relative_to(root).as_posix(); original = read(root, relative)
            if path.suffix == '.trx':
                data = producer.outcome_trx(original)
                require(ET.fromstring(data).get('evidenceSchema') == producer.TRX_ROSTER_SCHEMA)
                transform = producer.TRX_ROSTER_SCHEMA
                if expected != BASELINE:
                    source = read(controls, 'tests/test_fdm_validation_guards.py', 1024 * 1024)
                    names = {n.name for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef) and n.name.startswith('test_')}
                    try:
                        diagnostic = python_diagnostics(original, names)
                    except ValueError:
                        diagnostic = None
                    if diagnostic is not None:
                        require(not diagnostics); diagnostics = True
                        name = 'fdm-python-24.txt'; (target/name).write_bytes(diagnostic)
                        files.append(dict(path=name,bytes=len(diagnostic),sha256=sha(diagnostic),transform='validated-synthetic-unittest/v1'))
            else:
                data = producer.coverage_bytes(original); transform = 'verbatim-cobertura'
            total += len(data); require(total <= 128 * 1024 * 1024)
            name = producer.relative_name(path.relative_to(raw_root).as_posix()); dest = target/'reports'/name
            dest.parent.mkdir(parents=True,exist_ok=True); dest.write_bytes(data)
            files.append(dict(path='reports/'+name,bytes=len(data),sha256=sha(data),originalSha256=sha(original),transform=transform))
    inputs = []
    for name in ('.github/workflows/validate.yml', '.github/workflows/dotnet-validate.yml', 'actions/dotnet-validate/action.yml'):
        data = read(root, name, 1024 * 1024); inputs.append(dict(path=name,bytes=len(data),sha256=sha(data)))
    require(head(root) == expected and head(controls) == control_head)
    metadata = dict(schemaVersion=1,repository='MALIEV-Co-Ltd/Legacy.Maliev.Workflows',expectedHead=expected,observedHead=expected,
        controlHead=control_head,workflowSha=workflow_sha,validationActionSha='ce7a577d9672c44cd445915420e3c552c70317d1',runId=run_id,runAttempt=attempt,
        gateInputs=inputs,files=files,trxAvailable=any(f['path'].endswith('.trx') for f in files),
        coverageAvailable=any(f['path'].endswith('coverage.cobertura.xml') for f in files),coverageGateAvailable=False,
        python24DiagnosticsAvailable=diagnostics,rawTrxExported=False,acceptanceCertified=False)
    (target/'source-binding.json').write_text(json.dumps(metadata,sort_keys=True)+'\n',encoding='utf-8')
    return metadata


def main():
    try:
        require(len(sys.argv) == 1)
        metadata = retain(Path(os.environ['GITHUB_WORKSPACE']), os.environ['EXPECTED_SOURCE_HEAD'],os.environ['EVIDENCE_OWNER_HEAD'],
            os.environ['GITHUB_RUN_ID'],os.environ['GITHUB_RUN_ATTEMPT'],os.environ['GITHUB_WORKFLOW_SHA'])
        require(metadata['trxAvailable'] and (metadata['expectedHead'] == BASELINE or metadata['python24DiagnosticsAvailable']))
        return 0
    except (KeyError, ValueError, OSError, ET.ParseError, subprocess.SubprocessError):
        print('[workflows-evidence] FAILED: custody or diagnostics unavailable; details redacted',file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
