"""Reuse Studio's verified actor and CSRF policy; never forward client identity headers."""
from pathlib import Path
import httpx
from fastapi import APIRouter,Depends,HTTPException,Request
from fastapi.responses import FileResponse,Response,JSONResponse
import core

router=APIRouter()

@router.get('/connectors/')
async def index():return FileResponse(Path(__file__).parent/'static/connectors/index.html')

@router.get('/api/connectors/users')
async def users(request:Request,user=Depends(core.actor)):
    if not user.admin:raise HTTPException(403,'Somente administradores')
    header=request.headers.get('authorization','')
    token=header[7:] if header.startswith('Bearer ') else request.cookies.get('studio_token','')
    if token.count('.')!=2:return {'users':[]}
    response=await core.HTTP.get('http://webui:8080/api/v1/users/',headers={'Authorization':'Bearer '+token})
    if response.status_code!=200:return {'users':[]}
    data=response.json();rows=data if isinstance(data,list) else data.get('users',[])
    return {'users':[{k:r[k] for k in ['id','name','email','role'] if k in r} for r in rows]}

@router.api_route('/api/connectors/{path:path}',methods=['GET','POST','PUT'])
async def proxy(path:str,request:Request,user=Depends(core.actor)):
    if not user.admin:core.require(user,'chat')
    if not path or any(v in path for v in ['..','\\','//',':']):raise HTTPException(404)
    if path!='mcp' and not path.startswith('v1/'):raise HTTPException(404)
    key=Path('/run/secrets/connector_hub_key').read_text().strip()
    headers={'Authorization':'Bearer '+key,'X-Actor-Id':user.owner,'X-Actor-Admin':str(user.admin).lower(),
        'Content-Type':request.headers.get('content-type','application/json')}
    if request.headers.get('origin'):headers['Origin']=request.headers['origin']
    try:
        response=await core.HTTP.request(request.method,'http://connector-hub:8070/'+path,
            params=request.query_params,content=await request.body(),headers=headers,timeout=120)
    except httpx.HTTPError:raise HTTPException(503,'Central de conectores indisponível; o chat continua acessível') from None
    if path=='v1/openapi.json' and response.status_code==200:
        data=response.json();data['servers']=[{'url':'/studio/api/connectors'}]
        data.setdefault('components',{}).setdefault('securitySchemes',{}).update({
            'BearerAuth':{'type':'http','scheme':'bearer','description':'Sessão Moara AI ou chave individual com escopo chat e autorização na fonte.'},
            'StudioCookie':{'type':'apiKey','in':'cookie','name':'studio_token','description':'Operações POST/PUT exigem X-Studio-CSRF: 1.'}})
        data['security']=[{'BearerAuth':[]},{'StudioCookie':[]}]
        return JSONResponse(data)
    return Response(response.content,status_code=response.status_code,media_type=response.headers.get('content-type','application/json'))
