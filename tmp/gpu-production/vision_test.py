import json,httpx,base64,zlib,struct,time,os
from pathlib import Path
if os.getenv('MOARA_VISION_TEST_KEY_FILE'):
 key=Path(os.environ['MOARA_VISION_TEST_KEY_FILE']).read_text().strip()
else:
 from moara.gateway.settings import Settings
 key=Settings.load().llm_key
def chunk(t,d):return struct.pack('>I',len(d))+t+d+struct.pack('>I',zlib.crc32(t+d)&0xffffffff)
png=bytes.fromhex('89504e470d0a1a0a')+chunk(b'IHDR',struct.pack('>IIBBBBB',64,64,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((bytes([0])+bytes([255,0,0])*64)*64))+chunk(b'IEND',b'')
started=time.monotonic()
r=httpx.post('http://gateway:8000/v1/vision/analyze',headers={'Authorization':'Bearer '+key},json={'prompt':'Qual é a cor predominante desta imagem? Responda em uma frase curta.','images':[base64.b64encode(png).decode()]},timeout=180)
report={'status':r.status_code,'seconds':time.monotonic()-started,'result':r.json(),'synthetic_only':True}
print(json.dumps(report,ensure_ascii=False))
assert r.status_code==200 and 'vermelh' in r.json()['analysis'].lower()
