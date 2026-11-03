import pathlib,sys
root=pathlib.Path(__file__).resolve().parents[2]
source=(root/'infrastructure/site-entry/run_unified_browser.py').read_text().replace('citations_ui_test.py','chat_stream_citations_ui_test.py').replace('citations-ui-stage.json','chat-stream-citations-stage.json').replace('citations-ui-public.json','chat-stream-citations-public.json')
sys.argv.append('--citations')
exec(compile(source,'chat_stream_citations','exec'),{'__file__':str(root/'infrastructure/site-entry/run_unified_browser.py')})
