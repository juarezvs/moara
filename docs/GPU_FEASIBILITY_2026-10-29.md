# Viabilidade da Moara no computador com GPU — 29/10/2026

Atualização: os testes autorizados posteriormente foram concluídos. Consulte os resultados medidos em [GPU_VALIDATION_2026-10-29.md](GPU_VALIDATION_2026-10-29.md). O texto abaixo preserva o diagnóstico anterior aos testes.

## Parecer

A NVIDIA RTX A2000 12 GB é compatível com aceleração do Ollama e a inicialização CUDA funcionou no host. Há viabilidade técnica para usar o computador como servidor de inferência de modelos menores. Recomenda-se manter aplicação, dados e modelos grandes em 172.19.5.250 e, em uma etapa posterior autorizada, testar inferência GPU em 172.19.5.246.

A transferência integral não é recomendada preservando a configuração atual: o destino tem aproximadamente 32 GB de RAM física, enquanto o Ollama de origem sozinho usa 68,44 GiB na amostra. Uma implantação reduzida é plausível, mas exige mudar a residência dos modelos e medir capacidade. Não houve migração, instalação, alteração de configuração ou benchmark de inferência nesta análise.

## Inventário observado por SSH

| Recurso | Destino 172.19.5.246 | Origem 172.19.5.250 |
|---|---|---|
| Nome | srvai-am | srvdev01-am |
| SO | Ubuntu 26.04.1 LTS, kernel 7.0.0-42 | Ubuntu 26.04.1 LTS; inventário histórico de CPU complementa as consultas atuais |
| CPU | Core i7-14700, 20 núcleos híbridos, 28 threads | 2 Xeon Silver 4214, 24 núcleos/48 threads no inventário de 26/10 |
| RAM | 30 GiB visíveis, aproximadamente 29 GiB disponíveis | 247 GiB, aproximadamente 168 GiB disponíveis |
| GPU | RTX A2000 12GB e Intel UHD 770 | Inferência atual observada como 100% CPU |
| Disco | NVMe Samsung 512 GB comerciais; raiz 466 GiB, 434 GiB livres | Raiz 1,1 TiB; 276 GiB usados, 764 GiB livres |
| Runtime | Docker, Ollama e nvidia-ctk não encontrados no PATH | 25 containers ativos |
| Rede | Ethernet negociada em 1.000 Mb/s | Mesmo segmento de rede |

O ping do destino à origem apresentou média de 0,410 ms em três pacotes, sem perdas. Isso indica baixa latência pontual; não mede banda sustentada, concorrência ou confiabilidade. O DNS de moara.am.trf1.gov.br continua apontando para 172.19.5.250.

O diretório de aplicação da origem ocupa aproximadamente 37 GiB; a árvore Docker, 226 GiB; o volume Ollama, 167 GiB. O volume Ollama já está incluído na árvore Docker: esses valores não devem ser somados. Há espaço nominal para uma cópia, mas isso não substitui dimensionamento dos volumes, crescimento, staging e backups. Copiar diretamente a árvore Docker não é um procedimento de migração consistente.

## Verificação da GPU

- PCI: NVIDIA GA106, RTX A2000 12GB, dispositivo 10de:2571.
- Driver carregado: NVIDIA 595.91.07, módulos nvidia e nvidia_uvm presentes; Secure Boot habilitado.
- Teste pela biblioteca libcuda.so.1: cuInit retornou 0; placa identificada corretamente; compute capability 8.6.
- Memória reportada pela API CUDA: aproximadamente 11,62 GiB utilizáveis.
- NVML inicializou e reportou aproximadamente 11,61 GiB livres e temperatura de 35 °C na amostra.
- nvidia-smi não foi encontrado. Isso não significa ausência de driver: CUDA e NVML foram consultadas diretamente por Python/ctypes, sem instalar ferramentas ou carregar modelos.

