# Validação da Moara com GPU — 29/10/2026

Atualização: a integração foi colocada em produção posteriormente. O estado instalado e o aceite final estão em [GPU_PRODUCTION_2026-10-29.md](GPU_PRODUCTION_2026-10-29.md). Este documento preserva os resultados do ensaio anterior à ativação.

## Resultado

Recomendação confirmada por execução real: manter aplicação e dados em 172.19.5.250 e usar a RTX A2000 12 GB de 172.19.5.246 para inferência dos modelos menores. Nos testes com a mesma quantidade de tokens produzidos, as respostas aquecidas ficaram aproximadamente 4,2 a 5,4 vezes mais rápidas. Isso não significa aceleração equivalente de todos os módulos ou de todas as solicitações da plataforma.

A integração foi medida em uma instância temporária da Moara com as rotas reais de chat, autenticação, catálogo, identidade e auditoria. O site de produção continuou com seu encaminhamento CPU. Ao terminar, os três containers temporários na origem foram removidos e o container GPU foi parado, sem reinício automático nem porta de inferência em escuta. O ambiente e os pesos selecionados ficaram preparados no novo computador para uma eventual ativação posterior.

## Método e comparabilidade

- 36 solicitações comparativas: três perfis, dois casos por perfil e três repetições por caso, em CPU e GPU.
- CPU: HTTPS em https://localhost:8443/moara/api/v1/chat/completions, no servidor de produção.
- GPU: HTTP em 127.0.0.1:18075/api/v1/chat/completions, na Moara temporária do mesmo servidor, encaminhando pelo adaptador real para 172.19.5.246:11435.
- Mesmas imagens de aplicação já instaladas; mesmo Ollama 0.40.6 por digest SHA-256; mesmos pesos, templates, identidade institucional, perfis e contexto configurado em 8.192 tokens.
- 33 blobs copiados, aproximadamente 18,55 GB, com SHA-256 verificado e dependências dos manifestos conferidas. Nenhum documento, banco, segredo da Moara ou conversa de usuário foi transferido para o computador GPU.
- Ajuste de execução no destino: aliases selecionados receberam num_gpu=-1, preservando os pesos. O adaptador de embeddings temporário também recebeu esse ajuste. O código e os parâmetros de produção permaneceram inalterados.
- Textos inteiramente fictícios; casos de resumo curto, código e resumo de aproximadamente 1.300–1.500 tokens de entrada, já incluindo a identidade. Saída limitada a 128 tokens, temperatura zero e seed 42.
- A instância temporária usou as dependências existentes de autenticação, identidade e catálogo. O seu startup foi restrito para não executar bootstrap, migrações ou despachantes de jobs. As chamadas produziram os registros normais de autenticação, solicitações e auditoria.

Os números de uso contínuo abaixo são as medianas das repetições 1 e 2 de cada caso. A repetição 0 é apresentada separadamente quando contém carga inicial. As repetições aquecidas também reutilizam o cache de prefixo; isso foi observado nos dois backends. Trata-se de uma amostra exploratória, sem percentis de capacidade institucional.

## Tempo percebido pela rota de chat

| Perfil/caso | CPU | GPU | Razão CPU/GPU | Tokens de saída CPU/GPU |
|---|---:|---:|---:|---:|
| Qwen3 8B, resumo curto | 15,27 s | 3,25 s | 4,70× | 128 / 128 |
| Qwen3 8B, texto longo | 17,78 s | 3,28 s | 5,41× | 128 / 128 |
| Qwen2.5-Coder 7B, código | 13,19 s | 3,04 s | 4,34× | 128 / 128 |
| Qwen2.5-Coder 7B, texto longo | 13,27 s | 3,08 s | 4,31× | 128 / 128 |
| Gemma 4 12B, resumo curto | 6,75 s | 1,61 s | 4,19× | 46 / 46 |
| Gemma 4 12B, texto longo | 17,56 s | 3,10 s | 5,67×* | 128 / 108 |

*No último caso, a GPU gerou uma resposta menor e encerrou naturalmente; a CPU atingiu o limite de tokens. A razão de latência não representa uma comparação com a mesma quantidade de saída. A divergência também mostra que temperatura zero e mesma seed não garantem respostas idênticas entre CPU e GPU. Vários casos atingiram o teto de 128 tokens; os tempos medem essa saída limitada e não a conclusão de tarefas extensas.

| Perfil/caso curto | Primeiro conteúdo visível CPU | Primeiro conteúdo visível GPU |
|---|---:|---:|
| Qwen3 8B | 3,89 s | 0,88 s |
| Qwen2.5-Coder 7B | 3,97 s | 0,97 s |
| Gemma 4 12B | 5,01 s | 1,24 s |

O primeiro conteúdo visível inclui o processamento e a proteção de identidade da Moara. Não equivale ao primeiro token interno do Ollama. Pelo mesmo motivo, a métrica experimental approx_stream_tokens_per_second dos JSONs brutos não deve ser interpretada como velocidade de geração: a proteção pode reter um prefixo e liberá-lo em bloco. As conclusões usam duração completa, quantidade de tokens e tempo até conteúdo visível.

## Carga inicial, residência e concorrência

