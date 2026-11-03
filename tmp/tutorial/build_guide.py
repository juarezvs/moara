import json,html,math,zipfile
from pathlib import Path
from xml.sax.saxutils import escape
from PIL import Image as PILImage
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4,landscape
from reportlab.lib.colors import HexColor,white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'output/tutorial-moara';PDF=ROOT/'output/pdf';PDF.mkdir(parents=True,exist_ok=True)
pages=json.loads((ROOT/'tmp/tutorial/pages.json').read_text(encoding='utf-8'))
report=json.loads((ROOT/'docs/evidence/tutorial-production-report.json').read_text(encoding='utf-8'))
assert report['passed']
(OUT/'dados-ficticios/tutorial-alfa.txt').write_text('No procedimento fictício Alfa, o prazo de resposta é de cinco dias úteis.\n',encoding='utf-8')
(OUT/'dados-ficticios/tutorial-indicadores.csv').write_text('setor,quantidade\nA,2\nA,3\nB,4\n',encoding='utf-8')
for p in pages:assert (OUT/'imagens'/p['image']).is_file()
trouble=[
('Não vejo Documentos ou MOARA DEV','Você pode estar no chat da raiz. Abra /moara/espaco e confira o título Espaço de trabalho.'),
('O menu Espaço de trabalho não aparece','A permissão workspace.use é necessária. Se o endereço direto também não abrir, registre a URL final e peça a conferência do perfil de acesso.'),
('Não vejo Indexar para consulta','Entre em Documentos e selecione um documento enviado. O botão aparece dentro de Editar item.'),
('Não encontro Consultar Documentos','O título real é Consultar conhecimento. Role abaixo dos cartões do módulo.'),
('Não encontro Arquiteto','Role até Agentes especializados e abra a lista Especialidade. Não há uma aba superior chamada Arquiteto.'),
('O trabalho está Na fila ou Em execução','Use Atualizar em Execuções e aguarde. Há processamento serial de IA e carregamento de modelos; não crie várias execuções iguais.'),
('A execução aparece como Falhou','Abra Resultado e registre error. Para no_compatible_execution_available, o administrador deve conferir perfil autorizado, modelo habilitado e configuração pronta.'),
('Não vejo os botões de executar código','Sua conta precisa de development.execute. A conta comum do tutorial não recebeu essa permissão. Revisar a proposta e exportar Git continuam sendo testes separados.'),
('Ainda vejo uma tela diferente','Confira a URL completa; use Ctrl+F5. Se persistir, registre a tela e a mensagem de erro sem expor senha ou conteúdo sigiloso.')
]
css="""*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#eff4fb;color:#142747;font-family:Arial,sans-serif;line-height:1.6}header{padding:48px max(24px,calc((100% - 1080px)/2));background:#10213d;color:white}header h1{font-size:38px;line-height:1.15;margin:12px 0}header a{color:#8edaff}main{max-width:1120px;margin:30px auto;padding:0 20px}section{background:white;border:1px solid #dbe5f0;border-radius:16px;padding:30px;margin:24px 0;scroll-margin-top:16px}h2{font-size:28px;line-height:1.2;margin:8px 0 20px}h3{font-size:19px}a{color:#145ec7}nav a{display:inline-block;margin:5px 14px 5px 0}.tag{font-size:12px;letter-spacing:1.5px;font-weight:bold;color:#2466bb}.note{background:#eef5ff;border-left:4px solid #2466bb;padding:14px 18px;margin-top:20px}li{padding:5px 0}figure{margin:24px 0 0;background:#f5f8fc;padding:14px;border-radius:10px}img{display:block;max-width:100%;height:auto;margin:auto;border:1px solid #d6e1ee}figcaption{font-size:13px;color:#48607d;margin:10px 0 0}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:12px;border-bottom:1px solid #dde5ef;vertical-align:top}td:first-child{width:30%;font-weight:bold}.downloads a{display:inline-block;background:#eaf2ff;border-radius:8px;padding:9px 14px;margin:5px}footer{padding:24px;text-align:center;color:#48607d}@media(max-width:600px){header h1{font-size:30px}section{padding:20px}h2{font-size:24px}td,th{padding:8px}}@media print{header{padding:20px;color:#142747;background:white}section{break-inside:avoid;box-shadow:none}nav,.downloads{display:none}}"""
parts=['<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Tutorial Moara - seis testes com telas reais</title><style>'+css+'</style><header><div>MOARA AI · TUTORIAL VERIFICADO EM 27/10/2026</div><h1>Seis testes, passo a passo<br>com telas reais da Moara</h1><p>A R2 está publicada. Para este roteiro, entre no <a href="https://moara.am.trf1.gov.br/moara/espaco">Espaço de trabalho</a>, e não apenas no chat da página inicial.</p></header><main>']
parts.append('<section><h2>Antes de começar</h2><p>Capturas feitas no endereço de produção, usando uma conta fictícia com papel Usuário e autorização temporária apenas para o perfil de IA fast. A autorização foi retirada e a conta foi desativada ao terminar. Nenhuma tela foi recriada por IA.</p><p>A execução de código é opcional e não foi liberada à conta comum. Foram verificados: indexação, resposta com fonte, agente Arquiteto, DOCX/PDF, proposta e aceitação de código, Git, fluxo simulado e Analytics.</p><div class="downloads"><a href="dados-ficticios/tutorial-alfa.txt" download>Baixar TXT fictício</a><a href="dados-ficticios/tutorial-indicadores.csv" download>Baixar CSV fictício</a><a href="tutorial-moara.pdf">Abrir PDF</a></div><nav>'+''.join('<a href="#etapa-'+str(i)+'">'+escape(p['tag'])+'</a>' for i,p in enumerate(pages,1))+'</nav></section>')
for i,p in enumerate(pages,1):
 parts.append('<section id="etapa-'+str(i)+'"><div class="tag">'+escape(p['tag'])+'</div><h2>'+escape(p['title'])+'</h2><p>'+escape(p['intro'])+'</p><ol>'+''.join('<li>'+escape(s)+'</li>' for s in p['steps'])+'</ol><figure><a href="imagens/'+p['image']+'" target="_blank"><img loading="lazy" src="imagens/'+p['image']+'" alt="'+escape(p['caption'])+'"></a><figcaption>'+escape(p['caption'])+' Clique na imagem para ampliar.</figcaption></figure><div class="note">'+escape(p['note'])+'</div></section>')
