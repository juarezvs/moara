import pathlib
root=pathlib.Path(__file__).resolve().parents[2]
source=(root/'infrastructure/chat-stream/prepare_proxy.py').read_text().replace('tmp/chat-stream-stage.json','tmp/public-web-stage.json').replace('tmp/chat-stream-tls','tmp/public-web-tls').replace('tmp/chat-stream-proxy.json','tmp/public-web-proxy.json').replace('moara-chat-stream-tls-','moara-public-web-tls-')
exec(compile(source,'public_web_proxy','exec'),{'__file__':str(root/'infrastructure/chat-stream/prepare_proxy.py')})
