# Estado da implantação

26/10/2026. Nenhuma nova versão foi implantada nesta sessão.

Servidor existente: `172.19.5.250`, código em `/home/nutec/ai-server`.
25 containers em execução; healthchecks declarados em estado healthy na coleta.
Docker rootless confirmado; `Linger=yes`; unidade `ai-server` habilitada, porém
failed. Unidade `ai-backup` failed; timer ativo. A existência de backups antigos
foi observada, sem leitura de conteúdo ou nova restauração.

Portas observadas: 22; 80/443 no IP institucional; 8080/8443 em loopback. A
disponibilidade HTTPS com certificado e login válidos ainda não foi revalidada.
Nenhuma porta/firewall/TLS foi modificada. Sudo exige autenticação interativa.