parts.append('<section><h2>Se algo não aparecer</h2><table><tr><th>Situação</th><th>O que conferir</th></tr>'+''.join('<tr><td>'+escape(a)+'</td><td>'+escape(b)+'</td></tr>' for a,b in trouble)+'</table></section>')
parts.append('<section><h2>Mais duas capturas de conferência</h2><p>Os textos gerados podem variar entre execuções. Confira os resultados, não apenas o estado da tarefa.</p>')
for name,caption in [('06-resultado-arquiteto.png','Análise do agente Arquiteto, gerada no teste real.'),('10-proposta-revisada.png','Proposta de código e revisão obtidas no teste real.')]:
 parts.append('<figure><a href="imagens/'+name+'" target="_blank"><img loading="lazy" src="imagens/'+name+'" alt="'+caption+'"></a><figcaption>'+caption+'</figcaption></figure>')
parts.append('</section></main><footer>Produção: moara.am.trf1.gov.br · R2 · Capturas com dados fictícios · 27/10/2026</footer></html>')
(OUT/'tutorial-moara.html').write_text(''.join(parts),encoding='utf-8')
pdfmetrics.registerFont(TTFont('Guide','C:/Windows/Fonts/arial.ttf'));pdfmetrics.registerFont(TTFont('GuideBold','C:/Windows/Fonts/arialbd.ttf'))
W,H=landscape(A4);path=PDF/'tutorial-moara.pdf';c=canvas.Canvas(str(path),pagesize=(W,H))
c.setTitle('Moara - seis testes com telas reais');c.setAuthor('Moara AI')
navy=HexColor('#142747');blue=HexColor('#2466bb');muted=HexColor('#50647e')
def para(text,x,top,width,size=10.3,leading=14.4,color=navy,bold=False):
 style=ParagraphStyle('p',fontName='GuideBold' if bold else 'Guide',fontSize=size,leading=leading,textColor=color)
 p=Paragraph(text,style);pw,ph=p.wrap(width,1000);p.drawOn(c,x,top-ph);return top-ph
def chrome(tag,title,num,total):
 c.setFillColor(HexColor('#f2f6fc'));c.rect(0,0,W,H,fill=1,stroke=0)
 c.setFillColor(blue);c.rect(0,H-9,W,9,fill=1,stroke=0)
 para('MOARA AI  /  GUIA DE TESTES',34,H-27,500,9,12,blue,True)
 para('27/10/2026  |  Telas reais de produção',W-270,H-27,240,8.8,12,muted)
 para(tag,34,H-62,W-68,9,12,blue,True)
 para(escape(title),34,H-82,W-68,23,28,navy,True)
 c.setStrokeColor(HexColor('#d6e0ed'));c.line(34,37,W-34,37)
 para('moara.am.trf1.gov.br/moara/espaco  |  Dados fictícios',34,26,W-150,8,10,muted)
 para(str(num)+' / '+str(total),W-90,26,56,8,10,muted)
 c.linkURL('https://moara.am.trf1.gov.br/moara/espaco',(34,12,350,30),relative=0)
def screenshot(name,x,top,maxw,maxh,window=None):
 image=OUT/'imagens'/name;iw,ih=PILImage.open(image).size
 if window:sy,sh=window
 else:sy,sh=0,ih
 scale=min(maxw/iw,maxh/sh);dw,dh=iw*scale,sh*scale;y=top-dh
 c.setFillColor(white);c.roundRect(x-5,y-5,dw+10,dh+10,6,stroke=0,fill=1)
 c.saveState();clip=c.beginPath();clip.rect(x,y,dw,dh);c.clipPath(clip,stroke=0,fill=0)
 c.drawImage(str(image),x,y-(ih-sy-sh)*scale,width=iw*scale,height=ih*scale,mask='auto')
 c.restoreState()
 return y
