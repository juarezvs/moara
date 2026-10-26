# Estado do projeto — 26/10/2026

O usuário autorizou todas as fases restantes; não há aprovação pendente.

A plataforma ampliada foi publicada às 16:59 UTC (12:59 em Manaus), em
https://moara.am.trf1.gov.br/moara/espaco. Migração aditiva 0005_platform aplicada.
Um gateway substituído, 24 containers preservados; todos em execução e saudáveis.

| Fase | Resultado verificável | Limite atual |
|---|---|---|
| 0–1 | Diagnóstico, inicialização, backup e restore corrigidos | Reboot, firewall, GDS e backup externo dependem da infraestrutura |
| 2 | Ollama/llama.cpp: 9 configurações, 18 amostras | Não certifica todos os modelos nem qualidade jurídica |
| 3 | APIs protegidas, migrations, ACL, versões e auditoria append-only | Revisão independente ainda necessária para certificação |
| 4 | Angular, espaço de trabalho e testes desktop/mobile | Editor avançado de workflows permanece via API |
| 5 | Propostas/diff/revisão, aceitação e sandbox por digest | Rootless Docker, não VM/gVisor; sem Git remoto ou instalação livre de dependências |
| 6 | Upload, PDF/DOCX/OCR, embeddings, híbrida, reranking e citações | Corpus sintético; avaliação jurídica ampla e cross-encoder dedicado pendentes |
| 7 | Conectores existentes e 72 testes sintéticos | PJe novo depende de API/contrato/credenciais |
| 8 | Indicadores reproduzíveis de CSV e conectores existentes | Definições de indicadores corporativos dependem da instituição |
| 9 | Processos, fontes, linha do tempo e minutas | Não assina, decide, protocola ou valida juridicamente |
| 10 | Grupos existentes, prompts/templates/assistentes versionados | Compartilhar assistente não concede acesso às fontes |
| 11 | 43 verificações LDAPS em dois diretórios fictícios | SPNEGO precisa de SPN/keytab; sem novo login de usuário real |
| 12 | Jobs, idempotência, cancelamento, agendamento e etapas fixas | Notificações simuladas; sem efeitos externos reais |
| 13 | Backend, conectores, UI, inferência, concorrência e restore | Smoke de 12 requisições não certifica capacidade institucional |

Existe uma entrega funcional publicada cobrindo os módulos das fases 2–13, mas
**não se declara concluído o aceite integral de toda a especificação**.

Continuidade: PLATFORM_RELEASE.md, PLATFORM_USER_GUIDE.md, PLATFORM_API.md,
DEPLOYMENT_STATUS.md, TEST_RESULTS.md e OPEN_ISSUES.md. Evidências brutas ficam
em docs/evidence, fora do Git. Nenhum segredo ou dado corporativo foi trazido
para o workspace.
