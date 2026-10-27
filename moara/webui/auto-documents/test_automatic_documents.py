import asyncio,importlib.util,sys,types,unittest
from pathlib import Path
from unittest.mock import AsyncMock
from fastapi import HTTPException
spec=importlib.util.spec_from_file_location('auto_docs',Path(__file__).with_name('automatic_documents.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Tests(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  self.file=types.SimpleNamespace(id='own',filename='ficticio.pdf',data={'status':'completed','content':'A NUTEC deverá validar o sistema até 30/11/2026. A SECAD deverá emitir a nota.'})
  self.fetch=AsyncMock(return_value=self.file);self.access=AsyncMock(return_value=True)
  for name in ['open_webui','open_webui.models','open_webui.models.files','open_webui.tools','open_webui.tools.builtin','open_webui.utils','open_webui.utils.misc']:
   sys.modules[name]=types.ModuleType(name)
  sys.modules['open_webui.models.files'].Files=types.SimpleNamespace(get_file_by_id=self.fetch)
  sys.modules['open_webui.tools.builtin']._has_read_access_to_file=self.access
  misc=sys.modules['open_webui.utils.misc']
  misc.get_last_user_message=lambda messages:next((x['content'] for x in reversed(messages) if x['role']=='user'),'')
  misc.add_or_update_system_message=lambda text,messages,append=True:[{'role':'system','content':text},*messages]
  self.body={'metadata':{'files':[{'id':'own','type':'file','content':'untrusted supplied fake content'}]},'messages':[{'role':'user','content':'Sou da NUTEC. Tenho alguma providência neste processo?'}]}
 async def test_automatic_complete_content_and_citation(self):
  body,sources,handled=await m.prepare_documents(None,self.body,{'id':'user'},{})
  self.assertTrue(handled);self.assertIn('30/11/2026',sources[0]['document'][0]);self.assertEqual(sources[0]['metadata'][0]['coverage'],'full')
  self.assertNotIn('fake content',sources[0]['document'][0]);self.assertEqual(sources[0]['source']['id'],'own')
  self.access.assert_awaited_once()
 async def test_denied_never_injects(self):
  self.access.return_value=False
  with self.assertRaises(HTTPException) as error:await m.prepare_documents(None,self.body,{'id':'other'},{})
  self.assertEqual(error.exception.status_code,404);self.assertEqual(len(self.body['messages']),1)
 async def test_pending_does_not_answer(self):
  self.file.data['status']='pending'
  with self.assertRaises(HTTPException) as error:await m.prepare_documents(None,self.body,{'id':'user'},{})
  self.assertEqual(error.exception.status_code,409)
 async def test_blank_does_not_claim_read(self):
  self.file.data['content']=' '
  with self.assertRaises(HTTPException) as error:await m.prepare_documents(None,self.body,{'id':'user'},{})
  self.assertEqual(error.exception.status_code,422)
 async def test_no_attachments_unchanged(self):
  body={'messages':[]}
  self.assertEqual(await m.prepare_documents(None,body,{'id':'user'},{}),(body,[],False));self.fetch.assert_not_called()
 async def test_history_budget_fails_explicitly(self):
  self.body['messages'].insert(0,{'role':'assistant','content':'x'*20000})
  with self.assertRaises(HTTPException) as error:await m.prepare_documents(None,self.body,{'id':'user'},{})
  self.assertEqual(error.exception.status_code,413)
 def test_middle_action_not_lost(self):
  text=('Registro informativo de arquivo. '*2000)+' NUTEC deverá instalar o certificado até 20/12/2026. '+('Fim de registros históricos. '*2000)
  excerpt,full=m.select_content(text,'O que a NUTEC precisa fazer?',2500)
  self.assertFalse(full);self.assertIn('20/12/2026',excerpt);self.assertLessEqual(len(excerpt.encode()),2500)
 def test_utf8_budget_and_html_spaces(self):
  excerpt,full=m.select_content('A&#x20;NUTEC deve atuar.', '',100)
  self.assertEqual(excerpt,'A NUTEC deve atuar.');self.assertTrue(full)
  excerpt,full=m.select_content('ação '*10000,'ação',900)
  self.assertLessEqual(len(excerpt.encode()),900);self.assertFalse(full)
 def test_similar_duties_with_different_deadlines_are_not_deduplicated(self):
  common='Registro administrativo sobre acompanhamento da atividade técnica e atualização dos controles internos. '*5
  first=common+' A NUTEC deverá renovar o certificado Atlas até 20/12/2026. '
  second=common+' A NUTEC deverá renovar o certificado Boreal até 21/12/2026. '
  text=('Histórico sem tarefa atual. '*500)+first+('Histórico sem tarefa atual. '*500)+second+('Histórico sem tarefa atual. '*500)
  excerpt,full=m.select_content(text,'Quais as providências e prazos da NUTEC?',4000)
  self.assertFalse(full);self.assertIn('20/12/2026',excerpt);self.assertIn('21/12/2026',excerpt)
if __name__=='__main__':unittest.main()
