# Fase 2 — comparação CPU em 26/10/2026

Foram executadas nove configurações e 18 amostras sintéticas, em containers sem
rede, sem portas, com limite de 24 CPUs e 16 GiB. Mesmo arquivo GGUF Qwen2.5-Coder
7B, verificação de SHA-256 e cabeçalho GGUF. Nenhum modelo produtivo foi substituído.

| Runtime | Threads | Contexto | NUMA | Tokens/s, segunda amostra |
|---|---:|---:|---|---:|
| Ollama | 12 | 4096 | padrão | 10,72 |
| Ollama | 24 | 4096 | padrão | 11,81 |
| Ollama | 48 | 4096 | padrão | 4,04 |
| Ollama | 12 | 8192 | padrão | 10,27 |
| llama.cpp | 12 | 4096 | padrão | 10,35 |
| llama.cpp | 12 | 4096 | distribute | 13,42 |
| llama.cpp | 24 | 4096 | distribute | 16,01 |
| llama.cpp | 48 | 4096 | distribute | 5,74 |
| llama.cpp | 12 | 8192 | distribute | 13,34 |

48 threads pioraram a geração neste ensaio. llama.cpp com 24 threads e NUMA
distribute teve o melhor resultado da segunda amostra. Isso não basta para
substituir o runtime produtivo: são prompts curtos, duas repetições, quota de CPU
e sem teste representativo de concorrência ou qualidade jurídica.

Todas as respostas falharam no critério estrito de JSON puro; a resposta observada
incluiu cercas Markdown. Esse resultado não foi convertido em aprovação por
remover silenciosamente as cercas do benchmark. A implementação de propostas
aceita cercas explicitamente e valida o JSON resultante antes de usar os dados.

Decisão: preservar Ollama e as configurações existentes. Manter llama.cpp como
candidato com evidência, sem promover automaticamente uma configuração apenas
pela taxa de geração. Separar testes sintéticos de inferência dos testes de
qualidade que exigem corpus institucional aprovado.

Referências primárias:
- [Qwen2.5-Coder GGUF oficial e licença Apache 2.0](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF)
- [llama.cpp server](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
- [EmbeddingGemma e seus termos](https://huggingface.co/google/embeddinggemma-300m)

Relatório bruto local: docs/evidence/phase2-cpu-matrix.json.
Script reproduzível: inference/llamacpp/cpu_matrix.py.
