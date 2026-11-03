from pathlib import Path
p=Path('moara/web/src/app/workbench.html');s=p.read_text(encoding='utf8')
start=s.index("    @if(view()!=='editor'){")
end=s.index('      </footer>',start)+len('      </footer>')
footer=s[s.index('      <footer',start):end]
assert s[end:].startswith('\n    }')
s=s[:start]+'    <ng-template #workComposer>\n'+footer+'\n    </ng-template>\n    @if(view()!==\'editor\'&&(messages().length||view()!==\'inicio\')){<ng-container [ngTemplateOutlet]="workComposer"/>}'+s[end+len('\n    }'):]
needle='          <div class="context-card">'
assert needle in s
s=s.replace(needle,'          <div class="welcome-composer"><ng-container [ngTemplateOutlet]="workComposer"/></div>\n'+needle,1)
p.write_text(s,encoding='utf8')
p=Path('moara/web/src/app/chat.ts');s=p.read_text(encoding='utf8').replace("import { DatePipe } from '@angular/common';","import { DatePipe,NgTemplateOutlet } from '@angular/common';").replace('imports:[FormsModule,DatePipe,','imports:[FormsModule,DatePipe,NgTemplateOutlet,');p.write_text(s,encoding='utf8')
