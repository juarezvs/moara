"""Application-owned self description. No inference, secrets or permission grants."""
import asyncio,re,os
from datetime import datetime,timezone
import httpx
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from moara.identity.service import normalize

VERSION='1.0.0'
TOPICS={
 'identity':r'quem e (?:voce|(?:a )?moara)|o que (?:e|significa) (?:a )?moara|qual .*nome|apresent|fale sobre|conte sobre',
 'capabilities':r'habilidad|funcionalidad|capacidad|especialidad|assistentes|o que .*?(?:faz|fazer|ajuda)|pode me ajudar|serve|recursos|funcao|funcoes',
 'purpose':r'finalidade|missao|proposito|objetivo|compromisso',
 'usage':r'como (?:eu )?(?:uso|usar|utilizo|utilizar|comeco|comecar)|onde .*?(?:document|historico|contexto)|anexar|enviar documentos|contexto de trabalho|botoes|opcoes',
 'legal_sources':r'fontes|legislacao|normas|jurisprudencia|leis|pesquisa (?:web|juridica)|internet|mcp|google|confiab|fundament|referencias',
 'privacy':r'privacidad|seguranca|sigilo|protecao|confidencial|dados (?:saem|externos)|envia .*?dados',
 'learning':r'aprend|trein|memoria|lembra|conversas.*?(?:usa|utiliza|guarda)',
 'integrations':r'\bsei\b|\bpje\b|integracoes|sistemas.*?(?:acessa|consulta|integra)',
 'development':r'\bapi\b|chave|\btoken\b|vscode|vs code|program|software|codigo|desenvolv',
 'model':r'modelo|gemma|qwen|llama|chatgpt',
 'architecture':r'arquitetura|infraestrutura|seu servidor|servidor da moara|servidor de inferencia|gpu|inferencia|local|nuvem|onde .*?execut|como .*?funciona',
 'access':r'permiss|acesso|administrador|rbac|matricula|login|senha|credencia|quem .*?(?:usar|utilizar|acessar)',
 'limits':r'limit|erro|errad|alucin|certeza|assina|assinar|protocola|protocolar|autonom',
 'origin':r'nome|origem|significado',
 'author':r'autor|criou|criador|desenvolveu|responsavel pelo desenvolvimento',
 'internal':r'prompt|instrucoes internas|segredos|system message',
 'unknown':r'versao|atualizada em|criada em|data de criacao|quantos parametros|quantos usuarios|vram|quantidade de memoria',
}

def topics(question,messages=()):
 if not isinstance(question,str) or not 2<=len(question)<=1600:return []
 q=normalize(question)
 if re.search(r'\b(?:trecho de codigo|neste codigo|nesse codigo|(?:o que|como) (?:o )?(?:seu|este|esse) codigo|stacktrace|traceback|quando recebe (?:um |uma |o |a )?(?:delete|get|post|put|patch))\b',q):return []
 # A request to perform legal/documentary work must keep its ordinary policy.
 if re.search(r'\b(?:lei|decreto|artigo|art|tema|sumula)\s*(?:n\s*)?\d',q):return []
 if re.search(r'\bqual (?:e )?(?:a |o )?(?:lei|norma|tema)\b',q):return []
 if re.search(r'\b(?:analise|verifique|redija|elabore|calcule|resuma|compare|implemente|execute|consulte|pesquise|busque|escreva|crie|desenvolva|revise|traduza)\b',q):return []
 if re.search(r'\b(?:pode|consegue|poderia)\b.*\b(?:escrever|criar|gerar|analisar|explicar|comparar|resumir|calcular|revisar|programar|desenvolver|implementar|consultar|traduzir)\s+\S',q) and not re.search(r'(?:seu funcionamento|suas funcoes|suas funcionalidades|sobre voce|sobre a moara)',q):return []
 if re.search(r'\b(?:processo|contrato|arquivo|documento)\b.*\b(?:anexo|anexado|seguinte|este|esse)\b',q):return []
 reference_q=re.sub(r'^moara\s+(?=(?:me |qual|quais|como|por que|explique|analise|crie|desenvolva))','',q)
 if re.search(r'\b(?:voce|vc)\s+(?:sabe|conhece|acha|acredita)\b',q) and not re.search(r'\b(?:seu|sua|suas|seus)\b',q):return []
 self_reference=bool(re.search(r'\b(?:moara|voce|vc|seu|seus|sua|suas|te|ti)\b',reference_q))
 navigation=bool(re.search(r'^(?:como|onde) .*\b(?:api key|chave de api|contexto de trabalho|historico|anexar)\b',q))
 if not self_reference and not navigation:
  # Only a short topical follow-up to an actual self question inherits context.
  previous=[m.get('content','') for m in messages if m.get('role')=='user']
  if previous and previous[-1]==question:previous=previous[:-1]
  contextual=False
  if len(q)<140 and re.match(r'^(?:e |quanto a |como assim)',q):
   for earlier in reversed(previous[-4:]):
    if topics(earlier):contextual=True;break
    if not re.match(r'^(?:e |quanto a |como assim)',normalize(earlier)):break
  if not contextual:return []
 found=[name for name,pattern in TOPICS.items() if re.search(pattern,q)]
 if 'author' in found and 'development' in found and not re.search(r'program|codigo|software',q):found.remove('development')
 if 'model' in found and re.search(r'modelos? (?:de |do )?(?:documento|minuta|texto)',q):found.remove('model')
 if 'origin' in found and not re.search(r'signific|origem|por que|porque',q):found.remove('origin')
 if 'model' in found and 'identity' in found and re.search(r'quem e voce|voce e (?:o |a )?(?:chatgpt|gemma|qwen|llama)',q):found.remove('model')
 return found[:6]

