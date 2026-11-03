import importlib.util
from pathlib import Path
from pypdf import PdfReader
spec=importlib.util.spec_from_file_location('a',Path('/tests/automatic_documents.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
text=' '.join(p.extract_text() or '' for p in PdfReader('/tests/fixtures/processo-ficticio-extenso.pdf').pages)
query='Sou da NUTEC. Preciso fazer algo relacionado a este processo? Informe a providência e o prazo, se houver.'
for budget in [1500,4000,9000]:
 excerpt,full=m.select_content(text,query,budget)
 assert '20/12/2026' in excerpt[:1000],(budget,excerpt[:1000])
 assert len(excerpt.encode())<=budget and not full
 print({'budget':budget,'selected_bytes':len(excerpt.encode()),'required_action_in_first_1000_characters':True})
