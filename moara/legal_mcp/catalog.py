"""Official federal catalogue and Câmara history. Proposals are never law text."""
import json,re,asyncio
from datetime import datetime,timezone,date
from urllib.parse import urlencode,urlsplit
import httpx
from .contracts import Bill,LegislativeHistory,today
from .sources import OfficialSources,sequence,clean,mapping

def stamp():return datetime.now(timezone.utc).isoformat()

async def tracked(adapter,url,result,expected='json'):
    host=urlsplit(url).hostname
    attempt={'source':{'legis.senado.leg.br':'Senado','normas.leg.br':'normas.leg.br','dadosabertos.camara.leg.br':'Câmara dos Deputados'}.get(host,host),
        'url':url,'attempted_at':stamp()}
    try:
        data,snapshot=await adapter.fetch(url,expected)
        result['snapshots'].append(snapshot)
        attempt.update(status='retrieved',sha256=snapshot['sha256'])
        return data
    except (httpx.HTTPError,ValueError,KeyError,TypeError) as error:
        attempt.update(status='unavailable',failure=type(error).__name__)
        if isinstance(error,httpx.HTTPStatusError):attempt['http_status']=error.response.status_code
        raise
    except asyncio.CancelledError:
        attempt.update(status='unavailable',failure='timeout_or_cancelled')
        raise
    finally:result['source_checks'].append(attempt)

async def search(client,spec):
    result={'status':'unconfirmed','checked_at':stamp(),'candidates':[],'snapshots':[],'source_checks':[],
            'legal_conclusion_allowed':False,'coverage':'federal_partial','gaps':[]}
    params={'tipo':spec.kind,'numero':spec.number}
    if spec.year:params['ano']=spec.year
    try:
        data=await tracked(OfficialSources(client),'https://legis.senado.leg.br/dadosabertos/legislacao/lista.json?'+urlencode(params),result)
        root=mapping(data.get('ListaDocumento'));docs=sequence(mapping(root.get('documentos')).get('documento'))
        for doc in docs:
            # Do not turn a fuzzy API response into an exact identification.
            if int(str(doc.get('numero','')).replace('.',''))!=spec.number:continue
            if str(doc.get('tipo','')).split('-')[0]!=spec.kind:continue
            if spec.year and str(doc.get('anoassinatura'))!=str(spec.year):continue
            identifier=str(doc.get('id',''))
            if not identifier.isdigit():continue
            result['candidates'].append({'id':identifier,'kind':spec.kind,'number':spec.number,
                'year':doc.get('anoassinatura'),'name':clean(doc.get('normaNome')),'summary':clean(doc.get('ementa'))[:3000],
                'source':'https://legis.senado.leg.br/dadosabertos/legislacao/'+identifier+'.json'})
        result['result_count']=len(result['candidates']);result['truncated']=len(result['candidates'])>50
        result['candidates']=result['candidates'][:50];result['status']='catalogue_retrieved'
    except (httpx.HTTPError,ValueError,KeyError,TypeError):result['gaps'].append('Catálogo oficial indisponível ou identificação não validada.')
    result['gaps'].append('Localização no catálogo não confirma redação, vigência, revogação ou efeitos judiciais. Consulte a norma na data relevante.')
    return result

def matches_bill(row,bill):
    try:return row['siglaTipo']==bill.kind and int(row['numero'])==bill.number and int(row['ano'])==bill.year
    except (KeyError,TypeError,ValueError):return False

def history_record(spec):
    return {'status':'unconfirmed','bill':spec.bill.model_dump(),'reference_date':str(spec.reference_date),
            'checked_at':stamp(),'normative_text':False,'legal_conclusion_allowed':False,'events':[],
            'snapshots':[],'source_checks':[],'gaps':['Proposições e tramitações não substituem texto promulgado, publicação ou conferência de vigência.']}

