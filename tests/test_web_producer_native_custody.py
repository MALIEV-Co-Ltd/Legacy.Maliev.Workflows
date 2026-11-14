"""Isolated mocked CLI controls; no Docker or subprocess is started."""
import ast
import importlib.util
import textwrap
import contextlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

workflow = (Path(__file__).resolve().parents[1] / '.github/workflows/publish-image.yml').read_text(encoding='utf-8')
segment = workflow.split('      - name: Verify packaged Web assets and source revision\n', 1)[1].split('\n      - name: Scan the built image before publication', 1)[0]
tree = ast.parse(textwrap.dedent(segment.split('        run: |\n', 1)[1]))
names = {'open_receipt', 'append_event', 'child_identity', 'run_bounded', 'inspect',
         'verify_owned_container', 'release_owned_container', 'unique_object', 'native', 'on_termination',
         'owned_export_directory', 'check_inspection_deadline', 'inspection_watchdog',
         'cleanup_watchdog', 'watchdog_until'}
nodes = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom)) or isinstance(n, ast.FunctionDef) and n.name in names]
subject = importlib.util.module_from_spec(importlib.util.spec_from_loader('inline_custody', loader=None))
exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), '<inline-custody>', 'exec'), subject.__dict__)
producer_native = subject.native



class Pipe:
    def __init__(self, number): self.number = number
    def fileno(self): return self.number
    def close(self): pass


class Child:
    def __init__(self, code=0):
        self.pid, self.stdout, self.stderr = 42, Pipe(10), Pipe(11)
        self.code, self.finished = code, False
    def poll(self): return self.code if self.finished else None
    def wait(self, timeout): self.finished = True; return self.code
    def terminate(self): self.finished = True; self.code = -15
    def kill(self): self.finished = True; self.code = -9


class Selector:
    def __init__(self): self.entries = {}
    def register(self, pipe, event, name): self.entries[pipe.fileno()] = SimpleNamespace(fileobj=pipe, data=name)
    def unregister(self, pipe): self.entries.pop(pipe.fileno())
    def get_map(self): return self.entries
    def select(self, timeout): return [(entry, 1) for entry in list(self.entries.values())]
    def close(self): pass


