# Estado da implantação — 26/10/2026

Servidor 172.19.5.250; código /home/nutec/ai-server.
URL: https://moara.am.trf1.gov.br/moara/espaco.

R2 publicada em 2026-10-27T01:00:11.039386+00:00. Imagem:
sha256:48989ca495c04815242fa0db9df3978a8d7d520c3b4184974a7fec593c8bf461
(moara-core:platform-20261026-r2). Anterior (R1):
sha256:47cfddf5b672bce68f24986e4bd9eba031f8310f97eb9fa454e5eb5e08acd92d.

Migração 0005_platform confirmada; PostgreSQL passou de 39 para 46 tabelas.
Somente ai-server-moara-gateway-1 foi substituído. Outros 24 containers preservados;
todos em execução e healthchecks disponíveis saudáveis. ai-server.service e
moara-sandbox-worker.service ativos. A unidade também está em infrastructure/systemd.

Rotas públicas /, /moara/, /studio/ e health retornaram 200. Recursos retornaram
401 sem credenciais. Agents, groups e runs retornaram 200 com sessão administrativa;
nenhum conteúdo institucional foi incluído no relatório.

## Backup e rollback

Antes: moara-before-migration-20261026T143424Z.tar.enc,
SHA256 c5ea939f57b25608df499d7834cf19106fb037d5fa10a1bcfb73eccd0f48f9a6.
Restore verificado em 14:35 UTC.

Após migração: moara-before-migration-20261026T170055Z.tar.enc,
SHA256 31b96098331e7da4633fe9889cc375c2f3ebb232fd4b835525226bf4ed363240,
858401792 bytes, 46 tabelas; restore isolado verificado.
Consulte o manifesto operacional para backups posteriores.

Preservação: /home/nutec/ai-server/docs/runtime/platform-release-20261026/before
e before-state.json no diretório pai. Migração aditiva: rollback da aplicação
não apaga tabelas nem restaura dados antigos sobre novos.

A primeira tentativa acionou rollback porque o teste usou ai-root-ca.crt em vez
da CA específica do domínio. A imagem anterior voltou saudável. O teste foi
corrigido para moara-domain-root-ca.crt e a publicação passou com validação de
cadeia e hostname; TLS não foi desativado.

Rollback manual: parar moara-sandbox-worker.service, aplicar a imagem anterior
no overlay e subir somente moara-gateway com --no-deps --no-build. Restaurar os
arquivos preservados e conferir rotas. Não usar down -v nem apagar migrations.

Não houve reboot, mudança de credenciais ou importação de dados de homologação.

## Preservação R2

Diretório: /home/nutec/ai-server/docs/runtime/platform-release-20261026-r2/before

Backup anterior: moara-before-migration-20261027T005817Z.tar.enc
SHA256 17eca3a91ed33a08403f53afe2bf15c7401a5eb02ccff37ca51941b381ec06d4. Restore verificado de 46 tabelas.
O supervisor de sandbox foi reiniciado para aplicar o timeout interno.
