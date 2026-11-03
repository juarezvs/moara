from pathlib import Path
p=Path('moara/web/src/app/chat.ts');s=p.read_text(encoding='utf8')
s=s.replace("this.lastTask='';this.editorText='';}","this.lastTask='';this.editorText='';this.draft='';this.workMode='chat';this.assistantId='auto';this.profile='auto';}")
s=s.replace("chooseDataAssistant(){this.assistantId='dados';","chooseDataAssistant(){this.workMode='chat';this.assistantId='dados';")
p.write_text(s,encoding='utf8')
p=Path('moara/web/src/app/workbench.html');s=p.read_text(encoding='utf8').replace("(click)=\"workMode='plan'\"","(click)=\"workMode='plan';dataMode=false\"").replace("(click)=\"workMode='draft'\"","(click)=\"workMode='draft';dataMode=false\"")
p.write_text(s,encoding='utf8')
