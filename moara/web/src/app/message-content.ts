import {Component,ChangeDetectionStrategy,computed,input,signal,HostListener,ElementRef,inject,OnDestroy} from '@angular/core';
import {marked} from 'marked';
import DOMPurify from 'dompurify';
import hljs from 'highlight.js/lib/core';
import javascript from 'highlight.js/lib/languages/javascript';
import typescript from 'highlight.js/lib/languages/typescript';
import python from 'highlight.js/lib/languages/python';
import json from 'highlight.js/lib/languages/json';
import bash from 'highlight.js/lib/languages/bash';
import xml from 'highlight.js/lib/languages/xml';
import css from 'highlight.js/lib/languages/css';
import sql from 'highlight.js/lib/languages/sql';
for(const [name,language] of Object.entries({javascript,typescript,python,json,bash,xml,css,sql}))hljs.registerLanguage(name,language);
const codeCache=new Map<string,string>();
let cacheCharacters=0;

const OFFICIAL=new Set(['legis.senado.leg.br','normas.leg.br','www.lexml.gov.br','www.planalto.gov.br','www.in.gov.br','portal.stf.jus.br','jurisprudencia.stf.jus.br','dadosabertos.camara.leg.br','www.gov.br','www.camara.leg.br','www2.camara.leg.br','scon.stj.jus.br','www.stj.jus.br','atos.cnj.jus.br','www.cnj.jus.br','www.cjf.jus.br']);
export function officialSource(value:string):URL|null {
 try {const u=new URL(value);return u.protocol==='https:'&&!u.username&&!u.password&&(!u.port||u.port==='443')&&OFFICIAL.has(u.hostname)?u:null;}catch{return null;}
}

export function messageHtml(content:string,streaming=false):string {
 const root=document.createElement('div');root.innerHTML=DOMPurify.sanitize(marked.parse(content,{async:false}) as string,{FORBID_TAGS:['form','input','button','iframe','object','style'],FORBID_ATTR:['style']});
 // These classes belong to application controls, never to message HTML.
 for(const element of root.querySelectorAll('[class]'))for(const name of ['moara-source','source-hint','source-hint-heading','moara-typing-cursor'])element.classList.remove(name);
 const references=new Map<string,string>();
 for(const p of root.querySelectorAll('p,li')) {
  const link=Array.from(p.querySelectorAll('a[href]')).find(a=>officialSource(a.getAttribute('href')||''));
  const id=p.textContent?.match(/^\s*\[((?:L|J)\d+\.\d+)\]/)?.[1];
  if(id&&link)references.set(id,link.getAttribute('href')!);
 }
 const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);const nodes:Text[]=[];
 while(walker.nextNode())nodes.push(walker.currentNode as Text);
 for(const node of nodes){
  if(node.parentElement?.closest('a,pre,code'))continue;
  const regex=/\[((?:L|J)\d+\.\d+)\]/g;let match:RegExpExecArray|null;let offset=0;const fragment=document.createDocumentFragment();let changed=false;
  while((match=regex.exec(node.data))){const url=references.get(match[1]);if(!url)continue;fragment.append(node.data.slice(offset,match.index));const a=document.createElement('a');a.href=url;a.textContent=match[0];fragment.append(a);offset=match.index+match[0].length;changed=true;}
  if(changed){fragment.append(node.data.slice(offset));node.replaceWith(fragment);}
 }
 for(const a of root.querySelectorAll<HTMLAnchorElement>('a[href]')) {
  const url=officialSource(a.getAttribute('href')||'');
  if(!url)continue;
  a.classList.add('moara-source');a.target='_blank';a.rel='noopener noreferrer';
  a.setAttribute('aria-label',`Fonte externa: ${a.textContent}, ${url.hostname}`);
  a.setAttribute('aria-haspopup','dialog');
 }
 for(const code of root.querySelectorAll<HTMLElement>('pre>code')){
  if(streaming&&code.parentElement===root.lastElementChild)continue;
  const language=Array.from(code.classList).find(c=>c.startsWith('language-'))?.slice(9);
  const text=code.textContent||'';
  if(!language||!hljs.getLanguage(language)||text.length>50000)continue;
  const key=language+'\0'+text;let highlighted=codeCache.get(key);
  if(highlighted===undefined){
   highlighted=DOMPurify.sanitize(hljs.highlight(text,{language,ignoreIllegals:true}).value);
   codeCache.set(key,highlighted);cacheCharacters+=key.length;
   while(codeCache.size>64||cacheCharacters>200000){const oldest=codeCache.keys().next().value!;cacheCharacters-=oldest.length;codeCache.delete(oldest);}
  }
  code.innerHTML=highlighted;code.classList.add('hljs');
 }
 if(streaming){
  const cursor=document.createElement('span');cursor.className='moara-typing-cursor';cursor.setAttribute('aria-hidden','true');
  const last=root.lastElementChild;
  const tail=last?.matches('p,h1,h2,h3,h4,h5,h6')?last:last?.matches('ul,ol')?last.querySelector('li:last-child'):last?.matches('pre')?last.querySelector('code'):null;
  (tail||root).append(cursor);
 }
 return root.innerHTML;
}

