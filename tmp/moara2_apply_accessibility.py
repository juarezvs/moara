from pathlib import Path
changes={
 'moara/web/src/app/shell.ts':[
  ("import { ErrorBox } from './ui';","import { ErrorBox } from './ui';\nimport { AccessibilitySettings } from './accessibility';"),
  ('RouterOutlet,A11yModule,ErrorBox]','RouterOutlet,A11yModule,ErrorBox,AccessibilitySettings]'),
  ('<div class="top-actions">','<div class="top-actions"><moara-accessibility/>')],
 'moara/web/src/app/login.ts':[
  ("import { ErrorBox } from './ui';","import { ErrorBox } from './ui';\nimport { AccessibilitySettings } from './accessibility';"),
  ('imports:[FormsModule,RouterLink,ErrorBox]','imports:[FormsModule,RouterLink,ErrorBox,AccessibilitySettings]'),
  ('<main class="login-scene">','<div class="login-accessibility"><moara-accessibility/></div><main class="login-scene">'),
  ('Sua IA local, segura e privada','Inteligência a serviço da Justiça.'),
  ('Inteligência artificial ao seu lado,<br>com total privacidade. Seus dados. No seu ambiente.','Apoio jurídico, administrativo, documental<br>e tecnológico para a Justiça Federal.'),
  ('Faça login no Moara AI','Entre na Moara'),
  ('Acesso à sua IA local, segura e privada.','Acesso institucional à inteligência jurídica e institucional.')],
 'moara/web/src/app/about.ts':[
  ("import { ErrorBox,Loading } from './ui';","import { ErrorBox,Loading } from './ui';\nimport { AccessibilitySettings } from './accessibility';"),
  ('imports:[RouterLink,ErrorBox,Loading]','imports:[RouterLink,ErrorBox,Loading,AccessibilitySettings]'),
  ('<div><a href="/">Abrir chat</a>','<div><moara-accessibility/><a href="/">Abrir chat</a>'),
  ('<section class="panel governance">','<section id="libras" class="panel section-gap"><h2>Apresentação pública em Libras</h2><p>Ative o VLibras para o manifesto público da Moara. O quadro de tradução fica isolado das conversas, documentos e sessões institucionais.</p><button type="button" class="secondary" (click)="libras.set(!libras())">{{libras()?\'Fechar apresentação em Libras\':\'Ativar VLibras para o manifesto público\'}}</button>@if(libras()){<iframe class="public-libras-frame" title="Manifesto público da Moara com VLibras" src="/moara/api/v1/accessibility/libras" sandbox="allow-scripts" referrerpolicy="no-referrer"></iframe>}</section><section class="panel governance">'),
  ("private api=inject(Api);identity=signal<IdentityDocument|null>(null);","private api=inject(Api);libras=signal(false);identity=signal<IdentityDocument|null>(null);")],
}
for name,pairs in changes.items():
 p=Path(name);text=p.read_text(encoding='utf-8')
 for old,new in pairs:
  if old not in text:raise RuntimeError('Expected source not found: '+name)
  text=text.replace(old,new)
 p.write_text(text,encoding='utf-8',newline='\n')
print('ACCESSIBILITY_UI_PREPARED')
