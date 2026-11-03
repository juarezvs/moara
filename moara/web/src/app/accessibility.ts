import {Component,HostListener,Injectable,inject,signal} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {A11yModule} from '@angular/cdk/a11y';

@Injectable({providedIn:'root'})
export class AccessibilityPrefs {
  scale=signal(100);contrast=signal(false);dyslexic=signal(false);
  initialize(){try{const value=JSON.parse(localStorage.getItem('moara.accessibility.v1')||'{}');this.scale.set([100,115,130,150].includes(value.scale)?value.scale:100);this.contrast.set(value.contrast===true);this.dyslexic.set(value.dyslexic===true);}catch{}this.apply();}
  apply(){document.documentElement.style.fontSize=(14*this.scale()/100)+'px';document.documentElement.classList.toggle('a11y-large-text',this.scale()!==100);document.documentElement.classList.toggle('a11y-high-contrast',this.contrast());document.documentElement.classList.toggle('a11y-dyslexic',this.dyslexic());try{localStorage.setItem('moara.accessibility.v1',JSON.stringify({scale:this.scale(),contrast:this.contrast(),dyslexic:this.dyslexic()}));}catch{}}
  reset(){this.scale.set(100);this.contrast.set(false);this.dyslexic.set(false);this.apply();}
}

@Component({selector:'moara-accessibility',standalone:true,imports:[FormsModule,A11yModule],template:`
<button type="button" class="secondary a11y-trigger" aria-label="Preferências de acessibilidade" aria-haspopup="dialog" [attr.aria-expanded]="open()" (click)="toggle()">Aa<span> Acessibilidade</span></button>
@if(open()){<button type="button" class="a11y-backdrop" tabindex="-1" aria-label="Fechar preferências de acessibilidade" (click)="close()"></button><section class="a11y-panel panel" role="dialog" aria-modal="true" aria-labelledby="a11y-title" [cdkTrapFocus]="true" [cdkTrapFocusAutoCapture]="true"><div class="section-heading"><h2 id="a11y-title">Preferências de leitura</h2><button type="button" class="icon-button" aria-label="Fechar acessibilidade" (click)="close()">×</button></div>
<label>Tamanho do texto<select [ngModel]="prefs.scale()" (ngModelChange)="prefs.scale.set($event);prefs.apply()"><option [ngValue]="100">100%</option><option [ngValue]="115">115%</option><option [ngValue]="130">130%</option><option [ngValue]="150">150%</option></select></label>
<label class="check-label"><input type="checkbox" [ngModel]="prefs.contrast()" (ngModelChange)="prefs.contrast.set($event);prefs.apply()">Alto contraste</label>
<label class="check-label"><input type="checkbox" [ngModel]="prefs.dyslexic()" (ngModelChange)="prefs.dyslexic.set($event);prefs.apply()">Fonte OpenDyslexic</label>
<p class="small muted">As preferências ficam neste navegador. A fonte é servida pela própria Moara.</p>
<button type="button" class="text-button" (click)="prefs.reset()">Restaurar preferências</button>
<p><a href="/moara/sobre#libras" (click)="close()">Libras na apresentação pública</a></p></section>}`,styles:[`
:host{display:inline-block}.a11y-trigger{white-space:nowrap}.a11y-backdrop{position:fixed;inset:0;z-index:2990;background:#0005;border:0;border-radius:0}.a11y-panel{position:fixed;z-index:3000;right:16px;top:76px;width:min(360px,calc(100vw - 32px));max-height:calc(100vh - 100px);overflow:auto;padding:20px!important;display:grid;gap:16px;text-align:left;color:var(--text);background:var(--panel)}.a11y-panel h2{font-size:1.1rem}.a11y-panel p{margin:0}.a11y-panel label{font-size:.95rem}@media(max-width:760px){.a11y-trigger span{display:none}.a11y-trigger{padding:8px 12px}}`]})
export class AccessibilitySettings {
  prefs=inject(AccessibilityPrefs);open=signal(false);trigger:HTMLElement|null=null;
  toggle(){if(this.open())this.close();else{this.trigger=document.activeElement as HTMLElement;this.open.set(true);}}
  close(){this.open.set(false);this.trigger?.focus();}
  @HostListener('document:keydown.escape') onEscape(){if(this.open())this.close();}
}
