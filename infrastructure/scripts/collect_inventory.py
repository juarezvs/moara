"""Collect read-only evidence over SSH, preserving host-key verification."""
from pathlib import Path
import argparse
import datetime
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='nutec@172.19.5.250')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    day = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    target = args.output or ROOT / 'docs' / 'evidence' / f'server-inventory-{day}.txt'
    script = Path(__file__).with_name('inventory.sh').read_bytes().replace(b'\r\n', b'\n')
    try:
        result = subprocess.run(
            ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
             '-o', 'ConnectTimeout=10', '--', args.host, 'bash -s'],
            input=script, capture_output=True, timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f'Inventory failed: {error}', file=sys.stderr)
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(result.stdout + result.stderr)
    print(f'SSH exit={result.returncode}; evidence={target}')
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
