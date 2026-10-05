"""Read-only source observation; no fetch, mutation, build or deployment adapter."""
import os
import pathlib
import re
import subprocess
import time
import threading
import json
import sys


class SourceFailure(RuntimeError):
    def __init__(self, step, exit_code=1):
        super().__init__('Release source rejected at ' + step)
        self.step = step
        self.exit_code = exit_code


def read_git_output(command, root, environment, timeout, step):
    """Bound both native streams before decoding; errors never echo provider bytes."""
    if timeout <= 0:
        raise SourceFailure(step)
    try:
        process = subprocess.Popen(command, cwd=root, env=environment, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, bufsize=0)
    except Exception:
        raise SourceFailure(step) from None
    outputs = [bytearray(), bytearray()]
    completed = [threading.Event(), threading.Event()]
    invalid = threading.Event()

    def drain(index, pipe):
        try:
            while True:
                data = os.read(pipe.fileno(), 4096)
                if not data:
                    break
                if len(outputs[index]) + len(data) > 16384:
                    invalid.set()
                    break
                outputs[index].extend(data)
        except Exception:
            invalid.set()
        finally:
            completed[index].set()

    readers = [threading.Thread(target=drain, args=(i, pipe), daemon=True)
               for i, pipe in enumerate((process.stdout, process.stderr))]
    for reader in readers:
        reader.start()
    deadline = time.monotonic() + timeout
    try:
        while not (process.poll() is not None and all(done.is_set() for done in completed)):
            if invalid.is_set() or time.monotonic() >= deadline:
                raise SourceFailure(step)
            time.sleep(0.005)
        if invalid.is_set():
            raise SourceFailure(step)
        if process.returncode != 0:
            raise SourceFailure(step, process.returncode if 0 < process.returncode <= 255 else 1)
        try:
            return bytes(outputs[0]).decode('utf-8', errors='strict')
        except UnicodeError:
            raise SourceFailure(step) from None
    finally:
        if process.poll() is None:
            process.kill()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass
        for reader in readers:
            reader.join(timeout=0.1)
        for pipe in (process.stdout, process.stderr):
            pipe.close()


def verify_release_source(repository_root, expected_commit, expected_origin, *, allow_fixture_origin=False, timeout_seconds=10):
    if not isinstance(expected_commit, str) or not re.fullmatch(r'[a-f0-9]{40}', expected_commit):
        raise SourceFailure('INPUT')
    approved = isinstance(expected_origin, str) and re.fullmatch(r'https://github\.com/MALIEV-Co-Ltd/(?:maliev-web|Legacy\.Maliev\.[A-Za-z]+)\.git', expected_origin)
    fixture = type(allow_fixture_origin) is bool and allow_fixture_origin and isinstance(expected_origin, str) and expected_origin.startswith('file:///')
    if not (approved or fixture) or type(allow_fixture_origin) is not bool:
        raise SourceFailure('INPUT')
    try:
        root = pathlib.Path(repository_root).resolve(strict=True)
        if not root.is_dir() or type(timeout_seconds) not in (int, float) or not 0 < timeout_seconds <= 30:
            raise ValueError()
    except Exception:
        raise SourceFailure('INPUT') from None
    deadline = time.monotonic() + timeout_seconds
    # Ambient repository/index/object selectors and config-injection variables
    # must not redirect this explicit checkout or alter its origin observation.
    environment = {key: value for key, value in os.environ.items() if not key.upper().startswith('GIT_')}
    environment.update(GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0', GIT_NO_REPLACE_OBJECTS='1', GCM_INTERACTIVE='Never')

    def read(step, *arguments):
        return read_git_output(['git', '-c', 'core.fsmonitor=false', '-c', 'core.untrackedCache=false', *arguments],
                               root, environment, deadline - time.monotonic(), step)

    def exact_line(value):
        if not value.endswith('\n') or '\n' in value[:-1] or '\r' in value.rstrip('\r\n'):
            raise SourceFailure('REPOSITORY')
        return value.rstrip('\r\n')

    top = exact_line(read('REPOSITORY', 'rev-parse', '--show-toplevel'))
    if pathlib.Path(top).resolve() != root:
        raise SourceFailure('REPOSITORY')
    head = exact_line(read('HEAD', 'rev-parse', 'HEAD'))
    if head != expected_commit:
        raise SourceFailure('HEAD')
    if read('CLEAN', 'status', '--porcelain=v1', '--untracked-files=normal', '--ignore-submodules=none'):
        raise SourceFailure('CLEAN')
    origin = exact_line(read('ORIGIN', 'remote', 'get-url', '--all', 'origin'))
    if origin != expected_origin:
        raise SourceFailure('ORIGIN')
    remote = read('REMOTE_MAIN', 'ls-remote', '--exit-code', '--refs', 'origin', 'refs/heads/main')
    match = re.fullmatch(r'([a-f0-9]{40})\trefs/heads/main\r?\n', remote)
    if match is None or match[1] != expected_commit:
        raise SourceFailure('REMOTE_MAIN')
    # Reobserve local state after transport. This narrows the observation
    # window; it cannot atomically lock another process or remote main.
    if exact_line(read('HEAD', 'rev-parse', 'HEAD')) != expected_commit:
        raise SourceFailure('HEAD')
    if read('CLEAN', 'status', '--porcelain=v1', '--untracked-files=normal', '--ignore-submodules=none'):
        raise SourceFailure('CLEAN')
    if exact_line(read('ORIGIN', 'remote', 'get-url', '--all', 'origin')) != expected_origin:
        raise SourceFailure('ORIGIN')
    return dict(schemaVersion='offline-release-source/v1', sourceCommit=expected_commit,
                repositoryIdentity='isolated-fixture-origin' if fixture else expected_origin,
                cleanObserved=True, remoteMainObserved=True, deploymentAllowed=False, liveAccepted=False)


def main():
    def unique_pairs(pairs):
        values = {}
        for key, value in pairs:
            if key in values:
                raise ValueError()
            values[key] = value
        return values
    try:
        raw = sys.stdin.buffer.read(8193)
        if len(raw) > 8192:
            raise ValueError()
        request = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_pairs)
        if not isinstance(request, dict) or set(request) != {'repositoryRoot', 'expectedCommit', 'expectedOrigin', 'allowFixtureOrigin'}:
            raise ValueError()
        proof = verify_release_source(request['repositoryRoot'], request['expectedCommit'], request['expectedOrigin'],
                                      allow_fixture_origin=request['allowFixtureOrigin'])
        print(json.dumps(proof, separators=(',', ':')))
        return 0
    except SourceFailure as failure:
        print(json.dumps({'schemaVersion': 'offline-release-source/v1', 'rejectedAt': failure.step,
                          'exitCode': failure.exit_code, 'deploymentAllowed': False, 'liveAccepted': False}, separators=(',', ':')))
        return failure.exit_code
    except Exception:
        print('{"schemaVersion":"offline-release-source/v1","rejectedAt":"INPUT","exitCode":1,"deploymentAllowed":false,"liveAccepted":false}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
