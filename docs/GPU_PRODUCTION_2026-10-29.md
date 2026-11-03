# Moara com inferência GPU em produção — 29/10/2026

## Entrega

A Moara está configurada para uso em https://moara.am.trf1.gov.br. A seleção automática usa o Gemma 4 12B Q4_K_M, com contexto de 8.192 tokens, no computador 172.19.5.246. Os perfis “Moara principal” e “Respostas rápidas” também usam esse modelo. O embeddinggemma:300m continua com os mesmos pesos e 768 dimensões, agora em um serviço GPU próprio.

Aplicação, autenticação, históricos, documentos, bancos, conectores e jobs continuam em 172.19.5.250. Os especialistas maiores permanecem em CPU. Foram preservadas alternativas explícitas “Qwen3 8B · CPU” e “Gemma 4 26B · CPU”, com as permissões dos perfis de origem. Nenhuma conversa ou documento corporativo foi migrado para armazenamento no computador GPU; a inferência processa os dados necessários em memória.

## Arquitetura instalada

| Componente | Local e função |
|---|---|
| Gateway Moara e adaptador | Servidor atual; autenticação, seleção autorizada, filas, auditoria e recuperação em CPU |
| moara-gpu-tunnel | Container rootless no servidor atual; túnel SSH com reconexão automática |
| moara-gpu-ollama | Computador GPU; somente o modelo principal residente |
| moara-gpu-embeddings | Computador GPU; somente o modelo de embeddings residente |
| moara-gpu.service | Inicialização automática dos serviços e aquecimento dos modelos |
| moara-gpu-warm.timer | Conferência e recuperação de residência a cada 30 segundos após terminar a execução anterior |

Foram separados os runtimes porque o gerenciador do Ollama compartilhado passou a recolocar os embeddings em CPU durante o ensaio integrado. A configuração final usa um modelo por runtime, evitando que a execução de embeddings substitua o principal. Ambos usam keep_alive=-1; a checagem de residência exige execução integral em GPU e reconstrói o residente se necessário.

O Ollama mantém a imagem 0.40.6 por digest já testado. O runtime principal tem limite de 24 GiB de RAM; o de embeddings, 4 GiB. O acesso à NVIDIA é reservado nos dois containers. Os pesos existentes foram reaproveitados; não houve troca silenciosa do modelo de embedding nem reindexação do acervo.

## Comunicação e continuidade

Os serviços GPU escutam somente em 127.0.0.1:11434 e 127.0.0.1:11435 no computador novo. O servidor atual os alcança por dois encaminhamentos em um túnel SSH. Não há API Ollama publicada para a rede local.

A chave de transporte permanece como segredo no servidor atual. No destino, ela permite somente encaminhamento para esses dois endereços de loopback, a partir de 172.19.5.250, com shell forçado a /bin/false e restrições de agente/terminal. A chave do host é fixada no known_hosts do serviço. Nenhuma senha é usada pelo transporte de produção.

O gateway verifica os residentes e usa CPU quando o serviço GPU não está pronto, a conexão falha ou o upstream falha antes da entrega da resposta. Uma falha no serviço de embeddings não desativa o encaminhamento GPU do chat. Depois da recuperação, o gateway volta a usar GPU automaticamente; as sondagens são armazenadas por até dez segundos. Não se repete uma geração depois de entregar parte da resposta ao usuário.

O túnel permanece em execução e tenta reconectar enquanto o computador GPU reinicia. Sua saúde não bloqueia a inicialização da aplicação em CPU. O wrapper Compose do servidor atual inclui o novo overlay; as imagens foram construídas localmente, e o procedimento de inicialização existente continua sem reconstruções automáticas.

## Validações executadas

