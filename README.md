# MOARA AI

Inteligência Artificial Institucional da Justiça Federal do Amazonas.

Este workspace foi iniciado em 26/10/2026 para dar continuidade à instalação
existente em `nutec@172.19.5.250:/home/nutec/ai-server`. O diretório local estava
vazio; o servidor já contém uma plataforma Angular/FastAPI e 25 containers ativos.
Na Fase 1 foram importados 83 arquivos selecionados de código e publicadas as
correções de backup/inicialização. Esta cópia permanece parcial; não contém dados,
segredos, pesos ou toda a configuração necessária a uma instalação do zero.

- [Entrega operacional da Fase 1](docs/PHASE1_OPERATIONS.md)
- [Diagnóstico real da Fase 0](docs/PHASE_0_REPORT.md)
- [Plano executável e aprovação da Fase 1](docs/IMPLEMENTATION_PLAN.md)
- [Estado e continuidade](docs/PROJECT_STATUS.md)
- [Decisões arquiteturais](docs/ARCHITECTURE_DECISIONS.md)
- [Resultados de verificação](docs/TEST_RESULTS.md)
- [Pendências](docs/OPEN_ISSUES.md)

## Repetir o inventário

Requer Python 3 e OpenSSH, com chave de autenticação e identidade do servidor
previamente verificadas. Nenhuma biblioteca Python adicional é necessária.

```powershell
python infrastructure/scripts/collect_inventory.py
```

O coletor executa consultas de diagnóstico e grava a evidência localmente em
`docs/evidence/`. Não lê conteúdo de segredos, bancos, prompts ou documentos.
Não instala dependências nem reinicia serviços. SSH usa `BatchMode=yes` e
`StrictHostKeyChecking=yes`; falhas de verificação não são contornadas.

O código operacional continua no servidor. Os fontes importados mantêm a estrutura
de origem e os hashes registrados em docs/SOURCE_ORIGIN.json. Não copiar
`secrets/`, `.env`, backups, dumps, volumes ou relatórios com dados pessoais para Git.
