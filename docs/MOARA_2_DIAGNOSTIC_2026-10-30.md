# Moara 2.0 — diagnóstico inicial em 30/10/2026

## Inventário confirmado antes de novas alterações

| Recurso | Aplicação: 172.19.5.250 | Inferência: 172.19.5.246 |
|---|---|---|
| Host | srvdev01-am | srvai-am |
| Sistema | Ubuntu Server 26.04.1 | Ubuntu Server 26.04.1 |
| CPU | 2 Xeon Silver 4214; 24 núcleos / 48 threads | Core i7-14700; 20 núcleos híbridos / 28 threads |
| RAM | 247,3 GiB; 146,2 GiB disponíveis na amostra | 30,5 GiB; 19,9 GiB disponíveis |
| Disco raiz | 1,07 TiB; cerca de 762 GiB disponíveis | 465,9 GiB; cerca de 407 GiB disponíveis |
| GPU | Sem inferência GPU local | NVIDIA RTX A2000 12 GB, driver 595.91.07 |
| VRAM física | — | 9.955 MiB usados, 1.944 MiB livres reportados |

Os valores são amostras de operação, não garantias de disponibilidade futura.
Não utilizar a soma de `size_vram` das respostas do Ollama para dimensionar esta
placa: os valores observados nessa API são inferiores ao consumo físico reportado
pelo driver.

Modelo principal: Gemma 4 11,9B, Q4_K_M, alias `moara-main-gpu`, contexto 8.192.
Embedding: `embeddinggemma:300m`, 768 dimensões, contexto 2.048. Ambos aparecem
**100% GPU / Forever**, em runtimes separados do Ollama 0.40.6. Serviço de
inicialização e timer de residência ativos e habilitados. As portas 11434/11435
escutam somente em loopback.

Decisão: compartilhar o modelo principal entre os seis assistentes. A folga atual
de VRAM não sustenta a hipótese de seis modelos grandes residentes. Preservar
contexto, pesos e runtime; usar fila e concorrência limitada. Não anunciar seis
gerações simultâneas sem medição e orçamento de memória.

## Arquitetura e componentes reutilizáveis

Há 27 containers de produção em execução; os serviços com healthcheck estavam
saudáveis. Aplicação Angular/FastAPI, identidade versionada, sessões institucionais,
RBAC, PostgreSQL/pgvector, Redis, auditoria, histórico, armazenamento documental,
jobs, OCR, pesquisa híbrida, embeddings, reranking, exportação e conectores já
existem. Open WebUI permanece como chat institucional compatível.

Aplicação e dados persistentes estão em 172.19.5.250. O transporte de inferência é
hoje HTTP em loopback/redes Docker dentro de **túnel SSH autenticado e criptografado**,
com chave restrita e chave do host fixada. Isso não equivale a afirmar que a API
de inferência já oferece TLS/mTLS: essa é uma lacuna frente ao desenho proposto.

A consulta jurídica inicial já está publicada e testada, conforme
[relatório específico](LEGAL_VERIFICATION_2026-10-30.md). Não certifica integralmente
vigência/eficácia nem jurisprudência; explicita lacunas e suspende conclusões.

O manifesto ativo no início deste diagnóstico é a versão 1.0.0, orientada ao
propósito anterior. O catálogo de agentes técnicos preexistentes e recursos de assistentes
personalizados não corresponde ainda aos seis assistentes oficiais do novo prompt.

O roteamento automático ainda pode selecionar especialistas grandes em CPU.
Preservá-los para seleção explícita autorizada, priorizando o modelo GPU para os
assistentes oficiais. A recuperação atual em CPU já foi testada anteriormente;
eventuais alterações devem conservar a continuidade sem inferência pesada surpresa.

## Preservação

O backup de 30/10/2026 às 07:02:52 UTC tem relatório de restauração verificada às
07:04:18 UTC: PostgreSQL, contagens, hashes de arquivos/configuração, SQLite e CA
conferidos em ambiente isolado, sem modificar a produção. Antes de novas migrações
e da publicação da identidade 2.0, executar novamente o procedimento existente
de backup online e restauração isolada para incluir a etapa jurídica recém-publicada.

Não remover dados, modelos, volumes ou serviços funcionais. A cópia Windows é
parcial; o código e a implantação completos do servidor continuam como referência
para comparação. Guardar imagens e versões anteriores para reversão.

## Lacunas e sequência de implementação

| Frente | Próxima entrega | Critério de validação |
|---|---|---|
| Identidade | Manifesto fornecido, assinatura e identidade 2.0 versionados | FAQ/identidade estáveis ao trocar modelo; versão anterior preservada |
| Seis assistentes | Catálogo oficial, seleção manual/automática, prompts e ferramentas permitidas | Autorização no backend; todos compartilham o principal sem ampliar acesso |
| Escopo | Classificação contextual e decisões de política na aplicação | Recusar entretenimento; permitir loterias como tema jurídico, alimentação como contratação e treinamento institucional |
| Orquestração | Contexto, ferramentas, prazo, auditoria e modelo principal | Sem roteamento automático pesado; fontes não alteram permissões |
| Normas/jurisprudência | Ampliar pesquisa e distinção de efeitos temporais | Fonte oficial e evidências; ausência de confirmação permanece explícita |
| PJe/SEI | Contratos e adaptadores de leitura conforme integração oficial disponível | Não ativar sem endpoint, autenticação, autorização e teste real; sem escrita/assinatura/tramitação |
| Documentos/dados | Reutilizar RAG/conectores; completar rastreabilidade e formatos | ACL antes da recuperação; SQL efetivamente somente leitura; dados e senhas não saem para fontes públicas |
| Administração/UI | Cartões oficiais, ferramentas/modelos, auditoria e acessibilidade | Teclado, permissões, status verdadeiro e regressão no navegador |
| Transporte/operação | Avaliar TLS/mTLS privado preservando transporte atual | Certificados e identidade entre serviços, streaming e reversão testados |

Não se considera a Moara 2.0 concluída com este diagnóstico. Integrações sem API
oficial/credenciais e funcionalidades ainda não homologadas devem aparecer como
pendentes, sem respostas fictícias apresentadas como integração real.
