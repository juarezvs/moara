# Leitura automática de anexos no chat

## Problema confirmado

Os perfis auto/general/fast da integração tinham file_context=false e ferramentas nativas habilitadas. O modelo recebia a referência do anexo, mas podia responder sem usar view_file/query_chat_files. Apenas instruir o usuário a pedir uma leitura não corrige esse fluxo.

## Mudança

A extensão em moara/webui/auto-documents abre os arquivos anexados antes da primeira inferência e fornece fontes ao mecanismo nativo de contexto/citações. Essa etapa é obrigatória para anexos do tipo file, independentemente da decisão do modelo de chamar uma ferramenta.

- Resolve o ID no armazenamento do servidor; não confia em conteúdo, nome ou status enviado pelo cliente.
- Reutiliza a autorização nativa de leitura. Arquivos sem acesso não são expostos.
- Arquivo pendente, com falha ou sem texto gera erro explícito; não produz uma resposta fingindo análise.
- Inclui integralmente o texto curto. Para documentos maiores, percorre o texto extraído inteiro e seleciona passagens por termos da pergunta e linguagem de obrigações/prazos, com localização por caracteres e cobertura parcial declarada.
- Mantém orçamento UTF-8 limitado, reserva para instruções/citações e erro explícito quando o histórico não comporta a análise.
- Orienta a responder à pergunta original com providência, setor responsável, prazo expresso e fonte; não pedir nova autorização para ler ou um resumo ao usuário.
- Mostra a etapa real “Moara está lendo os documentos anexados…”.

A leitura automática não transforma texto parcial em análise integral. Para documentos extensos, a resposta deve distinguir os trechos examinados de uma conclusão exaustiva. Não foi instalado novo modelo. PDFs precisam de texto extraível; a detecção de ausência de texto é explícita, sem simular OCR.

## Implantação

Base preservada: ai-webui:moara-feedback-20261027.
Imagem publicada: ai-webui:moara-auto-documents-20261027-r4.
Digest: sha256:eaf105ff83f5b1957c6dce4f544b91adbb59d460b4cd144d61967833d2299985.
Apenas webui recriado. Lote 16, concorrência 1 e os indicadores existentes preservados.
Reversão: restaurar moara/infrastructure/chat-feedback-compose.yml de docs/runtime/auto-documents-20261027/compose-before.yml no servidor e recriar somente webui pelo helper Compose completo; não remover volumes.

## Verificação

Nove testes isolados passaram: conteúdo integral, citações, acesso negado, estado pendente, texto vazio, ausência de anexos, orçamento do histórico, passagem no meio de documento extenso, limite UTF-8 e entidades HTML.

Teste pelo navegador publicado usa PDFs integralmente fictícios e pergunta natural, sem ordenar uso de ferramentas:
1. Providência NUTEC: validar Atlas até 12/11/2026; ofício pertence à SECAD.
2. Apenas ciência para NUTEC: tarefa da SECAD não deve ser atribuída à NUTEC.
3. Documento de oito páginas: obrigação de renovar certificado Boreal até 20/12/2026 na sexta página.

Relatório: docs/evidence/automatic-documents-browser.txt. As rotinas removem apenas arquivos e conversas sintéticos que criaram e revogam a sessão temporária. Tarefas auxiliares de títulos/etiquetas são desabilitadas no ensaio para não competir com a inferência principal; o processamento do anexo e da pergunta é o fluxo normal publicado.

## Correção da verificação de backup

O banco temporário do teste de restauração aceitava conexão via socket durante a inicialização e reiniciava logo em seguida. A prontidão agora é verificada por TCP em 127.0.0.1, disponível no servidor definitivo. O backup existente foi restaurado em ambiente isolado; hashes, contagens, bancos SQLite e PostgreSQL passaram. Nenhum dado de produção foi modificado pelo teste.

A primeira rodada passou nos documentos curtos, mas o caso extenso revelou uma resposta incorreta. A revisão ordena passagens por relevância, preserva as posições originais e remove trechos quase duplicados. O PDF de oito páginas foi usado em um teste de regressão com orçamentos de 1.500, 4.000 e 9.000 bytes: a obrigação e o prazo precisam aparecer nos primeiros 1.000 caracteres em todos eles. Relatório do reteste pelo navegador: docs/evidence/automatic-documents-long-r2.txt.

A rotina completa ai-backup.service também foi executada novamente e encerrou com sucesso após a correção.

A segunda rodada extensa localizou a obrigação, mas apresentou conclusão inicial contraditória. A revisão final filtra o histórico repetitivo quando a pergunta é sobre providências e há determinações específicas. Trechos com obrigações não são descartados como quase duplicados: há teste adicional para duas tarefas semelhantes com prazos diferentes. O teste de navegador passou a rejeitar explicitamente a negação de obrigações quando o documento contém a providência esperada. Relatório final: docs/evidence/automatic-documents-long-r3.txt.

Resultado final confirmado na revisão r3: pergunta natural sobre o PDF de oito páginas respondida com a determinação de renovar o certificado do portal Boreal até 20/12/2026, juntar evidência e citar a fonte, sem negar a obrigação. Eventos de leitura automática e fontes foram observados. Tempo desse ensaio: 158 segundos. Arquivo e conversa sintéticos removidos, sessão temporária revogada. Os cenários curtos de providência e mera ciência passaram na primeira rodada; a revisão final preserva a inclusão integral dos documentos curtos. Saúde final, hash do módulo e preservação dos outros serviços: docs/evidence/automatic-documents-final-health.txt.

## Continuação de conversas longas — revisão r4

A rejeição baseada no tamanho do histórico foi substituída por compactação da cópia enviada ao modelo. A imagem é ai-webui:moara-auto-documents-20261027-r4, digest sha256:eaf105ff83f5b1957c6dce4f544b91adbb59d460b4cd144d61967833d2299985.

- O histórico salvo não é reescrito ou apagado.
- Instruções system/developer, pergunta atual e sua cadeia ativa de ferramentas permanecem integrais.
- Rodadas recentes cabem como blocos completos, mantendo chamadas e resultados de ferramentas juntos.
- Partes antigas recebem recortes textuais limitados, identificados como histórico parcial. A primeira instrução do usuário recebe um trecho prioritário; não há promessa de retenção integral de todas as instruções antigas.
- Fontes dos anexos são consultadas novamente sob a mesma autorização, sem novo upload.
- O evento em português informa que o histórico foi ajustado apenas para aquela resposta.
- Se a pergunta atual ou as próprias instruções/ferramentas excederem o espaço disponível, permanece uma falha explícita; não se corta a pergunta nem se desliga o limite do gateway.

Treze testes internos passaram, incluindo preservação do histórico original, identidade da pergunta atual, proteção de instruções, pares de ferramentas e nova leitura do arquivo após redução de um histórico grande.
Teste de navegador: docs/evidence/history-continuation-browser.txt. Ele cria somente uma conversa fictícia, com 16 mensagens antigas e um PDF, faz duas perguntas sem reenviar o anexo e compara o conteúdo original de cada mensagem salva após cada resposta.

Resultado r4: ambas as perguntas de continuação passaram, com evento de compactação e nova leitura do documento em cada rodada, apenas um upload e as 16 mensagens originais preservadas exatamente. A primeira resposta identificou a validação Atlas pela NUTEC até 12/11/2026; a segunda confirmou que esse prazo não foi atribuído à SECAD. Conversa e arquivo fictícios removidos. Serviço saudável e backup verificado: docs/evidence/history-compaction-final-health.txt.
