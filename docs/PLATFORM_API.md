# API dos novos módulos

Base: /moara/api/v1/platform. Autenticação, origem e CSRF seguem o gateway
existente. A documentação OpenAPI completa requer status.read.

| Operação | Caminho | Permissão |
|---|---|---|
| Listar/criar/editar/arquivar itens | /resources, /resources/{id} | workspace.use e propriedade para alterações |
| Versões | /resources/{id}/versions | workspace.use e ACL atual |
| Upload/download | /documents, /documents/{id}/download | documents.use e ACL |
| Chunks e pesquisa | /documents/{id}/chunks, /knowledge/search | knowledge.use e ACL |
| Preencher template | /templates/{id}/render | documents.use |
| Indicadores | /analytics/query | data.query |
| Criar execução | /runs | workspace.use e permissão da operação |
| Consultar/cancelar | /runs/{id}, /runs/{id}/cancel | jobs.read/jobs.cancel e proprietário |
| Revisar/aceitar código | /projects/{id}/review, /projects/{id}/accept | development.use |
| Aprovar execução | /projects/{id}/execute | development.execute e sessão interativa |
| Grupos e agentes | /groups, /agents | workspace.use |

PUT exige version; versões obsoletas retornam 409. Nunca há sobrescrita silenciosa.
POST /runs aceita idempotency_key de até 100 caracteres. Repetição com mesmo
conteúdo retorna a mesma execução; conteúdo diferente retorna 409.

Operações de fila: document.ingest, knowledge.answer, assistant.run,
project.generate, legal.draft e workflow.run. project.execute só entra pela rota
interativa de aprovação. A fila comporta até 24 jobs ativos; processamento de IA
é serial para controlar o consumo de CPU. Timeout de job: 600 segundos. Lease
expirada falha explicitamente; não há repetição automática de efeitos.

Workflows aceitam até 12 etapas. Tipos: knowledge.search, template.render,
analytics.aggregate e notification.test. Não existem etapas shell, SQL livre,
HTTP arbitrário ou envio externo.

Chaves de API preservam scopes e allowed_profiles. Para documentos,
allowed_sources deve conter explicitamente os UUIDs autorizados; lista vazia
não concede acesso documental. As permissões são sempre a interseção da chave,
da conta e da ACL atual.

Erros não incluem conteúdo de documentos nem segredos. Logs guardam identificador,
rota, status e tipo de falha. Conteúdos e resultados não são enviados à telemetria.
