import asyncio,json,os,unittest
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
import httpx
from pydantic import ValidationError
from fastapi import HTTPException
from moara.legal_mcp import web_search as web
from moara.gateway import web_research as gateway,orchestration
from moara.identity import load_identity,compose_prompt

class PolicyTests(unittest.TestCase):
 def test_general_questions_do_not_require_institutional_purpose(self):
  for text in ['Ensine a preparar uma receita de bolo.','Faca meu horoscopo.','Crie uma historia romantica.']:
   value=orchestration.contextual_rules(text)
   self.assertEqual(value['scope'],'allowed')
  identity=load_identity();before=identity.sha256
  text=compose_prompt(identity,[{'role':'user','content':'Explique fotossintese'}])[0]['content']
  self.assertIn('Não pergunte qual é a finalidade institucional',text)
  self.assertEqual(before,identity.sha256)
 def test_official_acts_and_tools_still_require_authority(self):
  self.assertEqual(orchestration.contextual_rules('Assine uma sentenca')['reason'],'official_act_requires_human_authority')
 def test_public_web_planning_never_sends_private_case_data(self):
  self.assertIsNone(gateway.plan('Explique fotossintese'))
  self.assertIsInstance(gateway.plan('Pesquise na web Angular signals documentacao oficial'),web.WebSearch)
  for text in ['Pesquise meu processo 1234567-12.2026.4.01.0000','Verifique CPF 111.222.333-44','Pesquise o anexo']:
   self.assertTrue(gateway.plan(text)['private'])
 def test_public_web_search_is_not_a_private_connector_or_development_action(self):
  for text in ['Pesquise na web Angular signals documentacao oficial','Pesquise na internet indicadores economicos do Brasil']:
   result=orchestration.contextual_rules(text)
   self.assertEqual(result['assistant'],'documental');self.assertEqual(result['reason'],'public_web_research')
 def test_unsafe_urls_and_queries_are_rejected(self):
  for url in ['http://public.com','https://localhost/','https://127.0.0.1/','https://10.0.0.1/','https://user:pass@example.com','https://example.com:8000/','file:///etc/passwd']:
   with self.subTest(url=url),self.assertRaises(ValueError):web.validate_url(url)
  for query in ['CPF 111.222.333-44','email user@example.com','senha secreta']:
   with self.assertRaises(ValidationError):web.WebSearch(query=query)
 def test_citations_require_existing_source_and_exact_quote(self):
  sources={'W1.1':{'url':'https://angular.dev/guide/signals','excerpt':'Signals track how and where your state is used throughout an application.'}}
  good={'paragraphs':[{'text':'Signals acompanham o estado da aplicacao.','source_id':'W1.1','quote':'Signals track how and where your state is used'}]}
  self.assertIn('https://angular.dev',gateway.validate_synthesis(good,sources))
  self.assertEqual(sources['W1.1']['support_quotes'],[good['paragraphs'][0]['quote']])
  for field,value in [('source_id','W99.1'),('quote','A fonte nunca disse isto')]:
   bad=json.loads(json.dumps(good));bad['paragraphs'][0][field]=value
   with self.assertRaises(ValueError):gateway.validate_synthesis(bad,sources)

