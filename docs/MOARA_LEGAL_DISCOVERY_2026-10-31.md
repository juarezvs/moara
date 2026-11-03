# Pesquisa de legislação por assunto

Correção de 31/10/2026, America/Manaus. O usuário não precisa saber o número da lei para iniciar uma pesquisa federal por assunto.

## Fluxo e comportamento

Antes, a conferência exigia uma norma já identificada e devolvia uma solicitação de número/ano para perguntas como “qual a lei que trata de crime de trânsitos?”. Agora a aplicação pesquisa o assunto nos catálogos oficiais, identifica candidatas, verifica os textos e registra as fontes antes de responder.

1. Perguntas informativas sem data usam a data atual, indicada ao final da resposta. Casos concretos ou referências temporais ambíguas continuam podendo exigir esclarecimento.
2. São extraídas palavras públicas do assunto, com limites e exclusão de identificadores e narrativas pessoais reconhecidas. O relato integral não é enviado ao catálogo externo. Pequenas variações, como “crime de trânsitos”, são normalizadas.
3. A busca textual oficial da Câmara fornece candidatas e ementas. Referências recorrentes a uma lei-base em ementas de alterações são verificadas no catálogo numérico do Senado. A busca não fica restrita a um mapa de respostas sobre trânsito.
4. A IA pode selecionar apenas IDs de candidatas já recuperadas. Não pode inventar o número de uma norma nessa etapa. Em caso de falha, é usada a ordenação limitada do catálogo, registrada como tal. O texto da candidata é consultado novamente pela ferramenta de pesquisa jurídica.
5. A compilação atual da Câmara pode ser localizada pelo registro exato da norma e pelo link explícito “Texto Atualizado”. A publicação original não é usada como substituto silencioso do texto atualizado. Compilações atuais não comprovam redação histórica.
6. Perguntas de identificação recebem uma resposta direta construída com o nome e a ementa recuperados. Explicações substantivas continuam usando trechos e validação de citações. A resposta não começa exigindo identificação ou data quando a própria consulta informativa permite pesquisar.
7. O registro preserva a consulta, candidatas, seleção, verificações, textos, cópias comprimidas, SHA-256 e datas. A página de evidências e seu download continuam restritos ao proprietário e à chave correspondente.

Uma pergunta nova não herda uma lei ou data de um assunto anterior. Perguntas curtas de continuidade reconhecidas reutilizam o contexto do assunto. Candidatas publicadas depois do ano de referência são excluídas; a ementa corrente não é oferecida como evidência textual histórica.

## MCP e fontes

MCP **0.5.0**, com a nova ferramenta `discover_federal_norms`. `research_legal_sources` também aceita assunto e mantém compatibilidade com referências explícitas. O serviço continua privado, autenticado, com fontes aprovadas, limites de requisição, tamanho e tempo. O modelo não decide se pode pular a conferência jurídica.

Fontes de integração: [busca oficial da Câmara](https://www.camara.leg.br/legislacao/busca), [orientações da pesquisa textual](https://www2.camara.leg.br/atividade-legislativa/legislacao/pesquisa/como-pesquisar) e [documentação da API do Senado](https://legis.senado.leg.br/dadosabertos/v3/api-docs). A pesquisa textual cobre ementa, indexação, apelidos e texto; resultados de busca são pistas para localizar a norma, não prova automática de vigência.

## Verificação

139 testes automatizados de backend, incluindo: descoberta sem número, isolamento de assunto/data entre turnos, referências verificadas, rejeição de IDs inexistentes sugeridos pelo modelo, restrição de URLs, vínculo exato com a compilação atual, ausência de resposta inventada para busca sem resultado e proteção contra uso de norma posterior à data histórica.

Consultas reais pela API da Moara, em candidato isolado e na publicação, com evidências reproduzidas por SHA-256:

- Crimes de trânsito: identificação do CTB, Lei 9.503/1997.
- Proteção de dados pessoais: identificação da Lei 13.709/2018.
- Violência doméstica contra a mulher: identificação da Lei 11.340/2006.
- Promoção na Lei 8.112/1990: preservação da explicação fundamentada.

No navegador, a pergunta original é enviada pelo chat e a resposta é conferida, incluindo CTB, número da lei, fonte oficial e link de evidências. A regressão também cobre login, contexto, histórico, RBAC e API do VS Code. Contas e conversas sintéticas são desativadas/arquivadas e credenciais de teste revogadas.

## Limites

A descoberta automática por assunto tem cobertura federal parcial. Busca sem resultado não comprova inexistência de lei. Assuntos estaduais/municipais podem exigir localidade, órgão ou portal oficial. Pesquisa genérica de jurisprudência não é substituída por resultados de leis: pode exigir delimitação da questão e do tribunal. A cobertura anterior de referências identificadas do STF/STJ permanece.

Um catálogo corrente não certifica vigência integral, revogações, regras transitórias, constitucionalidade ou modulação. A identificação de uma lei não autoriza concluir que todos os artigos se aplicam a qualquer fato. A redação e a efetividade de normas para datas passadas dependem das evidências disponíveis; lacunas são indicadas.

Não foram incorporadas as penas do exemplo do usuário como resposta pronta. Valores, penas, requisitos e exceções precisam constar dos dispositivos efetivamente consultados.

## Operação

Imagem publicada: `moara-core:legal-discovery-20261031`, overlay `moara/infrastructure/legal-discovery-compose.yml`, para gateway e MCP. Bases exatas preservadas: `moara-core:pre-legal-discovery-20261031` e `moara-core:pre-mcp-discovery-20261031`. Sem migração de banco, alteração de AD/RBAC ou reinício da inferência. Modelo principal e embeddings permanecem residentes na GPU.

Reversão: restaurar `backups/legal-discovery-20261031/compose-before` e recriar somente `moara-legal-mcp` e `moara-gateway`. Não remover volumes. Evidências: `docs/runtime/legal-discovery-stage.json`, `legal-discovery-public.json`, `legal-discovery-ui-stage.json`, `legal-discovery-ui-public.json`, `legal-discovery-sdk.json`, `legal-discovery-final.json` e `legal-discovery-chat.png`.
