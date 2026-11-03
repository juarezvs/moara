# Moara — coleta de metadados oficiais e integração LexML

## Análise das referências fornecidas

O **Manual de Pesquisa do Portal LexML**, Senado Federal, 2013, fornecido pelo usuário (44 páginas), descreve um catálogo referencial. As páginas 8–9 distinguem a pesquisa nos dados descritivos da pesquisa no inteiro teor. As páginas 27–29 orientam a consulta aos provedores, à publicação original, ao texto atualizado e às versões para determinada data. Os filtros por categoria, autoridade, localidade e tipo de documento ajudam a organizar uma coleta, mas não demonstram cobertura integral de um município ou órgão. Proposições, doutrina, publicações e decisões não podem ser classificados indiscriminadamente como normas vigentes.

A [notícia oficial do LexML](https://projeto.lexml.gov.br/institucional/noticias/portal-lexml-disponibiliza-metadados-das-normas-juridicas-federais-com-marcacao-schema-org-legislation-1), publicada em 2019 e modificada em 2020, descreve metadados JSON-LD Schema.org/Legislation. A quantidade e a cobertura mencionadas na notícia são históricas, não um inventário atual conferido pela Moara. Na inspeção real de 31/10/2026, as páginas da Lei Maria da Penha e da Lei 14.133/2021 retornaram fichas HTML, sem bloco `application/ld+json`. O coletor suporta JSON-LD quando presente e identifica expressamente o formato HTML quando ele for utilizado.

O [catálogo oficial de dados abertos do Senado](https://www12.senado.leg.br/dados-abertos/legislativo/legislacao/acervo-do-portal-lexml) aponta para a busca SRU `/busca/SRU`. O `robots.txt` observado do LexML restringe `/busca/` e permite `/urn`; o endpoint alternativo `/sru` testado retornou 404. A implementação não contorna essa restrição nem desafios de segurança. A enumeração usa a API oficial de legislação do Senado; o enriquecimento usa apenas as fichas LexML permitidas.

## Mecanismo implementado

1. Coletor determinístico e isolado enumera metadados federais do ano corrente e do ano anterior, nos tipos LEI, LCP, DEC e EMC. Os anos avançam automaticamente. Uma lista explícita de assinaturas acompanha normas históricas importantes para a utilização inicial; ela não contém respostas nem serve de mapa para classificar perguntas.
2. Cada registro conserva identidade, data de assinatura, ementa, apelidos, URN, URL, horário da coleta e cópia original com SHA-256. A URN é formada a partir da identificação oficial e é conferida na ficha LexML. Data de assinatura não é tratada como início de vigência.
3. A coleta de fichas LexML é gradual e rotativa, com até 30 tentativas por execução. Consulta a política de acesso, respeita intervalos e mantém as falhas visíveis. O intervalo observado é conservador: dez segundos, maior que os cinco segundos do grupo geral do portal. JSON-LD, quando presente, é interpretado sem executar scripts ou buscar contextos externos. Identidades divergentes são rejeitadas.
4. O índice textual local pesquisa ementas e apelidos, com SQL parametrizado. Links de provedores são referências não conferidas; não se seguem redirecionamentos ou endereços arbitrários. Metadados jamais são apresentados como inteiro teor ou prova de vigência.
5. A descoberta jurídica obrigatória da aplicação consulta também esse índice. Os candidatos seguem para o mecanismo já existente de recuperação e validação do texto oficial, na data relevante. O MCP dispõe de `search_legal_metadata`, mas a integração não depende de o modelo escolher chamar a ferramenta.
6. A resposta continua vinculada aos trechos oficiais recuperados e às citações verificadas. As evidências do catálogo utilizadas na descoberta também integram o registro da consulta. A interface oferece os links oficiais junto a cada registro.

Esse é um aprendizado operacional por indexação, descoberta e consulta de evidências. Não houve treinamento dos pesos do modelo, certificação de toda a legislação nem aceitação automática de conteúdo externo como instrução.

## Uso e operação

- Interface: **Referências → Catálogo de normas**, `/moara/chat?area=referencias&catalogo=metadados`.
- Pesquisa autenticada: `/moara/api/v1/legal/metadata`, permissão `chat.use`.
- Exportação autenticada: `/moara/api/v1/legal/metadata/export`, incluindo registros, manifesto e fontes originais comprimidas com hashes.
- Plano de coleta: `moara/infrastructure/legal-metadata-plan.json`. Adicionar uma assinatura histórica nesse arquivo não altera permissões de usuários nem gera conclusões jurídicas.
- Persistência: `data/legal/metadata`, no servidor de aplicação. Versões imutáveis em `versions`, originais em `snapshots` e ponteiro atômico `CURRENT`.
- Execução manual: `python3 infrastructure/legal/harvest_legal_metadata.py 30`, no diretório `/home/nutec/ai-server`. O bloqueio de arquivo evita concorrência entre execuções.
- Agendamento: timer de usuário `moara-legal-metadata.timer`, a cada seis horas, às 00:35, 06:35, 12:35 e 18:35 UTC, com variação de até três minutos e persistência após desligamento. O serviço tem limite de 25 minutos. O servidor opera em UTC; em Manaus são 20:35, 02:35, 08:35 e 14:35.
- Inspeção: `systemctl --user list-timers moara-legal-metadata.timer`; `journalctl --user -u moara-legal-metadata.service`; manifesto da versão corrente; `last_failure.json` quando houver falha de alimentação.

O trabalhador acessa apenas fontes públicas e a pasta de catálogo. Não recebe documentos, conversas, credenciais institucionais ou acesso ao banco. Os serviços de chat e MCP montam o catálogo somente para leitura. Não há mudança na inferência ou no modelo residente na GPU.

Uma falha de alimentação preserva a versão anterior. Uma falha de enriquecimento LexML preserva a evidência anterior, com status distinto de sucesso na última tentativa. A versão só é publicada após a gravação e conferência de integridade do índice. O catálogo não remove uma norma por ela deixar de aparecer num recorte de busca; também não interpreta isso como revogação. Estados, municípios e atos não cobertos continuam dependendo de fontes e adaptadores específicos.

## Validação e reversão

Os relatórios em `docs/runtime/legal-metadata-*.json` registram a imagem exata avaliada, a coleta, os testes de API, interface e o fluxo real de resposta. A suíte inclui regressão para uma regra real de `robots.txt` com curingas consecutivos, que antes causava retrocesso exponencial da expressão regular. A correção reduz curingas consecutivos equivalentes e conserva as restrições de acesso.

Somente gateway e MCP são recriados na publicação. A versão anterior fica nas tags `moara-core:pre-legal-metadata-app-20261031` e `moara-core:pre-legal-metadata-mcp-20261031`. O wrapper anterior é preservado em `backups/legal-metadata-20261031/compose-before`. Para reverter, desativar o timer, restaurar esse wrapper e executar o compose dos dois serviços com `--no-deps`. Preservar a pasta do catálogo para auditoria. Não remover volumes ou recriar a inferência.


## Resultado da validação inicial

A versão publicada usa a imagem `sha256:086237d7616ce566b4e9be7bd870e9fab0a5cae6c5411aa38499bb6bf84b81a8` e MCP 0.10.0. Passaram 196 testes automatizados, 11 verificações de API, 11 verificações de interface e 9 verificações do fluxo real de resposta, em homologação e na aplicação pública. Também passaram as 11 verificações de preservação do acervo STF (1.292 registros).

A primeira coleta publicou **1.278 registros de metadados federais**, com **6 fichas LexML** recuperadas das 8 tentadas. Duas fichas retornaram HTTP 503 e permaneceram com indisponibilidade registrada. Nenhuma das seis fichas retornou JSON-LD; foram reconhecidas pelo HTML rotulado, com identidade URN exata. O suporte JSON-LD foi validado por testes controlados de formato e identidade, não apresentado como uma coleta real de JSON-LD que não ocorreu.

A pergunta real sobre a lei de cargos e salários do Judiciário Federal foi respondida em aproximadamente **7,95 segundos**, identificando a Lei 11.416/2006, com texto oficial, link e evidências de descoberta por metadados. Essa medida refere-se apenas a essa consulta; não é uma estimativa para todas as perguntas. O manifesto corrente e o relatório final registram o avanço das coletas subsequentes.
