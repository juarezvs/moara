# Pendências e limites atuais

| ID | Estado | Trabalho restante |
|---|---|---|
| OPS-001 | Resolvido | Backup/restore antes e depois da migração |
| OPS-002 | Resolvido no escopo | Reboot físico exige janela operacional |
| OPS-003 | Parcial | TLS verificado; inspeção privilegiada de firewall pendente |
| OPS-004 | Dependência externa | Destino externo de backup, guarda da chave e retenção |
| SEC-001 | Alta | Kernel informa GDS vulnerável; tratar microcode/kernel |
| SANDBOX-001 | Limite | Rootless Docker+seccomp não substitui VM/gVisor |
| PERF-001 | Parcial | Matriz 7B pronta; faltam corpus representativo e carga prolongada |
| RAG-001 | Parcial | Pipeline passou com fontes fictícias; avaliar recall em corpus jurídico |
| AD-001 | Parcial | LDAPS testado; SPN/keytab necessários para Kerberos/SPNEGO |
| PJE-001 | Dependência externa | Endpoint oficial, contrato, credenciais e escopo; nenhuma integração real nova ativada |
| FLOW-001 | Deliberado | Operações fixas e notificações simuladas; efeitos externos exigem integração específica |
| DEV-001 | Parcial | Git local do projeto; sem integração dos projetos de usuário com Git remoto |
| DOC-001 | Parcial | DOCX preserva estilos, tabelas e cabeçalhos; PDF é cópia textual de conferência, sem fidelidade ao layout Word |
| QA-001 | Parcial | Smoke e testes sintéticos passaram; pentest e aceite institucional pendentes |
| INFRA-001 | Dependência externa | RAID/SMART, temperatura e inspeção privilegiada |

Não ocultar estes limites sob uma declaração de conclusão integral. A entrega
funcional e a cobertura estão em PLATFORM_RELEASE.md e PROJECT_STATUS.md.
