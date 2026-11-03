import pathlib,subprocess,json,difflib
root=pathlib.Path(__file__).resolve().parents[2]
code="""import pathlib,json
from html.parser import HTMLParser
r=pathlib.Path('/app/web')
class Links(HTMLParser):
 def __init__(self):super().__init__();self.paths=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='link' and a.get('rel')=='stylesheet':self.paths.append(a['href'])
p=Links();p.feed((r/'index.html').read_text());print(json.dumps({s:(r/s).read_text() for s in p.paths}))
"""
a=json.loads(subprocess.check_output(['docker','run','--rm','--network','none','--read-only','--entrypoint','python','moara-core:pre-legal-draft-app-20261102-r2','-c',code],text=True))
b=json.loads(subprocess.check_output(['docker','exec','ai-server-moara-gateway-1','python','-c',code],text=True))
x=''.join(a.values()).split('}');y=''.join(b.values()).split('}')
changes=[]
for kind,i,j,u,v in difflib.SequenceMatcher(None,x,y,autojunk=False).get_opcodes():
 if kind!='equal':changes.append({'operation':kind,'before':'}'.join(x[i:j]),'after':'}'.join(y[u:v])})
result={'before':list(a),'after':list(b),'changes':changes,'active_css_identical':x==y}
(root/'docs/runtime/legal-draft-css-check.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
