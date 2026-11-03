"""Optional Libras for the public manifesto, isolated from authenticated pages."""
import secrets
from html import escape
from fastapi import APIRouter,Request
from fastapi.responses import HTMLResponse

router=APIRouter(prefix='/api/v1/accessibility',tags=['Accessibility'])


@router.get('/libras')
async def libras(request:Request):
    identity,_=await request.app.state.identity.active()
    nonce=secrets.token_urlsafe(24)
    policy=("sandbox allow-scripts; default-src 'none'; script-src 'nonce-"+nonce+"' https://vlibras.gov.br https://cdn.jsdelivr.net/gh/spbgovbr-vlibras/vlibras-portal@v7.12.2/app/; "
        "style-src 'unsafe-inline' https://vlibras.gov.br https://cdn.jsdelivr.net; font-src https://vlibras.gov.br https://cdn.jsdelivr.net; "
        "img-src data: https://vlibras.gov.br https://cdn.jsdelivr.net; connect-src https://vlibras.gov.br https://cdn.jsdelivr.net; "
        "frame-src https://vlibras.gov.br; frame-ancestors 'self'; object-src 'none'; base-uri 'none'; form-action 'none'; worker-src blob:")
    content='''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Moara — apresentação pública em Libras</title><style>body{font:17px/1.7 system-ui;color:#172f40;background:#fff;margin:1.5rem 4rem 1.5rem 1.5rem}h1{font-size:1.5rem}p{white-space:pre-line}</style>
<h1>Moara — Inteligência a serviço da Justiça.</h1><p>Este quadro contém somente o manifesto público. Use o botão VLibras para traduzir o conteúdo público desta apresentação.</p><main><p>'''+escape(identity.document.declaration)+'''</p></main>
<script nonce="'''+nonce+'''">try{void localStorage.length}catch{const data=new Map();try{Object.defineProperty(window,'localStorage',{value:{getItem:k=>data.get(String(k))||null,setItem:(k,v)=>data.set(String(k),String(v)),removeItem:k=>data.delete(String(k)),clear:()=>data.clear(),key:i=>[...data.keys()][i]||null,get length(){return data.size}}})}catch{}}</script>
<script src="https://vlibras.gov.br/app/vlibras-plugin.js"></script></html>'''
    return HTMLResponse(content,headers={'Content-Security-Policy':policy,'X-Frame-Options':'SAMEORIGIN','Cache-Control':'no-store'})
