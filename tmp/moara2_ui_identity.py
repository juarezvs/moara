from pathlib import Path
changes={
 'moara/web/src/app/shell.ts':[
  ('<small>AI Local</small>','<small>Jurídica e Institucional</small>'),
  ('Moara AI <b>/</b> Plataforma local','Moara <b>/</b> Inteligência institucional'),
  ('Tecnologia com raízes, inovação com propósito.','Moara — Inteligência a serviço da Justiça.'),
  ("@if(auth.can('models.read')){","@if(auth.can('profiles.manage')){<a routerLink=\"/assistentes\" routerLinkActive=\"active\" (click)=\"open.set(false)\">Assistentes institucionais</a>}@if(auth.can('models.read')){")],
 'moara/web/src/app/about.ts':[
  ('Desenvolver.<br>Integrar. <em>Proteger.</em>','Inteligência<br>a serviço da <em>Justiça.</em>'),
  ('Moara AI · Inteligência local, segura e privada.','Moara — Inteligência a serviço da Justiça.'),
  ("</main><footer class=\"about-footer\">Moara — Inteligência a serviço da Justiça.</footer></div>`})", "</main><footer class=\"about-footer\">Moara — Inteligência a serviço da Justiça.</footer></div>`,styles:[`.declaration blockquote{white-space:pre-line;font-size:1.1rem;line-height:1.7;text-align:left}`]})")],
 'moara/web/src/app/chat.ts':[
  ('Desenvolva, estude e crie com sua IA local.','Pesquisa jurídica, apoio aos gabinetes e ao trabalho institucional.')],
 'moara/web/src/app/dashboard.ts':[
  ('Chat e desenvolvimento','Chat institucional e histórico'),
  ('Converse com roteamento automático, anexos, ferramentas e seu histórico no chat Moara.','Acesse o chat institucional existente e suas conversas anteriores.')],
}
for name,pairs in changes.items():
 p=Path(name);text=p.read_text(encoding='utf-8')
 for old,new in pairs:
  if old not in text:raise RuntimeError('Expected UI source not found: '+name)
  text=text.replace(old,new)
 p.write_text(text,encoding='utf-8',newline='\n')
print('MOARA2_UI_IDENTITY_PREPARED')
