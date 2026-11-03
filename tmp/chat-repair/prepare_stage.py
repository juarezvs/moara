from pathlib import Path
s=Path('infrastructure/moara2/stage.py').read_text().replace("image='moara-core:2.0-foundation-20261030'","image='moara-core:chat-intent-20261030'")
s=s.replace("name='moara2-stage-'","name='moara-chat-intent-stage-'").replace("'tmp/moara2-stage-name.txt'","'tmp/chat-intent-stage-name.txt'")
Path('infrastructure/chat-repair/stage.py').write_text(s)
