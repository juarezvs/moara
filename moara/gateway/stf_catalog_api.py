from fastapi import APIRouter,Depends,Query,HTTPException
from fastapi.responses import JSONResponse
from typing import Literal
from .auth import require
from moara.legal_mcp.stf_catalog import CatalogSearch,search,export

router=APIRouter(prefix='/api/v1/legal/stf-theses',tags=['Public STF thesis catalogue'])

@router.get('')
async def catalogue(query:str=Query(default='',max_length=160),bank:Literal['all','com','sem']='all',theme:int|None=Query(default=None,ge=1,le=99999),page:int=Query(default=1,ge=1,le=2000),limit:int=Query(default=20,ge=1,le=50),actor=Depends(require('chat.use'))):
 return search(CatalogSearch(query=query,bank=bank,theme=theme,page=page,limit=limit))

@router.get('/export')
async def download(actor=Depends(require('chat.use'))):
 try:result=export()
 except FileNotFoundError:raise HTTPException(503,'stf_catalog_not_collected') from None
 return JSONResponse(result,headers={'Content-Disposition':'attachment; filename="moara-stf-teses.json"','Cache-Control':'private, no-store'})
