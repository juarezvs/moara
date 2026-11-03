import pathlib,sys,base64
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from gpu_remote import source
p=pathlib.Path(r'C:\Users\am200401\Downloads\SEI_0003550_77.2026.4.01.8002.pdf')
encoded=base64.b64encode(p.read_bytes()).decode()
script="""python3 - <<'PY'
from pathlib import Path
import base64
folder=Path('/home/nutec/.cache/moara-validation-325b059af1f8');folder.mkdir(mode=0o700,exist_ok=True);folder.chmod(0o700)
p=folder/'process.pdf';p.write_bytes(base64.b64decode(PAYLOAD));p.chmod(0o600)
print('PRIVATE_PDF_VALIDATION_FIXTURE_READY')
PY
""".replace('PAYLOAD',repr(encoded))
print(source(script))
