import asyncio,json,unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
import httpx
from moara.legal_mcp.sources import OfficialSources
from moara.legal_mcp import stf_theses,jurisprudence
from moara.gateway.theme_answer import answer,readable,roman_sections

def bank(number=888,process='123456'):
 return [{'numeroTema':str(number),'descricaoTese':'1. A regra impede a concessão automática.2. A exceção exige, cumulativamente:(a) prova do requerimento;(b) prova de necessidade.3. Deve ser observado o Tema 1.234.','siglaClasse':'RE','numeroProcesso':process,'incidente':'77','dataAndamento':'01/01/2020'}]
def record(number=888,leading='RE 123456'):
 return {'reference':{'court':'STF','kind':'TEMA','number':number},'official_theme':{'number':number,'leading_case':leading,'title':'Objeto de teste','description':'Descrição de teste','reported_status':'Trânsito em julgado'},'source':'https://portal.stf.jus.br/jurisprudenciaRepercussao/tema.asp?num='+str(number),'excerpts':[],'snapshots':[],'source_checks':[],'gaps':[]}

class ThesisTests(unittest.IsolatedAsyncioTestCase):
 def test_popular_vocabulary_is_not_a_theme_number_map(self):
  self.assertEqual(jurisprudence.keywords('remédio alto custo e suas respectivas teses'),['medicamento','alto','custo'])
  self.assertNotIn('alto',jurisprudence.ACRONYMS)
  self.assertGreater(jurisprudence.matches('Fornecimento de medicamentos registrados no SUS','remédio alto custo'),0)
 async def test_fresh_bank_download_is_shared_within_one_research_only(self):
  seen=[]
  def handler(request):
   seen.append(request)
   if request.url.path=='/robots.txt':return httpx.Response(200,text='User-agent: *\nDisallow: /processos\nAllow: /repercussaogeral/\n'+'# policy '*20)
   self.assertEqual(request.method,'POST');self.assertEqual(request.content,b'tipo=com');return httpx.Response(200,json=bank())
  async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
   adapter=OfficialSources(client);a=record();b=record()
   await asyncio.gather(stf_theses.attach(adapter,a),stf_theses.attach(adapter,b));self.assertEqual(len(seen),2)
   self.assertTrue(a['published_thesis']['freshly_rechecked']);self.assertFalse(a['published_thesis']['effective_application_confirmed'])
   self.assertEqual(a['excerpts'][0]['text'],bank()[0]['descricaoTese'])
   await stf_theses.attach(OfficialSources(client),record());self.assertEqual(len(seen),4)
 async def test_leading_case_mismatch_never_attaches_a_thesis(self):
  adapter=SimpleNamespace(_fresh_theses_task=asyncio.create_task(asyncio.sleep(0,result={'items':[{'theme':888,'leading_case':'ARE 999','thesis_text':'Texto errado'}],'snapshots':[],'source_checks':[],'gaps':[]})))
  r=record();await stf_theses.attach(adapter,r);self.assertNotIn('published_thesis',r)
 async def test_provider_restrictions_are_not_bypassed(self):
  seen=[]
  def handler(r):seen.append(r);return httpx.Response(200,text='User-agent: *\nDisallow: /\n'+'# policy '*20)
  async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
   r=record();await stf_theses.attach(OfficialSources(c),r)
  self.assertEqual(len(seen),1);self.assertNotIn('published_thesis',r);self.assertTrue(r['gaps'])
 async def test_search_failure_is_not_a_cached_thesis_claim(self):
  async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(503))) as c:
   r=record();await stf_theses.attach(OfficialSources(c),r)
  self.assertNotIn('published_thesis',r);self.assertTrue(r['gaps'])
 def test_related_themes_come_only_from_actual_published_text(self):
  r=record();r['published_thesis']={'text':bank()[0]['descricaoTese']};self.assertEqual(stf_theses.related(r),[1234]);self.assertEqual(stf_theses.related(record()),[])
 async def test_explicit_relationship_outweighs_loose_subject_matches(self):
  from moara.legal_mcp.contracts import Research,today
  from moara.legal_mcp import research
  candidates=[{'reference':{'court':'STF','kind':'TEMA','number':n}} for n in [888,999]]
  async def checked(adapter,ref,at):
   r=record(ref.number);r['official_theme']['title']='Coleta pública'
   if ref.number==888:r['published_thesis']={'text':'Devem ser observadas as diretrizes do Tema 777.'}
   return r
  with patch.object(jurisprudence,'tracked',AsyncMock(return_value='html')),patch.object(jurisprudence,'listing',return_value=candidates),patch.object(research,'precedent',side_effect=checked):
   result=await jurisprudence.search_subject(SimpleNamespace(),Research(reference_date=today(),court='STF',subject_query='coleta pública',query='Quais os temas e as respectivas teses?'))
  self.assertEqual([r['reference']['number'] for r in result['precedents']],[888,777]);self.assertEqual(result['precedent_discovery']['additional_record_checks'][0]['reference']['number'],999)
 def test_formatter_preserves_cumulative_requirements_and_links(self):
  r=record();r['published_thesis']={'text':bank()[0]['descricaoTese'],'freshly_rechecked':True,'source':'https://portal.stf.jus.br/repercussaogeral/teses.asp'}
  out=answer([r],[]);self.assertIn('cumulativamente',out['answer']);self.assertIn('- (a) prova do requerimento',out['answer']);self.assertIn('- (b) prova de necessidade',out['answer']);self.assertIn('[Tese no STF]',out['answer']);self.assertFalse(out['inference_used'])
 def test_roman_summary_retains_full_text_and_all_subitems(self):
  text='I – Competência 1) Regra principal. 1.1) Exceção importante. II – Custeio 2) Regra de custeio. '+'Conteúdo integral. '*500
  r=record();r['published_thesis']={'text':text,'freshly_rechecked':True,'source':'https://portal.stf.jus.br/repercussaogeral/teses.asp'}
  out=answer([r],[])['answer'];self.assertEqual(len(roman_sections(text)),2);self.assertIn('<details>',out);self.assertIn('Exceção importante.',out);self.assertIn('Competência',out)

if __name__=='__main__':unittest.main()
