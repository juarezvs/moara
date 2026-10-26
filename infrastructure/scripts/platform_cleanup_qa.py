"""Remove only explicitly named, label-verified disposable test containers."""
import json,subprocess
expected={'moara-platform-browser':('moara.test','platform-ui'),'moara-platform-proxy':('moara.test','platform-ui'),
 'moara-platform-qa-api':('moara.environment','staging'),'moara-platform-qa-redis':('moara.environment','staging'),
 'moara-platform-qa-pg':('moara.environment','staging'),'moara-directory-test':('moara.test','directory'),
 'moara-ldap-alpha':('moara.test','directory'),'moara-ldap-beta':('moara.test','directory')}
removed=[]
for name,(key,value) in expected.items():
 p=subprocess.run(['docker','inspect',name],capture_output=True)
 if p.returncode:continue
 obj=json.loads(p.stdout)[0]
 if obj['Config'].get('Labels',{}).get(key)!=value:raise RuntimeError('unowned test fixture')
 # -v removes anonymous volumes belonging to this disposable fixture, never named production volumes.
 subprocess.run(['docker','rm','-f','-v',name],check=True,capture_output=True);removed.append(name)
for name,key,value in [('moara-platform-qa-isolated','moara.environment','staging'),('moara-directory-qa','moara.test','directory')]:
 p=subprocess.run(['docker','network','inspect',name],capture_output=True)
 if p.returncode:continue
 obj=json.loads(p.stdout)[0]
 if obj.get('Labels',{}).get(key)!=value or obj.get('Containers'):raise RuntimeError('network not disposable')
 subprocess.run(['docker','network','rm',name],check=True,capture_output=True)
print(json.dumps({'removed_owned_fixtures':removed,'production_resources_removed':False}))
