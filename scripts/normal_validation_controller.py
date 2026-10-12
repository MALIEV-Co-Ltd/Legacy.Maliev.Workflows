"""Fail-closed existing systemd user service and cgroup-v2 custody.

No installs, privilege grants or kernel allocations at import. Pure tests do not
qualify this controller. Its actual properties/namespace/cgroup proof is required.
"""
import hashlib
import base64
import json
import os
import re
from pathlib import Path
import select
import shutil
import signal
import socket
import struct
import subprocess
import sys
import time
import threading
import uuid
from normal_validation_lifecycle import scope as lifecycle_scope, namespace as lifecycle_namespace

GATE = Path(__file__).with_name("normal_validation_exec_gate.py").resolve()
CGROOT = Path("/sys/fs/cgroup")
MEMORY = 4 * 1024**3
PROPERTIES = {"CPUQuota": "200%", "MemoryMax": str(MEMORY), "MemorySwapMax": "0",
              "ExitType": "cgroup", "RemainAfterExit": "yes", "Type": "exec",
              "TimeoutStopSec": "10s", "KillMode": "control-group", "SendSIGKILL": "yes",
              "OOMPolicy": "stop", "Delegate": "no", "ProtectControlGroups": "yes",
              "NoNewPrivileges": "yes", "RestrictNamespaces": "yes", "PrivateMounts": "yes"}
ENV_ALLOWED = {"N62_RUN_ID", "N62_RESOURCE_DIRECTORY", "RECOVERY_AUTH_ROOT", "RECOVERY_INTRANET_ROOT",
               "RECOVERY_NOTIFICATION_ROOT", "RecoveryAuthRoot", "RecoveryIntranetRoot", "RecoveryNotificationRoot",
               "MalievWorkspaceRoot", "UseLocalMalievDependencies", "UseSharedCompilation", "TESTCONTAINERS_RYUK_DISABLED",
               "DOTNET_PROCESSOR_COUNT", "MSBUILDDISABLENODEREUSE", "DOTNET_CLI_TELEMETRY_OPTOUT",
               "DOTNET_GCHeapHardLimit"}


def save(path, value):
    temporary = path.with_suffix(".pending")
    raw=json.dumps(value,allow_nan=False).encode()
    if len(raw)>1024*1024:raise RuntimeError('Custody record quota')
    descriptor=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
    try:
        with os.fdopen(descriptor,'wb',closefd=False) as stream:
            stream.write(raw);stream.flush();os.fsync(descriptor)
    finally:os.close(descriptor)
    temporary.replace(path)


def identity(pid):
    root = Path(f"/proc/{pid}")
    raw = (root / "stat").read_text()
    fields = raw[raw.rfind(")") + 2:].split()
    return {"pid": int(pid), "birthTicks": int(fields[19]),
            "executable": str((root / "exe").resolve(strict=True)),
            "cgroup": (root / "cgroup").read_text().strip()}


def executable_digest(path):
    from normal_validation_custody import stable_read
    return hashlib.sha256(stable_read(path,128*1024*1024)).hexdigest()


def parse_show(text):
    return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)


def seconds(text):
    parts = re.findall(r'(\d+(?:\.\d+)?)(us|ms|min|h|s)', text)
    if not parts or re.sub(r'(\d+(?:\.\d+)?)(us|ms|min|h|s)|\s', '', text):
        raise RuntimeError('Finite manager timeout readback required')
    scales = {'us': 0.000001, 'ms': 0.001, 's': 1, 'min': 60, 'h': 3600}
    return sum(float(value)*scales[unit] for value, unit in parts)


def scope_path(group):
    if not group.startswith("/") or ".." in Path(group).parts:
        raise RuntimeError("Invalid kernel cgroup path")
    path = (CGROOT / group.lstrip("/")).resolve()
    if not path.is_relative_to(CGROOT.resolve()) or path == CGROOT.resolve():
        raise RuntimeError("Controller scope is not a contained child")
    return path


