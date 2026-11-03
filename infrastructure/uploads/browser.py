import pathlib,sys
root=pathlib.Path(__file__).resolve().parents[2]
source=(root/'infrastructure/site-entry/run_unified_browser.py').read_text()
source=source.replace('chat_background_ui_test.py','document_upload_ui_test.py').replace('chat-background-ui-stage.json','document-upload-ui-stage.json').replace('chat-background-ui-public.json','document-upload-ui-public.json')
source=source.replace("'proxy':proxy,","'proxy':proxy,'candidate_ip':json.loads((ROOT/'tmp/document-upload-proxy.json').read_text())['ip'] if stage else None,")
source=source.replace("'unified-dark.png']","'unified-dark.png','document-upload-progress.png']")
sys.argv.append('--chat-background')
exec(compile(source,'chat_stream_browser','exec'),{'__file__':str(root/'infrastructure/site-entry/run_unified_browser.py')})
