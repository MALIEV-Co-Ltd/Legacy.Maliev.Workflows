"""Ordinary FDM source/admission/TRX guards; never execute consumer evidence."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET

SOURCE_SHA = '29214f53f1574b89799e6d58ea1cebea03fffe04'
SOURCE_PARENT = '135e526d0dab85c415b3afdcefd7b70fe2c82e2f'
BASELINE_FULL_WORKFLOW = 'f29f2ce40bf31b067e84b6de4e3547d2fe2c3de3'
PHASES = ('margin', 'endpoint', 'ticket', 'persistence', 'startup', 'browser',
          'readiness-summary', 'readiness-pdf', 'readiness-worker',
          'readiness-collapsed-summary', 'readiness-material-filter',
          'readiness-bulk-table', 'readiness-selected-material', 'readiness-seven-part')
ADMISSION_PHASES = (*PHASES, 'build', 'assets', 'browser-install', 'startup-host', 'format')
PHASE_MANIFEST = 'tests/fdm-validation-phases.json'
SOURCE_MANIFEST = 'tests/fdm-validation-source.json'
STARTUP_PROOF = 'scripts/Invoke-FdmStartupProof.ps1'
COVERAGE_PINS = {
    'tests/web-fx-generated-inclusive.runsettings': '73f436bbdca7731a39d1d87f48f4b82ef0386d81f20bfa004f3c240c0290ed5c',
    'tests/Test-WebFxRawCoverage.ps1': 'b8142c9509fd152dc3df40847d07dab64b5fa28fcc40edb24c9bd2888b082c9d',
}
HEX40 = re.compile(r'[0-9a-f]{40}')
HEX64 = re.compile(r'[0-9a-f]{64}')
CLR_CLASS = re.compile(r'[A-Za-z_][A-Za-z_0-9]*(?:`[0-9]+)?(?:[.+][A-Za-z_][A-Za-z_0-9]*(?:`[0-9]+)?)*')
CLR_METHOD = re.compile(r'[A-Za-z_][A-Za-z_0-9]*(?:`[0-9]+)?')


class GuardError(ValueError):
    """Refuse without exposing file bodies, test parameters or credentials."""


def require(value):
    if not value:
        raise GuardError('FDM validation proof rejected')


def keys(value, expected):
    require(type(value) is dict and set(value) == set(expected))


def relative(value):
    require(type(value) is str and value and len(value) <= 512)
    require('\\' not in value and ':' not in value and not value.startswith('/'))
    require(all(part and part not in ('.', '..') for part in value.split('/')))
    require(all(32 < ord(c) < 127 for c in value))
    require(PurePosixPath(value).as_posix() == value)
    return value


def regular(info):
    require(not stat.S_ISLNK(info.st_mode))
    require(not (getattr(info, 'st_file_attributes', 0) & 1024))


def path_for(root, name):
    root = Path(root).absolute()
    for segment in [*reversed(root.parents), root]:
        info = segment.lstat(); regular(info); require(stat.S_ISDIR(info.st_mode))
    path = root
    parts = relative(name).split('/')
    for part in parts[:-1]:
        path = path / part
        info = path.lstat(); regular(info); require(stat.S_ISDIR(info.st_mode))
    return path / parts[-1]


def read_file(root, name, limit):
    path = path_for(root, name)
    info = path.lstat(); regular(info); require(stat.S_ISREG(info.st_mode) and info.st_size <= limit)
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0)
    with os.fdopen(os.open(path, flags), 'rb') as stream:
        held = os.fstat(stream.fileno()); regular(held)
        require((info.st_dev, info.st_ino) == (held.st_dev, held.st_ino) and info.st_size == held.st_size)
        data = stream.read(limit + 1)
        final = os.fstat(stream.fileno())
    observed = path.lstat(); regular(observed)
    require(len(data) <= limit and len(data) == held.st_size)
    require((held.st_dev, held.st_ino, held.st_size, held.st_mtime_ns) ==
            (final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns) ==
            (observed.st_dev, observed.st_ino, observed.st_size, observed.st_mtime_ns))
    return data, observed


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result); result[key] = value
    return result


def json_file(root, name, limit=128 * 1024):
    data, info = read_file(root, name, limit)
    return json.loads(data.decode('utf-8'), object_pairs_hook=unique_pairs), data, info


def sha(data):
    return hashlib.sha256(data).hexdigest()


def head(expected, observed):
    require(type(expected) is str and HEX40.fullmatch(expected) and expected == observed)


def phase_manifest(root):
    manifest, data, _ = json_file(root, PHASE_MANIFEST)
    keys(manifest, ('schemaVersion', 'sourceSha', 'sourceParent', 'phases'))
    require(type(manifest['schemaVersion']) is int and manifest['schemaVersion'] == 1)
    require(manifest['sourceSha'] == SOURCE_SHA and manifest['sourceParent'] == SOURCE_PARENT)
    require(type(manifest['phases']) is list and len(manifest['phases']) == len(PHASES))
    phases = {}
    for item in manifest['phases']:
        keys(item, ('id', 'filter', 'expectedPassingRows'))
        require(type(item['id']) is str and item['id'] in PHASES and item['id'] not in phases)
        require(type(item['filter']) is str and 0 < len(item['filter']) <= 4096)
        require(all(32 <= ord(c) < 127 for c in item['filter']))
        rows = item['expectedPassingRows']; require(type(rows) is list and 0 < len(rows) <= 4096)
        identities = set()
        for row in rows:
            keys(row, ('class', 'method', 'displaySha256'))
            require(type(row['class']) is str and CLR_CLASS.fullmatch(row['class']))
            require(type(row['method']) is str and CLR_METHOD.fullmatch(row['method']))
            require(type(row['displaySha256']) is str and HEX64.fullmatch(row['displaySha256']))
            identity = (row['class'], row['method'], row['displaySha256'])
            require(identity not in identities); identities.add(identity)
        phases[item['id']] = item
    require(set(phases) == set(PHASES))
    return phases, sha(data)


def source_custody(root, expected_head, observed_head, clean, full_workflow_sha):
    head(expected_head, observed_head); require(clean is True)
    require(HEX40.fullmatch(full_workflow_sha) and full_workflow_sha != BASELINE_FULL_WORKFLOW)
    manifest, _, _ = json_file(root, SOURCE_MANIFEST)
    keys(manifest, ('schemaVersion', 'sourceSha', 'sourceParent', 'fullWorkflowSha', 'files', 'worker'))
    require(type(manifest['schemaVersion']) is int and manifest['schemaVersion'] == 1)
    require(manifest['sourceSha'] == SOURCE_SHA and manifest['sourceParent'] == SOURCE_PARENT)
    require(manifest['fullWorkflowSha'] == full_workflow_sha)
    phases, phase_hash = phase_manifest(root)
    files = manifest['files']; require(type(files) is list and 0 < len(files) <= 256)
    admitted = {}
    for item in files:
        keys(item, ('path', 'bytes', 'sha256', 'checkoutPolicy'))
        name = relative(item['path']); require(name not in admitted)
        require(name in ('.gitattributes', 'Directory.Build.props', PHASE_MANIFEST, STARTUP_PROOF) or
                name.startswith(('Legacy.Maliev.Web/', 'Legacy.Maliev.Web.Application/', 'Legacy.Maliev.Web.Tests/', 'tests/')))
        require(type(item['bytes']) is int and 0 <= item['bytes'] <= 4 * 1024 * 1024)
        require(type(item['sha256']) is str and HEX64.fullmatch(item['sha256']))
        require(item['checkoutPolicy'] in ('lf', 'opaque'))
        data, _ = read_file(root, name, 4 * 1024 * 1024)
        require(len(data) == item['bytes'] and sha(data) == item['sha256'])
        if item['checkoutPolicy'] == 'lf':
            data.decode('utf-8'); require(b'\r' not in data)
        admitted[name] = item
    require(PHASE_MANIFEST in admitted and '.gitattributes' in admitted and STARTUP_PROOF in admitted)
    require(admitted[STARTUP_PROOF]['checkoutPolicy'] == 'lf' and admitted[STARTUP_PROOF]['bytes'] > 0)
    require(all(name in admitted for name in (
        'Legacy.Maliev.Web.Application/Pricing/PricingEngine.cs',
        'Legacy.Maliev.Web.Application/Pricing/PricingCatalog.cs',
        'Legacy.Maliev.Web.Tests/FdmQuantityMarginTests.cs',
        'Legacy.Maliev.Web.Tests/AdditiveQuoteTicketServiceTests.cs')))
    require(admitted['.gitattributes']['checkoutPolicy'] == 'lf')
    attrs = read_file(root, '.gitattributes', 128 * 1024)[0].decode('utf-8').splitlines()
    require('* text=auto eol=lf' in attrs)
    for folder in ('Sources', 'Resolved'):
        pattern = 'Legacy.Maliev.Web.Application/Pricing/Profiles/' + folder + '/*.json'
        require(any(line.split()[:2] == [pattern, '-text'] for line in attrs))
        require(any(name.startswith(pattern[:-6]) and name.endswith('.json') and
                    item['checkoutPolicy'] == 'opaque' for name, item in admitted.items()))
    for name, digest in COVERAGE_PINS.items():
        require(sha(read_file(root, name, 256 * 1024)[0]) == digest)
    worker = manifest['worker']; keys(worker, ('path', 'referencePath', 'sha256', 'pin'))
    require(type(worker['path']) is str and worker['path'].startswith('Legacy.Maliev.Web/wwwroot/'))
    require(worker['path'] in admitted and worker['referencePath'] in admitted)
    require(worker['sha256'] == admitted[worker['path']]['sha256'])
    require(type(worker['pin']) is str and re.fullmatch('[0-9a-f]{16}', worker['pin']))
    require(worker['sha256'].startswith(worker['pin']))
    reference = read_file(root, worker['referencePath'], 4 * 1024 * 1024)[0].decode('utf-8')
    require(len(re.findall(r'(?<![0-9a-f])' + worker['pin'] + r'(?![0-9a-f])', reference)) == 1)
    return dict(expectedHead=expected_head, sourceSha=SOURCE_SHA, sourceParent=SOURCE_PARENT,
                files=len(admitted), phaseManifestSha256=phase_hash, phases=len(phases),
                fullWorkflowSha=full_workflow_sha, runtimeAcceptance=False, wholeShaClosure=False)


def admission(phase, expected_head, observed_head, free_bytes, dotnet_jobs, now):
    require(phase in ADMISSION_PHASES); head(expected_head, observed_head)
    require(type(free_bytes) is int and free_bytes >= 3072 * 1024 ** 2)
    require(type(dotnet_jobs) is list and not dotnet_jobs)
    require(type(now) in (float, int) and math.isfinite(now) and now > 0)
    return dict(schemaVersion=1, phase=phase, expectedHead=expected_head,
                observedEpoch=now, expiresEpoch=now + 900, freeBytes=free_bytes,
                foreignDotnetJobs=0, admissionId=str(uuid.uuid4()))


def write_receipt(root, phase, receipt):
    require(phase in ADMISSION_PHASES)
    path_for(root, PHASE_MANIFEST)
    directory = Path(root).absolute()
    for part in ('TestResults', 'fdm', phase):
        directory = directory / part
        if not directory.exists():
            directory.mkdir()
        info = directory.lstat(); regular(info); require(stat.S_ISDIR(info.st_mode))
    name = 'TestResults/fdm/' + phase + '/admission.json'
    require(not (directory / (phase + '.trx')).exists())
    target = path_for(root, name)
    with target.open('xb') as stream:
        stream.write(json.dumps(receipt, sort_keys=True).encode('utf-8'))


def tag(node):
    return node.tag.rsplit('}', 1)[-1]


def identity_id(value):
    require(type(value) is str and len(value) == 36)
    try:
        parsed = str(uuid.UUID(value))
    except ValueError:
        raise GuardError('FDM validation proof rejected') from None
    require(parsed == value.lower())
    return parsed


def trx_roster(data):
    require(0 < len(data) <= 16 * 1024 * 1024)
    require(not re.search(br'<!\s*(?:DOCTYPE|ENTITY)', data, re.I) and b'\x00' not in data)
    root = ET.fromstring(data); require(tag(root) == 'TestRun')
    require(sum(1 for _ in root.iter()) <= 80000)
    require(not any(tag(n) == 'ErrorInfo' or (tag(n) == 'RunInfo' and n.get('outcome') in ('Error', 'Failed', 'Aborted')) for n in root.iter()))
    sections = {}
    for name in ('TestDefinitions', 'TestEntries', 'Results', 'ResultSummary'):
        matches = [node for node in root.iter() if tag(node) == name]
        require(len(matches) == 1 and matches[0] in list(root)); sections[name] = matches[0]
    definitions = {}; executions = set()
    for node in sections['TestDefinitions']:
        require(tag(node) == 'UnitTest')
        identifier = identity_id(node.get('id')); display = node.get('name')
        require(identifier not in definitions and type(display) is str and 0 < len(display) <= 4096)
        methods = [n for n in node if tag(n) == 'TestMethod']; execute = [n for n in node if tag(n) == 'Execution']
        require(len(methods) == len(execute) == 1)
        cls, method = methods[0].get('className'), methods[0].get('name')
        require(type(cls) is str and len(cls) <= 512 and CLR_CLASS.fullmatch(cls) and type(method) is str and len(method) <= 512 and CLR_METHOD.fullmatch(method))
        execution = identity_id(execute[0].get('id')); require(execution not in executions); executions.add(execution)
        definitions[identifier] = (display, execution, cls, method)
    require(0 < len(definitions) <= 4096)
    entries = set()
    for node in sections['TestEntries']:
        require(tag(node) == 'TestEntry')
        identifier, execution = identity_id(node.get('testId')), identity_id(node.get('executionId'))
        require(identifier in definitions and definitions[identifier][1] == execution and identifier not in entries)
        entries.add(identifier)
    require(entries == set(definitions))
    results = set(); identities = set()
    require(sum(1 for n in root.iter() if tag(n) == 'UnitTestResult') == len(sections['Results']))
    for node in sections['Results']:
        require(tag(node) == 'UnitTestResult')
        identifier = identity_id(node.get('testId')); require(identifier in definitions and identifier not in results)
        display, execution, cls, method = definitions[identifier]
        require(node.get('testName') == display and identity_id(node.get('executionId')) == execution and node.get('outcome') == 'Passed')
        require(not any(tag(n) in ('ErrorInfo', 'Message', 'StackTrace') for n in node.iter()))
        identity = (cls, method, sha(b'trx-display/v1\0' + display.encode('utf-8')))
        require(identity not in identities); identities.add(identity); results.add(identifier)
    require(results == set(definitions))
    counters = [n for n in sections['ResultSummary'] if tag(n) == 'Counters']
    require(len(counters) == 1 and sections['ResultSummary'].get('outcome') in ('Passed', 'Completed'))
    expected = {'total': len(results), 'executed': len(results), 'passed': len(results), 'failed': 0, 'notExecuted': 0}
    for name, count in expected.items():
        value = counters[0].get(name); require(value is not None and re.fullmatch(r'\d+', value) and int(value) == count)
    for name in ('error', 'timeout', 'aborted', 'inconclusive', 'notRunnable', 'disconnected'):
        if name in counters[0].attrib:
            require(counters[0].get(name) == '0')
    return identities


def validate_trx(root, phase, name, expected_head, observed_head, now):
    require(phase in PHASES); head(expected_head, observed_head)
    require(name == 'TestResults/fdm/' + phase + '/' + phase + '.trx')
    phases, manifest_hash = phase_manifest(root)
    receipt, _, _ = json_file(root, 'TestResults/fdm/' + phase + '/admission.json', 8192)
    keys(receipt, ('schemaVersion', 'phase', 'expectedHead', 'observedEpoch', 'expiresEpoch',
                   'freeBytes', 'foreignDotnetJobs', 'admissionId', 'phaseManifestSha256'))
    require(type(receipt['schemaVersion']) is int and receipt['schemaVersion'] == 1 and receipt['phase'] == phase and receipt['expectedHead'] == expected_head)
    require(receipt['phaseManifestSha256'] == manifest_hash and receipt['foreignDotnetJobs'] == 0)
    require(type(receipt['freeBytes']) is int and receipt['freeBytes'] >= 3072 * 1024 ** 2)
    require(type(receipt['observedEpoch']) in (int, float) and type(receipt['expiresEpoch']) in (int, float))
    require(math.isfinite(receipt['observedEpoch']) and math.isfinite(receipt['expiresEpoch']) and math.isfinite(now))
    require(receipt['expiresEpoch'] == receipt['observedEpoch'] + 900 and receipt['observedEpoch'] <= now <= receipt['expiresEpoch'])
    require(type(receipt['admissionId']) is str and str(uuid.UUID(receipt['admissionId'])) == receipt['admissionId'])
    data, info = read_file(root, name, 16 * 1024 * 1024)
    require(receipt['observedEpoch'] <= info.st_mtime <= now)
    actual = trx_roster(data)
    expected = {(row['class'], row['method'], row['displaySha256']) for row in phases[phase]['expectedPassingRows']}
    require(actual == expected)
    return dict(expectedHead=expected_head, phase=phase, passingRows=len(actual),
                trxSha256=sha(data), phaseManifestSha256=manifest_hash,
                admissionId=receipt['admissionId'], runtimeAcceptance=False)


def observe_git(root):
    environment = dict(os.environ, GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0')
    def git(*args):
        result = subprocess.run(['git', '-C', str(root), *args], capture_output=True,
                                timeout=10, env=environment, check=False)
        require(result.returncode == 0 and len(result.stdout) <= 1024 * 1024)
        return result.stdout.decode('utf-8')
    observed = git('rev-parse', 'HEAD').strip()
    clean = not git('status', '--porcelain', '--', '.', ':!.maliev-fdm-validation-tools').strip()
    return observed, clean


def observe_linux():
    require(os.name == 'posix' and Path('/proc/meminfo').is_file())
    memory = Path('/proc/meminfo').read_text()
    available = re.search(r'^MemAvailable:\s+(\d+) kB$', memory, re.M); require(available is not None)
    jobs = []
    processes = [p for p in Path('/proc').iterdir() if p.name.isdigit()]; require(len(processes) <= 4096)
    for process in processes:
        try:
            if (process / 'comm').read_text().strip() == 'dotnet':
                jobs.append(dict(pid=int(process.name), identity='dotnet', startTicks=(process / 'stat').read_text().rsplit(')', 1)[1].split()[19]))
        except FileNotFoundError:
            continue
    return int(available.group(1)) * 1024, jobs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('source', 'admission', 'trx'))
    parser.add_argument('--root', required=True); parser.add_argument('--expected-head', required=True)
    parser.add_argument('--phase'); parser.add_argument('--trx'); parser.add_argument('--full-workflow-sha')
    args = parser.parse_args()
    try:
        root = Path(args.root).absolute(); observed, clean = observe_git(root)
        if args.mode == 'source':
            result = source_custody(root, args.expected_head, observed, clean, args.full_workflow_sha)
        elif args.mode == 'admission':
            source_custody(root, args.expected_head, observed, clean, args.full_workflow_sha)
            phases, manifest_hash = phase_manifest(root)
            memory, jobs = observe_linux()
            result = admission(args.phase, args.expected_head, observed, memory, jobs, time.time())
            result['phaseManifestSha256'] = manifest_hash
            write_receipt(root, args.phase, result)
        else:
            source_custody(root, args.expected_head, observed, clean, args.full_workflow_sha)
            result = validate_trx(root, args.phase, args.trx, args.expected_head, observed, time.time())
        print(json.dumps(result, sort_keys=True)); return 0
    except (GuardError, OSError, ValueError, TypeError, KeyError, ET.ParseError, subprocess.SubprocessError):
        print('FDM validation proof rejected', file=__import__('sys').stderr); return 2


if __name__ == '__main__':
    raise SystemExit(main())
