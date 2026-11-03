# Correções de conversa e análise de anexos — 30/10/2026

Publicado no gateway da Moara, mantendo o ambiente de trabalho, os dados e o
modelo GPU existentes. Não houve migração de banco nem troca de modelo/contexto
físico: o principal continua com 8.192 tokens.

## Problemas reproduzidos

1. “Quais suas habilidades?” e “O que você pode fazer?” não coincidiam com as
   poucas formulações da FAQ e eram encaminhadas ao classificador, que as marcava
   como pesquisa jurídica. A aplicação exigia indevidamente data e normas.
2. Uma resposta curta com a data não mantinha de modo determinístico a referência
   normativa do turno anterior. Novas normas também podiam ser misturadas às
   citadas anteriormente na conversa.
3. No chat original, o texto recuperado do anexo e a pergunta eram classificados
   juntos. Palavras técnicas do documento podiam escolher a Moara Desenvolvedora,
   mesmo quando o pedido era analisar um processo.
4. O PDF fornecido tem cinco páginas e 156.638 bytes; a extração local obteve
   aproximadamente 7.200 bytes UTF-8. Com o pedido real, a reserva de 4.096 tokens
   de saída reproduziu `estimated_context_budget_exceeded` no chat original.

## Correções

- Reconhecimento determinístico de formulações sobre capacidades, com variações
  de saudação e cortesia. A resposta usa a FAQ publicada e não executa o modelo.
  Não se alterou o manifesto publicado nem seu hash.
- Perguntas mistas sobre habilidades **e uma questão jurídica concreta** continuam
  sujeitas ao fluxo jurídico; as expressões não funcionam como escape da política.
- “Hoje”, uma data explícita ou uma data curta continuam a norma/artigo pendentes.
  Datas inválidas não reutilizam silenciosamente datas antigas. A pergunta por
  data agora identifica a norma encontrada e oferece a escolha atual/histórica.
- O template do recuperador identifica a pergunta com delimitadores próprios.
  O adaptador reconhece também a pergunta original que o WebUI acrescenta após
  o template. A classificação usa essa pergunta, enquanto os trechos do documento
  permanecem dados não confiáveis para o modelo. O reconhecimento requer a
  identidade WebUI autenticada ou sessão WebUI já validada; não concede permissões.
- Respostas sobre esses trechos passam por geração controlada, validação dos
  identificadores de citação e pela barreira de referências legais não conferidas.
  Validar o identificador de uma citação não equivale a certificar sua interpretação
  ou vigência. A leitura integral não é presumida.
- O orçamento de contexto ajusta primeiro a reserva de saída. Se ainda necessário
  em uma consulta documental, retira turnos anteriores completos, preservando a
  pergunta e as fontes atuais. A resposta informa essa redução, os metadados
  registram as contagens e o histórico armazenado permanece intacto.
- A pergunta atual, as fontes atuais e a política central não são cortadas para
  caber. Se continuarem grandes demais, a resposta é um erro compreensível em
  português, com orientação para nova análise/particionamento; não uma análise
  apresentada como completa após truncamento silencioso.

O planejamento usa a estimativa conservadora de bytes UTF-8/3, identificada nos
metadados. Não se apresenta essa estimativa como contagem exata do tokenizer.

## Verificação

64 testes unitários passaram, incluindo reconhecimento de intenção, mudança de
assunto, datas, isolamento entre fonte/pergunta, marcadores maliciosos no documento,
preservação do texto atual e aviso explícito de ajuste do contexto.

O fluxo real do chat original foi testado com o PDF fornecido, sem publicar seu
conteúdo nos relatórios. Após a correção:

| Configuração do pedido | Resultado |
|---|---|
| Padrão, 512 tokens de saída | HTTP 200, Moara Documental, GPU, citações com IDs presentes na fonte |
| Reserva de 4.096 tokens | HTTP 200, saída ajustada a 2.471 tokens máximos, sem erro de orçamento |

Nos dois testes, os 17.161 bytes do pedido composto foram mantidos pela aplicação,
sem omissão de mensagens nem corte do contexto atual. O número inclui políticas,
instruções e o anexo recebido; não corresponde ao tamanho do PDF em disco.

A sequência de conversa informada pelo usuário também foi repetida pela API
compatível, em JSON e streaming: saudação, duas perguntas sobre habilidades,
Lei 14.133/2021 art. 6, resposta “hoje”, mudança de assunto e pergunta técnica.
A conferência legal gera evidência e mantém conclusão suspensa se não confirma
vigência. Essa limitação não foi removida para corrigir a conversação.

Relatórios privados no servidor, sob `docs/runtime/`:
`chat-repair-before.json`, `chat-repair-acceptance-stage.json`,
`chat-repair-acceptance-production.json`, `chat-repair-retrieval-template.json`,
`pdf-root-probe.json`, `pdf-root-probe-after.json`.

## Operação e reversão

Imagem: `moara-core:chat-intent-20261030`; overlay
`moara/infrastructure/chat-intent-compose.yml` ao final do wrapper Compose.
Build e testes: `python3 infrastructure/chat-repair/build.py`.

Preservados: imagem `moara-core:pre-chat-intent-20261030`, wrapper anterior em
`backups/chat-intent-20261030/compose-before` e template anterior em
`backups/chat-intent-20261030/rag-template-before.json`.
O template foi atualizado pela API administrativa, enviando somente `RAG_TEMPLATE`;
as demais configurações foram comparadas e permaneceram iguais.

Backup anterior à publicação: `moara-before-migration-20261030T173102Z.tar.enc`,
restauração isolada aprovada às 17:32:25 UTC. Não restaurar o banco para reverter
apenas esta imagem. A reversão do template deve considerar alterações posteriores
de outros administradores. O servidor de inferência, a residência GPU, os pesos e
os certificados não foram reiniciados ou substituídos por esta correção.