focus={'09-projeto-solicitar.png':(365,345),'11-projeto-arquivos-git.png':(705,505),'12-fluxo-etapa.png':(380,544),'14-analytics-configurar.png':(400,633)}
total=len(pages)+2
for n,p in enumerate(pages,1):
 chrome(p['tag'],p['title'],n,total)
 top=H-128;left=248;rightx=310;rightw=W-rightx-34
 blocks=[escape(p['intro'])]+[str(i)+'. '+escape(s) for i,s in enumerate(p['steps'],1)]+['<b>Confira:</b> '+escape(p['note'])]
 size=10.2;lead=14
 while True:
  heights=[]
  for b in blocks:
   pp=Paragraph(b,ParagraphStyle('measure',fontName='Guide',fontSize=size,leading=lead));heights.append(pp.wrap(left,1000)[1]+9)
  if sum(heights)<=top-52 or size<=9:break
  size-=0.2;lead-=0.3
 y=top
 for b in blocks:y=para(b,34,y,left,size,lead)-9
 if y<40:raise RuntimeError('Text overflow on page '+str(n))
 bottom=screenshot(p['image'],rightx,top,rightw,365,focus.get(p['image']))
 caption=p['caption']+(' Recorte da captura; imagem completa no HTML.' if p['image'] in focus else '')
 para(escape(caption),rightx,bottom-14,rightw,8.8,12,muted)
 c.showPage()
chrome('DIAGNÓSTICO','Se uma opção não aparecer',len(pages)+1,total)
y=H-130
for a,b in trouble:
 y=para(escape(a),34,y,220,10,13,blue,True)
 # Align the answer with the previous row's top, using max row height.
 # Recompute independent paragraph heights for consistent table rows.
 style1=ParagraphStyle('a',fontName='GuideBold',fontSize=10,leading=13)
 style2=ParagraphStyle('b',fontName='Guide',fontSize=10,leading=13)
 h1=Paragraph(escape(a),style1).wrap(220,1000)[1];h2=Paragraph(escape(b),style2).wrap(510,1000)[1]
 rowtop=y+h1;para(escape(b),280,rowtop,510,10,13)
 y=rowtop-max(h1,h2)-13
 if y<43:raise RuntimeError('Troubleshooting page overflow')
c.showPage()
chrome('CONFERÊNCIA FINAL','Checklist dos seis testes',len(pages)+2,total)
items=[
('1. Documentos','O TXT foi indexado; a resposta informa cinco dias úteis e cita a fonte.'),
('2. Agente Arquiteto','A análise foi concluída e o resultado pode ser aberto em Execuções.'),
('3. Templates','O texto Olá, Pessoa de teste. aparece no DOCX e no PDF de conferência.'),
('4. MOARA DEV','A proposta foi revisada, os arquivos foram aceitos e o histórico Git foi baixado. Execução exige permissão adicional.'),
('5. MOARA FLOW','O resultado mostra a notificação simulada e external_writes: false.'),
('6. Analytics','A tabela mostra A = 5 (2 registros) e B = 4 (1 registro).')
]
y=H-135
for a,b in items:
 c.setStrokeColor(blue);c.rect(36,y-13,11,11,stroke=1,fill=0)
 y=para('<b>'+escape(a)+'</b> - '+escape(b),60,y,W-100,11,16)-20
para('Escopo da verificação',34,y-8,W-68,12,16,blue,True)
para('As capturas foram obtidas na versão publicada, com conta fictícia de usuário e acesso temporário ao perfil fast. O acesso foi retirado e a conta desativada ao terminar. As imagens não são mockups. A captura de execução de código não faz parte deste teste com conta comum.',34,y-34,W-68,10.5,15)
para('Abra tutorial-moara.html para ampliar as 16 imagens e use os arquivos da pasta dados-ficticios. Se houver falha, registre URL, etapa e mensagem; nunca compartilhe senha.',34,y-92,W-68,10.5,15)
c.showPage();c.save()
(OUT/'tutorial-moara.pdf').write_bytes(path.read_bytes())
(OUT/'LEIA-ME.txt').write_text('Tutorial Moara - 27/10/2026\n\n1. Extraia todo o ZIP.\n2. Abra tutorial-moara.html no navegador para ver e ampliar as telas.\n3. Ou abra tutorial-moara.pdf.\n4. Use os arquivos TXT e CSV da pasta dados-ficticios.\n5. Site dos testes: https://moara.am.trf1.gov.br/moara/espaco\n\nAs capturas são reais, feitas em produção com dados fictícios. A conta temporária foi desativada.\n',encoding='utf-8')
with zipfile.ZipFile(ROOT/'output/tutorial-moara-completo.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
 for f in sorted(OUT.rglob('*')):
  if f.is_file() and f.name!='erro-captura.png':z.write(f,Path('tutorial-moara')/f.relative_to(OUT))
print(json.dumps({'pdf':str(path),'pages':total,'screenshots':len(report['images']),'zip':str(ROOT/'output/tutorial-moara-completo.zip')},ensure_ascii=False))
