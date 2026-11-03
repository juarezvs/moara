from pathlib import Path
p=Path('moara/web/src/app/chat.ts');s=p.read_text(encoding='utf8')
s=s.replace("import { ActivatedRoute } from '@angular/router';","import { ActivatedRoute,RouterLink } from '@angular/router';")
s=s.replace("import { AssistantPicker } from './assistant-picker';","import { AssistantPicker,OfficialAssistant } from './assistant-picker';\nimport { WorkbenchIcon } from './workbench-icon';\ninterface WorkResource {id:string;kind:string;title:string;version:number;body:any;}")
start=s.index('@Component({');end=s.index('export class ChatPage',start)
s=s[:start]+"@Component({standalone:true,imports:[FormsModule,DatePipe,ErrorBox,AssistantPicker,RouterLink,WorkbenchIcon],templateUrl:'./workbench.html',styleUrl:'./workbench.css'})\n"+s[end:]
start=s.index('  async uploadDocument(');end=s.index('\n  async load()',start)
s=s[:start]+"  async uploadDocument(event:Event){const input=event.target as HTMLInputElement;try{await this.uploadFiles(Array.from(input.files||[]));}finally{input.value='';}}"+s[end:]
s=s.replace("void this.load();void this.loadDocuments();}","void this.load();void this.loadDocuments();void this.loadWorkbench();this.route.queryParamMap.subscribe(params=>{const area=params.get('area');if(area&&this.workTabs.some(tab=>tab.id===area))this.view.set(area);});}")
s=s.replace("if(!regenerate){this.messages.update(m=>[...m,{role:'user',content:this.draft.trim()}]);this.draft='';}","if(!regenerate){this.lastTask=this.draft.trim();const prepared=this.preparedMessage(this.lastTask);this.messages.update(m=>[...m,{role:'user',content:prepared}]);this.draft='';}")
s=s.replace("messages:input,stream:true}","messages:input,stream:true,max_tokens:this.writingLength==='detailed'?1280:this.writingLength==='concise'?384:768}")
s=s.replace("this.notice.set('');}\n  async open", "this.notice.set('');this.selectedTemplate.set(null);this.acceptedPlan='';this.lastTask='';this.editorText='';}\n  async open")
s=s.replace("async open(c:Chat){if(this.busy()||this.uploading())return;try{", "async open(c:Chat){if(this.busy()||this.uploading())return;this.selectedTemplate.set(null);this.acceptedPlan='';this.workMode='chat';try{")
s=s.replace('  auth=inject(Auth);',Path('tmp/workbench_methods.txt').read_text(encoding='utf8')+'\n  auth=inject(Auth);',1)
p.write_text(s,encoding='utf8')
p=Path('moara/web/src/app/shell.ts');s=p.read_text(encoding='utf8');s=s.replace('[class.menu-open]="open()"','[class.menu-open]="open()" [class.focus-workbench]="router.url.startsWith(\'/chat\')"');p.write_text(s,encoding='utf8')
