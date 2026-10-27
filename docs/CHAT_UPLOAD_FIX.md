# Correções do chat nativo — 27/10/2026

O chat em https://moara.am.trf1.gov.br/ usa Open WebUI. É diferente do espaço institucional /moara/espaco.

## Causas confirmadas

1. A integração webui tinha lote de um trecho e cota de 120 requisições/minuto.
2. Embeddings e respostas compartilham a fila de inferência. Uma espera superior a 120 segundos também pode retornar 429.
3. A alteração de lote pela API é apenas em memória nesta versão: as variáveis de lote são lidas do ambiente ao iniciar.
4. A leitura nativa view_file retornava por padrão 10.000 caracteres. Junto do histórico e das ferramentas, esse texto pode ultrapassar o orçamento de contexto do modelo.

## Implementação

- Overlay `moara/infrastructure/chat-feedback-compose.yml`: lotes de 16, concorrência 1, processamento sequencial. Esses valores foram confirmados por API após recriar o serviço.
- Imagem `ai-webui:moara-feedback-20261027`, baseada na imagem anterior preservada `ai-webui:before-feedback-20261027`.
- Identificador publicado: `sha256:6097bff8940e3499eb6a2197426ee9832e72c9e8ca58465cb14f68eecb4472b6`.
- Repetição apenas do lote corrente em respostas HTTP 429/503/504 do gateway interno. Até seis tentativas, orçamento de 900 segundos por chamada; Retry-After respeitado. Não repete falhas de autenticação nem altera outros provedores.
- Progresso de envio medido pelo navegador; extração sem percentual fictício; indexação medida pelos trechos concluídos; etapa explícita de espera e de salvamento. Arquivo só aparece pronto após status completed.
- A rota de status mantém sua autorização original. Progresso não contém texto do documento.
- Indicadores “Moara está preparando a resposta…” e “Moara está escrevendo a resposta…” ligados à requisição e aos eventos reais de conteúdo do chat.
- Leitura de arquivo: padrão de 2.000 caracteres, limite de 4.000; limite também aplicado a linhas excepcionalmente longas. Paginação mantida, autorização preservada e ferramenta orientada a buscar passagens relevantes.
- Mensagem em português para excesso de contexto. O limite de segurança do gateway foi preservado; um histórico já extenso ainda pode exigir nova conversa.

## Validação

- Oito testes de lotes, progresso, repetição, cancelamento e limites passaram.
- Quatro testes do leitor instalado, com documento fictício de mais de 100 mil caracteres, passaram: padrão, limite, paginação, linha longa e acesso negado.
- Chromium com respostas simuladas verificou percentuais, espera, conclusão, eventos de resposta e mensagem de contexto, sem erros JavaScript.
- Navegador de produção confirmou a extensão, o estado de preparação e o desaparecimento do indicador ao concluir a resposta.
- Ensaio de upload real: TXT fictício de 1.363.149 bytes, consulta restrita à coleção criada pelo teste e remoção somente desse arquivo. Relatório final em `docs/evidence/embedding-upload-validation-feedback.txt`.
- Ensaio pelo navegador com documento fictício longo: leitura com view_file e resposta correta “cinco dias úteis”, sem erro de contexto. Conversa e arquivo removidos. Relatório: `docs/evidence/chat-feedback-browser-production.txt`. Uma consulta sem indicar leitura do início não localizou a informação esperada; a redução do trecho não garante a qualidade de toda busca semântica.
- O primeiro ensaio após publicação identificou o retorno ao lote 1. Foi interrompido explicitamente, seu arquivo removido, a configuração persistida e o ensaio repetido.
- Backup verificado antes da publicação. Somente webui foi recriado; demais contêineres preservados.

## Uso e limites

Atualizar a página com Ctrl+F5. Arquivos anteriores que terminaram com erro não são reprocessados automaticamente. Para repetir uma conversa que já ultrapassou o contexto, abrir nova conversa, anexar o documento e perguntar por um ponto específico.

O percentual de envio é diferente do percentual de indexação. Durante a extração ou espera, o sistema mostra a etapa sem simular avanço. A cota e a capacidade de processamento continuam limitadas; a repetição é finita.

## Reversão

O servidor preserva o helper anterior em `docs/runtime/chat-feedback-20261027/compose-before.sh` e a imagem anterior em `ai-webui:before-feedback-20261027`. Para reverter, restaurar o helper anterior e recriar apenas webui com o conjunto completo de overlays. Não remover volumes. A reversão também remove os novos indicadores e limites de trecho.

## Testes reproduzíveis

Executar `test_progress.py` e `test_excerpts.py` na imagem candidata, montando esta pasta em /tests, com rede desabilitada. O segundo testa o código instalado, sem abrir banco real. Executar `test_frontend.py` em Chromium/Playwright com a mesma montagem e rede desabilitada.

Os relatórios devem conter somente metadados de teste. Uma exceção do cliente de navegador incluiu o token temporário de manutenção; essa sessão foi revogada imediatamente, o relatório foi saneado e o tratamento de erros foi ajustado para ocultar o token. Nenhuma credencial permanente foi alterada. O documento institucional informado pelo usuário não foi usado como fixture de teste.

Resultado final confirmado: upload concluído, 4.275 trechos, progresso monotônico até 100%, espera observada, recuperação de um trecho e arquivo removido. Foram 1.179,4 segundos (cerca de 20 minutos), com consultas de chat simultâneas e texto muito mais denso que muitos PDFs de mesmo tamanho. Os três 429 observados na janela de testes não impediram a conclusão; a contagem inclui as outras consultas sintéticas concorrentes. Serviço saudável e demais contêineres inalterados. Resumo: docs/evidence/chat-feedback-final-validation.txt.
