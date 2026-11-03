"""Authenticated, metadata-only view of the private inference service."""
import httpx
from fastapi import APIRouter,Depends,Request
from .auth import require
router=APIRouter(prefix='/api/v1/observability',tags=['Observability'])

@router.get('/inference')
async def status(request:Request,actor=Depends(require('status.read'))):
    settings=request.app.state.settings
    try:
        response=await request.app.state.http.get(settings.legacy_gateway+'/v1/inference/status',
            headers={'Authorization':'Bearer '+settings.llm_key},timeout=8)
        response.raise_for_status();return {'available':True,**response.json()}
    except (httpx.HTTPError,ValueError):return {'available':False,'reason':'inference_status_unavailable'}