@Component({selector:'moara-message-content',changeDetection:ChangeDetectionStrategy.OnPush,standalone:true,template:`
 <div class="markdown" [innerHTML]="html()" (mouseover)="hover($event)" (mouseout)="leave($event)" (focusin)="hover($event)" (focusout)="leave($event)" (click)="activate($event)"></div>
 @if(source();as s){<aside class="source-hint" popover="manual" role="dialog" aria-label="Fonte externa" [style.left.px]="s.left" [style.top.px]="s.top" [style.width.px]="s.width" (mouseenter)="cancelClose()" (mouseleave)="scheduleClose()" (focusin)="cancelClose()" (focusout)="leave($event)">
 <div class="source-hint-heading"><span>FONTE EXTERNA</span><button type="button" aria-label="Fechar fonte" (click)="close(true)">×</button></div>
 <strong>{{s.label}}</strong><small>{{s.host}}</small><p>Consulte o documento no portal de origem.</p>
 <a [href]="s.url" target="_blank" rel="noopener noreferrer">Abrir fonte oficial <span aria-hidden="true">↗</span></a>
 </aside>}`,styleUrl:'./message-content.css'})
export class MessageContent implements OnDestroy {
 content=input('');streaming=input(false);html=computed(()=>messageHtml(this.content(),this.streaming()));host:ElementRef<HTMLElement>=inject(ElementRef);
 source=signal<{url:string;host:string;label:string;left:number;top:number;width:number}|null>(null);
 private anchor:HTMLAnchorElement|null=null;private timer:ReturnType<typeof setTimeout>|null=null;private suppressFocus=false;
 cancelClose(){if(this.timer)clearTimeout(this.timer);this.timer=null;}
 scheduleClose(){this.cancelClose();this.timer=setTimeout(()=>{const panel=this.host.nativeElement.querySelector('.source-hint');if(panel?.contains(document.activeElement)||this.anchor===document.activeElement)return;this.close();},220);}
 hover(event:Event){if(this.suppressFocus&&event.type==='focusin')return;const anchor=(event.target as Element)?.closest<HTMLAnchorElement>('a.moara-source');if(!anchor)return;this.show(anchor);}
 private show(anchor:HTMLAnchorElement){const url=officialSource(anchor.href);if(!url)return;this.cancelClose();if(this.anchor!==anchor)this.anchor?.setAttribute('aria-expanded','false');this.anchor=anchor;anchor.setAttribute('aria-expanded','true');const r=anchor.getBoundingClientRect();const width=Math.min(340,window.innerWidth-24);this.source.set({url:url.href,host:url.hostname,label:anchor.textContent?.replace(/^\[|\]$/g,'').trim()||'Documento oficial',left:Math.max(12,Math.min(r.left,window.innerWidth-width-12)),top:Math.max(12,r.bottom+205<window.innerHeight?r.bottom+6:r.top-205),width});setTimeout(()=>{const popup=this.host.nativeElement.querySelector<HTMLElement>('.source-hint');if(!popup)return;popup.showPopover?.();const bounds=popup.getBoundingClientRect();const current=this.source();if(current&&bounds.bottom>window.innerHeight-12)this.source.set({...current,top:Math.max(12,window.innerHeight-bounds.height-12)});});}
 leave(event:Event){const next=(event as FocusEvent|MouseEvent).relatedTarget as Node|null;if(next instanceof Element&&next.closest('.source-hint,a.moara-source')&&this.host.nativeElement.contains(next)){this.cancelClose();return;}this.scheduleClose();}
 activate(event:MouseEvent){const anchor=(event.target as Element)?.closest<HTMLAnchorElement>('a.moara-source');if(!anchor||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;event.preventDefault();this.show(anchor);setTimeout(()=>this.host.nativeElement.querySelector<HTMLAnchorElement>('.source-hint a')?.focus());}
 close(restore=false){this.cancelClose();const anchor=this.anchor;anchor?.setAttribute('aria-expanded','false');this.source.set(null);this.anchor=null;if(restore&&anchor){this.suppressFocus=true;anchor.focus();this.suppressFocus=false;}}
 @HostListener('document:keydown.escape') escape(){if(this.source())this.close(true);}
 @HostListener('document:pointerdown',['$event']) outside(event:PointerEvent){if(!this.host.nativeElement.contains(event.target as Node))this.close();}
 @HostListener('window:resize') resize(){this.close();}
 @HostListener('document:scroll') scroll(){this.close();}
 ngOnDestroy(){this.cancelClose();}
}
