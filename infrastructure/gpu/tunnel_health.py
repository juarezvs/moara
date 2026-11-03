import json
import urllib.request

with urllib.request.urlopen('http://127.0.0.1:11434/api/ps', timeout=3) as response:
    rows = json.load(response).get('models', [])
assert any(row.get('name') == 'moara-main-gpu:latest' and row.get('size', 0) > 0
           and row.get('size_vram') == row['size'] for row in rows)
