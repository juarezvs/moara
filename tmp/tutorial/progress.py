import subprocess
q="SELECT r.kind,r.status,coalesce(r.error_code,''),r.attempts,round(extract(epoch from now()-r.created_at)) FROM moara.platform_runs r JOIN moara.accounts a ON a.id=r.account_id WHERE a.name='Tutorial Moara - dados fictícios' ORDER BY r.created_at DESC LIMIT 6"
print(subprocess.check_output(['docker','exec','ai-server-postgres-1','psql','-U','postgres','-d','ai','-Atc',q],text=True))
