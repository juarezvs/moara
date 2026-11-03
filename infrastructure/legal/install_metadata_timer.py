"""Install an unattended user timer after validation of the public application."""
import pathlib,json,subprocess
root=pathlib.Path(__file__).resolve().parents[2]
image=subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip()
for name in ['legal-metadata-public.json','legal-metadata-ui-public.json','legal-metadata-chat-public.json']:
 r=json.loads((root/'docs/runtime'/name).read_text());assert all(r['checks'].values()) and r['tested_image_id']==image
assert subprocess.check_output(['loginctl','show-user','nutec','-p','Linger','--value'],text=True).strip()=='yes','User services must survive logout/reboot'
units=pathlib.Path.home()/'.config/systemd/user';units.mkdir(parents=True,exist_ok=True)
service='''[Unit]
Description=Moara official normative metadata collector
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
WorkingDirectory=%s
ExecStart=/usr/bin/python3 %s/infrastructure/legal/harvest_legal_metadata.py 30
TimeoutStartSec=25min
UMask=0077
'''%(root,root)
timer='''[Unit]
Description=Refresh Moara public legal metadata every six hours

[Timer]
OnCalendar=*-*-* 00,06,12,18:35:00 UTC
RandomizedDelaySec=3min
Persistent=true
Unit=moara-legal-metadata.service

[Install]
WantedBy=timers.target
'''
for name,body in [('moara-legal-metadata.service',service),('moara-legal-metadata.timer',timer)]:
 p=units/name
 if p.exists() and p.read_text()!=body:raise RuntimeError('Refusing to overwrite an unrelated existing unit')
 p.write_text(body)
subprocess.run(['systemctl','--user','daemon-reload'],check=True)
subprocess.run(['systemctl','--user','enable','--now','moara-legal-metadata.timer'],check=True)
subprocess.run(['systemctl','--user','is-active','--quiet','moara-legal-metadata.timer'],check=True)
print(json.dumps({'timer_active':True,'interval_hours':6,'lexml_batch':30,'persistent_across_logout_and_reboot':True}))
