# Pendências

| ID | Prioridade | Pendência e evidência necessária |
|---|---|---|
| OPS-001 | Resolvida | Backup corrigido e restore isolado verificado em 26/10; ver PHASE1_OPERATIONS.md |
| OPS-002 | Resolvida no escopo | Unidade ativa; stack completa e persistência testadas em staging; reboot produtivo depende de janela |
| OPS-003 | Parcial | TLS/DNS/rotas verificados; inspeção privilegiada de firewall pendente |
| OPS-004 | Alta | Destino de backup fora do host, guarda separada da chave e política de retenção |
| SEC-001 | Alta | Avaliar GDS/microcode com infraestrutura; kernel indica Vulnerable |
| PERF-001 | Média | Rever quatro modelos Forever; benchmark threads/NUMA e capacidade concorrente |
| DATA-001 | Alta | Auditar fontes e ACLs existentes sem consultar ou copiar dados reais |
| DEV-001 | Parcial | 83 arquivos importados com hashes e versão local; restante da árvore remota ainda sem Git |
| QA-001 | Alta | Reexecutar testes em homologação, sem usar aceites históricos como novos |
| INFRA-001 | Média | Temperatura, RAID/SMART, certificados e firewall requerem inspeção adicional |
| AD-001 | Dependência | Domínio/CA/SPN/grupos e autenticação segura somente quando iniciar Fase 11 |
| RAG-001 | Dependência | Validar modelos/dimensões; não misturar índices de embeddings incompatíveis |
