import asyncio,hmac,json,os,time
from pathlib import Path
from fastapi import FastAPI,Request
from fastapi.responses import JSONResponse,Response
from pydantic import ValidationError
from .policy import PublicSearch
from .google import discover

def create_app(token=None):
 protected=token or Path(os.getenv('MOARA_BROWSER_KEY_FILE','/run/secrets/moara_google_browser_key')).read_text().strip()
 if len(protected)<32:raise RuntimeError('browser_service_secret_required')
 app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None);lock=asyncio.Lock();next_request=0;last_status='not_tested'
 @app.middleware('http')
 async def security(request,next_handler):
  if request.url.path=='/health':return await next_handler(request)
  if request.headers.get('origin') is not None or not hmac.compare_digest(request.headers.get('authorization',''),'Bearer '+protected):return Response(status_code=403)
  data=bytearray()
  async for chunk in request.stream():
   data.extend(chunk)
   if len(data)>2048:return Response(status_code=413)
  request._body=bytes(data);return await next_handler(request)
 @app.get('/health')
 async def health():return {'status':'ready','provider':'google_ai_mode_browser','last_provider_status':last_status,'provider_availability':'not_guaranteed','certifies_legal_content':False}
 @app.post('/references')
 async def references(request:Request):
  nonlocal next_request,last_status
  try:spec=PublicSearch.model_validate(await request.json())
  except (ValidationError,ValueError):return JSONResponse({'detail':'public_subject_required'},status_code=422)
  if lock.locked() or time.monotonic()<next_request:return JSONResponse({'provider':'google_ai_mode_browser','status':'rate_limited','hints':[],'normative_evidence':False,'generated_answer_used':False})
  async with lock:
   next_request=time.monotonic()+15
   try:
    result=await asyncio.wait_for(discover(spec.public_query()),35);last_status=result['status'];return result
   except TimeoutError:
    last_status='search_timeout';return {'provider':'google_ai_mode_browser','status':'search_timeout','hints':[],'normative_evidence':False,'generated_answer_used':False,'gaps':['Tempo limite do navegador; nenhum resultado foi confirmado.']}
 return app
