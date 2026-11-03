import subprocess
q="""SELECT json_build_object(
'active_tutorial_accounts',(SELECT count(*) FROM moara.accounts WHERE name='Tutorial Moara - dados fictícios' AND active),
'remaining_tutorial_profile_grants',(SELECT count(*) FROM moara.profiles p JOIN moara.accounts a ON p.allowed_subjects ? a.subject WHERE a.name='Tutorial Moara - dados fictícios'),
'pending_tutorial_jobs',(SELECT count(*) FROM moara.platform_runs r JOIN moara.accounts a ON a.id=r.account_id WHERE a.name='Tutorial Moara - dados fictícios' AND r.status IN ('queued','running')))"""
print(subprocess.check_output(['docker','exec','ai-server-postgres-1','psql','-U','postgres','-d','ai','-Atc',q],text=True))
