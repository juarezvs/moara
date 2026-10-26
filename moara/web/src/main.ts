import { Component,inject,provideAppInitializer } from '@angular/core';
import { bootstrapApplication } from '@angular/platform-browser';
import { provideRouter,RouterOutlet } from '@angular/router';
import { Auth,signedIn,allowed } from './app/auth';
import { Login } from './app/login';
import { Shell } from './app/shell';
import { About } from './app/about';
import { Dashboard } from './app/dashboard';
import { InstitutionalIdentity } from './app/identity';
import { PasswordPage } from './app/password';
import { ChatPage } from './app/chat';
import { CatalogPage } from './app/catalog';
import { AccessPage } from './app/access';
import { PlatformPage } from './app/platform';
import { SourcesPage } from './app/sources';

@Component({selector:'moara-root',standalone:true,imports:[RouterOutlet],template:'<router-outlet/>'})
class App {}
bootstrapApplication(App,{providers:[provideAppInitializer(()=>inject(Auth).initialize()),provideRouter([
  {path:'login',component:Login},{path:'sobre',component:About},{path:'senha',component:PasswordPage,canActivate:[signedIn]},
  {path:'',component:Shell,canActivate:[signedIn],children:[{path:'',component:Dashboard},
    {path:'espaco',component:PlatformPage,canActivate:[allowed('workspace.use')]},
    {path:'chat',component:ChatPage,canActivate:[allowed('chat.use')]},
    {path:'modelos',component:CatalogPage,canActivate:[allowed('models.read')]},
    {path:'acessos',component:AccessPage,canActivate:[allowed('users.read')]},
    {path:'fontes',component:SourcesPage,canActivate:[allowed('connectors.read')]},
    {path:'identidade',component:InstitutionalIdentity,canActivate:[allowed('identity.draft')]}]},
  {path:'**',redirectTo:''}
])]}).catch(()=>{document.body.textContent='Não foi possível carregar a Moara AI. Atualize a página e tente novamente.';});
