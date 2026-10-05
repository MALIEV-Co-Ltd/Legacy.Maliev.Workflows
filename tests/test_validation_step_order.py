"""Execute extracted trusted step bodies with an owned fake dotnet, never an SDK."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ('actions/dotnet-validate/action.yml', '.github/workflows/dotnet-validate.yml')
NAMES = ('Build', 'Verify formatting', 'Test', 'Audit vulnerable packages')
FROZEN_STEP_HASHES = {'actions/dotnet-validate/action.yml': {'Build': 'bec367edcb13163d0e6b51079b57b2621b63e4c8691fe4857a371e6627054b95', 'Test': '295d7d40a1e9f2ba193ad590b3a7926af7e70545d038735934019444dbb681f4', 'Verify formatting': 'd0964b847b652d47a61f2c337bbb96faf1b4478ffefe026089d25bf445f623e9', 'Audit vulnerable packages': '1ef055126bc37f47d4c61a8391836033f0115164eb486db78c890ec7a1ab09a6'}, '.github/workflows/dotnet-validate.yml': {'Build': '82ab49d47741e396e2d56ffc57ea5efe0361694b8d470a5e548b205031be887b', 'Test': '06100dcac73217924bc684667e52a4a3336b0e3d8d6bdde82d307a52f6b4465a', 'Verify formatting': '4dbb603a004ca71bdfdd783f6be970d274e06bc1048a1a8059185d9c7187ccf5', 'Audit vulnerable packages': '36417eb16f0f8bc47cbbb7e358a44df3a709386522f8860e7ddb08b06b18267a'}}


def steps(source):
    matches = list(re.finditer(r'(?m)^([ ]+)- name: (.+)\n', source))
    return {m.group(2): source[m.start():matches[i+1].start() if i+1 < len(matches) else len(source)]
            for i,m in enumerate(matches)}


def body(step):
    match = re.search(r'(?m)^([ ]+)run: (.+)\n?', step)
    assert match
    if match.group(2) != '|':
        return match.group(2)+'\n'
    indent = len(match.group(1))+2
    lines = []
    for line in step[match.end():].splitlines():
        if line.strip() and len(line)-len(line.lstrip()) < indent:
            break
        if line.strip(): lines.append(line[indent:])
    return '\n'.join(lines)+'\n'


class ValidationOrderTests(unittest.TestCase):
    def execute(self, relative, build=0, formatting=0, local='false'):
        source = (ROOT/relative).read_text()
        selected = steps(source)
        ordered = [name for name in selected if name in NAMES]
        with tempfile.TemporaryDirectory(prefix='validation-order-') as temporary:
            root = Path(temporary)
            fake = root/'dotnet'
            fake.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "$TRACE"\ncase "$1" in\n build) exit "$BUILD_EXIT";;\n format) exit "$FORMAT_EXIT";;\n *) exit 0;;\nesac\n', newline='\n')
            fake.chmod(0o700)
            script = root/'actual-steps.sh'
            script.write_text(''.join(body(selected[name]).replace('${{ inputs.solution }}','Fixture.slnx') for name in ordered),newline='\n')
            trace = root/'trace.txt'
            environment = dict(os.environ, PATH=str(root)+os.pathsep+os.environ['PATH'],
                TRACE=str(trace),BUILD_EXIT=str(build),FORMAT_EXIT=str(formatting),
                USE_LOCAL_MALIEV_DEPENDENCIES=local)
            bash = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else 'bash'
            result = subprocess.run([bash,'--noprofile','--norc','-e','-o','pipefail',str(script)],
                env=environment,capture_output=True,text=True,timeout=10)
            self.assertEqual('',result.stdout)
            self.assertEqual('',result.stderr)
            return result.returncode, trace.read_text().splitlines()

    def test_exact_original_steps_are_only_reordered_and_have_no_failure_waiver(self):
        for relative in SOURCES:
            with self.subTest(source=relative):
                source = (ROOT/relative).read_text()
                selected = steps(source)
                self.assertEqual(list(NAMES),[name for name in selected if name in NAMES])
                for name in NAMES:
                    self.assertEqual(FROZEN_STEP_HASHES[relative][name],hashlib.sha256(selected[name].encode()).hexdigest())
                    self.assertNotIn('continue-on-error',selected[name])
                    self.assertNotRegex(selected[name],r'(?m)^\s+if:')
                self.assertLess(source.index('- name: Restore'),source.index('- name: Build'))

    def test_actual_build_failure_stops_before_format_and_test(self):
        for relative in SOURCES:
            with self.subTest(source=relative):
                status,commands = self.execute(relative,build=17)
                self.assertEqual(17,status)
                self.assertEqual(['build Fixture.slnx --configuration Release --no-restore'],commands)

    def test_actual_format_failure_stops_before_test_and_audit(self):
        for relative in SOURCES:
            with self.subTest(source=relative):
                status,commands = self.execute(relative,formatting=23)
                self.assertEqual(23,status)
                self.assertEqual(['build Fixture.slnx --configuration Release --no-restore',
                    'format Fixture.slnx --verify-no-changes --no-restore'],commands)

    def test_actual_success_preserves_all_argv_and_audit_in_both_dependency_modes(self):
        for relative in SOURCES:
            for local in ('true','false'):
                with self.subTest(source=relative,local=local):
                    status,commands = self.execute(relative,local=local)
                    self.assertEqual(0,status)
                    self.assertEqual(['build Fixture.slnx --configuration Release --no-restore',
                        'format Fixture.slnx --verify-no-changes --no-restore',
                        'test Fixture.slnx --configuration Release --no-build --no-restore',
                        'list Fixture.slnx package --vulnerable --include-transitive --no-restore'],commands)


if __name__ == '__main__':
    unittest.main(verbosity=2)