O suporte da família RTX A2000 consta na [documentação oficial do Ollama](https://docs.ollama.com/gpu). O Ubuntu 26.04 x86_64 consta na [matriz do NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/supported-platforms.html). A compatibilidade do hardware e a inicialização CUDA não certificam ainda o funcionamento da imagem Ollama usada na Moara dentro de containers.

## Adequação dos modelos atuais

Os tamanhos abaixo foram observados em ollama list na origem; são tamanhos dos artefatos, não a memória total de execução. Cache de contexto, buffers, paralelismo e outros modelos também consomem memória.

| Modelo atual | Artefato aproximado | Parecer para a A2000 |
|---|---:|---|
| Qwen2.5-Coder 7B Q4 | 4,7 GB | Bom candidato inicial; provável execução integral na GPU, sujeita a contexto e medição |
| Qwen3 8B Q4 | 5,2 GB | Bom candidato inicial, com a mesma ressalva |
| Gemma 12B Q4 (tags locais) | 8,0–8,2 GB | Candidato com menor folga; validar contexto e memória real |
| embeddinggemma 300M | 621 MB | Candidato a aceleração; preservar modelo, digest e dimensão dos índices |
| DeepSeek V2 Lite | 10 GB | Margem pequena; não garantir residência integral com contexto de 8K |
| Gemma 26B / Qwen3-Coder 30B / Qwen2.5-Coder 32B | 17–19 GB | Pesos excedem a VRAM; somente aceleração parcial, se suportada e útil no ensaio |
| Llama 3.1 e 3.3 70B Q4 | 42 GB cada | Pesos excedem a VRAM e a RAM do destino; manter na origem |

Não se deve assumir que parâmetros ativos de modelos MoE representam o tamanho dos pesos que precisam estar acessíveis. Também não é adequado carregar vários modelos simultaneamente na A2000 sem orçamento de memória.

## Alterações necessárias em uma etapa futura

1. Preparar Docker/Compose e acesso à GPU via NVIDIA Container Toolkit, conforme a [documentação NVIDIA](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html), preservando o modelo de isolamento escolhido para a aplicação.
2. Conferir compatibilidade da imagem Ollama e validar uma inferência sintética no container com GPU.
3. Adaptar as restrições atuais: o Compose local contém CUDA_VISIBLE_DEVICES=-1 e HIP_VISIBLE_DEVICES=-1; os aliases produtivos consultados ai-fast-8k, ai-coder-8k e ai-general-gemma4-26b-8k declaram num_gpu=0. O gateway produtivo também força num_gpu=0 em embeddings, visão e rotinas de validação. Apenas copiar os modelos manteria esses impedimentos.
4. No desenho distribuído, configurar upstreams por modelo e autenticação/restrição de rede para a comunicação entre os hosts. Os nomes Docker atuais não são resolvidos automaticamente no outro computador. Definir também o fluxo de gestão e instalação de modelos, hoje baseado no volume local compartilhado.
5. Usar inicialmente um modelo conversacional ou de código por vez na GPU. Manter especialistas grandes na origem e prever retorno ao backend atual.
6. Para transferência integral, redimensionar limites de RAM/CPU do Compose, reduzir residentes, migrar bancos por procedimento consistente, preservar volumes e segredos, validar conectores/LDAPS, proxy/TLS/DNS, backups e reversão. A cópia local em C:\moara é parcial e não basta para reconstruir toda a produção.

## Expectativa de velocidade e validação

É tecnicamente provável que modelos 7B/8B quantizados, totalmente residentes na GPU, respondam mais rápido que a execução CPU atual. A magnitude do ganho não foi medida e não há base para prometer um multiplicador ou número de tokens/s. O i7 ser mais recente tampouco prova que substitui o servidor Xeon para todas as cargas.

A GPU pode reduzir o processamento do prompt, a geração de tokens e o cálculo de embeddings. Não acelera automaticamente consultas a bancos, conectores, OCR, filas, rede ou toda a interface. Em modelos parcialmente descarregados, a CPU e a movimentação de dados podem limitar o resultado.

Ensaio proposto para uma próxima etapa: mesmo digest e quantização, prompts sintéticos curtos e longos, contextos de 4K e 8K, limite igual de resposta, medições frias e aquecidas, repetição e concorrência controlada. Registrar tempo até primeiro token, tokens/s, latência total, percentis, uso de RAM/VRAM e residência efetiva em GPU. Medir isoladamente o backend e depois a rota completa da Moara. Não executar esse ensaio sem a etapa futura de preparação e transferência autorizada.

## Evidências e limites

Consultas somente de diagnóstico nos dois servidores; evidências locais em docs/evidence/gpu-feasibility-172.19.5.246-2026-10-29.txt e gpu-feasibility-source-2026-10-29.txt. As demais amostras atuais de containers, memória, modelos e disco foram consultadas durante a sessão e resumidas acima. Não foram lidos documentos corporativos, conteúdo de bancos ou arquivos de segredos. Nenhuma senha foi incluída neste relatório ou nos arquivos de evidência.

A identificação SSH do destino foi observada na primeira conexão, sem validação externa independente da chave: ssh-ed25519, fingerprint MD5 e2:16:e1:96:63:47:69:09:49:06:5e:60:b5:7b:1a:14. A origem foi acessada com chave conhecida e StrictHostKeyChecking=yes.

Não foram avaliados desempenho sob carga, estabilidade prolongada, recuperação após reboot, saúde física do SSD, política de backup do destino ou capacidade multiusuário. A conclusão é de viabilidade técnica condicionada aos testes, e não de aceite para substituição imediata da produção.
