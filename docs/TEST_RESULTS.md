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
