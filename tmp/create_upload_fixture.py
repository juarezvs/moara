from io import BytesIO
from pathlib import Path
from reportlab.pdfgen import canvas
from pypdf import PdfReader,PdfWriter
root=Path('tmp/upload-json');root.mkdir(parents=True,exist_ok=True)
buf=BytesIO();c=canvas.Canvas(buf)
for i in range(176):
 c.drawString(50,790,'DOCUMENTO INTEGRALMENTE FICTICIO PARA TESTE DE ENVIO')
 c.drawString(50,760,'Pagina '+str(i+1)+'. O procedimento Alfa tem prazo de cinco dias uteis.')
 c.showPage()
c.save();base=buf.getvalue();target=11868084
def make(n):
 w=PdfWriter();w.clone_document_from_reader(PdfReader(BytesIO(base)))
 w.add_attachment('conteudo-ficticio-de-volume.txt',b'x'*n)
 out=BytesIO();w.write(out);return out.getvalue()
n=target-len(base)-1200
for _ in range(5):
 data=make(n)
 if len(data)==target:break
 n+=target-len(data)
assert len(data)==target
path=root/'pdf-ficticio-176-paginas.pdf';path.write_bytes(data)
reader=PdfReader(path);assert len(reader.pages)==176 and 'FICTICIO' in reader.pages[0].extract_text()
print({'fixture_bytes':len(data),'pages':len(reader.pages)})
