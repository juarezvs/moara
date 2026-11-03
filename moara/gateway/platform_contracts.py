"""Bounded contracts for institutional workspaces; no executable expressions."""
import json,re
from typing import Literal
from uuid import UUID
from pydantic import BaseModel,ConfigDict,Field,model_validator
from fastapi import HTTPException

Kind=Literal['document','prompt','template','assistant','project','case','workflow','dashboard']
class Strict(BaseModel):
 model_config=ConfigDict(extra='forbid')
class ResourceCreate(Strict):
 kind:Kind
 title:str=Field(min_length=1,max_length=200)
 body:dict=Field(default_factory=dict)
 group_id:UUID|None=None
class ResourceUpdate(Strict):
 version:int=Field(ge=1)
 title:str=Field(min_length=1,max_length=200)
 body:dict
 group_id:UUID|None=None
class RunCreate(Strict):
 operation:Literal['document.ingest','knowledge.answer','assistant.run','project.generate','project.execute','agent.run','legal.draft','workflow.run']
 resource_id:UUID|None=None
 input:dict=Field(default_factory=dict)
 idempotency_key:str|None=Field(default=None,max_length=100,pattern=r'^[a-zA-Z0-9_.:-]+$')
class SearchRequest(Strict):
 query:str=Field(min_length=2,max_length=2000)
 document_ids:list[UUID]=Field(default_factory=list,max_length=64)
 limit:int=Field(default=6,ge=1,le=12)
class Upload(Strict):
 filename:str=Field(min_length=1,max_length=180)
 content_base64:str=Field(min_length=4)
 title:str=Field(min_length=1,max_length=200)
 group_id:UUID|None=None
class TemplateRender(Strict):
 fields:dict[str,str]=Field(default_factory=dict,max_length=60)
 version:int=Field(ge=1)
class DatasetQuery(Strict):
 document_id:UUID
 group_by:str=Field(min_length=1,max_length=100)
 operation:Literal['count','sum','average']='count'
 value_column:str|None=Field(default=None,max_length=100)
 filters:dict[str,str]=Field(default_factory=dict,max_length=10)
class FlowTemplate(Strict):
 template_id:UUID
 version:int|None=Field(default=None,ge=1)
 fields:dict[str,str]=Field(default_factory=dict,max_length=60)
class FlowNotification(Strict):
 message:str=Field(default='',max_length=2000)
class Revision(Strict):
 version:int=Field(ge=1)
class Approval(Strict):
 version:int=Field(ge=1)
 digest:str=Field(pattern=r'^[a-f0-9]{64}$')
class ProjectFiles(Strict):
 version:int=Field(ge=1)
 files:dict[str,str]=Field(max_length=64)
class CaseEvent(Strict):
 date:str=Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
 description:str=Field(min_length=1,max_length=2000)
 document_id:UUID
 page:int|None=Field(default=None,ge=1,le=500)

OPERATIONS={'agent.run':(None,'chat.use'),'project.execute':('project','development.execute'),'document.ingest':('document','documents.use'),'knowledge.answer':(None,'knowledge.use'),
 'assistant.run':('assistant','workspace.use'),'project.generate':('project','development.use'),
 'legal.draft':('case','documents.use'),'workflow.run':('workflow','workflows.use')}
AGENTS=[
 {'id':'coordinator','name':'Coordenador','purpose':'Plano, etapas e evidências','tools':['knowledge.search']},
 {'id':'developer','name':'Desenvolvedor','purpose':'Código e testes propostos','tools':['project.propose']},
 {'id':'architect','name':'Arquiteto','purpose':'Arquitetura e contratos','tools':[]},
 {'id':'analyst','name':'Analista de dados','purpose':'Indicadores calculados em fontes autorizadas','tools':['analytics.aggregate']},
 {'id':'legal','name':'Assistente jurídico','purpose':'Minutas com fontes para revisão humana','tools':['knowledge.search','template.render']},
 {'id':'security','name':'Revisor de segurança','purpose':'Revisão de código e permissões','tools':['project.review']},
 {'id':'documentation','name':'Documentação','purpose':'Documentação e templates','tools':['template.render']},
 {'id':'automation','name':'Automação','purpose':'Etapas declarativas e monitoradas','tools':['workflow.run']},
 {'id':'reviewer','name':'Revisor','purpose':'Conferência de fontes e resultados','tools':['knowledge.search']}]

