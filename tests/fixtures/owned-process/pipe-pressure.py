"""Direct-child fixture: no subprocess, network, persistent data or SDK."""
import os
import sys
import time

mode = sys.argv[1]
if mode == 'pressure':
    # Larger than ordinary OS pipe capacity; stdout appears only after stderr.
    os.write(2, b'e' * (2 * 1024 * 1024))
    os.write(1, b'pressure-complete\n')
elif mode == 'stdout-pressure':
    os.write(1, b'o' * (2 * 1024 * 1024))
    os.write(2, b'stdout-complete\n')
elif mode == 'stdin-pressure':
    os.write(2, b'e' * (2 * 1024 * 1024))
    count = len(sys.stdin.buffer.read())
    os.write(1, f'stdin-count:{count}\nstdin-complete\n'.encode('ascii'))
elif mode == 'sleep':
    time.sleep(60)
elif mode == 'exit':
    os.write(2, b'fixture-rejected\n')
    sys.exit(17)
else:
    raise ValueError('Exact fixture mode required')
