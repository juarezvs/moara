# Pesquisa de temas do STF por assunto — 31/10/2026

A aplicação encaminha perguntas sobre assuntos do STF ao MCP `research_precedents_by_subject`, sem exigir que o usuário conheça o número do tema. A pesquisa consulta o catálogo oficial, extrai os identificadores dos links encontrados e confere novamente a página do tema e seus andamentos. Não há tabela de respostas, doenças ou benefícios associada a números de temas.

As respostas dessa etapa usam os campos conferidos no tribunal, com links e evidências recuperáveis. O texto encontrado não é incorporado aos pesos do modelo: é contexto documental verificável para a consulta. Fontes inacessíveis ou referências insuficientes produzem lacunas explícitas.

O teste com uma conta de chat também identificou um erro anterior de seleção: o orquestrador fixava o alias `general`, embora essa conta tivesse autorização para o perfil `gemma4-12b`. A seleção automática agora prefere o perfil do principal entre os perfis efetivamente autorizados, mantendo a validação de ACL e as escolhas manuais. Não há concessão adicional de módulos ou perfis.

## Separação entre identificação e decisão

O registro do tema, o reconhecimento de repercussão geral, votos, propostas de tese e julgamento definitivo são fatos diferentes. O conector apresenta o estado do cadastro e o andamento pertinente mais recente, mas não certifica tese final ou modulação apenas por encontrar um acórdão de repercussão geral. A conferência corrente não comprova o estado histórico de um julgamento.

No exemplo solicitado, a pesquisa encontra o Tema 1310 / RE 1447945, sobre reforma militar e HIV assintomático. A resposta delimita esse regime e não atribui aposentadoria automática pelo INSS ou pelo regime civil. Na conferência de 31/10/2026, o andamento de 29/10/2026 registra julgamento suspenso. Os metadados e andamentos são lidos novamente em cada pesquisa; esses dados não são uma resposta fixada no código.

Fontes oficiais:

- [Tema 1310](https://portal.stf.jus.br/jurisprudenciaRepercussao/tema.asp?num=1310).
- [Andamentos do RE 1447945](https://portal.stf.jus.br/jurisprudenciaRepercussao/verAndamentoProcesso.asp?classeProcesso=RE&incidente=6689678&numeroProcesso=1447945&numeroTema=1310).

## Cobertura e provedores

A descoberta nova cobre o catálogo de repercussão geral do STF. As consultas por identificadores já existentes permanecem disponíveis. Não se promete pesquisa ampla de todos os tribunais, confirmação universal de efeitos ou atualização instantânea de toda a jurisprudência.

Nas explicações legislativas produzidas pelo modelo, citações inválidas continuam bloqueadas. Quando a explicação não passa nessa validação, a aplicação pode apresentar os trechos oficiais recuperados, em vez de uma paráfrase. Esse comportamento foi observado na regressão pública da pergunta sobre promoção: a fonte foi recuperada, mas a primeira explicação não passou na validação. Não equivale a indisponibilidade da fonte nem a uma resposta inventada.

Também ocorreram `ReadTimeout` de 15 segundos na pesquisa oficial do STF em uma rodada pública. As rodadas de navegador seguintes recuperaram o resultado, inclusive para o usuário restrito. Os relatórios das oscilações foram preservados (`jurisprudence-public-first.json` e `jurisprudence-public-timeouts.json`). A implantação não elimina indisponibilidades do tribunal. O teste de promoção aceita explicação com citações validadas ou a alternativa literal, desde que compare cada trecho e URL com as evidências efetivamente recuperadas; não exige sucesso do modelo para declarar o retorno literal seguro.

A pesquisa web auxiliar permanece limitada a referências candidatas, sem aceitar conteúdo de terceiros como prova jurídica. Para este caso, a descoberta e a conferência funcionam diretamente no STF.

Google/Gemini foi avaliado, mas não foi ativado: não há chave configurada e os [termos de Grounding with Google Search](https://ai.google.dev/gemini-api/terms#grounding-with-google-search) impõem condições de apresentação, armazenamento e uso automatizado dos links que não correspondem a um coletor genérico para indexação ou aprendizado. Não há conector Gemini anunciado como operacional.

## Validação e implantação

- 163 testes unitários, incluindo ausência de resultados, fontes não oficiais, identificação incorreta, zeros iniciais, datas futuras e distinção entre repercussão geral e mérito.
- API real: pergunta sobre HIV, outro tema por assunto (ICMS/PIS/COFINS), diálogo competitivo, crimes de trânsito, proteção de dados, violência doméstica e promoção na Lei 8112.
- Navegador: interface atual, fontes oficiais, evidências, controle de contexto, login e RBAC, incluindo pesquisa por usuário com acesso somente ao chat.
- Regressão da API compatível com os SDKs de desenvolvimento.

Imagem `moara-core:jurisprudence-20261031`, MCP 0.7.0. Sobreposição `moara/infrastructure/jurisprudence-compose.yml`. Somente gateway e MCP são atualizados; sem reiniciar inferência, proxy ou migrar dados. Backups preservados em `backups/jurisprudence-20261031`; imagens anteriores `moara-core:pre-jurisprudence-20261031` e `moara-core:pre-mcp-jurisprudence-20261031`.

Reversão: restaurar `compose-before` no wrapper e executar o wrapper com `up -d --no-deps moara-legal-mcp moara-gateway`, verificando as rotas de saúde. Não usar `compose down` nem apagar volumes.

Relatórios da execução em `docs/runtime/jurisprudence-*.json`; captura sanitizada `docs/runtime/jurisprudence-chat.png`.
