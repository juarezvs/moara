# Fase 0 — diagnóstico de 26/10/2026

## Resultado

Inventário somente leitura executado por SSH como `nutec`, usando autenticação
preexistente e verificação estrita da chave conhecida. Nenhuma alteração de
configuração, instalação, reinicialização, exclusão ou consulta a dados corporativos
foi executada. Os acessos de diagnóstico geram os registros normais de SSH/sudo.

Evidência local: `evidence/server-inventory-2026-10-26.txt`. A saída inclui falhas
e limitações; saída SSH zero significa execução do coletor, não saúde total.

## Ambiente observado

| Item | Observação real |
|---|---|
| Host/IP | `srvdev01-am`, `172.19.5.250/24` |
| SO/kernel | Ubuntu 26.04.1 LTS; `7.0.0-38-generic` |
| CPU | 2 Xeon Silver 4214, 24 núcleos físicos e 48 threads |
| Instruções | AVX-512 e AVX512_VNNI presentes em `lscpu` |
| NUMA | 2 nós; memória aproximadamente 128315/124867 MB |
| RAM | 247 GiB totais; aproximadamente 168 GiB disponíveis na coleta |
| Swap | 8 GiB; aproximadamente 13 MiB em uso; PSI sem pressão recente |
| Armazenamento | disco lógico 1,1 TiB, LVM/ext4; 779 GiB livres na raiz |
| Carga | aproximadamente 0,65/0,60/0,75 na primeira coleta |
| Runtime | Docker 29.9.1, Compose 5.6.0; configuração rootless confirmada |
| Linguagens do host | Python 3.14.4; Node não encontrado no PATH |
| Aplicação existente | `/home/nutec/ai-server`; sem Git na raiz consultada |
| Aplicação própria | `moara/web` Angular 22.2.3; `moara/gateway` Python/FastAPI |
| Identidade | manifesto e configuração em `moara/identity/manifest/` |
| Containers | 25 em execução; os que declaram healthcheck aparecem healthy |
| Serviços systemd do usuário | `ai-server.service` e `ai-backup.service` failed |
| Persistência | volumes PostgreSQL/pgvector, WebUI, Studio, Moara, Redis e métricas |
| Portas | SSH em interfaces gerais; 80/443 no IP institucional; 8080/8443 em loopback |
| Privilégios | Docker acessível como nutec; sudo não interativo indisponível |

Os dados de RAM e carga são amostras, não garantias de capacidade. O tipo físico,
redundância e saúde da controladora/discos não foram confirmados pelo `lsblk`.
Temperaturas indisponíveis: `sensors` não instalado. Firewall não confirmado:
`sudo -n ufw status verbose` exige autenticação. Nenhuma senha foi solicitada ou lida.

## Componentes existentes e inspeção

Foram lidos o README do servidor e documentos de arquitetura, validação, CPU,
limitações e backup. Arquivos de código, manifesto, requisitos e package.json foram
localizados. Não foi feita revisão integral do código, nem cópia da aplicação.

O ambiente contém gateway próprio, gateway de inferência, Angular, WebUI, Studio,
workers de conectores Oracle/PostgreSQL/MySQL/SQL Server/MongoDB/SQLite/REST,
PostgreSQL com pgvector, Redis, Celery, Caddy, Prometheus, Grafana e OpenTelemetry.
Também há geração de imagens em CPU. Existência de container não certifica segurança
ou funcionamento de cada funcionalidade. A documentação histórica não foi usada
como prova de execução de novos testes nesta sessão.

## Falhas reproduzidas e prioridade

1. **Backup agendado falhando.** `ai-backup.service` retorna código 1. O journal
   identifica `PermissionError` na inclusão de
   `/home/nutec/ai-server/secrets/secp_rbac_config.json` em `backups/backup.py:64`.
   O timer está ativo e tentou executar em 26/10. Não ler o arquivo para corrigir
   o problema nem ampliar globalmente suas permissões. Avaliar o mecanismo de
   preservação existente, que documenta leitura de volumes por helper isolado.
