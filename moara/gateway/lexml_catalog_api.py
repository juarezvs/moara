from fastapi import APIRouter,Depends,Query,HTTPException
from fastapi.responses import JSONResponse
from .auth import require
from moara.legal_mcp.lexml_catalog import MetadataSearch,search,export

router=APIRouter(prefix='/api/v1/legal/metadata',tags=['Official metadata catalogue'])

@router.get('')
async def catalogue(query:str=Query(default='',max_length=160),kind:str=Query(default='',pattern=r'^(LEI|LCP|DEC|DEL|EMC)?$'),number:int|None=Query(default=None,ge=1,le=999999),year:int|None=Query(default=None,ge=1800,le=2100),page:int=Query(default=1,ge=1,le=10000),limit:int=Query(default=20,ge=1,le=50),actor=Depends(require('chat.use'))):
 return search(MetadataSearch(query=query,kind=kind,number=number,year=year,page=page,limit=limit))

@router.get('/export')
async def download(actor=Depends(require('chat.use'))):
 try:result=export()
 except FileNotFoundError:raise HTTPException(503,'metadata_catalogue_unavailable') from None
 return JSONResponse(result,headers={'Content-Disposition':'attachment; filename="moara-metadados-lexml.json"','Cache-Control':'private, no-store'})
