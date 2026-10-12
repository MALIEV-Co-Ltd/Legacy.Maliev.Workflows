"""Authored deterministic controls; synthetic fixtures never certify kernel execution."""
import copy
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from normal_validation_lifecycle import verify
from normal_validation_custody import unique as unique_pairs, PHASES


class LifecycleControls(unittest.TestCase):
    def fixture(self):
        unit = 'n62-'+'c'*32+'-'+'f'*32+'.service'
        header = dict(producer='a'*40, run=1, attempt=1, job=2, head='b'*40, boot='00000000-0000-0000-0000-000000000000', resourceRun='c'*32)
        scope = dict(path='/sys/fs/cgroup/'+unit, device=1, inode=2, cpuMax=[200000,100000], memoryMax=4294967296, memorySwapMax=0)
        controller = dict(scope=scope, namespace=dict(noNewPrivileges=True,seccomp=2,cgroupMountsReadOnly=True,mountNamespace='mnt:[123]'), invocation='d'*32, unit=unit)
        sdk = dict(pid=10, birthTicks=20, executable='/dotnet', executableSha256='e'*64, cgroup='0::/'+unit)
        command = dict(phase='restore', startedMono=1, observedAtMono=5, nativeDeadlineMono=10, members=[dict(sdk, role='sdk')])
        before = dict(observedAtMono=2, scope=scope, namespace=controller['namespace'], helper=dict(sdk, executable='/python'), sdk=sdk,
                      manager=dict(InvocationID='d'*32, ExitType='cgroup', RemainAfterExit='yes', KillMode='control-group', MemoryMax='4294967296', MemorySwapMax='0', CPUQuotaPerSecUSec='2s'))
        terminal = dict(observedAtMono=3, nativePidfdExited=True,
                        manager=dict(InvocationID='d'*32, ExitType='cgroup', RemainAfterExit='yes', ActiveState='active', SubState='exited', Result='success', ExecMainStatus='0'),
                        scopeObservation=dict(scope=scope, kind='same-invocation-manager-cgroup-exited', populated=0, subtreePids=[]))
        removal = dict(observedAtMono=4, unit=unit, invocation='d'*32, unitTerminal=True, scopeAbsent=True, wrapperPidfdExited=True)
        value = dict(header, schema='normal-stage-lifecycle-v1', phase='restore', preExec=before, terminal=terminal, removal=removal)
        return value, header, command, controller

    def test_fixture_reader_only(self):
        self.assertEqual(4, verify(*self.fixture()))

    def test_missing_terminal_replay_overlap_and_absent_path_rejected(self):
        for mutation in ('missing', 'replay', 'overlap', 'path-only', 'populated', 'pidfd', 'scope-reuse', 'namespace', 'removal'):
            value, header, command, controller = copy.deepcopy(self.fixture())
            if mutation == 'missing': value['terminal'].pop('manager')
            if mutation == 'replay': value['terminal']['manager']['InvocationID'] = 'f'*32
            if mutation == 'overlap': value['removal']['observedAtMono'] = 2
            if mutation == 'path-only': value['terminal']['scopeObservation']['kind'] = 'pathname-absent'
            if mutation == 'populated': value['terminal']['scopeObservation']['populated'] = 1
            if mutation == 'pidfd': value['terminal']['nativePidfdExited'] = False
            if mutation == 'scope-reuse': value['preExec']['scope'] = dict(controller['scope'], inode=99)
            if mutation == 'namespace': value['preExec']['namespace'] = {}
            if mutation == 'removal': value['removal']['wrapperPidfdExited'] = False
            with self.subTest(mutation=mutation), self.assertRaises((ValueError, KeyError)):
                verify(value, header, command, controller)

    def test_duplicate_json_keys(self):
        with self.assertRaises(ValueError): unique_pairs([('run',1),('run',1)])

    def test_nested_types_reject_equal_numeric_and_bool_values(self):
        for mutation in ('header-float','header-bool','device-float','inode-float','memory-float','swap-bool','cpu-float','namespace-int','namespace-readonly-int','seccomp-float','extra-scope','extra-namespace','manager-int'):
            value, header, command, controller = copy.deepcopy(self.fixture())
            # Copy the nested evidence separately so an equal numeric value cannot hide by alias.
            value = copy.deepcopy(value)
            if mutation == 'header-float': value['run'] = 1.0
            if mutation == 'header-bool': value['attempt'] = True
            if mutation == 'device-float': value['preExec']['scope']['device'] = 1.0
            if mutation == 'inode-float': value['preExec']['scope']['inode'] = 2.0
            if mutation == 'memory-float': value['preExec']['scope']['memoryMax'] = 4294967296.0
            if mutation == 'swap-bool': value['preExec']['scope']['memorySwapMax'] = False
            if mutation == 'cpu-float': value['preExec']['scope']['cpuMax'][0] = 200000.0
            if mutation == 'namespace-int': value['preExec']['namespace']['noNewPrivileges'] = 1
            if mutation == 'namespace-readonly-int': value['preExec']['namespace']['cgroupMountsReadOnly'] = 1
            if mutation == 'seccomp-float': value['preExec']['namespace']['seccomp'] = 2.0
            if mutation == 'extra-scope': value['preExec']['scope']['extra'] = 1
            if mutation == 'extra-namespace': value['preExec']['namespace']['extra'] = True
            if mutation == 'manager-int': value['terminal']['manager']['ExecMainStatus'] = 0
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): verify(value,header,command,controller)

    def test_actual_producer_order(self):
        self.assertEqual(('restore','build','format','test','package-audit'), PHASES)


if __name__ == '__main__': unittest.main()
