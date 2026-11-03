from pathlib import Path
for name in ['moara/web/src/app/workbench.html','moara/web/src/app/shell.ts','moara/web/src/app/login.ts']:
 p=Path(name);s=p.read_text(encoding='utf8').replace('href="/"','href="/?interface=anterior"')
 if name.endswith('login.ts'):
  s=s.replace("import { Router,RouterLink }", "import { Router,RouterLink,ActivatedRoute }")
  s=s.replace('Usar o chat institucional →','Autenticação pelo chat anterior →')
  s=s.replace("auth=inject(Auth);router=inject(Router);", "auth=inject(Auth);router=inject(Router);route=inject(ActivatedRoute);")
  s=s.replace("await this.router.navigateByUrl('/');", "const target=this.route.snapshot.queryParamMap.get('returnTo')||'/chat';await this.router.navigateByUrl(target.startsWith('/')&&!target.startsWith('//')&&!/^\\/login(?:[/?]|$)/.test(target)?target:'/chat');")
 p.write_text(s,encoding='utf8')
p=Path('moara/web/src/app/auth.ts');s=p.read_text(encoding='utf8').replace("router.createUrlTree(['/login'])","router.createUrlTree(['/login'],{queryParams:{returnTo:state.url}})")
p.write_text(s,encoding='utf8')
