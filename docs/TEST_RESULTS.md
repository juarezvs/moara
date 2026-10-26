# Verificação da plataforma publicada — 26/10/2026

| Ensaio recente | Resultado |
|---|---|
| Build Angular | Passou; bundle inicial 626,20 kB bruto |
| Regressão backend | 77 testes passaram, incluindo cifra, serialização e isolamento de ferramentas |
| Conectores/SQL/SSRF/RBAC | 72 testes sintéticos passaram, sem rede |
| API/PostgreSQL/Redis | ACL, revogação, versões, arquivo privado, DOCX, analytics, fila e auditoria passaram |
| PDF/OCR | PDF digital e rasterizado reconhecidos por parser/Tesseract reais |
| Busca híbrida | pgvector real; embeddings determinísticos somente no teste de isolamento |
| Inferência local real | Embeddings, reranking, resposta citada, minuta e proposta/revisão passaram com textos fictícios |
| Sandbox | Python/TypeScript, rede negada, input readonly, sem segredos/socket, timeout e saída limitada |
| Aprovação durável | Digest errado rejeitado; versão aprovada persistiu saída 42 |
| LDAPS | 43 verificações em dois diretórios fictícios: TLS, injeção, grupos e revogação |
| Browser | Navegação, prompt, versões, fluxo, desktop/mobile, imagens e ausência de erros JS |
| Concorrência | 12 alterações: um sucesso e 11 conflitos; 12 enqueues idempotentes geraram um job |
| Agendamento | Disparo persistente observado no PostgreSQL |
| CPU | 9 configurações, 18 amostras; JSON estrito falhou e foi registrado, sem promoção automática |
| Publicação | 24 containers preservados; gateway substituído; autenticado 200 e anônimo 401 |
| Backup pós-migração | 46 tabelas restauradas em isolamento; sem restauração sobre produção |

Falhas corrigidas antes do aceite: contexto de Request ausente nos jobs, chave de
idempotência longa e serialização de UUIDs nas citações. Testes de regressão cobrem
contexto e serialização. O teste LDAPS antigo foi atualizado ao contrato ampliado,
exigindo identidade institucional verificada. A publicação exercitou rollback por
uso da CA errada no teste, corrigido sem desativar validação TLS.

Não foram medidos SLA, carga prolongada ou qualidade jurídica representativa.
Fixtures não foram importadas em produção. Evidências locais em docs/evidence.

---

# Histórico das fases 0 e 1 (anterior à entrega acima)

# Resultados de verificação — 26/10/2026

| Verificação executada | Resultado |
|---|---|
| Workspace e Git inicial | C:/moara vazio; sem repositório Git inicial |
| SSH BatchMode e chave estrita | Acesso bem-sucedido como nutec; Linux confirmado |
| Coletor pelo Python/OpenSSH | Executado, retorno SSH 0; evidência UTF-8 local |
| CPU/RAM/NUMA/disco/serviços/portas | Inventário real registrado |
| Containers e modelos | 25 ativos; catálogo real listado; quatro residentes CPU no principal |
| Systemd do usuário | Falhas reais em ai-server e ai-backup; Linger ativo |
| Diagnóstico no journal | Backup PermissionError; ai-server falhou esperando dependências |
| Temperaturas/firewall | Não confirmados: sensors ausente; sudo exige autenticação |
| Sintaxe Python | `python -m py_compile infrastructure/scripts/collect_inventory.py` passou |
| Sintaxe Bash | Script enviado por SSH para `bash -n`; retorno 0 |
| Links e evidências | Links locais Markdown e seções obrigatórias do inventário conferidos |

Uma primeira coleta via pipeline do PowerShell introduziu CR no shell remoto.
Corrigida por transporte binário via subprocess com normalização LF; a evidência
foi substituída por execução bem-sucedida. Chamadas exploratórias com quoting de
templates Docker falharam; comandos foram corrigidos no script antes da coleta final.

Nesta sessão não foram executados testes funcionais de chat, autorização, banco,
RAG, AD, conectores, backups/restauração, geração, segurança, build Angular ou
benchmarks. Documentos anteriores descrevem ensaios históricos, sem revalidação.
Nenhuma funcionalidade nova da plataforma é declarada homologada.

## Fase 1 — resultados posteriores à aprovação

8 testes passaram no Linux. Testes reais de persistência/dependências em staging,
backup pré-publicação, backup via systemd, restores isolados, HTTPS, autenticação
negativa, IDs de containers e hashes publicados passaram. Evidências locais em
docs/evidence/phase1-*. Detalhes e limitações: PHASE1_OPERATIONS.md. Os testes de
aplicação listados como não executados na Fase 0 continuam fora deste escopo.
