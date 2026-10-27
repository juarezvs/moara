"""Regression for a duty in the middle of an eight-page synthetic PDF."""
import importlib.util
from pathlib import Path
from pypdf import PdfReader

def main():
    root=Path(__file__).resolve().parent
    spec=importlib.util.spec_from_file_location('automatic_documents',root/'automatic_documents.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    text=' '.join(page.extract_text() or '' for page in PdfReader(root/'fixtures/processo-ficticio-extenso.pdf').pages)
    query='Sou da NUTEC. Preciso fazer algo relacionado a este processo? Informe a providência e o prazo, se houver.'
    for budget in [1500,4000,9000]:
        excerpt,full=module.select_content(text,query,budget)
        assert '20/12/2026' in excerpt[:1000], 'The actionable passage must precede repetitive background'
        assert len(excerpt.encode())<=budget and not full
        print({'budget':budget,'selected_bytes':len(excerpt.encode()),'action_in_first_1000_characters':True})
if __name__=='__main__':main()
