import subprocess
q="""SELECT p.id,p.enabled,p.public,p.settings->>'auto_eligible',m.provider,m.tag,m.enabled,m.capabilities->>'completion',b.ready,b.legacy_alias
FROM moara.profiles p LEFT JOIN moara.profile_models pm ON pm.profile_id=p.id LEFT JOIN moara.models m ON m.id=pm.model_id LEFT JOIN moara.execution_bindings b ON b.model_id=m.id ORDER BY p.id"""
print(subprocess.check_output(['docker','exec','ai-server-postgres-1','psql','-U','postgres','-d','ai','-Atc',q],text=True))
