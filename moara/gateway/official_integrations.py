"""Prepared read-only contracts; no unofficial PJe/SEI access is attempted."""
from typing import Literal,Protocol
import re,unicodedata
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from .auth import require

router=APIRouter(prefix='/api/v1/official-integrations',tags=['Official integrations'])
REGISTRY={
 'sei':{'id':'sei','name':'SEI TRF1','portal':'https://sei.trf1.jus.br/',
        'operations':['search_process','get_process','list_documents','get_document','get_history','build_timeline']},
 'pje':{'id':'pje','name':'PJe TRF1 — primeiro grau','portal':'https://pje1g.trf1.jus.br/',
        'operations':['search_process','get_process','list_documents','get_document','get_movements','build_timeline']},
}


class ReadRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    operation:Literal['search_process','get_process','list_documents','get_document','get_history','get_movements','build_timeline']
    process_id:str|None=Field(default=None,min_length=1,max_length=200)
    document_id:str|None=Field(default=None,min_length=1,max_length=200)
    query:str|None=Field(default=None,max_length=2000)
    cursor:str|None=Field(default=None,max_length=500)
    limit:int=Field(default=20,ge=1,le=50)


class ReadOnlyProvider(Protocol):
    """An homologated adapter must enforce origin authorization per resource.

    Implementations must not interpret a portal URL as an API endpoint, use
    browser automation, bypass origin ACLs or expose a write operation.
    """
    async def execute(self,actor,request:ReadRequest)->dict:...


def requested_system(text):
    value=''.join(c for c in unicodedata.normalize('NFKD',text.casefold()) if not unicodedata.combining(c))
    if re.search(r'\b(?:desenvolva|implemente|codigo|programacao|fastapi|api)\b',value):return None
    if not re.search(r'\b(?:consulte|consultar|acesse|acessar|busque|buscar|pesquise|pesquisar|localize|recupere|obtenha|liste|movimentacoes)\b',value):return None
    return 'sei' if re.search(r'\bsei\b',value) else 'pje' if re.search(r'\bpje\b',value) else None


@router.get('')
async def catalog(actor=Depends(require('connectors.read'))):
    return [{**value,'state':'prepared_not_connected','enabled':False,'read_only':True,
             'reason':'official_mechanism_pending_tribunal','origin_authorization_required':True,
             'external_actions_enabled':False} for value in REGISTRY.values()]


@router.post('/{system}/read')
async def read(system:Literal['sei','pje'],body:ReadRequest,actor=Depends(require('documents.use'))):
    actor.require('chat.use')
    if body.operation not in REGISTRY[system]['operations']:raise HTTPException(422,'unsupported_official_read_operation')
    raise HTTPException(409,{'code':'official_integration_pending_homologation','system':system,
        'portal':REGISTRY[system]['portal'],'message':'O tribunal ainda definirá o mecanismo oficial de integração. Nenhuma consulta foi executada. Use documentos legitimamente fornecidos e autorizados.',
        'read_only':True,'external_request_sent':False})
