"""Per-reference isolation and bounded official research, never a vigency certificate."""
import asyncio,re
from datetime import datetime,timezone
from urllib.parse import urlencode
import httpx
from .sources import OfficialSources,clean
from .texts import LegalHTML,relevant
from .contracts import today,SubjectSearch,Norm

async def precedent(adapter,spec,at):
    if spec.court=='STF' and spec.kind=='TEMA':
        from .jurisprudence import theme
        return await theme(adapter,spec,at)
    result={'reference':spec.model_dump(),'source':None,'status':'unavailable','excerpts':[],'snapshots':[],'source_checks':[],'gaps':[]}
    if at!=today():
        result['gaps']=['O estado atual de um precedente não comprova sua situação histórica ou futura.'];return result
    n=spec.number;k=spec.kind
    if spec.court=='STF':
        url=('https://portal.stf.jus.br/jurisprudenciaRepercussao/tema.asp?num='+str(n) if k=='TEMA' else
            'https://portal.stf.jus.br/jurisprudencia/sumariosumulas.asp?base='+('26' if k=='SV' else '30')+'&sumula='+str(n) if k in ('SV','SUMULA') else
            'https://portal.stf.jus.br/processos/listarProcessos.asp?'+urlencode({'classe':k,'numeroProcesso':n}))
    else:
        url=('https://scon.stj.jus.br/repetitivos/temas_repetitivos/pesquisa.jsp?'+urlencode({'novaConsulta':'true','tipo_pesquisa':'T','cod_tema_inicial':n,'cod_tema_final':n}) if k=='TEMA' else
            'https://scon.stj.jus.br/SCON/pesquisar.jsp?'+urlencode({'b':'SUMU' if k=='SUMULA' else 'ACOR','livre':str(n)+' '+k,'O':'JT'}))
    result['source']=url
    try:
        html,snapshot=await adapter.fetch(url,'html');result['snapshots'].append(snapshot)
        text=re.sub(r'\s+',' ',LegalHTML(html).text())
        marker=(r'Tema\s*(?:Repetitivo\s*)?[:\s]*'+str(n)+r'\b' if k=='TEMA' else r'\b'+str(n)+r'\b')
        match=re.search(marker,text,re.I)
        has_content=re.search(r'Tese Firmada|Descrição:|Questão submetida|Ementa|Enunciado',text,re.I)
        if not match or not has_content:raise ValueError('official_page_is_not_a_verified_result')
        fragment=text[max(0,match.start()-20):match.start()+10000]
        result.update(status='official_precedent_record_retrieved',excerpts=[{'device':spec.court+' '+k+' '+str(n),'name':spec.court+' '+k+' '+str(n),
            'text':fragment,'source':url,'version_date':str(at),'effective_date_confirmed':False,'text_truncated':len(text)>match.start()+10000}])
        result['source_checks'].append({'url':url,'status':'retrieved','sha256':snapshot['sha256']})
        if not re.search(r'Tese Firmada|Tese:',fragment,re.I):result['gaps'].append('A página recuperada não contém uma tese expressa; descrição do tema não é tese de julgamento.')
    except (httpx.HTTPError,ValueError,TypeError):result['gaps'].append('Não foi possível recuperar conteúdo decisório identificável nesta fonte oficial. Não será inventada tese ou situação processual.')
    result['gaps'].append('O registro não certifica inteiro teor, recursos pendentes, trânsito em julgado, modulação ou aplicabilidade a um caso concreto.')
    return result

