import unittest,tempfile,json,hashlib,gzip,base64,os
from pathlib import Path
from unittest.mock import patch,AsyncMock
from types import SimpleNamespace
import httpx
from pydantic import ValidationError
from moara.legal_mcp import stf_catalog as cat,jurisprudence as j
from moara.legal_mcp.contracts import Research,today

def record(number,text='A contribuição descrita neste tema tem natureza infraconstitucional.'):
 return {'numeroTema':str(number),'incidente':'123456','siglaClasse':'ARE','numeroProcesso':'987654','descricaoTese':text,'dataAndamento':'01/01/2020'}

async def imported(root,banks):
 def handler(request):
  if request.url.path.endswith('robots.txt'):return httpx.Response(200,text='User-agent: *\nDisallow: /processos\n')
  if request.url.path.endswith('.js'):return httpx.Response(200,text='retornartesesrepercussaogeral.asp; array.slice(0,20);')
  if request.url.path.endswith('teses.asp'):return httpx.Response(200,text='Última Atualização: 31/10/2026 12:00:00')
  bank=request.content.decode().split('=')[1];return httpx.Response(200,json=banks[bank])
 client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
 with patch.object(cat.httpx,'AsyncClient',return_value=client),patch.object(cat.asyncio,'sleep',AsyncMock()):return await cat.harvest(root)

class STFCollectionTests(unittest.IsolatedAsyncioTestCase):
 async def test_both_complete_banks_are_searchable_paginated_and_exported_with_proofs(self):
  with tempfile.TemporaryDirectory() as root:
   manifest=await imported(root,{'com':[record(333),record(334)],'sem':[record(444)]})
   self.assertEqual(manifest['counts'],{'com':2,'sem':1});self.assertEqual(manifest['unique_themes'],3)
   pages=[cat.search(cat.CatalogSearch(page=n,limit=1),root) for n in range(1,4)]
   self.assertEqual([p['items'][0]['theme'] for p in pages],[333,334,444])
   self.assertEqual(cat.search(cat.CatalogSearch(bank='sem'),root)['total'],1)
   self.assertEqual(cat.search(cat.CatalogSearch(query='contribuicao'),root)['total'],3)
   data=cat.export(root)
   for snapshot in data['manifest']['snapshots']:self.assertEqual(hashlib.sha256(gzip.decompress(base64.b64decode(snapshot['snapshot_gzip_base64']))).hexdigest(),snapshot['sha256'])
 async def test_partial_refresh_does_not_replace_the_previous_complete_version(self):
  with tempfile.TemporaryDirectory() as root:
   first=await imported(root,{'com':[record(333)],'sem':[record(444)]})
   with self.assertRaises(ValueError):await imported(root,{'com':[record(555)],'sem':[]})
   self.assertEqual(cat.current(root)[1]['version'],first['version']);self.assertEqual(cat.search(cat.CatalogSearch(),root)['total'],2)
 def test_case_class_is_preserved_and_dates_are_not_labeled_as_publication(self):
  row=cat.decode_bank(json.dumps([record(333)]).encode(),'sem')[0]
  self.assertIn('classeProcesso=ARE',row['andamento_url']);self.assertEqual(row['bank'],'sem');self.assertEqual(row['displayed_event_date'],'01/01/2020')
  self.assertNotIn('publication_date',row)
 async def test_conflicting_or_duplicate_theme_numbers_are_preserved_not_overwritten(self):
  with tempfile.TemporaryDirectory() as root:
   manifest=await imported(root,{'com':[record(333)],'sem':[record(333)]})
   self.assertEqual(manifest['total'],2);self.assertEqual(manifest['unique_themes'],1);self.assertEqual(manifest['themes_in_both_banks'],[333])
 def test_local_snapshot_is_never_a_current_legal_certificate_and_paths_are_bounded(self):
  with tempfile.TemporaryDirectory() as root:
   Path(root,'CURRENT').write_text('../../secrets')
   result=cat.search(cat.CatalogSearch(query='" OR 1=1 --'),root)
   self.assertFalse(result['available']);self.assertFalse(result['freshly_rechecked']);self.assertFalse(result['legal_conclusion_allowed'])
  with self.assertRaises(ValidationError):cat.CatalogSearch(limit=51)
  with self.assertRaises(ValueError):cat.decode_bank(b'[{"numeroTema":"secret"}]','com')
 async def test_catalogue_candidates_still_require_independent_live_verification(self):
  with tempfile.TemporaryDirectory() as root:
   await imported(root,{'com':[record(333,'O ICMS não compõe a base de incidência do PIS e da COFINS.')],'sem':[record(444)]})
   live={'reference':{'court':'STF','kind':'TEMA','number':333},'official_theme':{'title':'ICMS PIS COFINS','description':'Questão tributária'},'excerpts':[{'text':'registro conferido agora'}]}
   with patch.dict(os.environ,{'MOARA_STF_CATALOG_DIR':root}),patch.object(j,'tracked',AsyncMock(return_value='<html>Sem resultados oficiais na pesquisa</html>')),patch('moara.legal_mcp.research.precedent',AsyncMock(return_value=live)) as verify:
    result=await j.search_subject(SimpleNamespace(),Research(reference_date=today(),court='STF',subject_query='ICMS PIS COFINS'))
   self.assertEqual(result['precedents'][0]['reference']['number'],333);self.assertEqual(verify.await_args.args[1].number,333)
   with patch.dict(os.environ,{'MOARA_STF_CATALOG_DIR':root}),patch.object(j,'tracked',AsyncMock(return_value='<html>Sem resultados oficiais na pesquisa</html>')),patch('moara.legal_mcp.research.precedent',AsyncMock(return_value={'status':'unavailable','excerpts':[]})):
    result=await j.search_subject(SimpleNamespace(),Research(reference_date=today(),court='STF',subject_query='ICMS PIS COFINS'))
   self.assertEqual(result['precedents'],[])
