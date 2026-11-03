import json
from pathlib import Path
r=json.loads(Path('/home/nutec/ai-server/docs/runtime/embedding-upload-validation-20261027.json').read_text())
print(json.dumps({k:r.get(k) for k in ['processing_status','elapsed_seconds','passed']}))
print(json.dumps((r.get('progress_samples') or [{}])[-1]))
