"""Personal, inference-only credentials for local IDE development."""
import io,secrets,uuid,zipfile
from datetime import datetime,timezone,timedelta
from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException,Request
from fastapi.responses import Response
from pydantic import BaseModel,ConfigDict,Field,field_validator
from .auth import require,digest
from .database import as_json
from .catalog_api import visible_profiles,candidates

router=APIRouter(prefix='/api/v1/developer',tags=['VS Code integration'])
BASE_URL='https://moara.am.trf1.gov.br/moara/v1'
MODEL='moara-code'
SCOPES=('chat.use','profiles.read','identity.read','development.use')
MAX_ACTIVE_KEYS=10
WORKSPACE_RULE='''Trabalhe na pasta do projeto aberta no VS Code, identificada pelas ferramentas do editor. Nao fixe caminhos de outro projeto. Em workspaces com varias pastas, use a pasta do arquivo ativo ou esclareca qual projeto alterar quando houver ambiguidade. Use as ferramentas para ler, criar e editar arquivos e organizar pastas; execute testes pelo terminal do editor quando disponivel e autorizado. Leia antes de alterar, preserve trabalho existente e nao afirme ter salvo ou testado sem resultado real da ferramenta. Atenda projetos de qualquer finalidade, sem exigir relacao institucional.'''