As primeiras solicitações na GPU, incluindo a primeira inicialização dos runners/kernels para cada modelo, levaram 49,02 s no Qwen3 8B, 24,08 s no Coder 7B e 34,29 s no Gemma 12B. Esses valores não são comparáveis a modelos de CPU já residentes. Uma nova carga do Qwen3 8B, depois da inicialização e após alternar de modelo, levou 6,62 s com a mesma solicitação curta. Portanto, manter o modelo de uso principal aquecido importa para a experiência.

Os logs confirmaram offload integral dos modelos: 37/37 camadas no Qwen3, 29/29 no Coder e 49/49 no Gemma; o draft do Gemma também foi para a GPU. O contexto efetivo foi 8.192. As consultas de residência confirmaram tamanho de execução integralmente em VRAM para Qwen3 e Gemma. A GPU atingiu aproximadamente 9.143 MiB de uso, 63 °C e 69,57 W na amostra. Não ocorreram erros de falta de memória nos testes. Isso não certifica estabilidade térmica prolongada.

Dois chats simultâneos foram concluídos corretamente em cada ensaio: Qwen3 em 3,31 s e 6,52 s; Gemma em 3,10 s e 6,05 s. A segunda solicitação aguardou a fila serial existente. O teste confirma funcionamento básico de concorrência, não múltiplas gerações paralelas nem capacidade para muitos usuários.

## Embeddings e validações funcionais

O mesmo embeddinggemma:300m produziu lotes de 16 vetores com 768 dimensões válidas nos dois backends. Mediana aquecida: CPU 0,866 s; GPU 0,237 s, aproximadamente 3,65× de diferença. Primeira chamada: CPU 3,18 s; GPU 3,44 s.

A menor similaridade de cosseno entre vetores correspondentes foi 0,999974; a maior diferença absoluta por componente foi 0,000969. Isso apoia compatibilidade numérica neste conjunto sintético, preservando pesos e dimensão; não demonstra identidade bit a bit ou equivalência de ranking para todo o acervo. Não houve troca de modelo de embedding nem reindexação. Uma futura ativação deve incluir consultas de recuperação representativas antes de direcionar todos os embeddings para a GPU.

Outros resultados:

- Inicialização CUDA e nvidia-smi dentro do container: aprovadas.
- Chat sem autenticação: rejeitado; perfil não autorizado: rejeitado; mensagem inválida: rejeitada.
- Identidade institucional: preservada pela rota canônica, sem inferência desnecessária.
- Pergunta factual sintética: resposta correta, “5 dias úteis.”
- Streaming e término das respostas: aprovados em todos os 36 pedidos comparativos e nos ensaios de concorrência.
- Reinicialização do container GPU: concluída; nova requisição retornou HTTP 200 e embedding de 768 dimensões, integralmente na GPU.
- Restrição de rede temporária: origem 172.19.5.250 acessou a inferência; acesso da estação de trabalho à porta foi bloqueado. A regra foi retirada após parar o container. Uma instalação permanente precisa de proteção de rede persistente e definição de autenticação/canal entre hosts.

## Estado deixado e próximo passo técnico

No destino foram instalados Docker 29.1.3, Compose 2.40.3, NVIDIA Container Toolkit 1.20.1 e nvidia-utils correspondente ao driver 595.91.07 já existente. O container moara-gpu-validation permanece parado, com política de restart=no; pesos selecionados ficam em /home/nutec/moara-gpu-validation. Não foi feito reboot do computador.

Na origem, os containers moara-validation-http, moara-validation-adapter e moara-validation-embeddings foram removidos. A verificação final do site em CPU retornou HTTP 200 e “OK” com inference_used=true. Os endpoints de saúde e prontidão responderam corretamente. Os 25 containers originais estavam em execução e todos os que declaram healthcheck estavam saudáveis.

Ao finalizar, o embedding carregado pelo ensaio foi descarregado e o conjunto original de quatro modelos residentes em CPU foi recomposto: ai-fast-8k, ai-coder-8k, ai-general-gemma4-26b-8k e moara-63af8a56-8192-12t, todos novamente com residência Forever.

A arquitetura distribuída está validada para o escopo ensaiado. Para colocá-la em produção, ainda é necessário implementar encaminhamento por modelo, manter CPU para especialistas grandes, ajustar as restrições num_gpu/CUDA_VISIBLE_DEVICES somente onde adequado, definir residência para evitar trocas frequentes e configurar rede, autenticação, inicialização e retorno ao backend CPU. O ensaio não mudou a seleção automática nem a inferência pública dos usuários.

## Evidências

Em docs/evidence, arquivos com data 2026-10-29:

- gpu-validation-cpu-2026-10-29.json e gpu-validation-gpu-2026-10-29.json: 36 amostras, respostas sintéticas, tokens e metadados Moara.
- gpu-validation-extra-2026-10-29.json: controles de acesso, identidade, residência, recarga e concorrência.
- gpu-validation-embeddings-2026-10-29.json e gpu-validation-restart-2026-10-29.json.
- gpu-validation-telemetry-2026-10-29.csv e gpu-validation-runtime-2026-10-29.txt.
- gpu-validation-network-2026-10-29.json e gpu-validation-final-health-2026-10-29.txt.

Os scripts do ensaio ficam localmente em tmp e, na origem, em /home/nutec/ai-server/tmp/gpu-validation. As evidências não contêm tokens de sessão, senhas ou conteúdo corporativo. Datas no relatório usam 29/10 em Manaus; os logs do servidor registram 30/10 em UTC.