def kernel_limits(path):
    quota, period = (path / "cpu.max").read_text().split()
    if quota == "max" or int(period) <= 0 or int(quota) <= 0 or int(quota) > 2 * int(period):
        raise RuntimeError("Kernel aggregate CPU cap is not enforced")
    if int((path / "memory.max").read_text()) != MEMORY or int((path / "memory.swap.max").read_text()) != 0:
        raise RuntimeError("Kernel aggregate memory/swap cap is not enforced")
    stat = path.stat()
    return {"path": str(path), "device": stat.st_dev, "inode": stat.st_ino,
            "cpuMax": [int(quota), int(period)], "memoryMax": MEMORY, "memorySwapMax": 0}


def kernel_absent(scope):
    path = Path(scope["path"])
    if not path.exists():
        return True
    stat = path.stat()
    if (stat.st_dev, stat.st_ino) != (scope["device"], scope["inode"]):
        raise RuntimeError("Scope reused; preserve current owner")
    events = dict(line.split() for line in (path / "cgroup.events").read_text().splitlines())
    if events.get("populated") != "0":
        return False
    for member in [path, *path.rglob("*")]:
        if member.is_dir() and (member / "cgroup.procs").exists():
            if not member.resolve().is_relative_to(path.resolve()) or (member / "cgroup.procs").read_text().strip():
                return False
    return True


def kernel_namespace(pid):
    root = Path(f'/proc/{pid}')
    status = dict(line.split(':', 1) for line in (root / 'status').read_text().splitlines() if ':' in line)
    mounts = [line.split() for line in (root / 'mountinfo').read_text().splitlines() if ' - cgroup2 ' in line]
    if (status.get('NoNewPrivs', '').strip() != '1' or status.get('Seccomp', '').strip() != '2'
            or not mounts or any('ro' not in line[5].split(',') for line in mounts)
            or (root / 'ns/mnt').readlink() == Path('/proc/self/ns/mnt').readlink()):
        raise RuntimeError('Actual helper namespace/cgroup protection unverified')
    return {'noNewPrivileges': True, 'seccomp': 2, 'cgroupMountsReadOnly': True,
            'mountNamespace': str((root / 'ns/mnt').readlink())}


