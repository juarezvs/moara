# Decisões arquiteturais

## ADR-001 — continuidade da instalação existente

26/10/2026. A inspeção encontrou 25 containers ativos e aplicação própria Angular/
FastAPI. Evoluir essa base, com staging isolado. Não criar stack produtiva paralela
nem mover arquivos/imports antes de mapear dependências. Raiz remota atual:
`/home/nutec/ai-server`; workspace local de diagnóstico: `C:/moara`.

## ADR-002 — backend modular e dados locais

Preservar a separação Angular → FastAPI → roteador → runtime CPU. PostgreSQL com
pgvector, Redis/Celery, armazenamento e observabilidade já existem. Verificar
implementações e lacunas por domínio antes de adicionar serviços. Manter ACLs no
backend, autorização antes da recuperação e validação determinística de ferramentas.

## ADR-003 — runtime preservado até benchmark

Ollama já opera localmente. llama.cpp deve ser avaliado em isolamento com pesos,
quantização, contexto e parâmetros registrados. Não presumir superioridade ou
definir modelo produtivo por nome. Modelos grandes opcionais; residência e
concorrência serão revistas com medições de memória/latência.

## ADR-004 — estrutura-alvo sem migração prematura

A estrutura pedida `apps/web`, `apps/api`, `services`, `packages`, `connectors`,
`models`, `infrastructure`, `docs` e `tests` permanece como referência. Por enquanto,
o código remoto usa `moara/web`, `moara/gateway`, `moara/identity`, `connectors`,
`gateway/fastapi`, `ia-studio` e `infrastructure`. Reorganizar exige um marco próprio
com imports, builds e deploys verificados. Diretórios vazios não representam módulos
implementados. A arquitetura final mantém um backend modular e workers especializados.
