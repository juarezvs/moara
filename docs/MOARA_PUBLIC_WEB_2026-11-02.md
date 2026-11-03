# Atendimento e pesquisa web da Moara

## Escolha para o framework atual

A Moara mantém Angular no portal, FastAPI/Python no gateway e um MCP privado com Streamable HTTP. A integração implementada usa **SearXNG auto-hospedado + Trafilatura 2.3.1**, diretamente nesse MCP.

Não é necessário inserir outra aplicação completa, treinar o modelo do zero ou contratar uma API de busca. Os wrappers websearch-skill/tavily-open não foram adicionados: o MCP existente já fornece autenticação, contratos, rastreabilidade e ligação com a aplicação. Trafilatura fornece a extração, sem outro servidor de crawling.

SearXNG usa imagem oficial fixada pelo digest registrado em runtime/searxng-service.json. O serviço não publica portas no host; somente o MCP recebe acesso à sua rede privada. O container tem reinício automático, memória limitada e configuração privada. A chave interna de configuração não é uma chave de API paga.

## Atendimento sem justificativa de finalidade

A política operacional é agora versionada em moara/identity/attendance.py. A aplicação identifica internamente a especialidade adequada e não pergunta qual é a finalidade institucional para atender um pedido. Perguntas gerais recebem respostas diretas. Informações concretas indispensáveis ainda podem ser solicitadas, como documento ausente, objeto ambíguo ou data dos fatos relevante para a aplicação de uma norma.

O manifesto histórico de identidade foi preservado com seu hash. Suas antigas restrições de finalidade não são reproduzidas no prompt operacional atual. Não foram concedidas permissões de arquivos, conectores, administração, assinatura ou prática autônoma de atos oficiais.

Contas autorizadas apenas para chat podem conversar e pesquisar informações públicas sem receber ferramentas de documentos, desenvolvimento ou dados institucionais. A seleção manual de assistentes e o uso de documentos continuam obedecendo ao RBAC.

## Busca, leitura e verificação

1. A aplicação reconhece pedidos de pesquisa/verificação, sem depender de o modelo lembrar de usar uma ferramenta.
2. Somente termos públicos seguem para o buscador; documentos, relatos privados e identificadores pessoais não são enviados por esse fluxo.
3. O SearXNG retorna candidatos. O MCP baixa páginas HTTPS permitidas e extrai seu conteúdo com Trafilatura.
4. A síntese responde à pergunta usando trechos recuperados. As citações usam identificadores existentes; as passagens de apoio precisam corresponder literalmente aos trechos lidos.
5. A aplicação insere os links das fontes e registra data, hashes, trechos, passagens de apoio e cópias comprimidas das páginas em evidências criptografadas, isoladas por usuário/chave.

Pedidos explícitos podem ser feitos no chat, por exemplo: “Pesquise na web a documentação oficial do Angular Signals e explique como funcionam.” A interface informa a etapa de busca e leitura.

As instruções em páginas são dados não confiáveis. URLs privadas, credenciais em URLs, portas arbitrárias, redirecionamentos para destinos privados e resolução DNS que inclua endereços privados são rejeitados. A conexão usa o IP público conferido, preservando Host, SNI e validação TLS. O fluxo respeita robots.txt, limita tamanho, tempo, concorrência e redirecionamentos, e não resolve nem contorna CAPTCHAs.

## Legislação e jurisprudência

O SearXNG é prioritário na descoberta web de candidatos jurídicos. Ele não substitui o texto oficial, a identificação da norma, a data relevante, o exame de alterações nem a conferência jurisprudencial.

A recuperação passou a preservar o assunto completo antes de consultar a web, usando vocabulário dos catálogos oficiais sem adivinhar números de leis. URLs encontradas e suas contrapartes HTML são apenas candidatas até a resposta oficial ser recuperada e a identidade conferida.

