"""Closed SARH personnel queries. Internal identity keys never enter the LLM catalog.

RH_AFASTAMENTO belongs to prior-service averaging; it is deliberately excluded.
The dataset comprises registered diverse absences and registered license periods.
"""
import calendar
import html
import re
import time
import unicodedata
from datetime import date,datetime,timedelta
from zoneinfo import ZoneInfo
from fastapi import HTTPException

FIELDS={
 'SARH.RH_AFASTAMENTOS_DIVERSOS':{'AFAD_FUNC_SIGLA_FUNCIONARIO','AFAD_FUNC_COD_FUNCIONARIO','AFAD_DAT_INICIO_AFAST','AFAD_DAT_FIM_AFAST'},
 'SARH.RH_PERIODO_LICENCA':{'PLIC_LICE_SECAO_SUBSECAO','PLIC_LICE_COD_FUNCIONARIO','PLIC_LICE_COD_LICENCA','PLIC_INICIO_PERIODO','PLIC_FIM_PERIODO'},
 'SARH.RH_LICENCA':{'LICE_FUNC_SIGLA_SECAO_SUBSECAO','LICE_FUNC_COD_FUNCIONARIO','LICE_COD_LICENCA'},
 'SARH.RH_FUNCIONARIO':{'FUNC_SESB_SIGLA_SECAO_SUBSECAO','FUNC_COD_FUNCIONARIO','FUNC_PESS_C_P_F'},
 'SARH.RH_PESSOAL':{'PESS_C_P_F','PESS_NOME'},
 'SARH.RH_HIST_LOTACAO':{'HLOT_FUNC_SIGLA_SECAO_SUBSECAO','HLOT_FUNC_COD_FUNCIONARIO','HLOT_LOTA_COD_LOTACAO','HLOT_DAT_INIC_LOTACAO','HLOT_DAT_FIM_LOTACAO'},
 'SARH.RH_LOTACAO':{'LOTA_COD_LOTACAO','LOTA_SIGLA_LOTACAO','LOTA_DSC_LOTACAO'},
}
MONTHS=dict(zip(('janeiro','fevereiro','marco','abril','maio','junho','julho','agosto','setembro','outubro','novembro','dezembro'),range(1,13)))

def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFKD',value.casefold()) if not unicodedata.combining(c))

def intent(question):
    text=normalize(question)
    if re.search(r'\b(contracheques?|holerites?)\b',text):return 'payroll'
    if re.search(r'\b(afastad\w*|afastamentos?|licencas?)\b',text) and re.search(r'\b(servidores?|pessoas?|funcionarios?|setor|lotacao|quantos|quantas|liste|lista|mostre|monte|quem)\b',text):return 'absence'
    return None

def period(question,today=None):
    text=normalize(question);today=today or datetime.now(ZoneInfo('America/Manaus')).date()
    tokens=re.findall(r'\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})\b',text)
    def parsed(v):
        try:return date.fromisoformat(v) if '-' in v else datetime.strptime(v,'%d/%m/%Y').date()
        except ValueError:raise ValueError('Data inválida. Use dia/mês/ano ou ano-mês-dia.') from None
    if tokens:
        if len(tokens)>2:raise ValueError('Informe apenas o início e o fim do período.')
        if len(tokens)==1 and re.search(r'\b(desde|ate|antes|depois)\b|a partir',text):raise ValueError('Informe o início e o fim do período para esse filtro de datas.')
        start=parsed(tokens[0]);end=parsed(tokens[-1])
    elif 'hoje' in text:start=end=today
    elif 'mes passado' in text:
        end=today.replace(day=1)-timedelta(days=1);start=end.replace(day=1)
    elif 'este mes' in text or 'mes atual' in text:
        start=today.replace(day=1);end=start.replace(day=calendar.monthrange(start.year,start.month)[1])
    else:
        match=re.search(r'\b('+'|'.join(MONTHS)+r')\s*(?:de\s*|/)?(\d{4})\b',text)
        if not match:return None
        year=int(match[2]);month=MONTHS[match[1]];start=date(year,month,1);end=date(year,month,calendar.monthrange(year,month)[1])
    if start>end or (end-start).days>3660:raise ValueError('Informe um período em ordem cronológica, de até dez anos.')
    if end.year>=9999:raise ValueError('Data final fora do intervalo suportado.')
    return start,end

