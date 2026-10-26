# Estado da implantação

Atualizado em 26/10/2026 após aceitação da Fase 1.

Servidor: 172.19.5.250. Código: /home/nutec/ai-server. Correções publicadas somente
nos scripts de backup/inicialização e unidades systemd do usuário.

- ai-server.service: active/exited, Result=success, ExecMainStatus=0.
- ai-backup.service: inactive/dead após execução oneshot bem-sucedida,
  Result=success, ExecMainStatus=0. Inactive neste caso é o estado esperado.
- ai-backup.timer: active; agenda diária preservada.
- 25 containers originais em execução, IDs preservados; healthchecks existentes saudáveis.
- DNS moara.am.trf1.gov.br resolve 172.19.5.250; cadeia e hostname TLS verificados
  com a CA pública interna. /, /moara/, /studio/ e /health retornaram 200;
  /moara/api/v1/auth/me e /moara/api/v1/admin/accounts retornaram 401 sem credenciais.

Último backup verificado nesta sessão: moara-before-migration-20261026T131943Z.tar.enc.
Tamanho: 857828880 bytes.
SHA256: 6f2bc3f36ac68db3b160c6db7ca7eae833b6beb593601621a3227ef2df59b0a4.
Verificado em 2026-10-26T13:21:06.943333+00:00 (UTC), aproximadamente 09:21 em Manaus.

Rollback e evidências: PHASE1_OPERATIONS.md. Nenhuma imagem reconstruída, volume
produtivo removido ou reboot realizado. Firewall permanece sem inspeção privilegiada.