Questões jurídicas seguem pelo MCP de normas/jurisprudência e pelo controle de saída existente. Um domínio oficial não certifica sozinho veracidade de toda afirmação, vigência histórica ou efeitos no caso concreto. O campo official_domain das evidências web identifica domínios brasileiros gov.br/jus.br/leg.br; não é um cadastro universal de fontes oficiais estrangeiras ou de fornecedores técnicos.

## Disponibilidade e custos

Não há cobrança de uma API paga de pesquisa nesta integração. Permanecem os custos do servidor, energia, armazenamento e manutenção. Os motores consultados podem impor limites, negar acesso, suspender consultas ou apresentar CAPTCHA. Isso foi observado nos testes; o sistema usa motores alternativos e registra lacunas. Não há promessa de pesquisa ilimitada, cobertura integral ou atualização instantânea de toda a legislação.

## Legalyze e RAG

O artigo Legalyze descreve indexação hierárquica sensível à estrutura e recuperação lexical/semântica combinada. Isso é uma referência pertinente para evoluir a indexação de documentos jurídicos brasileiros. O repositório indicado no artigo retornou 404 durante esta análise; seu código e sua licença não foram validados para incorporação.

Esta entrega mantém o RAG atual e a recuperação estruturada de dispositivos legais. Não substitui nem reindexa silenciosamente o acervo documental e não treina pesos do modelo com as páginas consultadas.

## Referências primárias

- [API de pesquisa do SearXNG](https://docs.searxng.org/dev/search_api.html)
- [Configuração de busca e suspensão dos motores](https://docs.searxng.org/admin/settings/settings_search.html)
- [Instalação em container](https://docs.searxng.org/admin/installation-docker.html)
- [Trafilatura: extração de conteúdo](https://trafilatura.readthedocs.io/en/latest/corefunctions.html)
- [Trafilatura 2.3.1 e arquivos de distribuição](https://pypi.org/project/trafilatura/2.3.1/)
- [HTTP Core: conexão com IP conferido e SNI](https://www.encode.io/httpcore/extensions/#sni-hostname)
- [Artigo Legalyze](https://onlinelibrary.wiley.com/doi/10.1111/exsy.70415)

## Publicação e validação

Entrega publicada em 02/11/2026 no portal principal. Gateway e MCP estão saudáveis. A imagem publicada é a mesma aprovada nos testes; a inferência não foi reiniciada e não houve migração de banco.

| Verificação | Resultado |
|---|---|
| Testes unitários do backend e MCP | 280 aprovados |
| Testes reais pela API em homologação e produção | 14 verificações aprovadas em cada ambiente |
| Testes pelo navegador em homologação e produção | 8 verificações aprovadas em cada ambiente |
| Consulta geral e receita de bolo | Resposta sem exigência de finalidade institucional |
| Pesquisa da documentação Angular Signals | SearXNG, leitura da página real, explicação, link e evidência recuperável |
| Lei de cargos e salários do Judiciário Federal | Lei 11.416/2006 identificada com fontes oficiais e conferência jurídica |
| Acesso às evidências sem autenticação | Negado |
| Modelo principal e embeddings | Residentes na GPU |
| Interface Angular e catálogos oficiais | Assets preservados; catálogos montados somente para leitura |

A recuperação também foi corrigida para tolerar respostas vazias do catálogo do Senado e manter o assunto original da pergunta ao buscar fontes alternativas. A síntese web valida identificadores de fontes e passagens literais de apoio, com nova tentativa limitada quando o modelo devolve uma estrutura inválida.

Evidências locais: [conferência final](runtime/public-web-final.json), [API em produção](runtime/public-web-live-public.json), [navegador em produção](runtime/public-web-ui-public.json) e [testes unitários](runtime/public-web-tests.json). A configuração de publicação usa o overlay moara/infrastructure/public-web-compose.yml no script de composição existente; o serviço SearXNG mantém reinício automático separado.
