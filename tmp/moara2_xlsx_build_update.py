from pathlib import Path
p=Path('infrastructure/moara2/build.py');s=p.read_text();s=s.replace("'inference_status.py']","'inference_status.py','platform_documents.py','xlsx_documents.py']")
s=s.replace("'test_gpu_reranking.py']","'test_gpu_reranking.py','test_xlsx_documents.py']");p.write_text(s)
p=Path('moara/web/src/app/chat.ts');s=p.read_text(encoding='utf8').replace('.txt,.md,.csv,.pdf,.docx','.txt,.md,.csv,.pdf,.docx,.xlsx');p.write_text(s,encoding='utf8')