async def research(client,spec):
    result={'status':'official_research_unavailable','reference_date':str(spec.reference_date),'checked_at':datetime.now(timezone.utc).isoformat(),
            'legal_conclusion_allowed':False,'norms':[],'precedents':[],'gaps':[]}
    if spec.reference_date>today():result['gaps']=['Não é possível confirmar antecipadamente o estado futuro das fontes.'];return result
    adapter=OfficialSources(client)
    discovery=None
    if not spec.norms and spec.subject_query:
        from .discovery import discover
        discovery=await discover(client,SubjectSearch(query=spec.subject_query))
        result['discovery']=discovery
        candidates=discovery['candidates']
        if candidates:
            best=candidates[0]['relevance_score']
            selected=[r for r in candidates[:2] if r['relevance_score']>=max(4,best*.8)]
            spec=spec.model_copy(update={'norms':[Norm.model_validate(r['norm']) for r in selected]})
            discovery['selected_norms']=[n.model_dump() for n in spec.norms]
        else:
            result['gaps'].append('A pesquisa por assunto não encontrou identificação oficial suficiente. Refine o tema, o âmbito ou o órgão emissor; não é necessário saber o número da lei.')
    async def norm(n):
        try:
            value=await asyncio.wait_for(adapter.norm(n,spec.reference_date,enrich=False),40)
            total=len(value.get('excerpts',[]));value['excerpts']=relevant(value.get('excerpts',[]),spec.subject_query or spec.query,limit=28 if re.search(r'crit[ée]rios|requisitos|condi[çc][õo]es',spec.query,re.I) else 12)
            if spec.subject_query and value.get('name') and spec.reference_date==today():
                candidate=next((r for r in discovery['candidates'] if r['norm']==n.model_dump()),None) if discovery else None
                # Identity comes from the exact numeric catalogue checked by norm(), not model memory.
                summary=value.get('summary') or (candidate.get('summary') if candidate else '')
                if summary:
                    label={'LEI':'Lei','LCP':'Lei complementar','DEL':'Decreto-lei','DEC':'Decreto','EMC':'Emenda constitucional','CON':'Constituição'}[n.kind]
                    value['excerpts'].insert(0,{'device':'identificacao','name':'Identificação e ementa oficial','text':label+' '+str(n.number)+'/'+str(n.year)+' — '+value['name']+'. '+summary,
                        'source':value.get('identity_source') or 'https://legis.senado.leg.br/dadosabertos/legislacao/'+n.kind+'/'+str(n.number)+'/'+str(n.year)+'.json','version_date':str(spec.reference_date),'text_basis':'official_catalogue_identity_not_effective_date','effective_date_confirmed':False})
            value['retrieved_excerpt_count']=total;value['selected_excerpt_count']=len(value['excerpts'])
            return value
        except (httpx.HTTPError,ValueError,TypeError,AttributeError,KeyError,TimeoutError):
            return {'norm':n.model_dump(),'status':'unavailable','excerpts':[],'snapshots':[],'gaps':['Falha isolada nesta referência; outras fontes recuperadas continuam disponíveis.']}
    result['norms']=await asyncio.gather(*(norm(n) for n in spec.norms))
    result['precedents']=await asyncio.gather(*(precedent(adapter,p,spec.reference_date) for p in spec.precedents))
    for url in spec.official_urls:
        record={'source':url,'name':'Documento oficial informado','excerpts':[],'snapshots':[],'gaps':[]}
        try:
            if spec.reference_date!=today():raise ValueError('current_document_not_historical')
            html,snapshot=await adapter.fetch(url,'html');record['snapshots'].append(snapshot)
            text=LegalHTML(html).text()
            if not re.search(r'<(?:html|p|div)\b',html,re.I) or not re.search(r'\b(?:Art\.?\s*\d|Portaria|Resolu[çc][aã]o|Instru[çc][aã]o Normativa)\b',text,re.I):raise ValueError('not_identified_normative_document')
            excerpts=[]
            try:
                from .texts import articles_from_html
                excerpts=articles_from_html(html,url,[],spec.reference_date)
            except ValueError:pass
            record['excerpts']=relevant(excerpts,spec.query) if excerpts else [{'device':'documento oficial','text':re.sub(r'\s+',' ',text)[:12000],'source':url,'version_date':str(spec.reference_date)}]
            record['status']='official_document_retrieved'
            record['gaps'].append('Documento público indicado pelo usuário; identidade, consolidação integral e vigência exigem conferência adicional.')
        except (httpx.HTTPError,ValueError,TypeError):record['gaps'].append('URL não aprovada, conteúdo não identificável ou fonte indisponível.')
        result['norms'].append(record)
    if any(r.get('excerpts') for r in result['norms']+result['precedents']):result['status']='official_sources_retrieved'
    result['gaps'].append('Resposta informativa baseada nas fontes recuperadas; cobertura de alterações, vigência, eficácia e decisões judiciais não é exaustiva.')
    return result