def validate_body(kind,body):
 if len(json.dumps(body,ensure_ascii=False).encode())>150000:raise HTTPException(413,'resource_too_large')
 if kind in ('prompt','template'):
  if set(body)-{'text','variables','document_id','description'}:raise HTTPException(422,'invalid_resource_fields')
  if not isinstance(body.get('text',''),str) or len(body.get('text',''))>40000:raise HTTPException(422,'invalid_template')
  variables=body.get('variables',[])
  if not isinstance(variables,list) or len(variables)>60 or any(not isinstance(x,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,49}',x) for x in variables):raise HTTPException(422,'invalid_template_variables')
 for key in ('document_ids','events','tools'):
  if key in body and not isinstance(body[key],list):raise HTTPException(422,'invalid_list')
 if 'tools' in body and any(not isinstance(x,str) for x in body['tools']):raise HTTPException(422,'invalid_tools')
 if 'model' in body and (not isinstance(body['model'],str) or not 1<=len(body['model'])<=128):raise HTTPException(422,'invalid_model')
 if kind=='assistant':
  if set(body)-{'instructions','model','document_ids','tools','description','temperature'}:raise HTTPException(422,'invalid_resource_fields')
  if not isinstance(body.get('instructions',''),str) or len(body.get('instructions',''))>12000:raise HTTPException(422,'invalid_instructions')
  if set(body.get('tools',[]))-{'knowledge.search','template.render'}:raise HTTPException(422,'tool_not_allowed')
  if len(body.get('document_ids',[]))>64:raise HTTPException(422,'too_many_sources')
 if kind=='project':
  if set(body)-{'description','language','files','directories','review','last_run'}:raise HTTPException(422,'invalid_resource_fields')
  if body.get('language','python') not in {'python','fastapi','typescript','angular','react'}:raise HTTPException(422,'unsupported_project_language')
  validate_files(body.get('files',{}))
  from .project_tree import validate_directories
  validate_directories(body.get('files',{}),body.get('directories',[]))
 if kind=='workflow':
  if set(body)-{'description','steps','schedule','timeout_seconds'}:raise HTTPException(422,'invalid_resource_fields')
  steps=body.get('steps',[])
  if not isinstance(steps,list) or not 1<=len(steps)<=12:raise HTTPException(422,'workflow_steps_required')
  for step in steps:
   if not isinstance(step,dict) or set(step)-{'type','parameters'} or step.get('type') not in {'knowledge.search','template.render','notification.test','analytics.aggregate'}:raise HTTPException(422,'workflow_step_not_allowed')
   if not isinstance(step.get('parameters',{}),dict):raise HTTPException(422,'invalid_step_parameters')
   contract={'knowledge.search':SearchRequest,'template.render':FlowTemplate,'analytics.aggregate':DatasetQuery,'notification.test':FlowNotification}[step['type']]
   try:contract.model_validate(step.get('parameters',{}))
   except ValueError:raise HTTPException(422,'invalid_step_parameters') from None
  schedule=body.get('schedule',{})
  if not isinstance(schedule,dict):raise HTTPException(422,'invalid_schedule')
  if set(schedule)-{'enabled','interval_seconds'} or not isinstance(schedule.get('enabled',False),bool):raise HTTPException(422,'invalid_schedule')
  interval=schedule.get('interval_seconds',3600)
  if not isinstance(interval,int) or not 300<=interval<=2592000:raise HTTPException(422,'invalid_schedule_interval')
 if kind=='case':
  if set(body)-{'description','document_ids','events','draft','reviewed_version','review_note'}:raise HTTPException(422,'invalid_resource_fields')
  if len(body.get('document_ids',[]))>64 or len(body.get('events',[]))>300:raise HTTPException(422,'case_too_large')
  for event in body.get('events',[]):
   try:CaseEvent.model_validate(event)
   except ValueError:raise HTTPException(422,'invalid_case_event') from None
 if kind=='dashboard':
  if set(body)-{'description','document_id','group_by','operation','value_column','filters'}:raise HTTPException(422,'invalid_resource_fields')
 return body

def validate_files(files):
 if not isinstance(files,dict) or len(files)>64:raise HTTPException(422,'invalid_project_files')
 total=0
 if len({name.casefold() for name in files if isinstance(name,str)})!=len(files):raise HTTPException(422,'duplicate_project_path')
 for name in files:
  if isinstance(name,str) and any('/'.join(name.split('/')[:i]).casefold() in {p.casefold() for p in files if isinstance(p,str)} for i in range(1,len(name.split('/')))):raise HTTPException(422,'conflicting_project_path')
 for name,value in files.items():
  if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9_. /-]{1,180}',name) or name.startswith(('/','.')) or ':' in name or name.rstrip(' .')!=name or any(p.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(10)],*[f'LPT{i}' for i in range(10)]} for p in name.split('/')) or '\\' in name or any(p in ('','..','.') or p.rstrip(' .')!=p or p.startswith('.') for p in name.split('/')):raise HTTPException(422,'unsafe_project_path')
  if not isinstance(value,str) or len(value.encode())>200000:raise HTTPException(413,'project_file_too_large')
  total+=len(value.encode())
 if total>1000000:raise HTTPException(413,'project_too_large')
 return files
