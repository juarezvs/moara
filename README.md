# Moara AI — plataforma local de inteligência artificial

Implantação CPU-only em srvdev01-am (172.19.5.250), administrada por nutec via SSH por chave.

O plano foi aprovado em 19/10/2026 com autorização explícita para remover Nextcloud e dedicar
a máquina à IA. Docker rootless mantém a operação diária sem sudo. A stack usa serviços
isolados, HTTPS por túnel SSH, autenticação por cliente e inferência/embeddings locais.

O chat principal está em **https://localhost:8443/**, com tema Moara e seleção
**Moara AI · Automático** pelo gateway Moara. Históricos, anexos e ferramentas
permanecem na interface existente. A Central em `/moara/` administra conectores,
modelos e tokens; múltiplos diretórios LDAPS têm cadastro protegido.
Leia [chat integrado, equipe, IDEs e ADs](docs/MOARA-CHAT-INTEGRADO.md).

A primeira entrega da plataforma própria está em `https://localhost:8443/moara/`.
Ela reúne chat, identidade institucional, modelos, conectores, contas/chaves e monitoramento.
Consulte [operação da Moara](docs/MOARA-OPERACAO.md), [evidências dos testes](docs/MOARA-VALIDACAO.md)
e [backup/rollback](docs/backup-rollback.md). O chat anterior, com histórico e anexos,
permanece em `/` durante a migração incremental; o Studio permanece em `/studio/`.

Leia [a entrega Gemma 4](docs/migracao-gemma4.md), [o manual de administração](docs/administracao.md)
e [o diagnóstico e plano inicial](docs/diagnostico-e-plano.md).
Para integrações individuais, consulte [as chaves de API da equipe](docs/api-keys-equipe.md).
Os quatro modelos adicionais, os tempos medidos e o perfil atual de 12 threads estão em
[modelos e CPU](docs/MODELOS-CPU.md).
O código do SECP não é alterado. Não há ingestão automática de documentos institucionais.

## Componentes

Chat com tema Moara → gateway Moara/roteador → adaptador FastAPI → Ollama.
Clientes novos usam `/moara/v1`; os antigos e os serviços de embeddings/imagens
mantêm suas bases. PostgreSQL/pgvector mantém RAG;
Caddy termina TLS. O agente Aider usa workspace isolado. Continue roda na estação.
O alias general usa Gemma 4 26B A4B Q4_K_M. Programação usa Qwen3-Coder 30B A3B,
respostas rápidas usam Qwen3 8B e embeddings usam embeddinggemma:300m. A inicialização
carrega e verifica esses quatro modelos em CPU; ai-warm-models.service registra o resultado.
As redes de dados e agentes mantêm seu isolamento. O serviço de autenticação do
chat possui saída para DNS/LDAPS; não publica portas. Caddy usa uma rede edge
para publicação exclusivamente em loopback.

Instalação administrativa: infrastructure/scripts/bootstrap-root.sh, executada manualmente
com sudo no terminal. Depois: `bash infrastructure/scripts/deploy.sh` como nutec.
Não repetir bootstrap ou remoção de serviços em outro host: o script valida host e IP.

## Validação

Testes unitários do gateway: `python -m pytest tests/test_gateway.py -q`.
Testes do servidor implantado: `python3 tests/acceptance.py`.
Integração Gemma 4, WebUI e RAG: `python3 tests/gemma4-acceptance.py`.
Estado do carregamento: `systemctl --user status ai-server ai-warm-models`.
Benchmarks: `bash infrastructure/scripts/benchmark.sh`.

Scripts adicionais: status.sh, healthcheck.sh, backup.sh, restore.sh e update.sh.
Não confundir arquivos preparados com testes efetivamente executados: os resultados de
aceitação, restore e benchmark são gerados somente durante suas respectivas execuções.

Moara 2.0: [implantação, validações e limites](docs/MOARA_2_IMPLEMENTATION_2026-10-30.md).

[Ambiente de trabalho da Moara — interface e funcionalidades](docs/MOARA_WORKBENCH_2026-10-30.md).

[Correções de conversa e contexto de anexos](docs/MOARA_CHAT_REPAIRS_2026-10-30.md).


Entrada principal da Moara: [acesso, testes e procedimento de retorno](docs/MOARA_PRIMARY_ENTRY_2026-10-30.md).


Navegacao lateral e etapas de processamento: [implantacao e validacao](docs/MOARA_WORK_PROGRESS_2026-10-30.md).


MCP Normas 0.2: [fontes oficiais, historico legislativo e limites](docs/MOARA_LEGAL_SOURCES_V2_2026-10-30.md).


Identidade visual original: [interface, validacao e recuperacao](docs/MOARA_ORIGINAL_VISUAL_2026-10-30.md).


API pessoal para VS Code: [acesso, configuracao e validacao](docs/MOARA_VSCODE_API_2026-10-30.md).


Consultas informativas e limites de dispensa: [correcao, fontes e verificacoes](docs/MOARA_LEGAL_INFORMATION_2026-10-30.md).


Respostas juridicas fundamentadas: [fontes oficiais, cobertura e verificacoes](docs/MOARA_LEGAL_GROUNDING_2026-10-31.md).


Interface unica: [contexto, identidade e historico](docs/MOARA_UNIFIED_INTERFACE_2026-10-31.md).


Login de rede: [matricula, senha e orgao](docs/MOARA_NETWORK_LOGIN_2026-10-31.md).


Identidade e acessos: [cadastro automatico, RBAC e administracao](docs/MOARA_IDENTITY_RBAC_2026-10-31.md).


Pesquisa por assunto: [legislacao, fontes oficiais e evidencias](docs/MOARA_LEGAL_DISCOVERY_2026-10-31.md).


Pesquisa por assunto: [legislacao, fontes oficiais e evidencias](docs/MOARA_LEGAL_RECOVERY_2026-10-31.md).


Pesquisa por assunto: [legislacao, fontes oficiais e evidencias](docs/MOARA_JURISPRUDENCE_2026-10-31.md).


[Fontes junto aos trechos e painel de consulta](docs/MOARA_SOURCE_HINTS_2026-10-31.md).


[Descoberta web e restrição observada no Google Modo IA](docs/MOARA_GOOGLE_DISCOVERY_2026-10-31.md).


[Identificacao da lei de carreiras e recuperacao por assunto](docs/MOARA_CAREER_DISCOVERY_2026-10-31.md).


[Acervo de teses com e sem repercussao geral do STF](docs/MOARA_STF_THESIS_CATALOG_2026-10-31.md).


[Coleta automatica de metadados oficiais e integracao LexML](docs/MOARA_LEXML_METADATA_2026-10-31.md).


[Leitura do chat e teses oficiais do STF](docs/MOARA_CHAT_READING_2026-10-31.md).


[Interface institucional propria da Moara](docs/MOARA_INSTITUTIONAL_DESIGN_2026-10-31.md).


[Rolagem de processamento e inicio da resposta](docs/MOARA_CHAT_SCROLL_2026-11-01.md).
