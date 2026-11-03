# Operação, manutenção e reversão da Moara 2.0

A interface foi atualizada: a imagem ativa é `moara-core:legal-sources-v2-20261030`, com `legal-sources-v2-compose.yml` ao final do wrapper. Ela preserva o ambiente de trabalho e inclui as [correções de conversa/anexos](MOARA_CHAT_REPAIRS_2026-10-30.md). Ver [ambiente de trabalho e reversão](MOARA_WORKBENCH_2026-10-30.md). A raiz do portal agora abre o mesmo chat; veja [entrada principal e recuperação](MOARA_PRIMARY_ENTRY_2026-10-30.md). A imagem foundation citada abaixo registra a entrega anterior da base.

Ver [navegacao lateral e etapas de processamento](MOARA_WORK_PROGRESS_2026-10-30.md).

Ver [MCP Normas e fontes oficiais, versao 0.2](MOARA_LEGAL_SOURCES_V2_2026-10-30.md).

Diretório de implantação: `/home/nutec/ai-server`, servidor `172.19.5.250`.
Servidor GPU: `172.19.5.246`. Usar SSH autorizado e guardar credenciais fora do
repositório. Não copiar chaves privadas para relatórios, conversas ou argumentos
de processos.

## Componentes e diagnóstico

```sh
cd /home/nutec/ai-server
sh moara/infrastructure/scripts/compose.sh ps
docker exec ai-server-moara-gateway-1 python -c 'import urllib.request;print(urllib.request.urlopen("http://localhost:8075/api/v1/ready").status)'
```

No portal, a visão geral consulta `/moara/api/v1/observability/inference` com
`status.read`. O endpoint interno de inferência aceita somente a identidade de
serviço Moara. Não há nova porta GPU publicada externamente.

Na GPU:

```sh
systemctl status moara-gpu.service moara-gpu-warm.timer moara-gpu-tls.service
docker exec moara-gpu-ollama ollama ps
docker exec moara-gpu-embeddings ollama ps
nvidia-smi
```

O principal deve aparecer residente/Forever. A leitura física de VRAM vem do
driver; não dimensionar pela soma de `size_vram` do Ollama. Não reiniciar o
Ollama nem descarregar o principal para atualizar apenas o portal ou o relay TLS.

## TLS e certificados

`moara-gpu-tls.service` oferece proxy fixo de loopback 11443→11434 e 11444→11435,
mais estado físico em 11445. Exige certificado de cliente assinado pela CA privada.
Executa com usuário dinâmico e credenciais fornecidas pelo systemd, sem logs de
prompts. O túnel SSH tem chave de host fixada e encaminhamentos restritos.

A CA e a chave de cliente são geradas no servidor de aplicação. A chave do
servidor é gerada na GPU e não sai dela. Arquivos:

- Aplicação: `secrets/gpu-pki/ca.key`, `secrets/moara_gpu_ca.crt`,
  `secrets/moara_gpu_client.crt`, `secrets/moara_gpu_client.key`.
- GPU: `/etc/moara-gpu-tls/server.key`, `server.crt`, `ca.crt`.
- O diretório `secrets` da aplicação é 0700. O arquivo de cliente montado no
  container admite leitura do UID do serviço; a chave da CA não é montada.

Certificados de servidor e cliente foram emitidos por 365 dias em 30/10/2026;
a CA por 1.825 dias. **A renovação não está automatizada.** Programar manutenção
com antecedência, no máximo antes de outubro de 2027, conferindo as datas reais:

```sh
openssl x509 -in secrets/moara_gpu_client.crt -noout -dates
openssl x509 -in secrets/moara_gpu_client.crt -checkend 2592000 -noout
```

Renovar com a CA privada, EKU `clientAuth` para o gateway e `serverAuth` para a
GPU, preservando o SAN `moara-gpu-tunnel-tls`. Guardar cópias protegidas para
reversão. Após instalar os arquivos, reiniciar somente o serviço TLS na GPU e
recriar o gateway de inferência para recarregar o contexto SSL. Testar novamente
cliente válido, falta de certificado, CA desconhecida e nome incorreto.

O provisionador inicial é `infrastructure/gpu/provision_tls.py`; usa o helper SSH
local já disponível na implantação e credenciais transitórias de operador.
Ele não deve ser tratado como rotina automática de renovação.

## Build e validação

Os builds desta entrega usam imagens anteriores preservadas e dependências já
instaladas, evitando atualizações incidentais do runtime e do modelo:

```sh
python3 infrastructure/gpu/build_tls.py
python3 infrastructure/moara2/build_web.py
python3 infrastructure/moara2/build.py
```

O build core executa 43 testes; o de inferência, nove testes de recuperação.
Os testes reais adicionais estão em `infrastructure/moara2/validate_production.py`
e `infrastructure/gpu/validate_tls.py` (este último espera a candidata privada
preparada por `stage_tls.py`). São testes sintéticos, mas usam a GPU real e
consomem fila. Executá-los em janela apropriada. As chaves de teste são revogadas
e os documentos de teste arquivados.

O wrapper Compose inclui, ao final, `legal-compose.yml`, `gpu-tls-compose.yml` e
`moara2-compose.yml`. Não iniciar a stack apenas pelo arquivo base, que conserva
as imagens históricas. A imagem core ativa é
`moara-core:2.0-foundation-20261030`; inferência, `ai-gateway:mtls-20261030`.

## Backup e continuidade

```sh
bash infrastructure/scripts/backup.sh
```

O procedimento existente faz cópia online criptografada e restauração em rede
isolada, verificando tabelas, contagens, arquivos, SQLite e CA. O backup
`moara-before-migration-20261030T163305Z.tar.enc` passou em 30/10/2026 16:34:37 UTC.
O código/configurações finais precisam continuar entrando na rotina de backup.
Os pesos do modelo permanecem na GPU, em `/srv/moara-inference`; não assumir
que o backup da aplicação inclua esse diretório ou a chave TLS privada da GPU.

Candidatas privadas foram paradas e preservadas. Não executar `down -v`, pruning
de volumes/modelos ou restauração de banco em produção como forma rotineira de
reverter uma imagem.

## Reversão das imagens

Há imagens preservadas **já com GPU e conferência jurídica anteriores**:

- Core: `moara-core:pre-moara2-20261030`.
- Inferência: `ai-gateway:pre-mtls-20261030`.
- Wrapper anterior: `backups/moara2-20261030/compose-before`.

Para reverter apenas o core, criar um overlay restrito com a imagem anterior e
recriar somente `moara-gateway`. Migrações 8/9 são aditivas: manter tabelas,
históricos e documentos. Não reverter o banco para o horário do backup se houve
novas escritas. A identidade tem reversão auditada própria, se necessária; não
alterar diretamente as linhas publicadas.

Reverter o transporte exige também reautorizar **somente** os encaminhamentos
11434/11435 da chave de inferência e reativar o relay antigo pelo perfil rollback.
A cópia `/home/nutec/.ssh/authorized_keys.before-mtls-20261030`, na GPU, preserva
a configuração anterior. Não substituir integralmente o arquivo sem comparar
com alterações posteriores de outros operadores. A recuperação CPU continua
disponível sem enfraquecer a verificação TLS.

O escopo homologado do MCP jurídico, as APIs PJe/SEI, carga representativa,
certificação de acessibilidade e a renovação automatizada dos certificados
continuam pendências explícitas, sem simular integrações ou métricas.
