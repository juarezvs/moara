import pathlib,sys,base64,json
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from gpu_remote import source
r=pathlib.Path(__file__).resolve().parents[2]
files={name:base64.b64encode((r/name).read_bytes()).decode() for name in sys.argv[1:]}
script='''python3 - <<'PY'
import pathlib,base64,json
r=pathlib.Path('/home/nutec/ai-server')
for name,value in json.loads(PAYLOAD).items():
 p=r/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(base64.b64decode(value));p.chmod(0o644)
PY
'''.replace('PAYLOAD',repr(json.dumps(files)))
print(source(script))
