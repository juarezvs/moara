# Upload de documentos — 2 de novembro de 2026

O chat e o espaço de trabalho passam a enviar arquivos binários por um endpoint próprio, sem teto fixo de tamanho por documento. A mensagem de 4 MiB foi removida. O percentual de 0 a 100% representa bytes transferidos pelo navegador; a confirmação do armazenamento e a extração/indexação aparecem como etapas distintas, sem porcentagens simuladas.

## Implementação

- `POST /moara/api/v1/platform/documents/upload`: corpo binário, nome e título nos parâmetros. Mantém autenticação, CSRF, autorização, compartilhamento e auditoria.
- Armazenamento em segmentos criptografados de até 1 MiB, com SHA-256 e tamanho em `bigint`. Falhas e interrupções desfazem a transação, evitando documentos incompletos.
- Download em streaming, compatível com documentos antigos. A migração 011 preserva os arquivos e permissões existentes.
- Indexação com arquivos temporários privados no volume de dados, leitura progressiva e lotes de embeddings. O documento continua disponível para download se a indexação falhar.
- O proxy e o middleware dispensam a limitação de corpo exclusivamente para a nova rota binária. As proteções das demais requisições JSON permanecem.
- O modelo principal, os embeddings e o MCP não precisam ser reiniciados. O proxy recebe recarga graciosa.

Não há tamanho máximo configurado para o upload pela nova interface. A capacidade física de armazenamento, a conexão e os recursos necessários para processar cada formato continuam finitos. Validações de formato, codificação e conteúdo permanecem; a ausência de teto de upload não garante que todo arquivo seja válido ou indexável.

## Validação e operação

As evidências da publicação ficam em `docs/runtime/document-upload-*.json`. Incluem 312 testes de backend, 13 testes de frontend, testes de autenticação e compatibilidade, e envio real de PDF de aproximadamente 40 MiB pelo navegador. O teste compara o SHA-256 do download com o original e verifica os estados do percentual e a indexação no chat.

Foi feito backup criptografado com restauração de verificação antes da migração. A configuração anterior do aplicativo e do proxy fica em `backups/document-upload-20261102`. A expansão do banco é compatível com o aplicativo anterior; um eventual retorno de versão deve preservar documentos já recebidos e considerar a leitura dos novos segmentos. Não remover tabelas nem converter documentos por meio de uma reversão destrutiva.

Para acompanhar falhas, consultar as execuções `document.ingest`, os eventos de upload/download e os logs estruturados do gateway. Arquivos grandes podem aguardar a fila de indexação: 100% de transferência não significa que a indexação terminou.
