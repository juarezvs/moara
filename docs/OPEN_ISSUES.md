# Pendências

| ID | Prioridade | Pendência e evidência necessária |
|---|---|---|
| OPS-001 | Alta | Corrigir PermissionError do backup sem expor segredos; novo backup e restore isolado |
| OPS-002 | Alta | Diagnosticar ai-server failed; ciclo de inicialização/healthchecks em staging |
| OPS-003 | Alta | Confirmar firewall/TLS/DNS e mudança de acesso público frente a documentos antigos |
| OPS-004 | Alta | Destino de backup fora do host, guarda separada da chave e política de retenção |
| SEC-001 | Alta | Avaliar GDS/microcode com infraestrutura; kernel indica Vulnerable |
| PERF-001 | Média | Rever quatro modelos Forever; benchmark threads/NUMA e capacidade concorrente |
| DATA-001 | Alta | Auditar fontes e ACLs existentes sem consultar ou copiar dados reais |
| DEV-001 | Média | Cópia seletiva/versionamento do código remoto; raiz sem Git |
| QA-001 | Alta | Reexecutar testes em homologação, sem usar aceites históricos como novos |
| INFRA-001 | Média | Temperatura, RAID/SMART, certificados e firewall requerem inspeção adicional |
| AD-001 | Dependência | Domínio/CA/SPN/grupos e autenticação segura somente quando iniciar Fase 11 |
| RAG-001 | Dependência | Validar modelos/dimensões; não misturar índices de embeddings incompatíveis |
