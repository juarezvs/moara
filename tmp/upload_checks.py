from pathlib import Path
import subprocess
work=Path('/home/nutec/moara-auto-documents-20261027')
data=subprocess.check_output(['docker','run','--rm','--network','none','--entrypoint','cat','ai-webui:moara-auto-documents-20261027-r5','/app/build/static/moara/feedback.js'])
(work/'feedback.js').write_bytes(data)
subprocess.run(['docker','run','--rm','--network','none','--memory','2g','-v',str(work)+':/tests:ro','--entrypoint','python','ia-studio-renderer:1.0.0','/tests/test_upload_responses.py'],check=True)
