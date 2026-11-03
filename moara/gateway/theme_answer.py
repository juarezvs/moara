"""Readable, source-bound theme answers. No subject -> answer templates."""
import re
from html import escape

def label(number):return f'{number:,}'.replace(',','.')

def readable(text):
 # The official bank contains inverted-question-mark layout separators. Keep
 # source bytes in evidence; normalize only these separators for display.
 text=re.sub(r'\s+',' ',text.replace('¿',' ')).strip()
 text=re.sub(r'(?<!\d)(\d+(?:\.\d+)*[.)])\s+(?=[A-ZÀ-Ý])',r'\n\n\1 ',text)
 text=re.sub(r'(?<!\w)\(?([a-z])\)\s*',r'\n- (\1) ',text)
 return text.strip()

def roman_sections(text):
 text=re.sub(r'\s+',' ',text.replace('¿',' ')).strip()
 parts=re.split(r'(?<!\w)([IVX]{1,6})\s*[–-]\s*',text)
 result=[]
 for i in range(1,len(parts)-1,2):
  body=parts[i+1];m=re.search(r'(?<!\d)\b\d+(?:\.\d+)*[.)]\s+(?=[A-ZÀ-Ý])',body)
  if not m:continue
  title=body[:m.start()].strip();items=body[m.start():]
  child=re.search(r'(?<!\d)\b\d+\.\d+[.)]\s+',items)
  principal=items[:child.start()] if child else items
  if title and principal:result.append((parts[i]+' — '+title,principal.strip()))
 return result

def answer(records,rows):
 numbers=[r['official_theme']['number'] for r in records]
 intro='Os temas localizados e conferidos no STF para esta pesquisa são ' if len(records)>1 else 'O tema localizado e conferido no STF para esta pesquisa é '
 lines=[intro+' e '.join('**Tema '+label(n)+'**' for n in numbers)+'.']
 for i,record in enumerate(records,1):
  meta=record['official_theme'];number=meta['number'];source=record['source'];cite=' [STF]('+source+')'
  lines+=['## '+str(i)+'. Tema '+label(number)+' — '+meta['leading_case'],'**Questão central:** '+meta['title']+cite]
  if meta.get('reported_status'):lines.append('**Situação informada no cadastro oficial:** '+meta['reported_status']+'.'+cite)
  thesis=record.get('published_thesis',{})
  if thesis.get('freshly_rechecked') and thesis.get('text'):
   tc=' [Tese no STF]('+thesis['source']+')'
   lines.append('### Tese divulgada pelo STF')
   sections=roman_sections(thesis['text'])
   if len(thesis['text'])>6500 and sections:
    lines.append('A tese contém os seguintes eixos. Os trechos abaixo preservam a redação do STF; os subitens e as exceções estão no texto integral disponível ao final.')
    for title,text in sections:lines+=['**'+title+'**',readable(text)+tc]
    lines.append('<details><summary>Ler a tese integral e todos os subitens</summary><p>'+escape(readable(thesis['text'])).replace('\n','<br>')+'</p></details>')
   else:
    # Preserve every cumulative condition and exception, rather than asking a
    # model to compress a six-condition rule into fewer unsupported claims.
    blocks=re.split(r'\n\n',readable(thesis['text']))
    for block in blocks:
     if block.strip():lines.append(block.strip()+tc)
   lines.append('[Consultar a tese no portal do STF]('+thesis['source']+') · [Consultar o tema e o processo]('+source+').')
  else:
   lines.append('**Tese de mérito:** não foi possível confirmar o texto divulgado pelo STF nesta consulta. O objeto e a situação cadastral acima foram conferidos; reconhecimento de repercussão geral ou um voto não substituem a tese de mérito.')
  event=meta.get('latest_merits_event')
  if event and not thesis.get('text'):lines.append('**Andamento recuperado:** '+event['date']+' — '+event['label']+'. [Andamentos no STF]('+meta['andamento_url']+').')
  if re.search(r'militar|forças armadas',meta['title']+' '+meta['description'],re.I):
   lines.append('**Âmbito do tema:** reforma militar. Este resultado não estabelece aposentadoria automática para todos os regimes; aposentadoria civil ou pelo INSS exige pesquisa do regime correspondente.')
 if len(records)>1:
  lines.append('## Comparação dos temas')
  table=['| Tema | Processo | Objeto no cadastro oficial |','| --- | --- | --- |']
  for record in records:
   m=record['official_theme'];table.append('| [Tema '+label(m['number'])+']('+record['source']+') | '+m['leading_case']+' | '+m['title'].replace('|','\\|')+' |')
  lines.append('\n'.join(table))
  related=[r for r in records if r.get('related_by_official_thesis')]
  for r in related:lines.append('**Relação identificada na fonte:** o texto da tese do Tema '+label(r['related_by_official_thesis'])+' faz referência ao Tema '+label(r['official_theme']['number'])+'. [Banco oficial de teses](https://portal.stf.jus.br/repercussaogeral/teses.asp).')
 lines+=['## Aplicação ao caso concreto','O enquadramento do pedido exige considerar o objeto de cada tema, todos os requisitos e exceções da tese e eventuais regras de transição ou modulação nas decisões pertinentes. A apresentação do texto divulgado não certifica, isoladamente, sua aplicação ao caso.']
 return {'status':'official_theme_theses_answer','answer':'\n\n'.join(lines),'inference_used':False,'source_ids':[s['id'] for s in rows]}
