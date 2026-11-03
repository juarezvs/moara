"""Draft intent and reviewable document structure; no invented case facts."""
import re
from moara.legal_mcp.contracts import Norm,public_topic
from moara.legal_mcp.texts import folded

PORTAL_DRAFT='MODO DE TRABALHO: prepare um RASCUNHO para revisão humana. Preserve campos pendentes e diferencie fatos informados de hipóteses. Não pratique atos oficiais.'

def clean_request(text):
    # Remove only known presentation instructions. They are not legal subjects.
    text=text.replace(PORTAL_DRAFT,'')
    return re.sub(r'(?m)^REDAÇÃO: (?:objetiva, sem perder as informações necessárias\.|desenvolva os pontos relevantes, dentro do contexto disponível\.)\s*','',text).strip()

def requested(text):
    value=folded(clean_request(text))
    return bool(re.search(r'\b(?:crie|criar|elabore|elaborar|redija|redigir|prepare|preparar|faca|fazer|monte|montar|rascunhe|quero|preciso)\b',value)
                and re.search(r'\b(?:peticao|requerimento|contestacao|recurso|inicial)\b',value))

def subject(text):
    text=clean_request(text)
    text=re.sub(r'\b(?:crie|criar|elabore|elaborar|redija|redigir|prepare|preparar|faça|faca|fazer|monte|montar|rascunhe|petiç[ãa]o|peticao|requerimento|contestaç[ãa]o|contestacao|recurso|inicial|minuta|rascunho|fundamentaç[ãa]o|fundamentacao|robust[ao]|complet[ao]|detalhad[ao])\b',' ',text,flags=re.I)
    value=public_topic(text)
    if value:return value
    # A personal narrative must not be sent to a public search engine. Known
    # public concepts can still provide a research lead without names or IDs.
    terms=re.findall(r'\b(?:aposentadoria|pescador|pescadora|artesanal|segurado especial|segurada especial|previdenci[áa]ri[ao]|rural|pens[ãa]o|alimentos|usucapi[ãa]o|indenizaç[ãa]o|indenizacao|consumidor|licitaç[ãa]o|licitacao)\b',text,re.I)
    return public_topic(' '.join(dict.fromkeys(v.casefold() for v in terms))) if terms else ''

def special_fisher(text):
    value=folded(clean_request(text))
    return 'aposentadoria' in value and bool(re.search(r'\bpescador(?:a)?\b',value)) and bool(re.search(r'\bsegurad[oa] especial\b',value))

def research_leads(text):
    # Curated source-location leads, not an assertion of eligibility or vigency.
    # The MCP must freshly retrieve and identify the norm before any use.
    if special_fisher(text):
        return [Norm(kind='LEI',number=8213,year=1991,articles=['11','25','38-a','38-b','39','48','55','106'])]
    return []

def validate_claims(value):
    for paragraph in value.get('paragraphs',[]):
        text=folded(paragraph.get('text',''))
        if re.search(r'\b(?:requerente|autor|autora|cliente)\b',text) and re.search(r'enquadrando-se|enquadra-se|preenche|preencheu|comprovou|completa|completou|possui|implementou|faz jus|tem direito',text):
            if not re.search(r'\b(?:se|caso|desde que)\s+(?:sejam?\s+)?(?:comprovad|demonstrad)|condicionad|a confirmar|a comprovar',text):
                raise ValueError('unproven_individual_fact_in_draft')

def scope_issues(paragraphs,package):
    text=folded(' '.join(e.get('text','') for n in package.get('norms',[]) for e in n.get('excerpts',[])))
    if not re.search(r'individualmente\s+ou\s+em\s+regime\s+de\s+economia\s+familiar',text):return []
    issues=[]
    for index,paragraph in enumerate(paragraphs):
        value=folded(paragraph['text'])
        mandatory=re.search(r'(?:regime de )?economia familiar.{0,80}\b(?:fundamental|obrigatori\w*|necessari\w*|indispensavel)\b|\b(?:exige|exigencia|deve|precisa)\b.{0,70}regime de economia familiar|\bpescador\w*\b.{0,75}\bdeve\b',value) if 'economia familiar' in value else None
        qualified=re.search(r'\bindividualmente\b|\b(?:quando|se)\b.{0,50}(?:familiar|adotad|exercid)|\bcaso\s+(?:seja|sejam|adotad|exercid)\w*.{0,50}familiar|n[aã]o (?:e |se )?(?:obrigatori|exige)',value)
        regime_as_requirement=re.search(r'\b(?:tal|esse|este|o) regime\b.{0,30}\b(?:requisito|pressuposto|obrigatori\w*)\b',value) if 'economia familiar' in value else None
        if regime_as_requirement or mandatory and not qualified:issues.append({'index':index,'reason':'A fonte permite atividade individual OU economia familiar; não converter a segunda alternativa em requisito universal.'})
    return issues