- Nove testes automatizados de encaminhamento por allowlist, recuperação, circuito e independência dos serviços de chat/embeddings.
- Três testes de reranking: trecho único, preservação da busca híbrida quando o modelo devolve ranking inválido e reordenação válida com renumeração de citações.
- Seleção automática e perfis fast/general: Gemma 4 12B com execution_backend=gpu; streaming completo e duas solicitações simultâneas concluídas.
- Solicitação simples de código: encaminhada ao modelo principal GPU; especialistas complexos continuam nas faixas anteriores de seleção.
- Chamadas nativas de ferramentas, identidade institucional e alternativa explícita Qwen3 em CPU: aprovadas.
- Saída JSON e JSON Schema estrito: testadas na GPU antes de habilitar a capacidade no catálogo; saída JSON pelo perfil general também validada no endpoint público da Moara.
- Upload de documento fictício, indexação, busca restrita à fonte, resposta com citação e exportação em PDF: aprovados. Recursos de teste foram arquivados.
- Imagem sintética vermelha: análise correta pelo cliente autorizado, sem ampliar escopos de acesso.
- Chat institucional em /api/chat/completions: resposta com backend GPU pelo domínio público normal.
- Interface Angular em navegador isolado: transição da sessão institucional para a sessão Moara, envio, resposta renderizada, modelo visível e ausência de erros de JavaScript. A conversa criada pelo teste foi removida, e a sessão nativa do teste bem-sucedido foi revogada.
- HTTPS de produção acessível na estação Windows com validação normal do certificado.
- Permissões public/allowed_subjects/allowed_groups, ativação e seleção manual dos perfis fast/general conferidas contra o snapshot anterior: preservadas.
- O mapeamento principal permaneceu correto após recriar os gateways. O bootstrap foi ajustado para não reinserir o modelo antigo quando um perfil já tem um mapeamento administrativo.
- Reinicialização real do computador GPU com a configuração final de dois serviços: retorno automático dos dois residentes. Durante o reboot, a Moara de produção respondeu pela CPU com HTTP 200 em aproximadamente 1,94 s; posteriormente voltou à GPU.
- Lotes de 16 embeddings e entrada longa foram medidos pela rota da Moara; ambos os modelos continuaram integralmente na GPU. O lote aquecido de 16 textos levou aproximadamente 0,28 s na amostra.

As respostas factuais curtas em produção ficaram aproximadamente entre 0,57 e 1,3 segundo nas amostras registradas. O teste visual final renderizou a resposta em aproximadamente 1,26 s. Esses valores correspondem aos textos sintéticos curtos ensaiados; tamanho de saída, contexto, fila e inicialização influenciam a duração.

A troca teve uma falha transitória de inicialização do gateway causada pela tipagem de um parâmetro SQL. A consulta foi corrigida e os gateways foram recriados e validados. Também foi corrigido o reranking opcional: um resultado de ordenação inválido do modelo conserva os resultados autorizados da busca híbrida, em vez de impedir a resposta ao documento.

## Operação

Para uso normal, entrar na Moara e manter “Seleção automática”. Conversas com um especialista escolhido manualmente continuam respeitando essa escolha. Nenhuma instalação ou configuração adicional é necessária na estação do usuário.

No computador GPU, a configuração fica em /opt/moara-gpu e os pesos em /srv/moara-inference. Diagnóstico:

```sh
systemctl status moara-gpu.service moara-gpu-warm.timer
docker exec moara-gpu-ollama ollama ps
docker exec moara-gpu-embeddings ollama ps
nvidia-smi
```

Os dois modelos devem aparecer como 100% GPU e Forever. Para uma manutenção do computador GPU, a aplicação tem recuperação automática em CPU. Ao restabelecer a infraestrutura, iniciar moara-gpu.service e conferir o timer. Uma primeira carga pode levar mais tempo que uma resposta com modelo já aquecido.

No servidor atual, o estado de encaminhamento aparece nos metadados execution_backend e no contador ai_inference_backend_requests_total. Configuração: moara/infrastructure/gpu-compose.yml; inicialização: moara/infrastructure/scripts/compose.sh. A política de filas e os controles de autorização existentes foram mantidos.

## Preservação e evidências

As imagens anteriores estão preservadas como ai-gateway:pre-gpu-20261029 e moara-core:pre-gpu-20261029. Backups de configuração e do mapeamento/permissões dos perfis ficam no diretório backups do servidor atual, sem exportação de segredos para o workspace. O retorno automático à CPU não depende de restaurar banco ou reinstalar a plataforma.

Evidências locais em docs/evidence/gpu-production-*, incluindo aceite por API, interface, chat institucional, embeddings, residência, reinício, recuperação, permissões e saúde final. A imagem gpu-production-chat-2026-10-29.png contém somente a conversa sintética usada na validação. Os horários dos logs do servidor estão em UTC; a data desta entrega usa Manaus.
