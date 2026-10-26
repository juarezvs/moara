# Fase 1 — estabilização operacional

Entrega verificada em 26/10/2026. O usuário aprovou explicitamente o plano antes
das alterações. A implementação preservou a instalação existente.

## Problemas corrigidos

O backup diário antigo parava componentes e tentava ler diretamente arquivos
pertencentes ao usuário mapeado do Docker. A leitura de secp_rbac_config.json
falhava por permissão. O wrapper agora chama a rotina online de preservação e
restauração; um helper efêmero acessa a origem somente leitura, sem rede e com
DAC_READ_SEARCH restrito à execução de backup. Os arquivos originais mantêm
proprietários/permissões: o arquivo em questão continua 0400, UID/GID 110000.

O snapshot de configurações registra hashes e recusa erros de leitura, links não
aprovados e alterações durante a cópia. A chave do backup permanece separada.
Configurações, credenciais de recuperação e dados nunca são exportados para este
workspace. A cópia de preservação fica criptografada no servidor. Dependências,
caches, evidências de runtime e artefatos grandes não secretos têm exclusões
registradas no manifesto interno; isso não equivale a uma imagem integral do disco.

A unidade ai-server utilizava somente o Compose original e tinha falhado em
21/10 após interrupção/reinício, enquanto os containers seguiram operacionais.
A unidade passa a usar o helper Compose completo (25 serviços), com espera de
healthchecks, trava compartilhada com backup e flags para não reconstruir imagens,
baixar imagens ou recriar containers existentes. O gerador deploy.sh também foi
corrigido para não restaurar a unidade antiga numa implantação futura.

## Alterações publicadas

- moara/infrastructure/scripts/preservation.py: snapshot protegido de configurações,
  validação dos hashes e diretório raiz configurável para homologação administrativa.
- moara/infrastructure/scripts/config_snapshot.py: helper de cópia protegida.
- infrastructure/scripts/backup.sh: preservação online seguida de restore isolado.
- infrastructure/scripts/start-services.sh: inicialização serializada da stack completa.
- infrastructure/scripts/deploy.sh: geração coerente da unidade de inicialização.
- infrastructure/systemd/ai-server.service e ai-backup.service, copiados para o
  systemd do usuário nutec; timeout de backup de 3600 segundos.

## Verificação executada

| Ensaio | Resultado |
|---|---|
| 8 testes unitários no Linux | Passaram: exclusão da chave, falhas de leitura/credencial, cópia concorrente, symlink, ciphertext/HMAC adulterados e caminho de restore indevido |
| Ciclo de vida em staging sem rede | Dois containers; dependência saudável; PostgreSQL e arquivo persistiram após parada/início; IDs preservados |
| Backup pré-alteração | 857836272 bytes; restauração isolada aprovada |
| Backup pela unidade real corrigida | 857828880 bytes; 39 tabelas PostgreSQL, 11 bancos SQLite e hashes de arquivos/configurações validados |
| Estado final | ai-server ativo, backup concluído com código 0, timer ativo |
| Containers reais | 25, mesmos IDs anteriores, sem healthchecks com falha |
| HTTPS/DNS | Certificado e hostname válidos; 4 rotas 200 e 2 rotas protegidas 401 |
| Segredo protegido | Permissão e UID/GID preservados |
| Limpeza de staging | Containers/volumes fictícios removidos após validar rótulos únicos |

Os testes de adulteração usam dados fictícios e confirmam recusa antes de
qualquer chamada de descriptografia. O restore real usa container PostgreSQL sem
rede e sem portas; não substitui bancos de produção. Snapshots são consistentes
por serviço, sem garantia de transação distribuída entre todos os serviços.

## Artefatos e operação

Diretório privado de preservação das versões anteriores e evidências no servidor:
/home/nutec/moara-phase1/20261026T131413Z.

Backup pré-publicação: moara-before-migration-20261026T131428Z.tar.enc.
Backup da unidade corrigida: moara-before-migration-20261026T131943Z.tar.enc.
SHA256 do último: 6f2bc3f36ac68db3b160c6db7ca7eae833b6beb593601621a3227ef2df59b0a4.

Para executar o backup pela rotina operacional já instalada:

```sh
systemctl --user start ai-backup.service
systemctl --user show ai-backup.service -p Result -p ExecMainStatus
systemctl --user is-active ai-backup.timer
```

Confirmar também verified=true e nomes correspondentes em
/home/nutec/ai-server/docs/runtime/moara-preservation-latest.json e
moara-preservation-restore.json. Cada execução gera outro arquivo; não interpretar
somente a existência do arquivo ou Result=success antigo como um backup recente.
Não há remoção automática de backups adicionada nesta fase.

Para repetir o restore de um pacote específico, usar preservation.py verify com
um arquivo de preservação dentro de backups. O HMAC é conferido antes de descriptografar.
O coletor de inventário local continua disponível em infrastructure/scripts.

## Rollback restrito

As versões anteriores dos três scripts modificados e das duas unidades estão em
20261026T131413Z/before no diretório privado acima. Caso haja regressão, comparar
hashes e restaurar somente o arquivo/unidade afetado, preservando uma cópia da
versão atual. Para unidade, executar systemctl --user daemon-reload após a cópia.
Os helpers novos podem permanecer inativos; não exigem exclusão de dados.

Não reverter o backup completo para corrigir um script. A versão anterior do backup
tem a falha de permissão conhecida. Não executar deploy.sh completo, compose down -v,
limpeza geral ou reboot como rollback. Qualquer recuperação dos dados em produção
exige procedimento específico. Não foi necessário executar rollback nesta entrega.

## Limitações e próximos passos

Backup e chave ainda residem no mesmo equipamento: falta destino externo e guarda
separada. Pesos de modelos e histórico TSDB do Prometheus não são duplicados no
pacote. Kernel relata GDS vulnerável; firewall requer autenticação administrativa.
Não houve reboot produtivo nem certificação física de RAID/temperaturas. A persistência
foi validada em staging e no restore, conforme o escopo aprovado.

Fase 2 ainda deve revisar modelos/licenças/NUMA/threads. Testes de aplicação,
conectores corporativos e autenticação AD não foram reexecutados nesta fase.
