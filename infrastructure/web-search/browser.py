import pathlib,sys
root=pathlib.Path(__file__).resolve().parents[2]
source=(root/'infrastructure/site-entry/run_unified_browser.py').read_text().replace('chat_background_ui_test.py','public_web_ui_test.py').replace('chat-background-ui-stage.json','public-web-ui-stage.json').replace('chat-background-ui-public.json','public-web-ui-public.json')
source=source.replace("'proxy':proxy,","'proxy':proxy,'candidate_ip':json.loads((ROOT/'tmp/public-web-proxy.json').read_text())['ip'] if stage else None,")
sys.argv.append('--chat-background')
exec(compile(source,'public_web_browser','exec'),{'__file__':str(root/'infrastructure/site-entry/run_unified_browser.py')})
