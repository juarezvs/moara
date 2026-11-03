import pathlib,sys
root=pathlib.Path(__file__).resolve().parents[2]
source=(root/'infrastructure/site-entry/run_unified_browser.py').read_text().replace('chat_background_ui_test.py','project_files_ui_test.py').replace('chat-background-ui-stage.json','project-files-ui-stage.json').replace('chat-background-ui-public.json','project-files-ui-public.json')
sys.argv.append('--chat-background')
exec(compile(source,'project_files_browser','exec'),{'__file__':str(root/'infrastructure/site-entry/run_unified_browser.py')})
