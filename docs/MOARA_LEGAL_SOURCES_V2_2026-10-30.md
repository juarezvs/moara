# MCP Normas — fontes oficiais e histórico legislativo

## Resultado

O MCP privado da Moara passa à versão `0.2.0`. A conferência jurídica controlada pela aplicação consulta novamente as fontes oficiais a cada solicitação, sem reaproveitar uma cópia antiga como se tivesse sido conferida agora. A evolução preserva a redação histórica por data de referência e acrescenta a conferência de referências normativas correlatas e a proveniência legislativa da Câmara quando indicada expressamente pelo Senado.

Não há certificação automática completa de vigência ou eficácia. As consultas continuam com `legal_conclusion_allowed=false`: a data de uma versão textual não substitui a avaliação de publicação, entrada em vigor, transição, revogação ou efeitos judiciais. Cobertura inicial **federal parcial**, sem certificação de legislação estadual ou municipal. Nem a origem governamental nem uma resposta HTTP bem-sucedida garantem cobertura integral ou atualização instantânea.

## Fontes analisadas

| Fonte | Uso na implementação | Limites constatados |
|---|---|---|
| [API do Senado](https://legis.senado.leg.br/dadosabertos/v3/api-docs) | Catálogo por tipo/número/ano, identificação, publicações e referências a alterações | Os formatos variam por endpoint; esta integração usa JSON. A API pública dispensa autenticação; o MCP interno continua autenticado. |
| normas.leg.br | Dispositivos e versões estruturadas, identificação e proveniência do processo legislativo | Parte das normas não tem articulado estruturado. O campo de atualização do conjunto não é data de entrada em vigor. |
| [API da Câmara](https://dadosabertos.camara.leg.br/api/v2/api-docs) | Identificação única de proposição e tramitações até a data relevante | Projeto não é lei vigente; metadados correntes não demonstram situação histórica nem ausência de alterações. |
| [Portal da Transparência/CGU](https://portaldatransparencia.gov.br/api-de-dados) | Avaliado na documentação; excluído como fonte normativa | Trata de dados de transparência, gastos e outros registros administrativos. Exige token enviado após cadastro de e-mail. Não foi cadastrada conta nem provisionada integração financeira nesta entrega. |
| Planalto, DOU e referências constitucionais | Consultas e evidências anteriores preservadas | Planalto apresentou falha de conexão nos testes; buscas do DOU não certificam todas as edições, extras ou suplementos. STF, inteiro teor, embargos e modulação continuam sujeitos a conferência. |

Também foi testado um link de compilação HTML de Lei 9.868/1999 indicado no repositório, que retornou 404. Uma tentativa de página da Câmara apresentou conteúdo de erro. Essas fontes não foram promovidas a uma alternativa supostamente confiável para extrair redação atual. Nenhum bloqueio foi contornado.

## Ferramentas MCP

- `verify_legal_sources`: conferência existente, ampliada com proveniência e normas correlatas. Exige data de referência e de uma a três normas; até oito artigos por norma.
- `search_federal_norms`: catálogo oficial por tipo, número e ano opcional. Retorna candidatos e evidências, sem escolher automaticamente uma norma ambígua nem certificar vigência.
- `consult_legislative_history`: proposição por tipo/número/ano e data de referência. Confere lista, detalhes e tramitações na API da Câmara. Não recebe narrativa de caso nem URL arbitrária.

As ferramentas são somente leitura. A autorização do MCP interno e o bloqueio de origens de navegador permanecem ativos. A aplicação continua impondo a conferência jurídica, independentemente de preferências de ferramentas enviadas pelo cliente.

## Comportamento e salvaguardas

1. A identidade é validada conjuntamente por número, tipo, ano, URN e data de assinatura; não basta encontrar um número semelhante.
2. As versões textuais selecionadas são limitadas à data relevante. Blocos que alteram outra norma não são apresentados como se fossem dispositivos próprios dela.
3. Referências repetidas são deduplicadas. A aplicação consulta identificação e publicações de até **duas** normas correlatas mais recentes elegíveis no Senado, com filtro dos artigos quando o registro oferece essa associação. A cobertura é declarada incompleta.
4. A Câmara só é associada automaticamente quando a proveniência oficial identifica explicitamente um projeto da Câmara. Nunca se consulta um PL com o número e ano da lei apenas por coincidência.
5. Eventos posteriores à data relevante ou sem data válida são excluídos. Metadados correntes da proposição ficam separados e marcados como não históricos. Listas ambíguas e identificação paginada incompleta não são aceitas como correspondência única.
6. URLs de requisição são construídas a partir de identificadores tipados. O acesso externo aceita somente HTTPS, domínios permitidos e porta 443; redirecionamentos não são seguidos. URLs devolvidas pelas APIs não determinam livremente novos destinos.
7. Concorrência de duas requisições e espaçamento mínimo de 350 ms por domínio são compartilhados pelo cliente do serviço. Não há repetição ilimitada em caso de 429, 503 ou falha de fonte.
8. Cada consulta usa requisição de rede com `no-cache`; falhas não recuperam um resultado antigo como novo. São registrados horário, URL, hash, tamanho, ETag/Last-Modified quando presentes e cópia comprimida da resposta aceita. Esses cabeçalhos não certificam atualização jurídica.
   Consultas complementares à Câmara têm prazo total de 30 segundos; referências normativas correlatas, 12 segundos. O prazo do MCP continua limitado a 75 segundos. Uma indisponibilidade complementar preserva a identificação e as cópias já aceitas, além de registrar a tentativa interrompida; não invalida automaticamente os trechos normativos recuperados.
9. Trechos extensos têm marcação explícita de limite: até 8.000 caracteres por trecho e 100 dispositivos na resposta estruturada. O chat mostra até 20 trechos e informa a limitação. Os bytes completos das fontes aceitas ficam no pacote de evidências.
10. Emendas constitucionais numeradas foram acrescentadas ao contrato e à identificação textual, com teste real da EC 132/2023. Não se afirma cobertura automática de toda a Constituição ou de todas as espécies normativas.

## Uso no chat

Abrir https://moara.am.trf1.gov.br/ e usar, por exemplo:

> Confira a Lei 14.133/2021, art. 6, na data de hoje. Mostre os dispositivos encontrados, as fontes, as alterações verificadas e as lacunas.

Ou abrir **Referências → Legislação**, informar norma, dispositivo e data e escolher **Conferir fontes oficiais**. O processamento utiliza o indicador da Moara já publicado. O relatório passa a mostrar a atualização do conjunto informada pela fonte, as referências correlatas conferidas e a origem/tramitação na Câmara quando disponíveis.

O link **Consultar evidências e fontes** apresenta também a nova proveniência. A exportação completa mantém as cópias e hashes; a consulta resumida omite os bytes comprimidos. Reabrir uma evidência antiga não altera sua data de conferência. Propriedade, restrição por chave, criptografia e integridade do registro continuam obrigatórias.

## Testes e evidências

- 79 testes do backend aprovados, cobrindo a integração anterior, fluxos documentais, identidade, progressos, novas ferramentas, ambiguidades, falhas externas, eventos futuros, identificação estrita e preservação de evidências parciais em consultas interrompidas.
- Consultas reais: catálogo da Lei 14.133/2021; CPC art. 12 em 31/12/2015 e 01/01/2020, com redações distintas; Lei 14.133/2021 art. 6 na data da consulta; Lei 9.868/1999 art. 27 sem redação estruturada, sem fabricação de texto; EC 132/2023 art. 1; histórico do PL 6814/2017 até 01/01/2020.
- Chat em Chromium isolado: nova proveniência e referências correlatas, texto e datas, registro criptografado com integridade conferida, exportação com reprodução de hashes, página HTML de evidências, bloqueio de acesso anônimo e pergunta comum sobre habilidades.
- As conversas sintéticas são arquivadas e as sessões nativas de teste são revogadas. As evidências sintéticas de normas públicas permanecem no arquivo imutável por projeto.
- Relatórios no servidor: `docs/runtime/legal-sources-v2-live-stage.json`, `legal-sources-v2-ui-stage.json`, `legal-sources-v2-live-public.json`, `legal-sources-v2-ui.json` e `legal-sources-v2-http.json`.

## Implantação e recuperação

Imagem `moara-core:legal-sources-v2-20261030`, aplicada somente a `moara-gateway` e `moara-legal-mcp`, pelo overlay final `legal-sources-v2-compose.yml`. A imagem foi derivada da produção anterior, mantendo a coluna lateral, o indicador de processamento, as correções de conversas e os modelos existentes. Não houve migração de banco nem reinicialização da inferência.

Backup cifrado `moara-before-migration-20261030T225659Z.tar.enc`, com restauração isolada conferida às 18:58:33 de 30/10/2026, horário de Manaus. Imagem core anterior preservada como `moara-core:pre-legal-sources-v2-20261030`; imagem MCP anterior e demais imagens históricas permanecem disponíveis.

Para reverter esta entrega, restaurar `backups/legal-sources-v2-20261030/compose-before` sobre o wrapper, mantendo o modo 755, e executar `up -d --no-deps moara-legal-mcp moara-gateway` pelo wrapper. A configuração anterior seleciona as respectivas imagens de cada serviço. Conferir a saúde do MCP, `/moara/api/v1/ready` e uma consulta jurídica. Não remover evidências, históricos ou volumes e não executar `compose down`.

`MOARA_LEGAL_MCP_URL` permite apontar um candidato privado da aplicação ao seu candidato MCP. A produção mantém o destino interno padrão. A variável é configuração administrativa; não é parâmetro aceito de usuários. Candidatos privados sem portas públicas e sem consumo de trabalhos em segundo plano são interrompidos e preservados ao final da validação.
