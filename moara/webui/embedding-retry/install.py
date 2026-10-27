"""Apply only reviewed, fail-closed integration points to the pinned WebUI image."""
from pathlib import Path
import ast
root=Path('/app/backend/open_webui')
def replace_once(source,old,new):
    assert source.count(old)==1, 'Upstream integration point changed: '+old[:90]
    return source.replace(old,new)
p=root/'retrieval/utils.py';s=p.read_text()
s=replace_once(s,'async def agenerate_openai_batch_embeddings(', 'from open_webui.retrieval.moara_file_progress import with_embedding_retry as _moara_embedding_retry\n\n@_moara_embedding_retry\nasync def agenerate_openai_batch_embeddings(')
ast.parse(s);p.write_text(s)
p=root/'routers/retrieval.py';s=p.read_text()
old="""        future = asyncio.run_coroutine_threadsafe(
            embedding_function(
                list(map(lambda x: x.replace('\\n', ' '), texts)),
                prefix=RAG_EMBEDDING_CONTENT_PREFIX,
                user=user,
            ),
            request.app.state.main_loop,
        )"""
new="""        from open_webui.retrieval.moara_file_progress import embed_with_progress
        future = asyncio.run_coroutine_threadsafe(
            embed_with_progress(
                embedding_function,
                list(map(lambda x: x.replace('\\n', ' '), texts)),
                file_id=(metadata or {}).get('file_id'),
                batch_size=config['rag.embedding_batch_size'],
                prefix=RAG_EMBEDDING_CONTENT_PREFIX,
                user=user,
            ),
            request.app.state.main_loop,
        )"""
s=replace_once(s,old,new)
old="""    if file:
        try:
            collection_name = form_data.collection_name"""
new="""    if file:
        try:
            from open_webui.retrieval.moara_file_progress import publish_progress
            await publish_progress(file.id, 'extracting')
            collection_name = form_data.collection_name"""
s=replace_once(s,old,new);ast.parse(s);p.write_text(s)
p=root/'routers/files.py';s=p.read_text()
s=replace_once(s,"return {'status': file.data.get('status', 'pending')}","return {'status': file.data.get('status', 'pending'), 'progress': file.data.get('moara_progress')}")
ast.parse(s);p.write_text(s)
p=root/'tools/builtin.py';s=p.read_text()
s=s.replace('Get the content of a file by its ID. Supports pagination for large files.', 'Read one short excerpt of an authorized file. For questions about an attached document, prefer query_chat_files to retrieve relevant passages. Use offset pagination only when necessary; never assume an excerpt is the whole document.')
# Enforce the same character cap for line-based reads; do not allow a long line to bypass it.
old="            sliced = '\\n'.join(f'{s + i + 1}: {line}' for i, line in enumerate(selected))"
assert s.count(old)==2
s=s.replace(old,old+"\n            if len(sliced) > VIEW_FILE_MAX_CHARS:\n                sliced = sliced[:VIEW_FILE_MAX_CHARS]\n                is_truncated_by_chars = True\n            else:\n                is_truncated_by_chars = False")
s=s.replace("            is_truncated = e < total_lines","            is_truncated = e < total_lines or is_truncated_by_chars")
# Tell the model explicitly when a line excerpt had to be bounded.
needle="            if is_truncated:\n                result['truncated'] = True\n                result['next_start_line'] = e + 1"
assert s.count(needle)==2
s=s.replace(needle,"            if is_truncated:\n                result['truncated'] = True\n                if is_truncated_by_chars:\n                    result['pagination_hint'] = 'Trecho limitado. Use query_chat_files para localizar passagens relevantes, ou leitura por offset/max_chars.'\n                else:\n                    result['next_start_line'] = e + 1")
ast.parse(s);p.write_text(s)
# Frontend extension is additive and loads before the application starts.
p=Path('/app/build/index.html');s=p.read_text()
assert 'moara-feedback.js' not in s
s=replace_once(s,'</head>','<link rel="stylesheet" href="/static/moara/feedback.css?v=20261027"><script src="/static/moara/feedback.js?v=20261027"></script></head>')
p.write_text(s)
print('Moara upload progress, bounded retries and bounded file excerpts installed.')
