"""Execute the installed file reader with synthetic content and mocked access checks."""
import ast,asyncio,json,sys,types,unittest
from pathlib import Path
source=ast.parse(Path('/app/backend/open_webui/tools/builtin.py').read_text())
fn=next(n for n in source.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='view_file')
fn.returns=None
for arg in fn.args.args:arg.annotation=None
content='DOCUMENTO FICTICIO. Prazo Alfa: cinco dias uteis. '+('x'*100000)
file=types.SimpleNamespace(id='synthetic',filename='ficticio.txt',updated_at=0,created_at=0,data={'content':content})
class Files:
 @staticmethod
 async def get_file_by_id(identifier):return file if identifier=='synthetic' else None
async def access(*args):return True
ns={'VIEW_FILE_DEFAULT_MAX_CHARS':2000,'VIEW_FILE_MAX_CHARS':4000,'JSONCodec':types.SimpleNamespace(dumps=json.dumps),'_has_read_access_to_file':access}
module=types.ModuleType('open_webui.models.files');module.Files=Files
sys.modules['open_webui.models.files']=module
exec(compile(ast.Module(body=[fn],type_ignores=[]),'installed_reader','exec'),ns)
class Excerpts(unittest.IsolatedAsyncioTestCase):
 async def test_default(self):
  result=json.loads(await ns['view_file']('synthetic',__request__=object(),__user__={'id':'test'}))
  self.assertEqual(len(result['content']),2000);self.assertTrue(result['truncated']);self.assertEqual(result['next_offset'],2000)
 async def test_cap_and_pagination(self):
  result=json.loads(await ns['view_file']('synthetic',offset=2000,max_chars=999999,__request__=object(),__user__={'id':'test'}))
  self.assertEqual(len(result['content']),4000);self.assertEqual(result['next_offset'],6000)
 async def test_long_line_cannot_bypass_cap(self):
  result=json.loads(await ns['view_file']('synthetic',start_line=1,end_line=1,__request__=object(),__user__={'id':'test'}))
  self.assertLessEqual(len(result['content']),4000);self.assertTrue(result['truncated']);self.assertIn('pagination_hint',result)
 async def test_access_preserved(self):
  async def denied(*a):return False
  ns['_has_read_access_to_file']=denied
  try:
   result=json.loads(await ns['view_file']('synthetic',__request__=object(),__user__={'id':'other'}))
   self.assertIn('error',result);self.assertNotIn('content',result)
  finally:ns['_has_read_access_to_file']=access
if __name__=='__main__':unittest.main()