def render(query,grounded,package):
    value=folded(clean_request(query));fisher=special_fisher(query)
    administrative=bool(re.search(r'\b(?:administrativ[oa]|requerimento ao inss)\b',value))
    document='REQUERIMENTO ADMINISTRATIVO' if administrative else 'PETIÇÃO INICIAL' if fisher else next((label for word,label in [('contestacao','CONTESTAÇÃO'),('recurso','RECURSO'),('requerimento','REQUERIMENTO')] if word in value),'PETIÇÃO')
    subject_line='DE CONCESSÃO DE APOSENTADORIA — SEGURADO ESPECIAL PESCADOR' if fisher else '— [OBJETO E PROVIDÊNCIA A DEFINIR]'
    lines=['# RASCUNHO — '+document+' '+subject_line,
        '**Premissas para revisão:** documento preparatório; os campos entre colchetes precisam ser preenchidos e conferidos. A pesquisa das fontes não comprova os fatos nem o direito ao benefício.']
    if fisher:
        lines.append('**Informado no pedido:** pretende-se uma petição de aposentadoria para pescador indicado como segurado especial. **Hipótese de estrutura:** aposentadoria por idade do segurado especial; a modalidade precisa ser confirmada. Idade, sexo, períodos de pesca, DER, decisão do INSS e provas devem ser preenchidos ou conferidos a partir do relato e dos documentos; dados ausentes não foram presumidos.')
    lines += ['## 1. Endereçamento e qualificação',
        ('**AO INSTITUTO NACIONAL DO SEGURO SOCIAL — INSS / [UNIDADE COMPETENTE]**' if administrative else '**AO JUÍZO COMPETENTE DA [SUBSEÇÃO/COMARCA] — [RITO E COMPETÊNCIA A CONFERIR]**'),
        '**[NOME DO REQUERENTE]**, [nacionalidade], [estado civil], [profissão], [data de nascimento], CPF [número], residente em [endereço], por [advogado/procurador, se cabível, qualificação e procuração], apresenta o presente pedido '+('perante o INSS.' if administrative else 'em face do INSS, [QUALIFICAÇÃO E REPRESENTAÇÃO PROCESSUAL A CONFERIR].' if fisher else 'em face de [PARTE CONTRÁRIA E QUALIFICAÇÃO].'),
        '## 2. Dos fatos e do pedido administrativo']
    if fisher:
        lines += ['O requerente afirma exercer a pesca em **[LOCAL]**, no período de **[INÍCIO] a [FIM]**, em **[CONDIÇÕES DA ATIVIDADE E ORGANIZAÇÃO DO TRABALHO A DESCREVER]**. Esses campos são informações a levantar, e não fatos considerados comprovados nesta minuta.',
            '**[SE HOUVE PEDIDO ADMINISTRATIVO, COMPLETAR:]** Na data de **[DER — DATA DE ENTRADA DO REQUERIMENTO]**, foi apresentado ao INSS o pedido de **[ESPÉCIE DO BENEFÍCIO]**, NB/protocolo **[NÚMERO]**. **[SE HOUVE DECISÃO, INFORMAR SUA DATA E FUNDAMENTO; SE HÁ OMISSÃO, DESCREVER O ANDAMENTO REAL. NÃO AFIRMAR A EXISTÊNCIA DE PEDIDO OU INDEFERIMENTO SEM CONFERÊNCIA.]**',
            'A controvérsia a enfrentar é **[MOTIVO CONCRETO DO INDEFERIMENTO/QUESTÃO CONTROVERTIDA]**. A idade, os períodos alegados, a situação previdenciária e os documentos serão confrontados com a legislação aplicável nas respectivas datas.']
    else:lines.append('[NARRAR CRONOLOGICAMENTE OS FATOS EFETIVAMENTE INFORMADOS, AS PROVAS E A PROVIDÊNCIA PRETENDIDA; NÃO ACRESCENTAR DATAS, DECISÕES OU DOCUMENTOS INEXISTENTES.]')
    lines += ['## 3. Da fundamentação jurídica']
    if grounded.get('answer'):
        lines.append(grounded['answer'])
    else:
        lines.append('**[FUNDAMENTAÇÃO PENDENTE DE CONFERÊNCIA]** As tentativas de pesquisa não recuperaram texto oficial suficiente nesta consulta. A estrutura segue disponível para edição, mas não foram inseridos artigos, precedentes ou requisitos como se estivessem confirmados.')
    if fisher:
        # Render this sensitive alternative directly from an exact source phrase,
        # without asking the model to turn one permitted form into a requirement.
        for i,norm in enumerate(package.get('norms',[]),1):
            for j,excerpt in enumerate(norm.get('excerpts',[]),1):
                if re.search(r'individualmente\s+ou\s+em\s+regime\s+de\s+economia\s+familiar',excerpt.get('text',''),re.I):
                    source=excerpt.get('source') or norm.get('source')
                    if source:lines.append('**Forma de exercício da atividade:** o dispositivo consultado admite atuação **individualmente ou em regime de economia familiar**. A economia familiar não foi adotada como exigência universal nesta minuta. [L'+str(i)+'.'+str(j)+']('+source+')')
                    break
        lines.append('**Aplicação aos fatos — completar após a prova:** demonstrar, separadamente, **[ENQUADRAMENTO COMO SEGURADO ESPECIAL]**, **[REQUISITO ETÁRIO NA DATA PERTINENTE]**, **[PERÍODO DE ATIVIDADE/CARÊNCIA]** e **[DOCUMENTOS QUE SUSTENTAM CADA PERÍODO]**. A indicação de uma norma não supre a demonstração desses elementos.')
    lines += ['## 4. Da prova e dos pontos controvertidos',
        '[RELACIONAR OS DOCUMENTOS EFETIVAMENTE DISPONÍVEIS, SUAS DATAS, TITULARES E O FATO QUE CADA UM SUSTENTA. INDICAR DIVERGÊNCIAS, PERÍODOS SEM COBERTURA E OUTRAS PROVAS A REQUERER, COM PERTINÊNCIA AO CASO.]']
    if fisher:lines.append('Conferir o CNIS e o processo administrativo, a documentação da atividade pesqueira e eventual autodeclaração. Não se presume que registro de pescador, recebimento de seguro-defeso ou declaração isolada satisfaça automaticamente todos os requisitos da aposentadoria.')
    lines += ['## 5. Dos pedidos',
        'Diante do exposto, requer-se, **conforme os fatos e os fundamentos que forem confirmados**:',
        '1. [RECEBIMENTO E PROCESSAMENTO DO PEDIDO, COM DEFINIÇÃO DO RITO E DA COMPETÊNCIA, QUANDO JUDICIAL].',
        ('2. O reconhecimento da condição de segurado especial e dos períodos de atividade **[PERÍODOS]**, na extensão efetivamente comprovada.' if fisher else '2. [PROVIDÊNCIA PRINCIPAL, COM OBJETO, DESTINATÁRIO E EXTENSÃO PRECISOS].'),
        ('3. A concessão de **[MODALIDADE DA APOSENTADORIA]**, se demonstrados os requisitos aplicáveis, com termo inicial **[DATA E FUNDAMENTO A CONFERIR]** e efeitos financeiros **[A APURAR, SE CABÍVEIS]**.' if fisher else '3. [EFEITOS E PEDIDOS SUBSIDIÁRIOS, SOMENTE SE PERTINENTES E FUNDAMENTADOS].'),
        '4. A apreciação das provas indicadas e a produção de **[PROVAS PERTINENTES A ESPECIFICAR]**.',
        '5. [PEDIDOS EVENTUAIS DE GRATUIDADE, TUTELA, INTIMAÇÕES, ENCARGOS E DEMAIS CONSEQUÊNCIAS PROCESSUAIS: INCLUIR APENAS APÓS CONFERIR PRESSUPOSTOS, DOCUMENTOS E FUNDAMENTAÇÃO].',
        '## 6. Valor, fechamento e revisão',
        '**Valor da causa, quando cabível:** R$ **[VALOR A CALCULAR, COM MEMÓRIA E CRITÉRIO JURÍDICO A CONFERIR]**.',
        'Termos em que, pede deferimento.\n\n[LOCAL], [DATA].\n\n[NOME E ASSINATURA DO RESPONSÁVEL / OAB, QUANDO CABÍVEL].',
        '### Antes de utilizar',
        'Preencher os campos, confrontar os fatos e documentos com as fontes e revisar pedidos, competência e cálculos. Nenhuma ação foi protocolada ou assinada. A data de consulta das fontes não foi adotada como DER, data de aquisição do direito ou data dos fatos.']
    return '\n\n'.join(lines)