def sector(question):
    match=re.search(r'\b(?:setor|lota[cç][aã]o)\s+(?:de\s+)?(.+)',question,re.I)
    if not match:
        acronyms=[v for v in re.findall(r'\b[A-Z][A-Z0-9_-]{1,19}\b',question) if v not in {'SARH','ORACLE','JFAM'} and not re.fullmatch(r'SJ[A-Z]{2}',v)]
        if len(acronyms)==1:return acronyms[0]
        if acronyms:raise ValueError('Informe o setor usando sua sigla exata, por exemplo “setor NUTEC”.')
        return None
    value=re.split(r'[,;\n]|\s+(?:no\s+(?:per[ií]odo|m[eê]s)|entre\s|em\s|de\s+\d|na\s+SJ|da\s+SJ|SJ[A-Z]{2}\b)',match[1],maxsplit=1,flags=re.I)[0].strip(' ."“”\'')
    if not value or len(value)>100 or any(ord(c)<32 for c in value):raise ValueError('Informe a sigla ou o nome exato do setor.')
    return value

def quoted(value):return "'"+str(value).replace("'","''")+"'"
def day(value):return "DATE '"+value.isoformat()+"'"

def closed_policy(catalog):
    objects={}
    for name,fields in FIELDS.items():
        item=catalog.get(name)
        if not item or item['type']!='table' or not fields<={f['name'] for f in item['fields']}:
            raise HTTPException(409,'Estrutura SARH de pessoal não validada nesta fonte')
        objects[name]={'type':'table','fields':[dict(f,sensitive=f['name'] in {'PESS_C_P_F','FUNC_PESS_C_P_F'}) for f in item['fields'] if f['name'] in fields]}
    # Only fixed server-owned SQL uses this policy; it is never saved into the
    # general source policy or exposed as a free-query capability.
    return {'owners':[],'groups':[],'max_rows':100,'timeout':30,'allow_sensitive':True,'objects':objects,'blocked_objects':[],'audit':'hash_only'}

def queries(start,end,sector_id=None):
    upper=end+timedelta(days=1)
    events="""SELECT A.AFAD_FUNC_SIGLA_FUNCIONARIO AS SECAO,A.AFAD_FUNC_COD_FUNCIONARIO AS MATRICULA,
        A.AFAD_DAT_INICIO_AFAST AS INICIO,A.AFAD_DAT_FIM_AFAST AS FIM,'Afastamento diverso' AS CATEGORIA
        FROM SARH.RH_AFASTAMENTOS_DIVERSOS A
        UNION ALL SELECT P.PLIC_LICE_SECAO_SUBSECAO,P.PLIC_LICE_COD_FUNCIONARIO,
        P.PLIC_INICIO_PERIODO,P.PLIC_FIM_PERIODO,'Licença cadastrada'
        FROM SARH.RH_PERIODO_LICENCA P JOIN SARH.RH_LICENCA C
        ON C.LICE_FUNC_SIGLA_SECAO_SUBSECAO=P.PLIC_LICE_SECAO_SUBSECAO
        AND C.LICE_FUNC_COD_FUNCIONARIO=P.PLIC_LICE_COD_FUNCIONARIO AND C.LICE_COD_LICENCA=P.PLIC_LICE_COD_LICENCA"""
    base=' FROM ('+events+') A JOIN SARH.RH_FUNCIONARIO F ON F.FUNC_SESB_SIGLA_SECAO_SUBSECAO=A.SECAO AND F.FUNC_COD_FUNCIONARIO=A.MATRICULA'
    overlap=f"A.INICIO<{day(upper)} AND (A.FIM IS NULL OR A.FIM>={day(start)}) AND (A.FIM IS NULL OR A.FIM>=A.INICIO)"
    if sector_id is not None:
        if not isinstance(sector_id,int) or sector_id<0:raise ValueError('Código do setor inválido')
        base+=' JOIN SARH.RH_HIST_LOTACAO H ON H.HLOT_FUNC_SIGLA_SECAO_SUBSECAO=A.SECAO AND H.HLOT_FUNC_COD_FUNCIONARIO=A.MATRICULA'
        # All three intervals must overlap simultaneously. Independent overlaps
        # with the requested period alone would include wrong historical units.
        overlap+=f" AND H.HLOT_LOTA_COD_LOTACAO={sector_id} AND H.HLOT_DAT_INIC_LOTACAO<{day(upper)} AND (H.HLOT_DAT_FIM_LOTACAO IS NULL OR H.HLOT_DAT_FIM_LOTACAO>={day(start)})"
        overlap+=' AND (H.HLOT_DAT_FIM_LOTACAO IS NULL OR A.INICIO<=H.HLOT_DAT_FIM_LOTACAO) AND (A.FIM IS NULL OR H.HLOT_DAT_INIC_LOTACAO<=A.FIM) AND (H.HLOT_DAT_FIM_LOTACAO IS NULL OR H.HLOT_DAT_FIM_LOTACAO>=H.HLOT_DAT_INIC_LOTACAO)'
    count='SELECT COUNT(DISTINCT F.FUNC_PESS_C_P_F) AS TOTAL_PESSOAS,COUNT(CASE WHEN F.FUNC_PESS_C_P_F IS NULL THEN 1 END) AS SEM_IDENTIDADE'+base+' WHERE '+overlap
    listing='SELECT DISTINCT A.SECAO AS SECAO,A.MATRICULA AS MATRICULA,N.PESS_NOME AS NOME,A.INICIO AS INICIO,A.FIM AS FIM,A.CATEGORIA AS CATEGORIA'+base+' JOIN SARH.RH_PESSOAL N ON N.PESS_C_P_F=F.FUNC_PESS_C_P_F WHERE '+overlap+' ORDER BY NOME,INICIO,SECAO,MATRICULA'
    return count,listing

