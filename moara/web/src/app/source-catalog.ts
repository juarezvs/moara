import { Component,Input,Output,EventEmitter,OnChanges,SimpleChanges,signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Source,Policy,CatalogObject,CatalogRelationship } from './source-types';

@Component({selector:'moara-source-catalog',standalone:true,imports:[FormsModule],template:`
<div class="section-heading"><div><h3>Catálogo descoberto e acesso da IA</h3><p class="muted">{{entries().length}} objetos descobertos · {{approvedCount()}} selecionados · {{relationships().length}} relacionamentos verificados. Escolha as tabelas e os campos que a IA pode consultar.</p></div></div>
<label class="section-gap">Buscar tabela ou campo<input name="catalogSearch" [(ngModel)]="search" placeholder="FUNCIONARIO, SERV_PESSOAL, CARGO, LOTACAO…"></label>
<p class="notice-box">A seleção abaixo só passa a valer ao salvar. Os campos sensíveis seguem a política da fonte. A IA não recebe senha, endereço de conexão ou dados fora deste escopo.</p>
<div class="table-wrap"><table><thead><tr><th>Disponível à IA</th><th>Objeto</th><th>Tipo</th><th>Campos</th><th></th></tr></thead><tbody>
@for(entry of filtered();track entry.name){<tr><td><input type="checkbox" [attr.aria-label]="'Autorizar '+entry.name" [checked]="!!selected[entry.name]" (change)="toggle(entry.name,entry.item,$any($event.target).checked)" [disabled]="!editable||busy"></td><td><strong>{{entry.name}}</strong></td><td>{{entry.item.type}}</td><td>{{selected[entry.name]?.length||0}} / {{entry.item.fields.length}}</td><td><button class="text-button" (click)="editing.set(editing()===entry.name?'':entry.name)">Escolher campos</button></td></tr>
@if(editing()===entry.name){<tr><td colspan="5"><div class="field-options">@for(field of entry.item.fields;track field.name){<label class="check-label"><input type="checkbox" [checked]="selected[entry.name]?.includes(field.name)||false" [disabled]="!editable||busy||!permitted(field)" (change)="toggleField(entry.name,field.name,$any($event.target).checked)">{{field.name}} <small>{{field.type}}</small>@if(field.sensitive){<span class="badge warning">Sensível</span>}</label>}</div></td></tr>}
}@empty{<tr><td colspan="5">Nenhum objeto encontrado. Use Atualizar catálogo na visão geral caso a descoberta ainda não tenha sido executada.</td></tr>}
</tbody></table></div>
@if(editable){<button class="primary section-gap" (click)="save()" [disabled]="busy">{{busy?'Salvando…':'Salvar acesso da IA a tabelas e campos'}}</button>}
<h3 class="section-gap">Relacionamentos entre tabelas</h3><p class="muted small">Chaves declaradas na origem. Em uma chave composta, todas as colunas do vínculo devem participar da junção. A descoberta não libera novas tabelas ou campos para consulta.</p>
<div class="table-wrap"><table><thead><tr><th>Origem</th><th>Destino</th><th>Chave</th></tr></thead><tbody>
@for(relation of filteredRelationships();track relation.key){<tr><td>{{relation.from}}</td><td>{{relation.to}}</td><td>{{relation.name}}</td></tr>}@empty{<tr><td colspan="3">Nenhum relacionamento declarado disponível para este filtro.</td></tr>}
</tbody></table></div>
`})
export class SourceCatalog implements OnChanges {
 @Input({required:true})source!:Source;@Input()editable=false;@Input()busy=false;@Output()approved=new EventEmitter<Policy>();
 search='';editing=signal('');selected:Record<string,string[]>={};
 ngOnChanges(changes:SimpleChanges){if(changes['source'])this.selected=Object.fromEntries(Object.entries(this.source.policy?.objects||this.source.objects||{}).map(([name,item])=>[name,item.fields.map(f=>f.name)]));}
 entries(){return Object.entries(this.source.catalog?.objects||this.source.policy?.objects||this.source.objects||{}).map(([name,item])=>({name,item}));}
 filtered(){const query=this.search.trim().toLocaleLowerCase('pt-BR');return this.entries().filter(e=>!query||e.name.toLocaleLowerCase('pt-BR').includes(query)||e.item.fields.some(f=>f.name.toLocaleLowerCase('pt-BR').includes(query)));}
 permitted(field:{type:string;sensitive?:boolean}){return (!field.sensitive||!!this.source.policy?.allow_sensitive)&&!['BLOB','CLOB','NCLOB','LONG','RAW','LONG RAW','BFILE','XMLTYPE'].includes(field.type.toUpperCase());}
 approvedCount(){return Object.values(this.selected).filter(fields=>fields.length).length;}
 relationships(){
  const objects=this.source.catalog?.objects||this.source.policy?.objects||this.source.objects||{};
  const keys=this.source.semantic['join_keys'] as string[][]|undefined;
  const rows:CatalogRelationship[]=this.source.catalog?.relationships?.length?this.source.catalog.relationships:(keys||[]).map(([a,b,c,d])=>({from_object:this.source.semantic['schema']+'.'+a,from_field:b,to_object:this.source.semantic['schema']+'.'+c,to_field:d}));
  const groups=new Map<string,CatalogRelationship[]>();
  for(const row of rows){if(!objects[row.from_object]||!objects[row.to_object])continue;const key=row.from_object+':'+(row.constraint_name||[row.from_field,row.to_object,row.to_field].join(':'));groups.set(key,[...(groups.get(key)||[]),row]);}
  return [...groups].map(([key,values])=>{values.sort((a,b)=>(a.position||0)-(b.position||0));const row=values[0];return {key,name:row.constraint_name||'Chave estrangeira',from:row.from_object+' ('+values.map(v=>v.from_field).join(', ')+')',to:row.to_object+' ('+values.map(v=>v.to_field).join(', ')+')'};});
 }
 filteredRelationships(){const query=this.search.trim().toLocaleLowerCase('pt-BR');return this.relationships().filter(r=>!query||[r.from,r.to,r.name].join(' ').toLocaleLowerCase('pt-BR').includes(query));}
 toggle(name:string,item:CatalogObject,on:boolean){if(on)this.selected[name]=item.fields.filter(f=>this.permitted(f)).map(f=>f.name);else delete this.selected[name];}
 toggleField(name:string,field:string,on:boolean){const values=new Set(this.selected[name]||[]);on?values.add(field):values.delete(field);if(values.size)this.selected[name]=[...values];else delete this.selected[name];}
 save(){if(!this.source.policy)return;const objects:Record<string,CatalogObject>={};for(const entry of this.entries()){const chosen=this.selected[entry.name]||[];const fields=entry.item.fields.filter(f=>chosen.includes(f.name)&&this.permitted(f));if(fields.length)objects[entry.name]={...entry.item,fields};}this.approved.emit({...this.source.policy,objects});}
}
