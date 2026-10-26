# MOARA AI

Inteligência Artificial Institucional da Justiça Federal do Amazonas.

Este workspace foi iniciado em 26/10/2026 para dar continuidade à instalação
existente em `nutec@172.19.5.250:/home/nutec/ai-server`. O diretório local estava
vazio; o servidor já contém uma plataforma Angular/FastAPI e 25 containers ativos.
Não confundir este repositório de acompanhamento e diagnóstico com uma cópia
completa do código ou com uma nova implantação da aplicação.

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

O código da aplicação continua no servidor. A estrutura de origem será preservada
ao trazê-lo para desenvolvimento, após seleção e revisão dos arquivos. Não copiar
`secrets/`, `.env`, backups, dumps, volumes ou relatórios com dados pessoais para Git.