class Controller:
    def __init__(self, budget, output, run, cwd):
        self.budget, self.output, self.run_id = budget, output, run
        self.cwd = Path(cwd).resolve(strict=True)
        if not (len(run) == 32 and all(c in "0123456789abcdef" for c in run)):
            raise ValueError("Exact unpredictable run identity required")

    def call(self, args, maximum=10):
        with __import__('tempfile').TemporaryFile() as output:
            result=subprocess.run(args,stdout=output,stderr=output,check=True,
                                  timeout=self.budget.remaining(maximum))
            output.seek(0);raw=output.read(65537)
            if len(raw)>65536:raise RuntimeError('Controller observation output quota')
            return raw.decode('utf-8',errors='strict').strip()

    def show(self, unit):
        return parse_show(self.call(["systemctl", "--user", "show", unit]))

    def preflight(self):
        if (sys.platform != "linux" or os.environ.get("GITHUB_ACTIONS") != "true"
                or not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal")
                or not shutil.which("systemd-run") or not shutil.which("systemctl")):
            raise RuntimeError("Existing hosted Linux controller unavailable")
        self.call(["systemctl", "--user", "show", "--property=Version"])
        parent = self.show("-.slice")
        path = scope_path(parent["ControlGroup"])
        if not {"cpu", "memory"} <= set((path / "cgroup.controllers").read_text().split()):
            raise RuntimeError("Existing user-manager controller delegation unavailable")
        return {"parent": str(path), "controllerDelegation": "Existing; no mutation"}

    def owned(self, unit, receipt):
        show = self.show(unit)
        if show.get("LoadState") == "not-found":
            if not self.terminal_authority(receipt, receipt.get('cleanupTerminal', receipt.get('terminalBeforeStop', {})).get('manager', {})):
                raise RuntimeError("Missing custody is not service absence")
            return show
        if (show.get("InvocationID") != receipt.get("invocation")
                or f"N62_RUN_ID={self.run_id}" not in show.get("Environment", "").split()):
            raise RuntimeError("Transient service ownership changed; preserve it")
        if show.get('ControlGroup') != receipt.get('group'):
            # An emptied loaded unit may clear ControlGroup. Never accept a live/reused group.
            retained = receipt.get('cleanupTerminal', receipt.get('terminalBeforeStop', {})).get('manager', {})
            if (show.get('ControlGroup') != '' or not self.terminal_authority(receipt, show)
                    or not kernel_absent(receipt['scope'])):
                raise RuntimeError('Original terminal group authority missing; preserve it')
            if retained and not self.terminal_authority(receipt, retained):
                raise RuntimeError('Retained terminal invocation changed; preserve it')
        return show

    def preexec_authority(self, receipt):
        expected = {'InvocationID':receipt.get('invocation'), 'ExitType':'cgroup', 'RemainAfterExit':'yes',
                    'KillMode':'control-group', 'MemoryMax':str(MEMORY), 'MemorySwapMax':'0', 'CPUQuotaPerSecUSec':'2s'}
        if (not receipt.get('invocation') or not receipt.get('scope') or not receipt.get('namespace')
                or receipt.get('managerPreExec') != expected):
            return False
        try:
            lifecycle_scope(receipt['scope'])
            lifecycle_namespace(receipt['namespace'])
            if Path(receipt['scope']['path']) != scope_path(receipt['group']):
                return False
        except (ValueError, KeyError, TypeError, RuntimeError):
            return False
        return True

    def terminal_authority(self, receipt, manager):
        if not self.preexec_authority(receipt):
            return False
        return (manager.get('InvocationID') == receipt['invocation']
                and manager.get('ExitType') == 'cgroup' and manager.get('RemainAfterExit') == 'yes'
                and (manager.get('ActiveState'),manager.get('SubState')) in
                (('active','exited'),('inactive','dead'),('failed','failed')))

    def prove(self, unit, pid, runtime):
        show = self.show(unit)
        if (show.get("MainPID") != str(pid) or not show.get("InvocationID")
                or show.get("KillMode") != "control-group" or show.get("MemoryMax") != str(MEMORY)
                or show.get("MemorySwapMax") != "0" or show.get("CPUQuotaPerSecUSec") != "2s"
                or show.get("Delegate") != "no" or show.get("ProtectControlGroups") != "yes"
                or show.get("NoNewPrivileges") != "yes" or show.get("PrivateMounts") != "yes"
                or show.get("RestrictNamespaces") != "yes"
                or show.get('ExitType') != 'cgroup' or show.get('RemainAfterExit') != 'yes'
                or show.get("SendSIGKILL") != "yes" or show.get("OOMPolicy") != "stop"
                or not 0 < seconds(show.get('RuntimeMaxUSec', '')) <= runtime
                or not 0 < seconds(show.get('TimeoutStopUSec', '')) <= 10
                or f"N62_RUN_ID={self.run_id}" not in show.get("Environment", "").split()):
            raise RuntimeError("Actual transient service namespace/limit ownership proof failed")
        path = scope_path(show["ControlGroup"])
        current = identity(pid)
        if current["cgroup"] != "0::" + show["ControlGroup"]:
            raise RuntimeError("Actual helper cgroup does not match controller")
        return {"invocation": show["InvocationID"], "group": show["ControlGroup"],
                "scope": kernel_limits(path), "helper": current,
                "namespace": kernel_namespace(pid),
                "managerPreExec": {k:show[k] for k in ('InvocationID','ExitType','RemainAfterExit','KillMode','MemoryMax','MemorySwapMax','CPUQuotaPerSecUSec')},
                "startedMonoUsec": int(show["ActiveEnterTimestampMonotonic"])}

    def cleanup(self, receipt, wrapper=None, wrapper_fd=None, native_fd=None):
        # All calls/waits use this SAME job deadline, including the cleanup reserve.
        old = self.budget.cleanup
        self.budget.cleanup = True
        try:
            if not receipt.get("invocation") or not receipt.get("scope"):
                raise RuntimeError("Incomplete allocation custody; dependents preserved under finite service expiry")
            show = self.owned(receipt["unit"], receipt)
            if show.get("LoadState") != "not-found":
                # Cleanup is independent of PASS: stop the exact authenticated live/failed unit.
                # Keep original caps/namespace authority; incomplete custody never permits a stop.
                if not self.preexec_authority(receipt):
                    raise RuntimeError('Pre-exec ownership incomplete; preserve dependents')
                self.call(["systemctl", "--user", "stop", receipt["unit"]])
            while True:
                terminal = self.owned(receipt['unit'], receipt)
                if terminal.get('LoadState') != 'not-found':
                    if self.terminal_authority(receipt, terminal):
                        receipt['cleanupTerminal'] = {'observedAtMono':time.monotonic(),
                            'manager':{k:terminal.get(k) for k in ('InvocationID','ExitType','RemainAfterExit','ActiveState','SubState','Result','ExecMainStatus')}}
                    else:
                        time.sleep(self.budget.remaining(0.05))
                        continue
                authority = receipt.get('cleanupTerminal', receipt.get('terminalBeforeStop', {})).get('manager', {})
                if not self.terminal_authority(receipt, authority):
                    raise RuntimeError('Authoritative original cgroup terminal missing; preserve dependents')
                if kernel_absent(receipt['scope']):
                    break
                time.sleep(self.budget.remaining(0.05))
            if terminal.get("LoadState") != "not-found" and terminal.get("ActiveState") not in ("inactive", "failed"):
                raise RuntimeError("Transient service did not exit")
            if native_fd is not None:
                poll = select.poll()
                poll.register(native_fd, select.POLLIN)
                if not poll.poll(0):
                    raise RuntimeError("Exact native pidfd is not exited")
            elif receipt.get("native") or receipt.get('helper'):
                member = receipt.get('native', receipt.get('helper'))
                pid = member['pid']
                if Path(f"/proc/{pid}").exists() and identity(pid)["birthTicks"] == member["birthTicks"]:
                    raise RuntimeError("Original native identity still exists")
            if wrapper is None and not receipt.get("wrapperExitVerified"):
                raise RuntimeError("Wrapper absence unverified after restart")
            receipt.update({"scopeAbsent": True, "nativeExitVerified": True, "unitTerminal": True, "removalObservedAtMono":time.monotonic()})
            return receipt
        finally:
            self.budget.cleanup = old

    def cleanup_wrapper(self, wrapper, fd, receipt):
        if wrapper is None:
            return
        old = self.budget.cleanup
        self.budget.cleanup = True
        try:
            if wrapper.poll() is None and fd is not None:
                signal.pidfd_send_signal(fd, signal.SIGTERM)
            # Even an unavailable /proc identity cannot bypass owned Popen wait.
            try:wrapper.wait(timeout=self.budget.remaining(10))
            except subprocess.TimeoutExpired:
                if fd is None:raise RuntimeError('Original wrapper custody unavailable for escalation')
                signal.pidfd_send_signal(fd,signal.SIGKILL)
                wrapper.wait(timeout=self.budget.remaining(10))
            receipt["wrapperExitVerified"] = True
            receipt["wrapperExitedAtMono"] = time.monotonic()
            if fd is None:raise RuntimeError('Original wrapper pidfd missing')
            poll=select.poll();poll.register(fd,select.POLLIN)
            if not poll.poll(0):raise RuntimeError('Original wrapper pidfd exit unverified')
            receipt['wrapperPidfdExited']=True
        finally:
            self.budget.cleanup = old

    def run(self, argv, env, stage):
        self.preflight()
        started=time.monotonic()
        stage_seconds = min(900, self.budget.remaining())
        if stage_seconds < 10:
            raise TimeoutError("No finite controller startup budget")
        executable = Path(shutil.which(argv[0]) or "").resolve(strict=True)
        argv = [str(executable), *argv[1:]]
        directory = self.output / (stage + "-" + uuid.uuid4().hex)
        directory.mkdir(mode=0o700)
        unit = "n62-" + self.run_id + "-" + uuid.uuid4().hex + ".service"
        if self.show(unit).get("LoadState") != "not-found":
            raise RuntimeError("Proposed owned service already exists")
        receipt = {"stage": stage, "unit": unit, "run": self.run_id, "allocationStarted": True,
                   "startedMono":started,"expiryMono": min(started+stage_seconds,self.budget.deadline-300), "helperSha256": self.gate_digest(),
                   "executableSha256": executable_digest(executable), "argv": argv,
                   "sdkReleased": False, "scopeAbsent": False, "nativeExitVerified": False}
        custody = self.output / (stage + "-custody.json")
        save(custody, receipt)  # Intent BEFORE Popen; all later faults fail dependent admission.
        wrapper = None
        wrapper_fd = native_fd = None
        peer = None
        reader=None;reader_error=[];reader_stop=threading.Event()
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as gate, (self.output / (stage + ".log")).open("xb") as log:
                gate.bind(str(directory / "gate"))
                gate.listen(1)
                gate.settimeout(self.budget.remaining(5))
                args = ["systemd-run", "--user", "--wait", "--pipe", "--quiet", "--unit=" + unit,
                        "--property=WorkingDirectory=" + str(self.cwd),
                        "--property=RuntimeMaxSec=" + str(int(stage_seconds))]
                args += ["--property=" + k + "=" + v for k, v in PROPERTIES.items()]
                args += ["--setenv=" + k + "=" + env[k] for k in ("N62_RUN_ID",) if k in env]
                from normal_validation_custody import AUTHENTICATED_BYTES
                core_bytes=AUTHENTICATED_BYTES['scripts/normal_validation_custody.py']
                gate_bytes=AUTHENTICATED_BYTES['scripts/normal_validation_exec_gate.py']
                gate_code='import base64,types,sys\n'
                gate_code+='m=types.ModuleType("normal_validation_custody");m.__file__='+repr(str(GATE.with_name('normal_validation_custody.py')))+'\n'
                gate_code+='sys.modules["normal_validation_custody"]=m\n'
                gate_code+='exec(compile(base64.b64decode('+repr(base64.b64encode(core_bytes).decode())+'),m.__file__,"exec"),m.__dict__)\n'
                gate_code+='__file__='+repr(str(GATE))+'\n'
                gate_code+='exec(compile(base64.b64decode('+repr(base64.b64encode(gate_bytes).decode())+'),__file__,"exec"),globals())\n'
                if len(gate_code.encode())>120000:raise RuntimeError('Authenticated gate command quota')
                args += [sys.executable, "-I", "-S", "-B", "-c",gate_code, str(directory / "gate"), str(os.getpid())]
                wrapper = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                def drain():
                    size=0
                    try:
                        while True:
                            if reader_stop.is_set():break
                            if not select.select([wrapper.stdout],[],[],0.1)[0]:continue
                            chunk=os.read(wrapper.stdout.fileno(),65536)
                            if not chunk:break
                            size+=len(chunk)
                            if size>4*1024*1024:
                                reader_error.append('Native stage log quota')
                            elif not reader_error:
                                log.write(chunk);log.flush()
                    except BaseException:
                        reader_error.append('Native stage output reader failed')
                reader=threading.Thread(target=drain,name='owned-native-log',daemon=True);reader.start()
                receipt["wrapperPid"] = wrapper.pid
                wrapper_fd = os.pidfd_open(wrapper.pid)
                receipt["wrapper"] = identity(wrapper.pid)
                receipt["wrapper"]["executableSha256"] = executable_digest(receipt["wrapper"]["executable"])
                save(custody, receipt)
                peer, _ = gate.accept()
                peer.settimeout(self.budget.remaining(5))
                pid, uid, _ = struct.unpack("3i", peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                if uid != os.getuid() or peer.recv(16) != b"READY":
                    raise RuntimeError("Exec gate peer ownership unavailable")
                receipt.update(self.prove(unit, pid, int(stage_seconds)))
                receipt['preExecObservedAtMono']=time.monotonic()
                receipt["helper"]["executableSha256"] = executable_digest(receipt["helper"]["executable"])
                native_fd = os.pidfd_open(pid)
                if identity(pid) != {k:v for k,v in receipt["helper"].items() if k != 'executableSha256'}:
                    raise RuntimeError("Helper identity changed during pidfd acquisition")
                save(custody, receipt)
                self.budget.remaining(5)
                payload=json.dumps({"argv": argv, "executableSha256": receipt["executableSha256"], "environment": env}).encode()
                if len(payload)>65536:raise RuntimeError('Native gate payload quota')
                peer.send(payload)
                receipt["sdkReleased"] = True
                transition_deadline = min(time.monotonic() + 5, receipt["expiryMono"])
                while True:
                    if reader_error:raise RuntimeError(reader_error[0])
                    current = identity(pid)
                    if current["birthTicks"] != receipt["helper"]["birthTicks"] or current["cgroup"] != receipt["helper"]["cgroup"]:
                        raise RuntimeError("SDK transition escaped exact helper custody")
                    if current["executable"] == str(executable):
                        receipt["native"] = dict(current, executableSha256=receipt["executableSha256"])
                        receipt["transitionObservedAtMono"] = time.monotonic()
                        kernel_limits(Path(receipt["scope"]["path"]))
                        save(custody, receipt)
                        break
                    if time.monotonic() >= transition_deadline:
                        raise RuntimeError("Actual helper to SDK executable transition unverified")
                    time.sleep(self.budget.remaining(0.01))
                poll = select.poll()
                poll.register(native_fd, select.POLLIN)
                while True:
                    if reader_error:raise RuntimeError(reader_error[0])
                    show = self.owned(unit, receipt)
                    if (show.get('ExitType') == 'cgroup' and show.get('RemainAfterExit') == 'yes'
                            and show.get('ActiveState') == 'active' and show.get('SubState') == 'exited'
                            and show.get('Result') == 'success' and show.get('ExecMainStatus') == '0'
                            and poll.poll(0)):
                        receipt['terminalBeforeStop'] = {
                            'observedAtMono':time.monotonic(), 'nativePidfdExited':True,
                            'manager':{k:show[k] for k in ('InvocationID','ExitType','RemainAfterExit','ActiveState','SubState','Result','ExecMainStatus')},
                            'scopeObservedAbsent':kernel_absent(receipt['scope'])}
                        if not receipt['terminalBeforeStop']['scopeObservedAbsent']:
                            raise RuntimeError('Exited main is not descendant absence')
                        receipt['terminalBeforeStop']['scopeObservation']={
                            'scope':receipt['scope'],
                            'kind':'kernel-populated-zero' if Path(receipt['scope']['path']).exists() else 'same-invocation-manager-cgroup-exited',
                            'populated':0,'subtreePids':[]}
                        save(custody, receipt)
                        self.call(['systemctl','--user','stop',unit])
                        break
                    if time.monotonic() >= receipt['expiryMono']:
                        raise TimeoutError('Finite stage expiry before authoritative cgroup terminal')
                    time.sleep(self.budget.remaining(0.05))
                result = wrapper.wait(timeout=self.budget.remaining(10))
                receipt["wrapperExitVerified"] = True
                receipt["wrapperExitedAtMono"] = time.monotonic()
                receipt["exitCode"] = result
                if result != 0:
                    raise RuntimeError("Native stage failed")
                reader.join(timeout=self.budget.remaining(10))
                if reader.is_alive() or reader_error:raise RuntimeError('Native stage output not settled')
        finally:
            if peer is not None:
                peer.close()  # Close before stop/wait, including failed identity/receipt paths.
            try:
                # Reacquire only exact named service custody if early launch lookup failed.
                if wrapper is not None and not receipt.get("invocation"):
                    show = self.show(unit)
                    if show.get("MainPID", "0").isdecimal() and int(show["MainPID"]) > 0:
                        receipt.update(self.prove(unit, int(show["MainPID"]), int(stage_seconds)))
                self.cleanup(receipt, wrapper, wrapper_fd, native_fd)
            finally:
                try:
                    self.cleanup_wrapper(wrapper, wrapper_fd, receipt)
                finally:
                    reader_stop.set()
                    try:
                        if reader is not None:
                            old=self.budget.cleanup;self.budget.cleanup=True
                            try:reader.join(timeout=self.budget.remaining(10))
                            finally:self.budget.cleanup=old
                            if reader.is_alive():raise RuntimeError('Owned reader closure unverified')
                    finally:
                        if wrapper is not None and wrapper.stdout is not None:wrapper.stdout.close()
                        for fd in (wrapper_fd, native_fd):
                            if fd is not None:os.close(fd)
                        save(custody, receipt)
                        socket_path = directory / "gate"
                        if socket_path.exists():socket_path.unlink()
                        directory.rmdir()
        return receipt

    @staticmethod
    def gate_digest():
        from normal_validation_custody import AUTHENTICATED_BYTES
        return hashlib.sha256(AUTHENTICATED_BYTES['scripts/normal_validation_exec_gate.py']).hexdigest()
