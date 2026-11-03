import subprocess
code="""from pathlib import Path
s=Path('/app/backend/open_webui/routers/auths.py').read_text()
at=s.find('async def signout')
if at<0:at=s.find('async def signout')
print(s[max(0,at-80):at+2200])
"""
print(subprocess.check_output(['docker','exec','-i','ai-server-webui-1','python','-'],input=code.encode()).decode())