class Controls(unittest.TestCase):
    def test_shared_deadline_reserves_cleanup_and_child_reap(self):
        subject.receipt_fd = 1
        subject.inspection_deadline = 205
        subject.cleanup_deadline = 275
        for cleanup, now, expected in ((False, 200, None), (False, 190, 10),
                                       (True, 200, 70), (True, 270, None)):
            subject.in_cleanup = cleanup
            with self.subTest(cleanup=cleanup, now=now), \
                 patch.object(subject.time, 'monotonic', return_value=now), \
                 patch.object(subject, 'run_bounded', return_value='ok') as run:
                if expected is None:
                    with self.assertRaises(TimeoutError): producer_native(['info'])
                    run.assert_not_called()
                else:
                    self.assertEqual('ok', producer_native(['info']))
                    self.assertEqual(expected, run.call_args.kwargs['timeout'])

    def test_termination_raises_to_allow_exact_child_cleanup(self):
        with patch.object(subject.signal, 'signal') as install:
            with self.assertRaises(InterruptedError): subject.on_termination(15, None)
            install.assert_called_once_with(subject.signal.SIGTERM, subject.signal.SIG_IGN)

    def test_unsettled_export_preserves_directory_and_file(self):
        with patch.object(subject, 'inspection_watchdog', return_value=contextlib.nullcontext()), \
             patch.object(subject, 'cleanup_watchdog', return_value=contextlib.nullcontext()), \
             patch.object(subject, 'append_event'), \
             patch.object(subject.tempfile, 'mkdtemp', return_value='owned-directory'), \
             patch.object(subject.os, 'unlink') as unlink, patch.object(subject.os, 'rmdir') as rmdir:
            with self.assertRaises(TimeoutError):
                with subject.owned_export_directory():
                    raise TimeoutError('export unsettled')
            unlink.assert_not_called()
            rmdir.assert_not_called()

    def test_settled_export_removes_only_exact_regular_archive_and_directory(self):
        info = SimpleNamespace(st_mode=0o100600, st_nlink=1)
        subject.receipt_fd = 1
        with patch.object(subject, 'inspection_watchdog', return_value=contextlib.nullcontext()), \
             patch.object(subject, 'cleanup_watchdog', return_value=contextlib.nullcontext()), \
             patch.object(subject, 'append_event') as record, \
             patch.object(subject.tempfile, 'mkdtemp', return_value='owned-directory'), \
             patch.object(subject.os, 'lstat', return_value=info), \
             patch.object(subject.os, 'unlink') as unlink, patch.object(subject.os, 'rmdir') as rmdir:
            with subject.owned_export_directory() as (archive, state):
                state['exportSettled'] = True
            unlink.assert_called_once_with(archive)
            rmdir.assert_called_once_with('owned-directory')
            self.assertEqual(['invoked', 'settled'], [call.args[1]['event'] for call in record.call_args_list])

    def test_caller_deadline_missing_invalid_or_expired_fails_before_cli(self):
        base = {'CALLER_REPOSITORY': 'MALIEV-Co-Ltd/Legacy.Maliev.Web',
                'WEB_PRODUCER_CUSTODY': 'caller'}
        for value in ('nan', 'inf', '99', '401'):
            with self.subTest(value=value), \
                 patch.dict(subject.os.environ, dict(base, WEB_PRODUCER_OUTER_DEADLINE=value), clear=True), \
                 patch.object(subject.time, 'monotonic', return_value=100), \
                 patch.object(subject, 'native') as native:
                with self.assertRaises(ValueError): subject.inspect()
                native.assert_not_called()

    def test_archive_deadline_fails_closed(self):
        subject.inspection_deadline = 200
        with patch.object(subject.time, 'monotonic', return_value=200):
            with self.assertRaises(TimeoutError): subject.check_inspection_deadline()

    def test_archive_watchdog_is_bounded_and_restored(self):
        subject.inspection_deadline = 200
        with patch.object(subject.signal, 'ITIMER_REAL', 0, create=True), \
             patch.object(subject.signal, 'SIGALRM', 14, create=True), \
             patch.object(subject.signal, 'getitimer', return_value=(0.0, 0.0), create=True), \
             patch.object(subject.signal, 'getsignal', return_value='prior'), \
             patch.object(subject.signal, 'signal') as handler, \
             patch.object(subject.signal, 'setitimer', create=True) as timer, \
             patch.object(subject.time, 'monotonic', return_value=150):
            with subject.inspection_watchdog(): pass
            self.assertEqual([((0, 50),), ((0, 0),)], [(call.args,) for call in timer.call_args_list])
            self.assertEqual((14, 'prior'), handler.call_args.args)

    def run_case(self, phase, chunks, maximum=100, timeout=120, terminate_error=None,
                 launch_signal=None, launch_error=None):
        child, events = Child(), []
        handlers = {}
        def install(signum, handler): handlers[signum] = handler
        def launch(*args, **kwargs):
            if launch_signal is not None: handlers[launch_signal](launch_signal, None)
            if launch_error is not None: raise launch_error
            return child
        if terminate_error:
            child.terminate = lambda: (_ for _ in ()).throw(terminate_error)
        streams = {10: iter(chunks), 11: iter([b''])}
        with patch.object(subject.signal, 'SIGALRM', 14, create=True), \
             patch.object(subject.signal, 'getsignal', return_value='previous'), \
             patch.object(subject.signal, 'signal', side_effect=install), \
             patch.object(subject.subprocess, 'Popen', side_effect=launch), \
             patch.object(subject.selectors, 'DefaultSelector', Selector), \
             patch.object(subject.os, 'set_blocking'), \
             patch.object(subject.os, 'read', side_effect=lambda fd, n: next(streams[fd])), \
             patch.object(subject, 'child_identity', return_value={'pid': 42, 'startTicks': 10, 'executable': '/docker', 'device': 1, 'inode': 2}), \
             patch.object(subject, 'append_event', side_effect=lambda fd, e: events.append(e)):
            try:
                result = subject.run_bounded(['docker', phase], phase, 3, maximum=maximum, timeout=timeout)
                return result, None, events, child
            except BaseException as error:
                return None, error, events, child

    def test_success_records_each_phase(self):
        for phase in ('create', 'export', 'rm'):
            with self.subTest(phase=phase):
                result, error, events, _ = self.run_case(phase, [b'output', b''])
                self.assertIsNone(error)
                self.assertEqual('output', result)
                self.assertEqual(['invocation-intent', 'started', 'terminal'], [e['event'] for e in events])
                self.assertEqual('command-completed', events[-1]['daemonSettlement'])

    def test_overflow_stays_unproved_and_exact_child_is_stopped(self):
        _, error, events, child = self.run_case('export', [b'123456'], maximum=5)
        self.assertIsInstance(error, ValueError)
        self.assertTrue(child.finished)
        self.assertEqual('unproved', events[-1]['daemonSettlement'])

    def test_timeout_is_unproved_even_if_a_later_remove_succeeds(self):
        _, error, export, _ = self.run_case('export', [b''], timeout=0)
        _, remove_error, removal, _ = self.run_case('rm', [b'ok', b''])
        self.assertIsInstance(error, subject.subprocess.TimeoutExpired)
        self.assertIsNone(remove_error)
        self.assertEqual('unproved', export[-1]['daemonSettlement'])
        self.assertEqual('command-completed', removal[-1]['daemonSettlement'])

    def test_timeout_remains_primary_when_exact_child_cleanup_fails(self):
        _, error, events, _ = self.run_case('export', [b''], timeout=0,
                                            terminate_error=OSError('stop failed'))
        self.assertIsInstance(error, subject.subprocess.TimeoutExpired)
        self.assertIn('Exact CLI cleanup failed', error.__notes__[0])
        self.assertEqual('unproved', events[-1]['daemonSettlement'])

    def test_sigterm_and_alarm_at_launch_reap_exact_returned_child(self):
        for signum, error_type in ((subject.signal.SIGTERM, InterruptedError), (14, TimeoutError)):
            with self.subTest(signal=signum):
                _, error, events, child = self.run_case('export', [b''], launch_signal=signum)
                self.assertIsInstance(error, error_type)
                self.assertTrue(child.finished)
                self.assertEqual(42, events[-1]['cli']['pid'])
                self.assertEqual('unproved', events[-1]['daemonSettlement'])

    def test_launch_failure_records_unavailable_handle_as_unproved(self):
        _, error, events, _ = self.run_case('create', [b''], launch_error=OSError('spawn uncertain'))
        self.assertIsInstance(error, OSError)
        self.assertIsNone(events[-1]['cli']['pid'])
        self.assertEqual('unproved', events[-1]['daemonSettlement'])

    def test_full_inspect_timeout_preserves_primary_with_or_without_cleanup_failure(self):
        image, container, revision = 'sha256:' + 'c' * 64, 'a' * 64, 'd' * 40
        environment = {'CALLER_REPOSITORY': 'MALIEV-Co-Ltd/Legacy.Maliev.Web',
                       'SOURCE_DOCKERFILE': 'Legacy.Maliev.Web/Dockerfile',
                       'EXPECTED_SOURCE_REVISION': revision, 'BUILT_IMAGE': 'owned:tag'}
        for fail_cleanup in (False, True):
            calls = []
            def native(args):
                calls.append(args)
                if args[:2] == ['image', 'inspect']:
                    return revision if 'revision' in args[3] else image
                if args[0] == 'create': return container
                if args[:2] == ['container', 'inspect']:
                    return f'{container}|/legacy-web-assets-check-' + 'b' * 32 + f'|{image}|created'
                if args[:2] == ['container', 'export']:
                    raise subject.subprocess.TimeoutExpired(args, 120)
                if args[:2] == ['container', 'rm']:
                    if fail_cleanup: raise OSError('remove failed')
                    return container
                if args[0] == 'info': return 'daemon'
                if args[:2] == ['container', 'ls']: return ''
                raise AssertionError(args)
            subject.native = native
            with self.subTest(fail_cleanup=fail_cleanup), \
                 patch.dict(subject.os.environ, environment, clear=True), \
                 patch.object(subject.uuid, 'uuid4', return_value=SimpleNamespace(hex='b' * 32)), \
                 patch.object(subject, 'owned_export_directory', return_value=contextlib.nullcontext(('temporary/filesystem.tar', {'exportSettled': False}))):
                with self.assertRaises(subject.subprocess.TimeoutExpired) as caught:
                    subject.inspect()
                self.assertTrue(any(args[:2] == ['container', 'rm'] for args in calls))
                if fail_cleanup:
                    self.assertIn('cleanup is unresolved', caught.exception.__notes__[0])

    def test_full_inspect_success_validates_assets_and_exact_cleanup(self):
        image, container, revision = 'sha256:' + 'c' * 64, 'a' * 64, 'd' * 40
        inspect_node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'inspect')
        manifest_node = next(n for n in inspect_node.body if isinstance(n, ast.Assign)
                             and any(isinstance(t, ast.Name) and t.id == 'manifest' for t in n.targets))
        manifest = ast.literal_eval(manifest_node.value)
        names = manifest['scripts'] + manifest['routeScripts'] + list(manifest['routeScopedModules'].values())
        names += manifest['styles'] + manifest['routeStyles']
        files = {'app/wwwroot/dist/' + name: b'asset' for name in names}
        files['app/wwwroot/dist/asset-manifest.json'] = json.dumps(manifest).encode()
        fonts = ['outfit-latin-' + weight + '-normal-1.woff2' for weight in ('400', '500', '600')]
        fonts += ['noto-sans-thai-thai-' + weight + '-normal-1.woff2' for weight in ('400', '500', '600')]
        fonts += ['fa-brands-400-1.woff2', 'fa-regular-400-1.woff2', 'fa-solid-900-1.woff2', 'fa-v4compatibility-1.woff2']
        for font in fonts: files['app/wwwroot/dist/assets/' + font] = b'font'
        files['app/wwwroot/dist/site.min.css'] = ' '.join('url(./assets/' + font + ')' for font in fonts).encode()
        class Archive:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def __iter__(self):
                return iter([SimpleNamespace(name=path, size=len(data), isfile=lambda: True) for path, data in files.items()])
            def extractfile(self, member): return io.BytesIO(files[member.name])
        calls = []
        def native(args):
            calls.append(args)
            if args[:2] == ['image', 'inspect']: return revision if 'revision' in args[3] else image
            if args[0] == 'create': return container
            if args[:2] == ['container', 'inspect']: return f'{container}|/legacy-web-assets-check-' + 'b' * 32 + f'|{image}|created'
            if args[:2] == ['container', 'export']: return ''
            if args[:2] == ['container', 'rm']: return container
            if args[0] == 'info': return 'daemon'
            if args[:2] == ['container', 'ls']: return ''
            raise AssertionError(args)
        subject.native = native
        environment = {'CALLER_REPOSITORY': 'MALIEV-Co-Ltd/Legacy.Maliev.Web',
                       'SOURCE_DOCKERFILE': 'Legacy.Maliev.Web/Dockerfile',
                       'EXPECTED_SOURCE_REVISION': revision, 'BUILT_IMAGE': 'owned:tag'}
        with patch.dict(subject.os.environ, environment, clear=True), \
             patch.object(subject.uuid, 'uuid4', return_value=SimpleNamespace(hex='b' * 32)), \
             patch.object(subject, 'owned_export_directory', return_value=contextlib.nullcontext(('temporary/filesystem.tar', {'exportSettled': False}))), \
             patch.object(subject.os, 'lstat', return_value=SimpleNamespace(st_mode=0o100600, st_nlink=1, st_size=100)), \
             patch.object(subject.tarfile, 'open', return_value=Archive()):
            result = subject.inspect()
        self.assertEqual(25, result['assetCount'])
        self.assertEqual(10, result['fontCount'])
        self.assertEqual(container, result['inspectionContainerId'])
        self.assertEqual('settled', result['inspectionContainerCleanup'])
        self.assertIn(['container', 'rm', '--force', container], calls)


if __name__ == '__main__': unittest.main()
