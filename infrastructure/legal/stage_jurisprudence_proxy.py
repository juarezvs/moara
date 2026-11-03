import pathlib,json
root=pathlib.Path(__file__).resolve().parents[2]
stage=json.loads((root/'tmp/jurisprudence-stage.json').read_text())
(root/'tmp/unified-core-name.txt').write_text(stage['core'])
source=root/'infrastructure/site-entry/prepare_network_login_proxy.py'
exec(compile(source.read_text(),str(source),'exec'),{'__file__':str(source)})
