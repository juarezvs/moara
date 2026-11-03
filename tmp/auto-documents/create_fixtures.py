from pathlib import Path
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from pypdf import PdfReader
root=Path('tmp/auto-documents/fixtures');root.mkdir(parents=True,exist_ok=True)
styles=getSampleStyleSheet()
def make(name,pages):
 story=[]
 for n,paragraphs in enumerate(pages):
  if n:story.append(PageBreak())
  story += [Paragraph('PROCESSO FICTÍCIO - TESTE DA MOARA',styles['Heading1']),Paragraph('Sem valor administrativo ou jurídico. Página '+str(n+1),styles['Normal']),Spacer(1,18)]
  for text in paragraphs:story.extend([Paragraph(text,styles['BodyText']),Spacer(1,10)])
 SimpleDocTemplate(str(root/name),pagesize=A4,rightMargin=48,leftMargin=48,topMargin=48,bottomMargin=48).build(story)
 text='\n'.join(p.extract_text() or '' for p in PdfReader(root/name).pages)
 print(name,len(text))
make('processo-ficticio-providencias.pdf',[
 ['INFORMAÇÃO 001/2026. Assunto: habilitação do sistema Atlas.','O sistema Atlas será utilizado em uma simulação interna, sem dados reais.','Determina-se à NUTEC validar o acesso ao sistema Atlas até 12/11/2026 e registrar o resultado da validação neste processo.'],
 ['COMPETÊNCIAS. A SECAD deverá encaminhar o ofício de comunicação. O encaminhamento do ofício não é atribuição da NUTEC.','Não foi fixado prazo para a SECAD. O único prazo expresso neste documento é 12/11/2026, para a validação técnica pela NUTEC.']])
make('processo-ficticio-sem-providencias.pdf',[
 ['INFORMAÇÃO 002/2026. Assunto: arquivo administrativo.','O documento é encaminhado à NUTEC exclusivamente para ciência. Não há providência, resposta ou prazo atribuído à NUTEC.','A SECAD deverá arquivar o expediente. Essa tarefa cabe apenas à SECAD.']])
pages=[]
for n in range(8):
 paragraphs=['REGISTROS HISTÓRICOS - seção '+str(n+1)]
 paragraphs += [('Registro histórico '+str(n*12+i)+': este parágrafo descreve somente catalogação de documentos e organização de pastas. Não cria tarefa atual nem prazo. O registro serve para contextualizar a evolução do arquivo administrativo.') for i in range(10)]
 if n==5:paragraphs.insert(5,'DETERMINAÇÃO ATUAL: a NUTEC deverá renovar o certificado do portal Boreal até 20/12/2026 e juntar a evidência de renovação ao processo. A SECAD cuidará exclusivamente do arquivamento.')
 pages.append(paragraphs)
make('processo-ficticio-extenso.pdf',pages)