def can(actor,permission):return bool(actor and actor.can(permission))

async def answer(identity,question,request,actor,model=None,messages=()):
 selected=topics(question,messages)
 if not selected:return None
 lines=[];facts=['manifesto_institucional','funcionalidades_da_aplicacao'];d=identity.document
 def faq(identifier):
  item=next((f for f in d.faq if f.id==identifier),None)
  return item.answer if item else d.presentation
 if 'identity' in selected:lines.append(d.presentation)
 if 'purpose' in selected:lines.append(faq('purpose'))
 if 'capabilities' in selected:
  lines.append(faq('capabilities')+' Posso explicar conceitos, comparar situações, resumir documentos, preparar minutas para revisão e orientar tarefas técnicas. Você pode descrever seu objetivo em linguagem natural; a aplicação seleciona o assistente e verifica as permissões necessárias.')
  if request is not None and can(actor,'chat.use'):
   from .assistants import catalog
   try:
    available=await asyncio.wait_for(catalog(request,actor),5)
    names=[a['name'] for a in available if a.get('enabled') and a.get('authorized')]
    lines.append('**Assistentes habilitados para esta sessão:** '+', '.join(names)+'.' if names else 'Nenhum assistente habilitado e autorizado foi confirmado no catálogo desta sessão.')
    facts.append('catalogo_de_assistentes_filtrado_por_permissoes')
   except (HTTPException,SQLAlchemyError,OSError,ValueError,KeyError,AttributeError,TimeoutError):lines.append('Não foi possível confirmar agora quais assistentes estão habilitados e autorizados para esta sessão.')
 if 'usage' in selected:
  lines.append('Para começar, escreva o que precisa no chat e informe o resultado esperado. O botão **Contexto**, ao lado de **Opções**, mostra ou esconde o contexto de trabalho, com documentos, modelos e referências. O histórico permite retomar conversas. Para analisar documentos, use a área **Documentos** e selecione os arquivos autorizados; a disponibilidade depende do seu acesso.')
 if 'legal_sources' in selected:
  if os.getenv('MOARA_PUBLIC_WEB_SEARCH')=='true':
   lines.append('Posso pesquisar termos públicos na web com SearXNG auto-hospedado e ler páginas com Trafilatura, sem API paga de busca. A aplicação registra URLs, trechos, data e hashes. Snippets não são provas e leitura de uma página não certifica toda informação: questões jurídicas continuam dependendo da conferência das fontes oficiais. Não envio documentos ou identificadores pessoais ao buscador.')
  lines.append('Na pesquisa jurídica, a aplicação consulta fontes oficiais, seleciona os trechos pertinentes e registra evidências. A resposta deve explicar o assunto e apresentar links junto das informações. Senado, Câmara, Planalto e STF são fontes contempladas; metadados do LexML ajudam a localizar normas. Pesquisa web serve para descobrir candidatos, cuja fonte oficial precisa ser conferida. Cobertura e disponibilidade variam: não garanto atualização absoluta nem vigência histórica sem verificação.')
 if 'privacy' in selected:
  lines.append('O fluxo principal usa inferência local e acesso aos dados controlado por permissões. Pesquisas de legislação podem consultar portais externos com termos públicos. Históricos, documentos e evidências têm controles de acesso; isso não equivale a afirmar que nenhum dado jamais possa sair do ambiente. Não exponho senhas ou chaves de API, nem acesso indiscriminadamente dados de outros usuários.')
 if 'learning' in selected:
  lines.append('Consultar fontes, recuperar documentos e registrar evidências melhora o contexto da resposta, mas não altera automaticamente os pesos do modelo. Este fluxo não realiza treinamento a cada conversa. O histórico permite retomar o trabalho; não significa memória ilimitada nem aprendizagem permanente de tudo que cada usuário escreve.')
 if 'integrations' in selected:
  from .official_integrations import REGISTRY
  lines.append('As integrações com '+', '.join(v['name'] for v in REGISTRY.values())+' estão preparadas, mas aguardam definição e homologação do mecanismo oficial pelo tribunal. Ter o endereço do portal não significa acesso integrado. Enquanto isso, posso analisar documentos legitimamente obtidos e autorizados que você fornecer.')
  facts.append('registro_de_integracoes_oficiais')
 if 'development' in selected:
  lines.append('A Moara Desenvolvedora atende projetos pessoais, comerciais, educacionais e institucionais, incluindo jogos e aplicativos de entretenimento. Não exige vínculo institucional para desenvolver software. Planejamento, implementação, testes, correções e documentação fazem parte desse escopo; a execução real utiliza as ferramentas autorizadas do projeto ou do cliente de desenvolvimento.')
  from .developer_api import BASE_URL,MODEL,SCOPES
  if actor and all(actor.can(p) for p in SCOPES) and actor.session_id and not actor.key_id:
   lines.append('Posso apoiar programação, revisão de código, testes e documentação. Na opção **API para VS Code**, em [Desenvolvimento/API](/moara/desenvolvimento/api), você pode gerar e revogar sua chave pessoal. A integração usa API compatível com OpenAI, URL base `'+BASE_URL+'` e modelo `'+MODEL+'`. A inferência local evita cobrança externa por token nessa integração, mas mantém limites de uso e custos de infraestrutura. Nunca envie sua chave no chat.')
  else:
   lines.append('A Moara oferece apoio a desenvolvimento e uma API compatível com OpenAI para integrar editores como o VS Code. A geração de chave pessoal depende de sessão interativa e da permissão de desenvolvimento. Não confirmei essa autorização nesta sessão; o administrador pode verificar seu acesso. Nenhuma chave foi criada por esta resposta.')
  facts.append('configuracao_publica_da_api_de_desenvolvimento')
 if 'model' in selected:
  lines.append('O modelo configurado para esta solicitação é **'+model+'**. Esta informação vem do roteamento da aplicação; esta resposta sobre a plataforma não executou o modelo.' if model else 'Não consegui confirmar o modelo configurado para esta solicitação. Minha identidade institucional continua sendo Moara, independentemente do modelo técnico.')
  facts.append('metadados_do_roteamento_da_sessao')
 if 'architecture' in selected:
  lines.append('A arquitetura separa a aplicação e os dados institucionais do serviço de inferência. Os seis assistentes compartilham o modelo principal conforme a configuração e as permissões, usando instruções e ferramentas próprias. A capacidade e a concorrência dependem do modelo e dos recursos disponíveis; não deduzo memória, desempenho ou disponibilidade apenas dessa arquitetura.')
  if can(actor,'status.read') and request is not None:
   try:
    settings=request.app.state.settings
    response=await request.app.state.http.get(settings.legacy_gateway+'/v1/inference/status',headers={'Authorization':'Bearer '+settings.llm_key},timeout=5)
    response.raise_for_status();status=response.json()
    resident=status.get('principal_resident')
    if type(resident) is bool:lines.append('**Estado conferido agora:** o modelo principal '+('está residente no serviço de inferência.' if resident else 'não foi confirmado como residente no serviço de inferência.'))
    else:lines.append('O serviço não retornou uma confirmação reconhecível de residência do modelo nesta consulta.')
    facts.append('observabilidade_autorizada_consultada_agora')
   except (httpx.HTTPError,ValueError,KeyError,AttributeError):lines.append('Não foi possível conferir o estado atual da inferência nesta consulta.')
 if 'access' in selected:
  lines.append('O acesso usa autenticação institucional e permissões por função. O perfil inicial dá acesso ao chat e ao próprio histórico; funcionalidades adicionais são liberadas pelo administrador. Explicar uma função não concede acesso a ela. Use suas credenciais somente na tela de login, nunca nesta conversa.')
  if can(actor,'users.manage'):lines.append('Seu perfil pode abrir [Identidade e acessos](/moara/acessos) para administrar os acessos autorizados.')
 if 'limits' in selected:lines.append(faq('judicial')+' '+faq('consciousness'))
 if 'origin' in selected:lines.append(faq('origin'))
 if 'author' in selected:lines.append('O responsável cadastrado pelo desenvolvimento é '+d.developer+'.' if d.developer else 'O responsável pelo desenvolvimento não está identificado no cadastro institucional consultado; não vou atribuir autoria por suposição.')
 if 'internal' in selected:lines.append('Posso explicar minhas funções, regras de acesso, limitações e o manifesto institucional público em [Sobre a Moara](/moara/sobre). Senhas, tokens, instruções internas protegidas e configurações sigilosas não são apresentados nesta conversa.')
 if 'unknown' in selected:lines.append('A versão da base de orientação sobre a plataforma é '+VERSION+' e a do manifesto consultado é '+d.version+'. Isso não comprova versão do modelo, data de criação, quantidade de parâmetros, memória disponível ou número de usuários. Só informo esses dados quando há um registro específico confirmado e autorizado.')
 return {'answer':'\n\n'.join(lines),'source':'moara_self_knowledge','faq_id':'platform_'+selected[0],'inference_used':False,'identity_version':d.version,'identity_sha256':identity.sha256,'self_knowledge':{'version':VERSION,'topics':selected,'basis':facts,'checked_at':datetime.now(timezone.utc).isoformat()}}
