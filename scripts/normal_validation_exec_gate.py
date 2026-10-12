"""Source exec-gate candidate. No allocation on import; no released controller.

The peer payload is checked before exec. The future owner controller must prove
kernel scope/namespace and hold the original pidfd before sending this payload.
"""
import hashlib
import os
from pathlib import Path
import socket
import stat
import struct
import sys

# The isolated controller preloads this exact authenticated module from memory.
if 'normal_validation_custody' not in sys.modules:
    raise RuntimeError('Authenticated core module must already be loaded')
from normal_validation_custody import hex_string, keys, no_links, parse, require


def payload(raw):
    value = parse(raw, 65536)
    keys(value, ('argv','executableSha256','environment'))
    require(type(value['argv']) is list and 1 <= len(value['argv']) <= 32 and
            all(type(x) is str and 0 < len(x) <= 8192 and '\x00' not in x for x in value['argv']),
            'Bounded actual exec vector required')
    require(Path(value['argv'][0]).is_absolute(), 'Absolute SDK executable required')
    hex_string(value['executableSha256'], 64)
    environment=value['environment']
    require(type(environment) is dict and len(environment)<=512 and
            all(type(k) is str and type(v) is str and k and '\x00' not in k+v and '=' not in k
                for k,v in environment.items()), 'Bounded native environment required')
    require(sum(len(k.encode())+len(v.encode())+2 for k,v in environment.items())<=49152,
            'Native environment byte quota')
    return value


def main():
    require(len(sys.argv) == 3 and sys.argv[2].isdigit(), 'Exact gate owner arguments required')
    owner = int(sys.argv[2]); require(owner > 0, 'Positive gate owner required')
    with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as peer:
        peer.settimeout(5)
        peer.connect(sys.argv[1])
        pid, uid, _ = struct.unpack('3i', peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        require(pid == owner and uid == os.getuid(), 'Exact controller peer unavailable')
        peer.send(b'READY')
        value = payload(peer.recv(65537))
        # Executable quota is independent of source helper quota; do not rewrite.
        executable = Path(value['argv'][0])
        executable = no_links(executable)
        require(os.execve in os.supports_fd, 'Descriptor-bound native exec unavailable')
        descriptor = os.open(executable, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        try:
            first = os.fstat(descriptor)
            require(stat.S_ISREG(first.st_mode) and 0 < first.st_size <= 128 * 1024 * 1024,
                    'Bounded regular SDK executable required')
            digest = hashlib.sha256()
            cumulative=0
            with os.fdopen(descriptor, 'rb', closefd=False) as stream:
                for chunk in iter(lambda: stream.read(65536), b''):
                    cumulative+=len(chunk)
                    require(cumulative<=128*1024*1024,'Cumulative SDK executable quota')
                    digest.update(chunk)
            last = os.fstat(descriptor)
            require((first.st_dev, first.st_ino, first.st_size, first.st_mtime_ns, first.st_ctime_ns) ==
                    (last.st_dev, last.st_ino, last.st_size, last.st_mtime_ns, last.st_ctime_ns) and
                    digest.hexdigest() == value['executableSha256'], 'Actual SDK executable changed')
            peer.close()
            os.execve(descriptor, value['argv'], value['environment'])
        finally:
            os.close(descriptor)


if __name__ == '__main__':
    main()
