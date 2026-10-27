from pathlib import Path
import ast
p=Path('/app/backend/open_webui/utils/middleware.py');s=p.read_text()
old="""    if file_context_enabled:
        try:
            form_data, flags = await chat_completion_files_handler(request, form_data, extra_params, user)"""
new="""    from open_webui.utils.automatic_documents import prepare_documents
    form_data, automatic_sources, automatically_read = await prepare_documents(request, form_data, user, extra_params)
    sources.extend(automatic_sources)
    if file_context_enabled and not automatically_read:
        try:
            form_data, flags = await chat_completion_files_handler(request, form_data, extra_params, user)"""
assert s.count(old)==1
s=s.replace(old,new);ast.parse(s);p.write_text(s)
# Expose the actual document-reading phase in the existing feedback widget.
p=Path('/app/build/static/moara/feedback.js');s=p.read_text()
old="          const type = message.data?.type, data = message.data?.data;"
new=old+"""
          if (type === 'status' && data?.action === 'moara_reading_documents') {
            if (generation) status(data.done ? 'Moara está preparando a resposta…' : 'Moara está lendo os documentos anexados…');
            return;
          }"""
assert s.count(old)==1;s=s.replace(old,new);p.write_text(s)
p=Path('/app/build/index.html');s=p.read_text().replace('feedback.js?v=20261027','feedback.js?v=20261027-documents');p.write_text(s)
print('Automatic authorized document context installed.')
