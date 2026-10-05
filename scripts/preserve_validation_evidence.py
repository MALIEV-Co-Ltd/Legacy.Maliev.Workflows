"""Retain allowlisted existing runner evidence; never create test or coverage results."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

MAX_FILE = 32 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024
MAX_FILES = 2048


class EvidenceFailure(ValueError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(value):
    if not value:
        raise EvidenceFailure('evidence retention unavailable')


def relative_name(value):
    require(isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9._/-]{1,256}', value))
    require(not value.startswith('/') and all(p not in ('', '.', '..') for p in value.split('/')))
    return value


def relative_source_name(value):
    # Only source-candidate metadata may use this exact net10.0 SDK basename.
    # Inputs and retained payload paths keep the original strict allowlist.
    require(isinstance(value, str) and len(value) <= 256)
    directory, separator, filename = value.rpartition('/')
    if filename == '.NETCoreApp,Version=v10.0.AssemblyAttributes.cs':
        require(separator and 'obj' in directory.split('/'))
        relative_name(directory)
        return value
    return relative_name(value)


def read_owned(root, path):
    require(path.resolve().is_relative_to(root) and path.is_file())
    current = path
    while current != root:
        require(not current.is_symlink())
        current = current.parent
    require(path.stat().st_size <= MAX_FILE)
    return path.read_bytes()


def parse_xml(data):
    require(b'<!DOCTYPE' not in data.upper() and b'<!ENTITY' not in data.upper())
    try:
        return ET.fromstring(data)
    except ET.ParseError:
        raise EvidenceFailure('evidence retention unavailable') from None


def coverage_bytes(data):
    xml = parse_xml(data)
    require(xml.tag == 'coverage')
    allowed = {'coverage','sources','source','packages','package','classes','class','methods','method','lines','line','conditions','condition'}
    require(all(node.tag in allowed for node in xml.iter()))
    # Existing raw source filenames/settings/line hits are retained verbatim.
    # Unexpected output/environment payloads cannot acquire a coverage extension.
    require(b'-----BEGIN ' not in data and not re.search(rb'https?://[^\s"<>]*@', data))
    return data


def outcome_trx(data):
    original = parse_xml(data)
    tag = lambda node: node.tag.rsplit('}', 1)[-1]
    require(tag(original) == 'TestRun')
    result = ET.Element('TestRun')
    results = ET.SubElement(result, 'Results')
    found = 0
    for node in original.iter():
        if tag(node) != 'UnitTestResult':
            continue
        require(node.get('outcome') in ('Passed','Failed','NotExecuted','Inconclusive','Timeout','Aborted','Error','Warning','NotRunnable','Completed','InProgress','Pending'))
        attributes = {'outcome': node.get('outcome')}
        for key in ('testId','executionId'):
            if node.get(key) is not None:
                require(re.fullmatch(r'[A-Za-z0-9._-]{1,128}', node.get(key)))
                attributes[key] = node.get(key)
        ET.SubElement(results, 'UnitTestResult', attributes)
        found += 1
    counters = [node for node in original.iter() if tag(node) == 'Counters']
    require(found > 0 and len(counters) == 1)
    summary = ET.SubElement(result, 'ResultSummary')
    allowed_counters = {'total','executed','passed','failed','error','timeout','aborted','inconclusive','passedButRunAborted','notRunnable','notExecuted','disconnected','warning','completed','inProgress','pending'}
    require(set(counters[0].attrib) <= allowed_counters)
    require(all(re.fullmatch(r'[0-9]{1,12}', value) for value in counters[0].attrib.values()))
    ET.SubElement(summary, 'Counters', dict(counters[0].attrib))
    return ET.tostring(result, encoding='utf-8', xml_declaration=True)


def source_head(workspace):
    environment = {key:value for key,value in os.environ.items() if not key.upper().startswith('GIT_')}
    environment.update(GIT_OPTIONAL_LOCKS='0', GIT_NO_REPLACE_OBJECTS='1', GIT_TERMINAL_PROMPT='0')
    result = subprocess.run(['git','-C',str(workspace),'rev-parse','HEAD'], capture_output=True, env=environment, timeout=5)
    require(result.returncode == 0 and re.fullmatch(rb'[0-9a-f]{40}\r?\n', result.stdout))
    return result.stdout.decode('ascii').strip()


def prepare(*, workspace, runner_temp, repository, source_revision, results_directory, production_projects):
    workspace = Path(workspace).resolve()
    runner_temp = Path(runner_temp).resolve()
    require(workspace.is_dir() and runner_temp.is_dir() and not runner_temp.is_relative_to(workspace))
    require(re.fullmatch(r'MALIEV-Co-Ltd/Legacy\.Maliev\.[A-Za-z]+', repository))
    require(re.fullmatch(r'[0-9a-f]{40}', source_revision) and source_head(workspace) == source_revision)
    stem = repository.split('/')[1]
    relative_name(results_directory)
    require(production_projects and len(production_projects) <= 24 and len(set(production_projects)) == len(production_projects))
    for project in production_projects:
        require(re.fullmatch(r'[A-Za-z][A-Za-z0-9]*(?:\.[A-Za-z][A-Za-z0-9]*)*', project))
        require((project == stem or project.startswith(stem+'.')) and not any(part.endswith('Tests') or part in ('Tests','Acceptance') for part in project.split('.')))
    selected = []
    sources = []
    retained_bytes = 0
    def retain(name, data, original_hash, transform):
        nonlocal retained_bytes
        require(len(selected)+len(sources) < MAX_FILES and retained_bytes+len(data) <= MAX_TOTAL)
        selected.append((name, data, original_hash, transform))
        retained_bytes += len(data)
    coverage_available = False
    trx_available = False
    results = workspace/results_directory
    if results.exists():
        require(results.resolve().is_relative_to(workspace) and not results.is_symlink())
        for path in sorted(results.rglob('*')):
            if path.name != 'coverage.cobertura.xml' and path.suffix != '.trx':
                continue
            name = relative_name(path.relative_to(workspace).as_posix())
            data = read_owned(workspace, path)
            if path.suffix == '.trx':
                retain(name, outcome_trx(data), digest(data), 'outcome-only-trx/v1')
                trx_available = True
            else:
                retain(name, coverage_bytes(data), digest(data), 'verbatim')
                coverage_available = True
    settings = workspace/'coverage.runsettings'
    if settings.exists():
        data = read_owned(workspace, settings)
        settings_xml = parse_xml(data)
        require(settings_xml.tag == 'RunSettings')
        safe_settings = {'RunSettings','DataCollectionRunSettings','DataCollectors','DataCollector','Configuration',
                         'Format','ExcludeByFile','ExcludeByAttribute','Include','Exclude','SkipAutoProps','SingleHit',
                         'UseSourceLink','IncludeTestAssembly'}
        require(all(node.tag in safe_settings for node in settings_xml.iter()))
        retain('coverage.runsettings', data, digest(data), 'verbatim')
    binaries = {}
    for project in production_projects:
        binaries[project] = {}
        directory = workspace/project
        for extension in ('dll','pdb'):
            path = directory/'bin/Release/net10.0'/f'{project}.{extension}'
            binaries[project][extension] = path.exists()
            if path.exists():
                data = read_owned(workspace, path)
                require(len(data) > 0)
                retain(path.relative_to(workspace).as_posix(), data, digest(data), 'verbatim')
        source_start = len(sources)
        for path in sorted(directory.rglob('*.cs')):
            name = relative_source_name(path.relative_to(workspace).as_posix())
            data = read_owned(workspace, path)
            require(len(selected)+len(sources) < MAX_FILES)
            sources.append({'path':name,'sha256':digest(data),'bytes':len(data)})
        binaries[project]['sourceCandidates'] = len(sources)-source_start
    require(len(selected)+len(sources) <= MAX_FILES and sum(len(data) for _,data,_,_ in selected) <= MAX_TOTAL)
    require(source_head(workspace) == source_revision)
    stage = Path(tempfile.mkdtemp(prefix='validation-evidence-', dir=runner_temp))
    files = []
    for name,data,original_hash,transform in selected:
        target = stage/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        files.append({'path':name,'bytes':len(data),'sha256':digest(data),'originalSha256':original_hash,'transform':transform})
    complete = coverage_available and all(all(v.values()) for v in binaries.values()) and bool(sources)
    (stage/'source-map.json').write_text(json.dumps({'schemaVersion':1,'files':sources,'compiledMembershipCertified':False}, sort_keys=True)+'\n')
    (stage/'availability.json').write_text(json.dumps({'schemaVersion':1,'sourceRevision':source_revision,'repository':repository,
        'coverageAvailable':coverage_available,'trxAvailable':trx_available,'productionBinaries':binaries,'files':files,
        'complete':complete,'generatedInclusiveCertified':False,'sourceMapAttestation':False,
        'productionBinaryValidityCertified':False,'testOrCoverageAcceptanceCertified':False}, sort_keys=True)+'\n')
    return stage, complete


def main():
    stage, complete = prepare(workspace=os.environ['GITHUB_WORKSPACE'], runner_temp=os.environ['RUNNER_TEMP'],
        repository=os.environ['GITHUB_REPOSITORY'], source_revision=os.environ['GITHUB_SHA'],
        results_directory=os.environ['RESULTS_DIRECTORY'], production_projects=os.environ['PRODUCTION_PROJECTS'].splitlines())
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
        output.write('artifact-path='+str(stage)+'\n')
    if not complete:
        raise EvidenceFailure('evidence retention incomplete')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('[validation-evidence] FAILED: required or safe evidence unavailable; details redacted', file=sys.stderr)
        sys.exit(2)
