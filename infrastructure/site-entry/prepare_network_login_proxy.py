import pathlib
root=pathlib.Path(__file__).resolve().parents[2]
source=(root/'infrastructure/site-entry/prepare_unified_proxy.py').read_text()
start=source.index("subprocess.run(['docker','exec'")
prefix="import pathlib,subprocess,json,hashlib\nroot=pathlib.Path(__file__).resolve().parents[2]\nfolder=root/'tmp/network-login-proxy';folder.mkdir(exist_ok=True)\ncandidate=(root/'infrastructure/caddy/Caddyfile').read_text()\n"
exec(compile(prefix+source[start:],'network_login_proxy','exec'),{'__file__':__file__})
