from pathlib import Path
p=Path('tmp/tutorial/remote.py');s=p.read_text(encoding='utf-8')
needle="try:\n login=request('auth/login'"
insert="""def tutorial_profile_access(enable):
 subject='local:'+identifier
 if enable:
  q="UPDATE moara.profiles SET allowed_subjects=allowed_subjects || to_jsonb('"+subject+"'::text) WHERE id='fast' AND NOT allowed_subjects ? '"+subject+"';"
 else:q="UPDATE moara.profiles SET allowed_subjects=allowed_subjects - '"+subject+"' WHERE id='fast';"
 q+="INSERT INTO moara.audit(actor_subject,action,resource,status) VALUES('system:tutorial','tutorial.profile."+('grant' if enable else 'revoke')+"','"+identifier+"','ok');"
 subprocess.run(['docker','exec','ai-server-postgres-1','psql','-U','postgres','-d','ai','-v','ON_ERROR_STOP=1','-c',q],check=True,capture_output=True)
try:
 tutorial_profile_access(True)
 login=request('auth/login'"""
assert needle in s;s=s.replace(needle,insert)
s=s.replace("finally:\n request('admin/accounts/'","finally:\n tutorial_profile_access(False)\n request('admin/accounts/'")
p.write_text(s,encoding='utf-8')