class NetworkTests(unittest.IsolatedAsyncioTestCase):
 async def test_invalid_synthesis_is_repaired_without_inventing_source_ids(self):
  sources={'W1.1':{'url':'https://angular.dev/guide/signals','excerpt':'Signals notify interested consumers when the value changes.'}}
  bad={'paragraphs':[{'text':'Signals notificam os consumidores.','source_id':'W1.1','quote':'Esta frase nao esta na fonte'}]}
  good={'paragraphs':[{'text':'Signals notificam os consumidores quando o valor muda.','source_id':'W1.1','quote':'Signals notify interested consumers when the value changes.'}]}
  generate=AsyncMock(side_effect=[{'choices':[{'message':{'content':json.dumps(v)}}]} for v in (bad,good)])
  answer=await gateway.synthesize(None,None,'Explique signals',sources,generate)
  self.assertEqual(generate.await_count,2);self.assertIn('[W1.1]',answer);self.assertEqual(len(sources['W1.1']['support_quotes']),1)
 async def test_empty_senado_document_list_does_not_abort_recovery(self):
  from moara.legal_mcp.catalog import search
  from moara.legal_mcp.contracts import NormSearch
  async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'ListaDocumento':{'documentos':''}}))) as client:
   value=await search(client,NormSearch(kind='LEI',number=55555,year=2020))
  self.assertEqual(value['candidates'],[]);self.assertEqual(value['status'],'catalogue_retrieved')
 async def test_chat_only_account_gets_public_conversation_without_document_permissions(self):
  from moara.gateway.rbac import Actor
  from moara.gateway import assistants
  actor=Actor(uuid.uuid4(),'qa','QA',None,('user',),frozenset({'chat.use','profiles.read'}))
  body=SimpleNamespace(messages=[{'role':'user','content':'Pesquise na web Angular signals documentacao oficial'}],assistant_id='auto',model='auto',document_ids=[])
  request=SimpleNamespace(scope={},app=SimpleNamespace(state=SimpleNamespace(db=SimpleNamespace(audit=AsyncMock()))))
  with patch.object(assistants,'resolve',AsyncMock(side_effect=HTTPException(403,'not_authorized'))) as privileged,patch('moara.gateway.catalog_api.visible_profiles',AsyncMock(return_value=[{'id':'gemma4-12b'}])):
   context,canonical,_=await orchestration.prepare(body,request,actor,load_identity(),uuid.uuid4())
  self.assertIsNone(canonical);self.assertEqual(context['id'],'auto');self.assertEqual(context['public']['allowed_tools'],[]);privileged.assert_not_awaited()
  body.document_ids=[uuid.uuid4()]
  with patch.object(assistants,'resolve',AsyncMock(side_effect=HTTPException(403,'not_authorized'))):
   with self.assertRaises(HTTPException):await orchestration.prepare(body,request,actor,load_identity(),uuid.uuid4())
 async def test_dns_mixed_with_private_address_fails_closed(self):
  rows=[(None,None,None,None,('8.8.8.8',443)),(None,None,None,None,('127.0.0.1',443))]
  with patch.object(asyncio.get_running_loop(),'getaddrinfo',AsyncMock(return_value=rows)):
   with self.assertRaises(ValueError):await web.public_address('public.example.com')
 async def test_public_fetch_pins_address_but_preserves_tls_hostname(self):
  requests=[]
  def respond(request):
   requests.append(request)
   return httpx.Response(200,text='content',headers={'content-type':'text/plain'})
  async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
   with patch.object(web,'public_address',AsyncMock(return_value='8.8.8.8')):
    result=await web.download(client,'https://angular.dev/guide/signals')
  self.assertEqual(result[0],'https://angular.dev/guide/signals')
  self.assertEqual(requests[0].url.host,'8.8.8.8');self.assertEqual(requests[0].headers['host'],'angular.dev')
  self.assertEqual(requests[0].extensions['sni_hostname'],'angular.dev')
 async def test_redirect_to_private_destination_is_not_followed(self):
  async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(302,headers={'location':'https://127.0.0.1/admin'}))) as client:
   with patch.object(web,'public_address',AsyncMock(return_value='8.8.8.8')):
    with self.assertRaises(ValueError):await web.download(client,'https://example.com/')
 async def test_robots_denial_prevents_content_fetch(self):
  requests=[]
  def respond(request):
   requests.append(str(request.url));return httpx.Response(200,text='User-agent: *\nDisallow: /')
  async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
   with patch.object(web,'public_address',AsyncMock(return_value='8.8.8.8')):
    with self.assertRaisesRegex(ValueError,'robots_disallowed'):await web.extract_page(client,'https://example.com/page','public topic')
  self.assertEqual(len(requests),1)
 async def test_real_extractor_preserves_text_hash_and_snapshot(self):
  html='<html><body><article><h1>Explicacao de signals</h1>'+''.join('<p>Signals acompanham as mudancas do estado e notificam os componentes da aplicacao. A leitura registra a dependencia automaticamente.</p>' for _ in range(8))+'</article></body></html>'
  def respond(request):
   return httpx.Response(404) if request.url.path=='/robots.txt' else httpx.Response(200,text=html,headers={'content-type':'text/html'})
  async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
   with patch.object(web,'public_address',AsyncMock(return_value='8.8.8.8')):
    result=await web.extract_page(client,'https://example.com/page','signals estado')
  self.assertIn('Signals acompanham',result['excerpt']);self.assertEqual(len(result['sha256']),64)
  self.assertIn('snapshot_gzip_base64',result);self.assertEqual(result['claim_veracity'],'not_certified')
 async def test_discovery_filters_nonofficial_candidates_before_legal_recovery(self):
  def respond(request):return httpx.Response(200,json={'results':[{'url':'https://example.com/fake','title':'fake'},{'url':'https://www.planalto.gov.br/ccivil_03/leis/l8112cons.htm','title':'Lei'}]})
  async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
   with patch.dict(os.environ,{'MOARA_SEARXNG_URL':'http://moara-searxng:8080'}):
    result=await web.references(client,'promocao servidor',[])
  self.assertEqual(len(result['hints']),1);self.assertFalse(result['normative_evidence'])
 async def test_configured_searx_recovers_official_text_before_unrelated_catalogue(self):
  from moara.legal_mcp import web_recovery
  from moara.legal_mcp.contracts import Research,today
  record={'norm':{'kind':'LEI','number':55555,'year':2020,'articles':[]},'excerpts':[{'text':'Texto oficial recuperado','device':'Art. 1'}]}
  with patch.dict(os.environ,{'MOARA_SEARXNG_URL':'http://moara-searxng:8080'}),patch.object(web_recovery,'web_references',AsyncMock(return_value={'hints':[{'url':'https://www2.camara.leg.br/official'}]})) as lookup,patch.object(web_recovery,'current_web_links',AsyncMock(return_value=[record])),patch.object(web_recovery,'discover',AsyncMock()) as catalogue:
   value=await web_recovery.recover(SimpleNamespace(),Research(reference_date=today(),subject_query='cargos salarios judiciario federal'))
  self.assertEqual(value['recovery']['status'],'official_text_recovered');catalogue.assert_not_awaited()
  self.assertEqual(lookup.await_args.args[1],'cargos salarios judiciario federal')

if __name__=='__main__':unittest.main()
