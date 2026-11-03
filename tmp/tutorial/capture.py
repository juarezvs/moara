import json,sys,re,time
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
cfg=json.load(sys.stdin);base='https://moara.am.trf1.gov.br';out=Path('/tmp/tutorial');out.mkdir(exist_ok=True)
report={'origin':base,'environment':'production','synthetic_account':True,'checks':{},'images':[]}
def write_report(): (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,args=['--no-sandbox','--ignore-certificate-errors-spki-list='+cfg['spki']])
 context=browser.new_context(viewport={'width':1366,'height':950},device_scale_factor=1)
 page=context.new_page();page.set_default_timeout(25000)
 def snap(name,locator=None):
  page.locator('body').click(position={'x':1340,'y':30})
  if locator:locator.screenshot(path=str(out/name),timeout=30000)
  else:page.screenshot(path=str(out/name),full_page=False)
  report['images'].append(name);write_report()
 def section(name):return page.locator('section.card').filter(has=page.get_by_role('heading',name=name,exact=True))
 def button(name):return page.get_by_role('button',name=name,exact=True)
 def label(name):return page.get_by_label(name,exact=True)
 def tab(name):button(name).click();expect(label('Título')).to_be_visible()
 def post_click(action,path):
  with page.expect_response(lambda r:path in r.url and r.request.method=='POST' and r.status<400,timeout=60000) as response:action()
  return response.value.json()
 def wait_job(job,key):
  deadline=time.monotonic()+650
  while time.monotonic()<deadline:
   data=page.evaluate("async id=>{const r=await fetch('/moara/api/v1/platform/runs/'+id);if(!r.ok)throw new Error('Job read failed');return r.json()}",job['id'])
   if data['status'] not in ('queued','running'):
    report['checks'][key]={'status':data['status'],'error':data.get('error_code')};write_report()
    if data['status']!='completed':raise RuntimeError(key+':'+str(data.get('error_code')))
    button('Atualizar').click()
    row=page.locator('tr').filter(has=page.get_by_role('button',name='Resultado',exact=True)).first
    row.get_by_role('button',name='Resultado',exact=True).click()
    expect(page.locator('.platform-output')).not_to_be_empty()
    return data
   time.sleep(3)
  raise RuntimeError(key+':timeout')
 try:
  page.goto(base+'/',wait_until='networkidle',timeout=60000);report['root_url']=page.url;report['root_title']=page.title()
  snap('00-entrada-raiz.png')
  context.add_cookies([{'name':cfg['cookie_name'],'value':cfg['cookie'],'domain':'moara.am.trf1.gov.br','path':'/moara','secure':True,'httpOnly':True,'sameSite':'Strict'}])
  page.goto(base+'/moara/espaco',wait_until='networkidle')
  expect(page.get_by_role('heading',name='Espaço de trabalho',exact=True)).to_be_visible()
  report['workspace_url']=page.url;report['checks']['workspace_as_regular_user']=True
  snap('01-espaco-trabalho.png')
  # 1. Document upload, ingest, retrieval.
  page.locator('input[type=file]').set_input_files({'name':'tutorial-alfa.txt','mimeType':'text/plain','buffer':'No procedimento fictício Alfa, o prazo de resposta é de cinco dias úteis.'.encode()})
  expect(button('Indexar para consulta')).to_be_visible()
  snap('02-documento-indexar.png',page.locator('.platform-grid'))
  job=post_click(lambda:button('Indexar para consulta').click(),'/platform/runs')
  wait_job(job,'document_indexed')
  label('Pergunta').fill('Qual é o prazo do procedimento fictício Alfa? Cite a fonte.')
  snap('03-consultar-conhecimento.png',section('Consultar conhecimento'))
  job=post_click(lambda:button('Consultar fontes autorizadas').click(),'/platform/runs')
  result=wait_job(job,'knowledge_answer')
  report['checks']['citation_present']=bool(result['result'].get('citations'))
  snap('04-resposta-documental.png',section('Resultado'))
  # 2. Specialized agent.
  page.get_by_role('combobox',name=re.compile('^Especialidade')).select_option('architect')
  label('Solicitação ao agente').fill('Proponha uma arquitetura simples para um cadastro interno de tarefas fictícias. Responda em até cinco tópicos.')
  snap('05-agente-arquiteto.png',section('Agentes especializados'))
  job=post_click(lambda:button('Solicitar análise').click(),'/platform/runs')
  wait_job(job,'architect_agent');snap('06-resultado-arquiteto.png',section('Resultado'))
  # 3. Template.
  tab('Templates');label('Título').fill('Tutorial - saudação fictícia')
  label('Texto (use {{campo}} para variáveis)').fill('Olá, {{nome}}.')
  label('Variáveis separadas por vírgula').fill('nome');button('Salvar versão').click()
  expect(label('nome')).to_be_visible();label('nome').fill('Pessoa de teste')
  snap('07-template-preencher.png',section('Editar item'))
  with page.expect_download() as dl:button('Preencher e gerar DOCX').click()
  dl.value.save_as(str(out/'exemplo-gerado.docx'))
  expect(page.locator('.platform-output')).to_contain_text('Pessoa de teste')
  snap('08-template-resultado.png',section('Resultado'))
  with page.expect_download() as dl:button('Baixar PDF de conferência').click()
  dl.value.save_as(str(out/'exemplo-gerado.pdf'));report['checks']['template_downloads']=True;write_report()
  # 4. Project.
  tab('MOARA DEV');label('Título').fill('Tutorial - projeto Python 42')
  label('Descrição ou instruções').fill('Projeto fictício mínimo. Somente main.py, sem dependências, imprime 42.')
  button('Salvar versão').click();expect(label('Solicitação')).to_be_visible()
  label('Solicitação').fill('Crie somente main.py com print(42). Não adicione dependências.')
  snap('09-projeto-solicitar.png',section('Editar item'))
  job=post_click(lambda:button('Propor plano e arquivos').click(),'/platform/runs')
  wait_job(job,'project_proposal');snap('10-proposta-revisada.png',section('Resultado'))
  button('Aceitar arquivos propostos nesta versão').click()
  expect(page.get_by_role('status')).to_contain_text('Arquivos aceitos',timeout=30000)
  snap('11-projeto-arquivos-git.png',section('Editar item'))
  with page.expect_download() as dl:page.get_by_role('link',name='Exportar histórico Git',exact=True).click()
  dl.value.save_as(str(out/'projeto-tutorial.bundle'))
  report['checks']['git_download']=True
  report['checks']['execution_requires_extra_permission']=button('Revisar arquivos para execução').count()==0
  # 5. Flow
  tab('MOARA FLOW');label('Título').fill('Tutorial - fluxo fictício')
  label('Descrição ou instruções').fill('Teste sem envio de mensagens reais.')
  label('Mensagem de teste').fill('Esta é uma notificação fictícia do tutorial.')
  button('Adicionar etapa').click();button('Salvar versão').click()
  expect(button('Executar teste')).to_be_visible();snap('12-fluxo-etapa.png',section('Editar item'))
  job=post_click(lambda:button('Executar teste').click(),'/platform/runs')
  wait_job(job,'workflow');snap('13-fluxo-resultado.png',section('Resultado'))
  # 6. Analytics
  tab('Documentos')
  page.locator('input[type=file]').set_input_files({'name':'tutorial-indicadores.csv','mimeType':'text/csv','buffer':b'setor,quantidade\nA,2\nA,3\nB,4\n'})
  expect(button('Indexar para consulta')).to_be_visible()
  tab('Analytics');label('Título').fill('Tutorial - total fictício por setor')
  page.get_by_role('checkbox',name='tutorial-indicadores.csv',exact=True).check()
  label('Coluna de agrupamento').fill('setor')
  page.get_by_role('combobox',name=re.compile('^Operação')).select_option('sum')
  label('Coluna numérica').fill('quantidade');button('Salvar versão').click()
  expect(button('Calcular indicador')).to_be_visible();snap('14-analytics-configurar.png',section('Editar item'))
  with page.expect_download() as dl:button('Calcular indicador').click()
  dl.value.save_as(str(out/'indicador-gerado.csv'))
  expect(section('Indicador calculado')).to_be_visible()
  expect(section('Indicador calculado')).to_contain_text('5')
  expect(section('Indicador calculado')).to_contain_text('4')
  snap('15-analytics-resultado.png',section('Indicador calculado'))
  report['checks']['analytics']=True
  report['passed']=True
 except Exception as e:
  report['error']=str(e)[:1800];report['passed']=False
  try:snap('erro-captura.png')
  except Exception:pass
 finally:
  write_report();browser.close()
 print(json.dumps({'passed':report.get('passed'),'checks':report['checks'],'images':len(report['images']),'error':report.get('error')},ensure_ascii=False))
 if not report.get('passed'):raise SystemExit(1)
