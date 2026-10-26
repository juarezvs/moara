"""Temporary authenticated relay: synthetic QA requests to existing local inference."""
import hmac,json,os,urllib.request
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
actual=Path('/run/secrets/upstream').read_text().strip();qa=Path('/run/secrets/qa').read_text().strip()
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_POST(self):
  if not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+qa):self.send_error(401);return
  if self.path not in ('/v1/embeddings','/v1/chat/completions'):self.send_error(404);return
  size=int(self.headers.get('Content-Length','0'))
  if not 0<size<=200000:self.send_error(413);return
  body=self.rfile.read(size);payload=json.loads(body)
  if payload.get('model') not in ('embedding','fast'):self.send_error(403);return
  try:
   req=urllib.request.Request('http://'+os.environ['UPSTREAM_IP']+':8000'+self.path,data=body,headers={'Authorization':'Bearer '+actual,'Content-Type':'application/json'})
   with urllib.request.urlopen(req,timeout=300) as r:data=r.read(2000000)
   self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(data)
  except Exception:self.send_error(502)
ThreadingHTTPServer(('0.0.0.0',8000),Handler).serve_forever()
