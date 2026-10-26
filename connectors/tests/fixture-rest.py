import hmac
from pathlib import Path
from fastapi import FastAPI,Request,HTTPException
app=FastAPI(docs_url=None,redoc_url=None)
ROWS=[{'id':1,'nome':'Ana Sintética','saldo_minutos':120},{'id':2,'nome':'Beto Sintético','saldo_minutos':60},{'id':3,'nome':'Cris Sintética','saldo_minutos':0}]
@app.api_route('/employees',methods=['GET','HEAD'])
async def employees(request:Request):
    if not hmac.compare_digest(request.headers.get('authorization',''),'Bearer '+Path('/run/secrets/token').read_text().strip()):raise HTTPException(401)
    return ROWS
@app.get('/health')
async def health():return {'ok':True,'writes':0,'synthetic':True}
