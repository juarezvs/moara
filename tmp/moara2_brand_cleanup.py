from pathlib import Path
for name in ['about.ts','login.ts']:
    p=Path('moara/web/src/app')/name;s=p.read_text(encoding='utf8')
    s=s.replace('Moara <small>AI</small>','Moara').replace('Logo Moara AI','Logo Moara')
    if name=='about.ts':s=s.replace('<a href="/">Abrir chat</a>','<a routerLink="/chat">Conversar com a Moara</a>')
    p.write_text(s,encoding='utf8')
