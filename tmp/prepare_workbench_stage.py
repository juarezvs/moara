from pathlib import Path
s=Path('infrastructure/moara2/stage.py').read_text()
s=s.replace("image='moara-core:2.0-foundation-20261030'","image='moara-core:workbench-20261030'")
s=s.replace("name='moara2-stage-'","name='moara-workbench-stage-'")
s=s.replace("'tmp/moara2-stage-name.txt'","'tmp/workbench-stage-name.txt'")
Path('infrastructure/workbench/stage.py').write_text(s)