2. **Unidade de inicialização falhada.** `ai-server.service` está habilitada e
   falhou com código 1. O journal mostra erro de dependências Ollama/PostgreSQL
   durante `compose up --wait`, com saída 0 do container Ollama. Hoje os containers
   estão em execução. Isso não prova recuperação correta após reboot; a causa
   original da interrupção ainda precisa ser correlacionada com datas e eventos.
3. **Residentes em memória.** O runtime principal usa cerca de 70 GiB e mantém
   quatro modelos com expiração `Forever`. Não há pressão atual, mas a política
   diverge da preferência por ativação sob demanda e exige benchmark antes de mudar.
4. **Documentação divergente da rede atual.** Um documento anterior descreve somente
   loopback; `ss` mostra 80/443 no IP institucional. Revisar proxy, DNS, certificados
   e firewall antes de afirmar exposição segura ou acesso apenas por túnel.
5. **GDS.** O kernel indica Gather Data Sampling vulnerável; avaliar microcode e
   mitigação com a equipe de infraestrutura, sem alterar kernel ou BIOS nesta fase.

## Inferência CPU e modelos iniciais

O catálogo real contém Gemma 4 12B/26B, Qwen3 8B, Qwen3-Coder 30B,
Qwen2.5-Coder 7B/32B, DeepSeek V2 Lite, Llama 3.1/3.3 70B e embeddings.
Tags locais não comprovam procedência, licença ou integridade dos pesos.

Recomenda-se preservar o Ollama atual durante a estabilização. Separar um ensaio
llama.cpp posterior, com o mesmo checkpoint/quantização e contexto, sem trocar
silenciosamente o runtime produtivo. A ferramenta oficial
[llama-bench](https://github.com/ggml-org/llama.cpp/blob/master/tools/llama-bench/README.md)
permite registrar parâmetros e resultados para comparar threads. Não foram
executados benchmarks novos nesta sessão.

| Papel | Candidato inicial | Condição antes de ativar/mudar |
|---|---|---|
| Conversa | Gemma 4 12B já instalado | Conferir origem/licença/digest e qualidade em PT-BR |
| Código | Qwen2.5-Coder 7B Q4_K_M já instalado | Benchmark e ferramentas desabilitadas até validação |
| Embeddings | Preservar embeddinggemma:300m existente | Validar dimensão e índices atuais antes de reindexar |
| Especialista | DeepSeek Lite já instalado | Confirmar licença e suporte; ativação sob demanda |
| Grandes | Qwen 32B/Llama 70B já instalados | Uso opcional após medição de latência e memória |

A seleção é provisória. O repositório oficial
[Qwen2.5-Coder-7B-Instruct-GGUF](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF)
declara Apache 2.0 e oferece GGUF; isso não verifica o artefato local por si só.
Não escolher Gemma apenas pela tag: conferir manifesto e termos oficiais na Fase 2.
Não baixar modelos novos nesta fase.

## Comparação de implantação

| Alternativa | Avaliação |
|---|---|
| Evoluir a instalação existente com staging isolado | Recomendada; preserva dados, modelos e rotas e permite corrigir falhas atuais |
| Nova stack paralela completa | Exige justificar recursos duplicados, portas, migração e sincronização; reservar para incompatibilidade comprovada |
| Reinstalar o SO | Sem justificativa observada; destrutiva e fora do plano |
| Kubernetes | Não há necessidade demonstrada para este host |

## Limites de aceite

Inventário real e plano preparados. Aceite da Fase 0 ainda depende da aprovação do
plano específico. Permanecem sem confirmação: firewall, temperatura, saúde física,
recuperação automática, backup recente restaurável e segurança funcional completa.
Nenhuma fase posterior é declarada entregue pelo simples reaproveitamento do ambiente.
