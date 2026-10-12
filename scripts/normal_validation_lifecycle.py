"""Historical kernel/manager authority, never absent pathname alone."""
import math
import re


def fields(value, required):
    if type(value) is not dict or set(value) != required:
        raise ValueError('Exact nested lifecycle fields required')


def integer(value, minimum=1):
    if type(value) is not int or value < minimum:
        raise ValueError('Strict lifecycle integer required')


def string(value, pattern):
    if type(value) is not str or not re.fullmatch(pattern, value):
        raise ValueError('Strict lifecycle string required')


def scope(value):
    fields(value, {'path','device','inode','cpuMax','memoryMax','memorySwapMax'})
    string(value['path'], r'/sys/fs/cgroup/[^\x00]+')
    integer(value['device'],0); integer(value['inode'])
    integer(value['memoryMax']); integer(value['memorySwapMax'],0)
    if type(value['cpuMax']) is not list or len(value['cpuMax']) != 2:
        raise ValueError('Strict lifecycle CPU tuple required')
    for item in value['cpuMax']: integer(item)
    if value['memoryMax'] != 4294967296 or value['memorySwapMax'] != 0 or value['cpuMax'][0] > 2*value['cpuMax'][1]:
        raise ValueError('Lifecycle kernel limits widened')


def namespace(value):
    fields(value, {'noNewPrivileges','seccomp','cgroupMountsReadOnly','mountNamespace'})
    if value['noNewPrivileges'] is not True or value['cgroupMountsReadOnly'] is not True:
        raise ValueError('Strict lifecycle namespace booleans required')
    integer(value['seccomp'])
    if value['seccomp'] != 2: raise ValueError('Lifecycle seccomp protection missing')
    string(value['mountNamespace'], r'mnt:\[[0-9]+\]')


def manager(value, expected):
    fields(value, set(expected))
    if any(type(item) is not str for item in value.values()) or value != expected:
        raise ValueError('Strict lifecycle manager authority required')


def verify(value, header, command, controller):
    required = {'schema', 'producer', 'run', 'attempt', 'job', 'head', 'boot', 'resourceRun', 'phase', 'preExec', 'terminal', 'removal'}
    fields(value, required)
    for key in ('run','attempt','job'): integer(value[key])
    for key in ('producer','head'): string(value[key], r'[0-9a-f]{40}')
    string(value['boot'], r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}')
    string(value['resourceRun'], r'[0-9a-f]{32}')
    string(value['phase'], r'restore|build|format|test|package-audit')
    if value['schema'] != 'normal-stage-lifecycle-v1':
        raise ValueError('Exact original lifecycle evidence required')
    if any(value[k] != header[k] for k in ('producer','run','attempt','job','head','boot','resourceRun')) or value['phase'] != command['phase']:
        raise ValueError('Lifecycle source/job/phase identity mixed')
    before, terminal, removal = value['preExec'], value['terminal'], value['removal']
    fields(before, {'observedAtMono','scope','namespace','manager','helper','sdk'})
    scope(before['scope']); namespace(before['namespace'])
    if before['scope'] != controller['scope'] or before['namespace'] != controller['namespace']:
        raise ValueError('Actual pre-exec scope/caps/namespace evidence mixed')
    properties = before['manager']
    expected = {'InvocationID':controller['invocation'], 'ExitType':'cgroup', 'RemainAfterExit':'yes',
                'KillMode':'control-group', 'MemoryMax':'4294967296', 'MemorySwapMax':'0', 'CPUQuotaPerSecUSec':'2s'}
    manager(properties, expected)
    helper, sdk = before['helper'], before['sdk']
    for member in (helper,sdk):
        fields(member, {'pid','birthTicks','executable','executableSha256','cgroup'})
        if type(member['pid']) is not int or type(member['birthTicks']) is not int or member['pid'] <= 0 or member['birthTicks'] <= 0:
            raise ValueError('Actual transition kernel identity required')
        string(member['executable'], r'/[^\x00]+')
        string(member['executableSha256'], r'[0-9a-f]{64}')
        string(member['cgroup'], r'0::/[^\x00]+')
    if (helper['pid'],helper['birthTicks'],helper['cgroup']) != (sdk['pid'],sdk['birthTicks'],sdk['cgroup']):
        raise ValueError('Helper to SDK transition escaped kernel custody')
    if sdk['cgroup'] != '0::'+controller['scope']['path'].removeprefix('/sys/fs/cgroup'):
        raise ValueError('Transition belongs to another actual scope')
    if not any(m['role']=='sdk' and m['pid']==sdk['pid'] and m['birthTicks']==sdk['birthTicks']
               and m['executable']==sdk['executable'] and m['executableSha256']==sdk['executableSha256'] for m in command['members']):
        raise ValueError('Lifecycle SDK identity not in actual exited members')
    fields(terminal, {'observedAtMono','nativePidfdExited','manager','scopeObservation'})
    if terminal['nativePidfdExited'] is not True:
        raise ValueError('Actual native kernel exit proof missing')
    expected_terminal = {'InvocationID':controller['invocation'], 'ExitType':'cgroup', 'RemainAfterExit':'yes',
                         'ActiveState':'active', 'SubState':'exited', 'Result':'success', 'ExecMainStatus':'0'}
    manager(terminal['manager'], expected_terminal)
    observation = terminal['scopeObservation']
    fields(observation, {'scope','kind','populated','subtreePids'})
    scope(observation['scope'])
    if observation['scope'] != controller['scope']:
        raise ValueError('Terminal original scope identity missing')
    if observation['kind'] not in ('kernel-populated-zero','same-invocation-manager-cgroup-exited'):
        raise ValueError('Absent pathname alone is not descendant authority')
    if type(observation['populated']) is not int or observation['populated'] != 0 or type(observation['subtreePids']) is not list or observation['subtreePids'] != []:
        raise ValueError('Original descendant terminal proof missing')
    fields(removal, {'observedAtMono','unit','invocation','unitTerminal','scopeAbsent','wrapperPidfdExited'})
    string(removal['unit'], r'n62-[0-9a-f]{32}-[0-9a-f]{32}\.service')
    string(removal['invocation'], r'[0-9a-f]{32}')
    if removal['unit'] != controller['unit'] or removal['invocation'] != controller['invocation']:
        raise ValueError('Removal belongs to another invocation')
    if any(removal[k] is not True for k in ('unitTerminal','scopeAbsent','wrapperPidfdExited')):
        raise ValueError('Owned removal incomplete')
    times = [command['startedMono'], before['observedAtMono'], terminal['observedAtMono'], removal['observedAtMono'], command['observedAtMono']]
    if any(type(x) not in (int,float) or not math.isfinite(x) or x < 0 for x in times) or times != sorted(times):
        raise ValueError('Actual lifecycle chronology invalid')
    if terminal['observedAtMono'] > command['nativeDeadlineMono']:
        raise ValueError('Native completed outside original admitted phase lease')
    return removal['observedAtMono']
