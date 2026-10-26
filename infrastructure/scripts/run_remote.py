"""Run a reviewed local Python operations script over verified SSH."""
import argparse,subprocess,sys
sys.stdout.reconfigure(encoding="utf-8",errors="replace")
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('script',type=Path);p.add_argument('--report',type=Path);p.add_argument('--timeout',type=int,default=1800)
args=p.parse_args()
result=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=10','nutec@172.19.5.250','python3 -'],input=args.script.read_bytes(),capture_output=True,timeout=args.timeout)
if args.report:
 args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_bytes(result.stdout+result.stderr)
print(result.stdout.decode('utf-8',errors='replace'))
print(result.stderr.decode('utf-8',errors='replace'))
raise SystemExit(result.returncode)
