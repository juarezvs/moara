# Respostas jurídicas fundamentadas em fontes consultadas

Correção e ampliação do fluxo jurídico da Moara em 31/10/2026, America/Manaus.

## Problema e resultado

A pergunta “de acordo com a lei 8112/1990 o que é uma promoção” expôs três problemas: campos vazios ou referências em listas JSON-LD quebravam o leitor; o catálogo oficial identificava a compilação atual mas seu endereço binário retornava 404; o fluxo anterior permitia apenas selecionar trechos, suspendendo qualquer explicação didática.

O fluxo agora consulta fontes oficiais antes de responder e entrega ao modelo trechos pertinentes com identificadores. A IA explica esses trechos; a aplicação valida identificadores, existência das citações literais e referências normativas usadas antes de entregar a resposta. Cada ponto liberado tem sua fonte. Falhas de uma referência são isoladas. Falha do modelo não é apresentada como indisponibilidade da fonte: os trechos efetivamente obtidos continuam disponíveis.

O exemplo da promoção foi respondido com base na Lei 8.112/1990, arts. 8º, 10, 17 e 33, recuperados da compilação atual da Câmara. O texto não contém uma definição universal de passagem entre classes nem critérios completos para todas as carreiras; remete à legislação de carreira e aos regulamentos. A resposta explica essa relação sem inventar prazos ou requisitos.

## Consulta obrigatória e cobertura

- Referências expressas a normas e precedentes na pergunta acionam a etapa jurídica controlada pela aplicação, inclusive quando outra especialidade está selecionada.
- Respostas do portal são verificadas antes da entrega. Referências jurídicas acrescentadas espontaneamente acionam conferência e autorização de ferramenta. As capacidades internas de síntese são objetos privados do processo; campos JSON ou cabeçalhos do cliente não podem concedê-las.
- As consultas OpenAI do editor preservam o streaming de ferramentas; referências jurídicas expressas na entrada também passam pela conferência. Isso não representa inspeção completa de todo código ou texto transmitido por ferramentas do editor.
- Perguntas informativas usam a data atual, declarada na resposta. Datas explícitas prevalecem. Compilação corrente não é usada para comprovar redação histórica; referências temporais ambíguas ou fatos concretos ainda podem exigir esclarecimento.
- Senado/normas.leg.br continuam como fontes de identificação e texto estruturado. Compilações correntes explicitamente vinculadas pelo catálogo podem ser consultadas. Para a Lei 8.112, a Câmara é alternativa oficial configurada, consultada pela rede em cada operação. O conector não armazena uma resposta pronta sobre promoção.
- Acrescentada consulta identificada a temas do STF/STJ e busca oficial de súmulas/processos reconhecidos. É obrigatório distinguir tribunal e número: temas de mesmo número podem tratar de assuntos completamente diferentes. Uma descrição de tema não se transforma em tese julgada. Uma página de busca sem conteúdo identificável não é apresentada como resultado confirmado.
- Portarias, resoluções e outros atos com URL oficial informada podem ser recuperados nos domínios expressamente aprovados. Órgão emissor, número, ano e fonte podem ser solicitados para evitar ambiguidade. Não há catálogo automático integral de todos os órgãos, estados ou municípios.
- O conector de limites de dispensa permanece ativo, com extração dos valores da tabela oficial e conferência do ato e do exercício no PNCP.

Toda recuperação preserva cópias e SHA-256, com data da consulta, seleção dos trechos, referências e pontos aceitos na síntese. O proprietário pode revisar a evidência e baixar o manifesto. URLs arbitrárias, redirecionamentos para redes privadas, referências sem identificação e conteúdo sem fonte suficiente não liberam resposta factual de memória.

## Limites da validação

A validação de uma citação literal comprova que o texto existe no trecho recuperado, não demonstra automaticamente que toda interpretação é correta. Pontos com citações inválidas são excluídos e a limitação é indicada. Revisão jurídica permanece necessária. O campo `legal_conclusion_allowed=false` continua indicando que não há certificado global de vigência nem autorização para prática de ato no caso concreto; ele não impede explicações fundamentadas.

Não há promessa de atualização absoluta de toda a legislação ou jurisprudência. Bloqueios, portais incompletos, efeitos temporais, recursos, trânsito em julgado, modulação e cobertura de alterações são lacunas possíveis e devem ser indicadas. A consulta corrente a um tribunal não comprova por si só a situação histórica do precedente.

## Implantação e evidências

Imagem de aplicação/MCP: `moara-core:legal-grounding-20261031`, MCP 0.4.0; overlay final `moara/infrastructure/legal-grounding-compose.yml`. Base preservada: produção com API pessoal do VS Code, identidade original, seis assistentes e inferência residente na GPU. Sem migração de banco e sem reinício dos modelos.

111 testes automatizados, incluindo formato JSON-LD heterogêneo, endereço corrente 404 com recuperação pela Câmara, não uso de compilação atual para datas históricas, busca de artigos após o antigo corte dos primeiros 100, isolamento de fontes, citação literal, bloqueio de referências inventadas e impedimento de acesso a URLs não aprovadas.

Testes reais incluem a pergunta exata sobre promoção, explicação do art. 12 do CPC e Tema 1157 do STJ, reprodução das cópias e hashes, síntese na GPU e chat pelo navegador. Também verificados FAQ institucional e página de chaves para VS Code. Conversas sintéticas são arquivadas e sessões de teste revogadas.

Evidências em `docs/runtime/legal-grounding-stage.json`, `legal-grounding-public.json`, `legal-grounding-ui.json` e `legal-grounding-final.json`. Scripts correspondentes em `infrastructure/legal/`. A ativação exige evidência do candidato vinculada ao identificador exato da imagem, testes aprovados e backup com restauração verificada.

Backup prévio: `moara-before-migration-20261031T112619Z.tar.enc`, restauração isolada verificada, contagens PostgreSQL, integridade SQLite, arquivos e configuração conferidos. Para retorno, restaurar o wrapper salvo em `backups/legal-grounding-20261031/compose-before`, validar a configuração e recriar apenas `moara-legal-mcp` e `moara-gateway`. Manter dados e auditoria; não usar `compose down`.

Fontes oficiais verificadas: https://www2.camara.leg.br/legin/fed/lei/1990/lei-8112-11-dezembro-1990-322161-normaatualizada-pl.html e https://scon.stj.jus.br/repetitivos/temas_repetitivos/pesquisa.jsp?novaConsulta=true&tipo_pesquisa=T&cod_tema_inicial=1157&cod_tema_final=1157.
