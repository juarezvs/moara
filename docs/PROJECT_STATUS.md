# Estado do projeto — 26/10/2026

Atualização operacional de 29/10/2026: inferência GPU em produção em 172.19.5.246, com aplicação e dados preservados em 172.19.5.250. Gemma 4 12B e embeddings permanecem residentes em serviços GPU separados, com túnel SSH e retorno automático à CPU. Aceite, evidências e operação: [GPU_PRODUCTION_2026-10-29.md](GPU_PRODUCTION_2026-10-29.md).

O usuário autorizou todas as fases restantes; não há aprovação pendente.

A versão R2 foi publicada em 27/10 às 01:00 UTC (26/10, 21:00 em Manaus), em
https://moara.am.trf1.gov.br/moara/espaco. Migração aditiva 0005_platform aplicada.
Um gateway substituído, 24 containers preservados; todos em execução e saudáveis.

| Fase | Resultado verificável | Limite atual |
|---|---|---|
| 0–1 | Diagnóstico, inicialização, backup e restore corrigidos | Reboot, firewall, GDS e backup externo dependem da infraestrutura |
| 2 | Ollama/llama.cpp: 9 configurações, 18 amostras | Não certifica todos os modelos nem qualidade jurídica |
| 3 | APIs protegidas, migrations, ACL, versões e auditoria append-only | Revisão independente ainda necessária para certificação |
| 4 | Angular, espaço de trabalho e testes desktop/mobile | Editor visual de etapas fixas; sem execução arbitrária |
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

Atualização de 30/10/2026: [Moara 2.0 — implantação e validação](MOARA_2_IMPLEMENTATION_2026-10-30.md). Base institucional e inferência mTLS publicadas; PJe/SEI pendentes de mecanismos oficiais e conclusões jurídicas automáticas suspensas quando a verificação não é conclusiva.

Ambiente de trabalho publicado: [interface, funcionalidades e validação](MOARA_WORKBENCH_2026-10-30.md), inspirado nas referências visuais fornecidas. Backend, banco, residência GPU e controles jurídicos preservados.

Correção publicada: [perguntas sobre capacidades, continuação por data e orçamento de anexos](MOARA_CHAT_REPAIRS_2026-10-30.md). PDF fornecido validado pelo chat original; manifesto e residência GPU preservados.


Entrada principal da Moara: [acesso, testes e procedimento de retorno](MOARA_PRIMARY_ENTRY_2026-10-30.md).


Navegacao lateral e etapas de processamento: [implantacao e validacao](MOARA_WORK_PROGRESS_2026-10-30.md).


MCP Normas 0.2: [fontes oficiais, historico legislativo e limites](MOARA_LEGAL_SOURCES_V2_2026-10-30.md).


Identidade visual original: [interface, validacao e recuperacao](MOARA_ORIGINAL_VISUAL_2026-10-30.md).


API pessoal para VS Code: [acesso, configuracao e validacao](MOARA_VSCODE_API_2026-10-30.md).


Consultas informativas e limites de dispensa: [correcao, fontes e verificacoes](MOARA_LEGAL_INFORMATION_2026-10-30.md).


Respostas juridicas fundamentadas: [fontes oficiais, cobertura e verificacoes](MOARA_LEGAL_GROUNDING_2026-10-31.md).


Interface unica: [contexto, identidade e historico](MOARA_UNIFIED_INTERFACE_2026-10-31.md).


Login de rede: [matricula, senha e orgao](MOARA_NETWORK_LOGIN_2026-10-31.md).


Identidade e acessos: [cadastro automatico, RBAC e administracao](MOARA_IDENTITY_RBAC_2026-10-31.md).


Pesquisa por assunto: [legislacao, fontes oficiais e evidencias](MOARA_LEGAL_DISCOVERY_2026-10-31.md).


Pesquisa por assunto: [legislacao, fontes oficiais e evidencias](MOARA_LEGAL_RECOVERY_2026-10-31.md).


Pesquisa por assunto: [legislacao, fontes oficiais e evidencias](MOARA_JURISPRUDENCE_2026-10-31.md).


[Fontes junto aos trechos e painel de consulta](MOARA_SOURCE_HINTS_2026-10-31.md).


[Descoberta web e restrição observada no Google Modo IA](MOARA_GOOGLE_DISCOVERY_2026-10-31.md).


[Identificacao da lei de carreiras e recuperacao por assunto](MOARA_CAREER_DISCOVERY_2026-10-31.md).


[Acervo de teses com e sem repercussao geral do STF](MOARA_STF_THESIS_CATALOG_2026-10-31.md).


[Coleta automatica de metadados oficiais e integracao LexML](MOARA_LEXML_METADATA_2026-10-31.md).


[Leitura do chat e teses oficiais do STF](MOARA_CHAT_READING_2026-10-31.md).


[Interface institucional propria da Moara](MOARA_INSTITUTIONAL_DESIGN_2026-10-31.md).


[Rolagem de processamento e inicio da resposta](MOARA_CHAT_SCROLL_2026-11-01.md).

Atualização de 02/11/2026: [atendimento sem exigência de finalidade institucional e pesquisa web com SearXNG/Trafilatura](MOARA_PUBLIC_WEB_2026-11-02.md), publicados e validados com 280 testes unitários, 14 verificações reais de API e 8 de navegador em produção. Modelo principal e embeddings permanecem residentes na GPU.

Chat com rolagem da página: [alterações, diff e validação em desktop/celular](MOARA_PAGE_SCROLL_2026-11-02.md), publicado em 02/11/2026. Mensagens sem limite de altura nem scroll vertical interno, compositor sticky e Markdown preservado; 10 testes de streaming e 40 verificações no navegador em cada ambiente aprovados.

Minutas jurídicas: [petição com fontes oficiais, campos pendentes e edição](MOARA_LEGAL_DRAFTING_2026-11-02.md), publicada em 02/11/2026. Corrigidos o bloqueio genérico por data, a identificação do assunto com as instruções do portal e a leitura de referências internas nos artigos. Validação: 299 testes backend/MCP, 10 frontend, 11 verificações de API e 12 de navegador em cada ambiente; atualização concorrente de chaves de API preservada.
