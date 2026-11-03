import {Component,Input} from '@angular/core';
const BRAND_PATHS:Record<string,string>={
  context:'m12 3 9 5-9 5-9-5zM3 12l9 5 9-5M3 16l9 5 9-5',
  menu:'M4 6h16M4 12h16M4 18h16',
  sun:'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2',
  moon:'M21 14a9 9 0 0 1-11-11A9 9 0 1 0 21 14z',
  sparkles:'m12 3 2.4 6.6L21 12l-6.6 2.4L12 21l-2.4-6.6L3 12l6.6-2.4zM21 2v4M19 4h4',
  skill:'m12 3 2.4 6.6L21 12l-6.6 2.4L12 21l-2.4-6.6L3 12l6.6-2.4z',
  database:'M21 6c0 2-4 3-9 3S3 8 3 6s4-3 9-3 9 1 9 3zM3 6v6c0 2 4 3 9 3s9-1 9-3V6M3 12v6c0 2 4 3 9 3s9-1 9-3v-6',
  building:'M4 21V4h11v17M15 10h5v11M2 21h20M8 8h3M8 12h3M8 16h3M17 14h1M17 17h1',
  server:'M4 3h16v7H4zM4 14h16v7H4zM7 6h.01M7 17h.01M11 6h6M11 17h6',
  key:'M14 3a7 7 0 0 0-6.6 9.4L3 17v4h4v-3h3l2.6-2.6A7 7 0 1 0 14 3zM17 7h.01',
  shield:'m12 3 9 4v6c0 5-9 9-9 9s-9-4-9-9V7zM8 12l3 3 5-6',
  briefcase:'M9 7V4h6v3M3 7h18v14H3zM3 12c5 4 13 4 18 0M10 13h4v3h-4z',
  code:'m8 6-6 6 6 6M16 6l6 6-6 6M14 3l-4 18',
  arrow:'M5 12h15m-6-6 6 6-6 6'
};
const PATHS:Record<string,string>={home:'m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z',history:'M3 11a9 9 0 1 1 2.6 7M3 4v7h7M12 7v5l3 2',document:'M14 2H5a1 1 0 0 0-1 1v18a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V8zM14 2v6h6M8 12h8M8 16h8',model:'m12 3 9 5-9 5-9-5zM3 8v9l9 5 9-5V8M12 13v9',reference:'m12 3 9 5-9 5-9-5zM3 12l9 5 9-5M3 16l9 5 9-5',library:'M4 4h4v17H4zM10 4h4v17h-4zM16 5l4-1 4 16-4 1z',upload:'M12 16V3m-5 5 5-5 5 5M4 16v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4',law:'M12 3v18M5 21h14M4 6h16M6 6l-4 8h8zm12 0-4 8h8z',gavel:'m14 3 7 7-3 3-7-7zM4 20l10-10M3 21h8',skill:'M9 3h6v5h5v7h-5v6H9v-6H4V8h5z',settings:'M4 6h16M4 12h16M4 18h16M8 3v6M16 9v6M10 15v6',edit:'m14 4 6 6M4 20l5-1L21 7l-6-6L3 13z',chat:'M4 3h16v13H9l-5 5z',check:'m4 12 5 5L20 6',folder:'M3 7V4h6l3 3h9v14H3z',search:'M16 16l5 5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',plus:'M12 4v16M4 12h16'};
@Component({selector:'moara-work-icon',standalone:true,template:'<svg viewBox="0 0 26 26" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path [attr.d]="path"/></svg>',styles:[':host{display:inline-flex;width:22px;height:22px;flex-shrink:0}svg{width:100%;height:100%}']})
export class WorkbenchIcon {@Input() name='document';get path(){return BRAND_PATHS[this.name]||PATHS[this.name]||PATHS.document;}}
