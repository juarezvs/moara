# Moara — leitura do chat e teses oficiais do STF

## Comportamento implementado

Pergunta e resposta usam a mesma coluna de leitura, com largura máxima de 850 px, alinhamento comum e tipografia maior. O layout é responsivo e conserva a identidade Moara, a navegação à direita, o compositor e o indicador real de processamento. Cada resposta tem uma ação de cópia. Não se simulam tempos de pensamento ou conteúdo interno do modelo.

As respostas de temas com tese recuperada apresentam introdução direta, seção por tema, processo, objeto, situação informada no cadastro, tese organizada, referências junto aos trechos e tabela de comparação quando houver mais de um tema. Teses extensas mostram os eixos principais e oferecem expansão do texto integral, incluindo subitens e exceções. A formatação conserva condições cumulativas, negativas e requisitos do texto oficial.

O exemplo anexado pelo usuário foi tratado como referência de apresentação. Números de temas, processos, datas, súmulas, regras e situações processuais não foram copiados do exemplo como verdades presumidas.

## Recuperação e evidências

A busca compreende a variante popular “remédio” como termo de pesquisa de “medicamento”. Expressões de organização da pergunta, como “suas respectivas teses”, não são enviadas como palavras jurídicas de busca. Siglas relevantes mantêm tratamento próprio; uma palavra curta comum como “alto” não é tratada como sigla obrigatória que excluiria temas relacionados.

O catálogo local continua servindo para descoberta de candidatos. Para apresentar uma tese como conferida nesta consulta, o MCP recupera novamente o banco oficial publicado pelo STF, respeita a política de acesso e confere o número do tema e o processo com a ficha oficial consultada independentemente. A resposta não usa a tese antiga do catálogo local como se tivesse sido revalidada.

O download é compartilhado pelos temas de uma mesma pesquisa, sem cache de conteúdo entre perguntas. Há limite de resposta, TLS verificado, política de redirecionamentos restritiva, prazos e registro das falhas. O `robots.txt` do STF é um documento curto, tratado separadamente da validação de conteúdo de uma página normativa. As cópias e os hashes da política, do banco de teses, do cadastro e dos andamentos integram as evidências.

Quando a tese principal remete expressamente a outro tema, esse vínculo pode orientar a verificação e priorização dos resultados. Isso não é um mapa fixo de assuntos para números. Resultados menos pertinentes que foram examinados permanecem nas evidências, sem alargar desnecessariamente a resposta principal.

Na pergunta fornecida — “qual tema do stf que trata de remedio de alto custo e suas respectivas teses” — a tese oficial do Tema 6 remete ao Tema 1.234. Ambos são conferidos e apresentados, com seus respectivos processos. A fonte consultada e a situação cadastral são identificadas. Não são presumidas súmulas, datas de julgamento ou modulação que não tenham sido conferidas.

## Limites

Texto de tese divulgado, descrição do tema, reconhecimento de repercussão geral, andamento processual e aplicação a um caso são fatos distintos. A resposta identifica a tese efetivamente recuperada e a situação reportada pelo STF. A publicação da tese pode anteceder a publicação do acórdão. Não é emitida uma certificação genérica de efeitos, vigência histórica, trânsito ou aplicabilidade a qualquer caso.

Se o banco estiver indisponível ou a identidade divergir, a Moara informa a lacuna e pode apresentar os dados cadastrais efetivamente recuperados. Votos e descrições de temas não são transformados em tese final de mérito.

## Validação e operação

Relatórios `docs/runtime/chat-reading-*.json` registram imagem exata, testes, pergunta real, fontes e verificações de interface. A homologação inclui busca real pelo chat, textos das duas teses, preservação dos seis requisitos cumulativos, hashes, tabela renderizada, expansão do inteiro teor, cópia, hints e igualdade das larguras no desktop e no celular. A suíte automatizada inclui cenários sintéticos de outros temas, divergência de processo, restrição do provedor e ausência de tese, sem depender de respostas prontas para o exemplo.

A publicação recria apenas gateway e MCP. Catálogos somente para leitura, timer do coletor, dados, autenticação, RBAC, interfaces de API e modelo residente são preservados. A aplicação continua em `/moara/chat`, com acesso pela raiz.

Reversão: restaurar `backups/chat-reading-20261031/compose-before` e executar o compose somente dos serviços `moara-legal-mcp` e `moara-gateway`, com `--no-deps`. As imagens anteriores estão em `moara-core:pre-chat-reading-app-20261031` e `moara-core:pre-chat-reading-mcp-20261031`. Preservar as evidências e os dados dos catálogos.


## Resultado publicado

Imagem validada: `sha256:22a87ecb1b7ccda1da4c7e3b305f636686cbc9a34cc4e7caf9d0b194b76ccbb1`. Passaram 205 testes automatizados, 10 verificações do fluxo real de resposta, 12 verificações de interface em desktop e celular e 11 verificações de preservação do catálogo de metadados. A pergunta fornecida foi respondida na API pública em 9,87 segundos nessa medição; o tempo pode variar nas demais consultas.