def cell(value):
    value=html.escape(str(value if value is not None else 'Em aberto'),quote=False).replace('\n',' ').replace('\r',' ')
    return re.sub(r'([\\|\[\]()`*_])',r'\\\1',value)[:200]

async def answer(question,rows,user,hub):
    kind=intent(question)
    if not kind:return None
    def result(text,sources=(),mode='personnel_clarification'):
        return {'handled':True,'answer':text,'sources':list(sources),'execution_mode':mode}
    if kind=='payroll':
        selected=None
        match=re.search(r'\b(20\d{2})-(0[1-9]|1[0-2])\b',question)
        if match:selected=match[1]+'-'+match[2]
        else:
            match=re.search(r'\b(0?[1-9]|1[0-2])/(20\d{2})\b',question)
            if match:selected=match[2]+'-'+match[1].zfill(2)
            else:
                try:
                    dates=period(question)
                    if dates and dates[0].strftime('%Y-%m')==dates[1].strftime('%Y-%m'):selected=dates[0].strftime('%Y-%m')
                except ValueError:pass
        suffix='?competencia='+selected if selected else ''
        return result('[Abrir meu contracheque no SECP](https://secp.am.trf1.gov.br/meu-contracheque'+suffix+').\n\nEntre no SECP com seu próprio usuário e selecione o perfil **Servidor**. A consulta usa a matrícula vinculada à sua sessão no SECP; você poderá visualizar o demonstrativo e baixar o PDF. Os valores do contracheque não foram consultados nem copiados para este chat.',mode='personal_payroll_portal')
    if not user.get('admin'):return result('As análises de afastamentos ainda estão restritas à administração. Solicite a autorização da sua unidade e setor.',mode='personnel_access_denied')
    text=normalize(question).replace('por favor','')
    if re.search(r'\b(meus?|minhas?)\b',text):
        return result('A consulta pessoal de afastamentos exige um vínculo de matrícula verificado. Esta análise administrativa consulta a seccional e o setor informados; especifique esse escopo para continuar.')
    if re.search(r'\blicencas?\b',text) and not re.search(r'\b(afastad\w*|afastamentos?)\b',text):
        return result('O filtro exclusivo de licenças ainda não está configurado. Esta análise reúne afastamentos diversos e períodos de licença cadastrados; peça afastamentos por período e setor para consultar esse conjunto.')
    if 'em aberto' in text or re.search(r'\b(compar\w*|distribui\w*|agrup\w*|ranking|top|medic\w*|doenc\w*|saude|matern\w*|patern\w*|ferias|cid|aposent\w*|remuner\w*|inativos?|ativos?|apenas|somente|exceto|menos|mais|tipos?|motivos?|por|subordinad\w*|subsetor\w*|subunidad\w*|iniciad\w*|terminad\w*)\b',text):
        return result('Esta análise pronta considera afastamentos diversos e períodos de licença cadastrados, por período e setor exato. Seu pedido contém critérios adicionais ainda não configurados; informe apenas esse escopo para evitar uma contagem que ignore seus filtros.')
    if len(rows)!=1:
        return result('Informe uma seccional para a análise de afastamentos. Fontes autorizadas: '+', '.join(r['name'] for r in rows)+'.')
    row=await hub.source(str(rows[0]['id']),user,active=True)
    config=(row.get('semantic') or {}).get('personnel_analytics',{})
    if not config.get('enabled'):return result('A análise de afastamentos ainda não foi validada nesta fonte. Solicite a configuração à administração.')
    try:
        dates=period(question);selected_sector=sector(question)
    except ValueError as error:return result(str(error))
    if dates is None:return result('Informe o período, por exemplo “de 01/10/2026 a 31/10/2026” ou “hoje”. Você também pode informar a sigla exata do setor.')
    policy=closed_policy(row['catalog']['objects']);start,end=dates
    async def execute(sql,limit=100):
        current=await hub.authorize_execution(str(row['id']),user,personnel=True)
        if not (current.get('semantic') or {}).get('personnel_analytics',{}).get('enabled'):
            raise HTTPException(403,'A análise de pessoal foi desativada durante a consulta')
        if current.get('updated_at')!=row.get('updated_at'):raise HTTPException(409,'A fonte foi alterada durante a análise; envie a pergunta novamente')
        began=time.monotonic()
        try:
            value=await hub.worker('oracle','execute_readonly_query',current['connection'],hub.store.decrypt(current['credential']),policy=policy,
                request={'query':sql,'object':'SARH.RH_AFASTAMENTOS_DIVERSOS','limit':limit,'offset':0})
            await hub.audit(user,'query.execute',row['id'],query=sql,kind='oracle',rows=value['row_count'],duration=time.monotonic()-began,mode='hash_only')
            return value
        except Exception:
            await hub.audit(user,'query.execute',row['id'],query=sql,kind='oracle',status='error',duration=time.monotonic()-began,error='personnel_query_failed',mode='hash_only')
            raise
    sector_id=None;label='todas as lotações'
    if selected_sector:
        lookup='SELECT LOTA_COD_LOTACAO,LOTA_SIGLA_LOTACAO,LOTA_DSC_LOTACAO FROM SARH.RH_LOTACAO WHERE UPPER(LOTA_SIGLA_LOTACAO)=UPPER('+quoted(selected_sector)+') OR UPPER(LOTA_DSC_LOTACAO)=UPPER('+quoted(selected_sector)+')'
        options=await execute(lookup,20)
        if not options['rows']:return result('Não encontrei um setor com essa sigla ou nome exato. Informe a sigla cadastrada no SARH.')
        if options['row_count']!=1 or options['incomplete']:return result('O nome informado corresponde a mais de um setor. Informe a sigla que identifica unicamente o setor no SARH.')
        sector_id=int(options['rows'][0][0]);label=cell(options['rows'][0][1])+' — '+cell(options['rows'][0][2])
    count_sql,list_sql=queries(start,end,sector_id)
    counted=await execute(count_sql,1);total=int(counted['rows'][0][0])
    text=f'**{total} pessoas distintas** com afastamentos ou períodos de licença cadastrados entre **{start:%d/%m/%Y} e {end:%d/%m/%Y}**, em **{label}**. Fonte: **{row["name"]}**.'
    if len(counted['rows'][0])>1 and int(counted['rows'][0][1]):text+=' Há registros sem identificação de pessoa que não entraram nessa contagem.'
    tables=['SARH.RH_AFASTAMENTOS_DIVERSOS','SARH.RH_PERIODO_LICENCA','SARH.RH_LICENCA','SARH.RH_FUNCIONARIO']
    is_list=bool(re.search(r'\b(lista|liste|listar|mostre|monte|relacione|quem|nomes)\b',normalize(question)))
    if is_list and total:
        listed=await execute(list_sql);tables.append('SARH.RH_PESSOAL')
        text+='\n\n| Seção | Matrícula | Nome | Início cadastrado | Fim cadastrado | Registro |\n|---|---|---|---|---|---|\n'
        text+='\n'.join('| '+' | '.join(cell(v) for v in values)+' |' for values in listed['rows'])
        if listed['incomplete']:text+='\n\nExibidos até 100 registros. A contagem de pessoas acima foi calculada integralmente no banco.'
    if sector_id is not None:tables.extend(['SARH.RH_HIST_LOTACAO','SARH.RH_LOTACAO'])
    text+='\n\nEscopo: afastamentos diversos e períodos de licença cadastrados, incluindo períodos em aberto. Férias e afastamentos de tempo de serviço averbado não estão incluídos. A contagem elimina repetições da mesma pessoa. A consulta não é uma comprovação de presença ou ausência no ponto.'
    if sector_id is not None:text+=' O filtro considera a lotação histórica simultânea ao afastamento e ao período solicitado, sem incluir setores subordinados automaticamente.'
    return result(text,[{'id':str(row['id']),'name':row['name'],'objects':tables}],'validated_personnel_analysis')
