from pathlib import Path
s=Path('tmp/workbench-ui/run_production.py').read_text()
s=s.replace("WORK=ROOT/'tmp/workbench-ui'","WORK=ROOT/'tmp/chat-repair'")
s=s.replace('moara-workbench-ui-production1-20261030','moara-chat-repair-root-inspect4')
s=s.replace("WORK/'ui_test.py'","WORK/'ui_inspect.py'")
s=s.replace("['workbench-start.png','workbench-documents.png','workbench-editor.png','workbench-mobile.png','workbench-ui.json']","[]")
s=s.replace('workbench-ui.json','chat-repair-root-inspection.json')
Path('tmp/chat-repair/run_inspect.py').write_text(s)