async def history(adapter,spec,result=None):
    if result is None:result=history_record(spec)
    if spec.reference_date>today():
        result['gaps'].append('Não é possível confirmar uma tramitação futura.');return result
    bill=spec.bill
    try:
        data=await tracked(adapter,'https://dadosabertos.camara.leg.br/api/v2/proposicoes?'+urlencode(
            {'siglaTipo':bill.kind,'numero':bill.number,'ano':bill.year,'itens':100,'pagina':1}),result)
        rows=[d for d in sequence(data.get('dados')) if matches_bill(d,bill)]
        if any(link.get('rel')=='next' for link in sequence(data.get('links'))):raise ValueError('incomplete_bill_identification')
        if len(rows)!=1:raise ValueError('ambiguous_or_missing_bill')
        identifier=rows[0]['id']
        if not isinstance(identifier,int) or isinstance(identifier,bool) or identifier<=0:raise ValueError('invalid_bill_identifier')
        base='https://dadosabertos.camara.leg.br/api/v2/proposicoes/'+str(identifier)
        detail=await tracked(adapter,base,result);row=detail['dados']
        if not matches_bill(row,bill) or row.get('id')!=identifier:raise ValueError('bill_identity_mismatch')
        result.update(id=identifier,source=base,public_page='https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao='+str(identifier),
            current_metadata_at_collection={'summary':clean(row.get('ementa'))[:6000],'status':row.get('statusProposicao'),
                'final_urn':row.get('urnFinal'),'is_historical_status':False})
        events=await tracked(adapter,base+'/tramitacoes?'+urlencode({'dataFim':str(spec.reference_date)}),result)
        if not isinstance(events.get('dados'),list):raise ValueError('invalid_official_event_list')
        valid=[];excluded=0
        for row in sequence(events.get('dados')):
            try:at=date.fromisoformat(str(row.get('dataHora',''))[:10])
            except ValueError:excluded+=1;continue
            if at>spec.reference_date:excluded+=1;continue
            valid.append({k:row.get(k) for k in ['dataHora','sequencia','siglaOrgao','descricaoTramitacao','descricaoSituacao','despacho']})
        valid.sort(key=lambda row:(str(row['dataHora']),str(row.get('sequencia',''))))
        result.update(status='legislative_history_retrieved',events=valid[-200:],returned_event_count=len(valid),
            excluded_events=excluded,events_truncated=len(valid)>200,
            coverage_complete=False)
        if excluded:result['gaps'].append('Eventos sem data válida ou posteriores à data relevante foram excluídos do histórico apresentado.')
        if len(valid)>200:result['gaps'].append('Exibidos apenas os 200 eventos mais recentes retornados até a data relevante; a resposta original foi preservada.')
        result['gaps'].append('Metadados correntes foram coletados agora; não representam automaticamente a situação histórica nem comprovam cobertura integral.')
    except (httpx.HTTPError,ValueError,KeyError,TypeError):
        result['gaps'].append('Não foi possível identificar de modo único a proposição e conferir sua tramitação na Câmara.')
    return result

async def legislative_history(client,spec):return await history(OfficialSources(client),spec)

def originating_bill(structured):
    # Only the legislature's explicit CD provenance; never a number in case text
    # or an unrelated bill with the same number/year as a law.
    for key in ['legislationSourceProcess','sourceProcess']:
        for value in sequence(structured.get(key)):
            matches=re.findall(r'Projeto de Lei( Complementar)? \(CD\)\s+n[ºo°.]*\s*(\d+)\s*/\s*(\d{4})',clean(value.get('name')),re.I)
            if len(matches)==1:
                extra,number,year=matches[0]
                return Bill(kind='PLP' if extra else 'PL',number=int(number),year=int(year))
    return None

def unique(values):
    seen=set();out=[]
    for row in values:
        key=json.dumps(row,sort_keys=True,ensure_ascii=False)
        if key not in seen:seen.add(key);out.append(row)
    return out

def publication_date(value):
    try:return datetime.strptime(value,'%d/%m/%Y').date().isoformat()
    except (ValueError,TypeError):return None

async def related_changes(adapter,changes,articles,at,result=None):
    candidates={}
    for row in changes:
        code=str(row.get('codnormaposterior',''));when=publication_date(row.get('datapub'))
        if not code.isdigit() or not when or when>str(at):continue
        items=sequence((row.get('itens') or {}).get('item')) if isinstance(row.get('itens'),dict) else []
        if articles and items and not any(any(re.search(r'Art\.\s*'+re.escape(a)+r'(?![\dA-Za-z])',str(i.get('dispositivo','')),re.I) for a in articles) for i in items):continue
        if 'Altera' not in str(row.get('comentario','')) and 'Revoga' not in str(row.get('comentario','')):continue
        candidates[code]=max(when,candidates.get(code,''))
    selected=sorted(candidates,key=lambda code:candidates[code],reverse=True)[:2]
    if result is None:result={'checks':[],'snapshots':[],'source_checks':[]}
    result.update(candidate_count=len(candidates),limit=2,coverage_complete=False)
    for code in selected:
        try:
            data=await tracked(adapter,'https://legis.senado.leg.br/dadosabertos/legislacao/'+code+'.json',result)
            docs=sequence(data['DetalheDocumento'].get('documentos',{}).get('documento'))
            if len(docs)!=1 or str(docs[0].get('id'))!=code:raise ValueError('related_norm_identity_mismatch')
            doc=docs[0]
            result['checks'].append({'id':code,'identity':doc.get('identificacao'),'publications':doc.get('publicacoes'),
                'reported_publication_date':candidates[code],'effective_date_confirmed':False})
        except (httpx.HTTPError,ValueError,KeyError,TypeError):result['checks'].append({'id':code,'status':'unconfirmed'})
    return result