class PersonalKey(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name:str=Field(min_length=2,max_length=120)
    validity_days:int=Field(default=90,ge=1,le=90)
    rpm:int=Field(default=20,ge=1,le=60)
    @field_validator('name')
    @classmethod
    def nonempty_name(cls,value):
        value=value.strip()
        if len(value)<2:raise ValueError('name_required')
        return value

def interactive(actor):
    if actor.key_id or not actor.session_id or actor.auth_source=='integration':raise HTTPException(403,'interactive_session_required')
    for scope in SCOPES:actor.require(scope)

async def principal(db,actor):
    profile=next((p for p in await visible_profiles(db,actor) if p['id']=='general' and p['manual_allowed']),None)
    models=await candidates(db,profile) if profile else []
    return profile,[m for m in models if m['capabilities'].get('completion')]

def runtime_limits(models):
    context=int(models[0].get('context_length') or 4096) if models else 4096
    return context,min(4096,max(512,context//2))

@router.get('/configuration')
async def configuration(request:Request,actor=Depends(require('development.use'))):
    interactive(actor);profile,models=await principal(request.app.state.db,actor)
    context,maximum=runtime_limits(models)
    return {'base_url':BASE_URL,'model':MODEL,'available':bool(models),
        'tool_calls':bool(models and models[0]['capabilities'].get('tools')),
        'context_length':context,'max_output_tokens':maximum,'billing':'local_inference_no_external_token_billing',
        'scopes':list(SCOPES),'max_active_keys':MAX_ACTIVE_KEYS,
        'compatibility':['models','chat.completions','streaming','tool_calls'],
        'bundle_url':'/moara/api/v1/developer/continue.zip'}

@router.get('/keys')
async def keys(request:Request,actor=Depends(require('development.use'))):
    interactive(actor)
    return await request.app.state.db.execute('''SELECT id,name,scopes,allowed_profiles,rpm,created_at,expires_at,revoked_at,last_used_at
        FROM moara.api_keys WHERE account_id=CAST(:owner AS uuid) ORDER BY created_at DESC LIMIT 100''',{'owner':str(actor.user_id)})

@router.post('/keys',status_code=201)
async def create_key(body:PersonalKey,request:Request,actor=Depends(require('development.use'))):
    interactive(actor);db=request.app.state.db
    profile,models=await principal(db,actor)
    if not models:raise HTTPException(409,'developer_model_not_available')
    token='moara_'+secrets.token_urlsafe(40);identifier=uuid.uuid4();expires=datetime.now(timezone.utc)+timedelta(days=body.validity_days)
    async with db.engine.begin() as conn:
        owner=await db.execute('SELECT id,active FROM moara.accounts WHERE id=CAST(:owner AS uuid) FOR UPDATE',{'owner':str(actor.user_id)},one=True,conn=conn)
        if not owner or not owner['active']:raise HTTPException(403,'account_disabled')
        count=await db.execute('''SELECT count(*) AS count FROM moara.api_keys WHERE account_id=CAST(:owner AS uuid)
            AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at>now())''',{'owner':str(actor.user_id)},one=True,conn=conn)
        if count['count']>=MAX_ACTIVE_KEYS:raise HTTPException(409,'personal_api_key_limit')
        await db.execute('''INSERT INTO moara.api_keys(id,account_id,name,token_hash,scopes,allowed_profiles,allowed_sources,rpm,expires_at,created_by)
            VALUES(CAST(:id AS uuid),CAST(:owner AS uuid),:name,:hash,CAST(:scopes AS jsonb),CAST(:profiles AS jsonb),'[]'::jsonb,:rpm,:expires,CAST(:owner AS uuid))''',
            {'id':str(identifier),'owner':str(actor.user_id),'name':body.name.strip(),'hash':digest(token),
                'scopes':as_json(list(SCOPES)),'profiles':as_json(['general']),'rpm':body.rpm,'expires':expires},conn=conn)
        await db.audit(actor,'api_key.personal.create',identifier,request_id=request.state.request_id,conn=conn)
    return {'id':str(identifier),'token':token,'expires_at':expires,'display_once':True,'base_url':BASE_URL,'model':MODEL}

@router.post('/keys/{identifier}/revoke')
async def revoke(identifier:uuid.UUID,request:Request,actor=Depends(require('development.use'))):
    interactive(actor);db=request.app.state.db
    async with db.engine.begin() as conn:
        row=await db.execute('''UPDATE moara.api_keys SET revoked_at=COALESCE(revoked_at,now())
            WHERE id=CAST(:id AS uuid) AND account_id=CAST(:owner AS uuid) RETURNING id''',
            {'id':str(identifier),'owner':str(actor.user_id)},one=True,conn=conn)
        if not row:raise HTTPException(404,'api_key_not_found')
        await db.audit(actor,'api_key.personal.revoke',identifier,request_id=request.state.request_id,conn=conn)
    return {'revoked':True}

def continue_config(tool_calls=True,context_length=4096,max_output_tokens=2048):
    config = '''name: Moara Local
version: 1.0.0
schema: v1
models:
  - name: Moara Desenvolvedora
    provider: openai
    apiBase: '''+BASE_URL+'''
    apiKey: ${{ secrets.MOARA_API_KEY }}
    model: moara-code
    useResponsesApi: false
    roles: [chat, edit, apply]
'''+('    capabilities: [tool_use]\n' if tool_calls else '')+'''    defaultCompletionOptions:
      contextLength: 4096
      maxTokens: 1024
      temperature: 0.2
    requestOptions:
      timeout: 180000
      verifySsl: true
      caBundlePath: ${{ secrets.MOARA_CA_BUNDLE }}
'''

    return config.replace('contextLength: 4096','contextLength: '+str(context_length)).replace('maxTokens: 1024','maxTokens: '+str(max_output_tokens))+'\nrules:\n  - '+WORKSPACE_RULE+'\n'

@router.get('/continue.zip')
async def bundle(request:Request,actor=Depends(require('development.use'))):
    interactive(actor);_,models=await principal(request.app.state.db,actor)
    context,maximum=runtime_limits(models)
    cert=Path('/app/web/integrations/moara-domain-root-ca.crt')
    if not cert.is_file():raise HTTPException(503,'developer_certificate_not_available')
    raw=cert.read_bytes()
    if b'PRIVATE KEY' in raw or b'BEGIN CERTIFICATE' not in raw:raise HTTPException(503,'developer_certificate_not_available')
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('config.yaml',continue_config(bool(models and models[0]['capabilities'].get('tools')),context,maximum))
        z.writestr('.env.example','MOARA_API_KEY=COLE_A_CHAVE_GERADA_NA_MOARA\nMOARA_CA_BUNDLE=C:/Users/SEU_USUARIO/.continue/moara-domain-root-ca.crt\n')
        z.writestr('moara-domain-root-ca.crt',raw)
        z.writestr('LEIA-ME.txt','''MOARA NO VS CODE / CONTINUE
1. Use a extensão Continue (Continue.continue) no VS Code.
2. Abra a configuração local do Continue. Mescle a entrada de models de config.yaml em sua configuração existente; preserve outros modelos que quiser manter.
3. Copie o certificado moara-domain-root-ca.crt para %USERPROFILE%\\.continue no Windows, ou ~/.continue em Linux/macOS.
4. Copie as variáveis de .env.example para o arquivo .env da mesma pasta. Cole sua chave pessoal em MOARA_API_KEY e ajuste MOARA_CA_BUNDLE para o caminho absoluto do certificado. Não inclua aspas no .env.
5. Recarregue o VS Code e selecione Moara Desenvolvedora no Continue. Use Chat, edição ou Agent com as permissões de ferramentas do editor.
6. Abra a pasta do seu projeto no VS Code (Arquivo > Abrir Pasta) e selecione o modo Agent no Continue. A pasta aberta e as ferramentas do editor determinam o projeto; nenhum caminho fixo é necessário. O modo Chat apenas conversa; o modo Agent pode ler, criar e editar arquivos, organizar pastas e executar testes com as permissões locais. Em múltiplas pastas, indique a pasta desejada se não houver arquivo ativo.
7. A seção rules do config.yaml orienta o trabalho na pasta aberta. Mescle-a também na configuração existente. As permissões efetivas de arquivos e terminal continuam sob controle do VS Code/Continue, não da chave API.
A chave não é incluída neste pacote e nunca deve ser colocada em um repositório. Sua chave pode ser revogada na página API para VS Code da Moara.
As solicitações apontam para a Moara, não para a OpenAI. A inferência é local, sem cobrança de tokens de provedor externo. Contexto, concorrência e disponibilidade dependem do servidor local.
O protocolo configurado é Chat Completions. A configuração preserva TLS e inclui a CA pública institucional.
''')
    return Response(output.getvalue(),media_type='application/zip',headers={'Content-Disposition':'attachment; filename="moara-vscode-continue.zip"','Cache-Control':'no-store'})
