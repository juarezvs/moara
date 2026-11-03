"""Keep the forwarding service running while a remote host reboots."""
import signal
import subprocess
import sys
import threading

stop = threading.Event()
child = None


def terminate(signum, frame):
    stop.set()
    if child is not None:
        try:
            child.terminate()
        except ProcessLookupError:
            pass


signal.signal(signal.SIGTERM, terminate)
signal.signal(signal.SIGINT, terminate)
while not stop.is_set():
    child = subprocess.Popen(['/usr/bin/ssh', *sys.argv[1:]])
    status = child.wait()
    child = None
    if not stop.is_set():
        print('GPU tunnel disconnected; reconnecting, status=' + str(status), flush=True)
        stop.wait(3)
