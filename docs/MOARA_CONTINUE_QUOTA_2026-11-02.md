# Cota da integração Continue

A chave já configurada no Continue foi identificada por seu hash, sem copiar o token para o servidor ou para os relatórios. Sua cota anterior era 20 requisições por minuto. A configuração administrativa `rpm=0` agora desativa a cota por minuto dessa chave; não é uma cota finita ampliada.

Autenticação, validade, revogação, permissões e perfis autorizados continuam sendo verificados. A emissão pessoal de novas chaves conserva os limites existentes; somente a administração pode selecionar zero. Outras chaves e limites de login não foram alterados.

Imagem publicada: `moara-core:continue-unlimited-20261102`, construída sobre a imagem exata que já estava em execução. Apenas o gateway da aplicação foi recriado; os containers de inferência e demais serviços conservaram seus IDs.

Validação: 22 testes de autenticação, permissões e integração aprovados; 65 chamadas autenticadas a `/moara/v1/models` em 5,1 segundos, todas HTTP 200. Esse ensaio valida a ausência da antiga cota da chave sem ocupar a inferência com 65 gerações. Uma geração real em streaming com chamada nativa de ferramenta também foi verificada.

A remoção da cota não aumenta a memória ou o contexto do modelo, nem garante que o agente conclua qualquer projeto sem falhas. A fila de inferência conserva seus controles de capacidade. O Continue usa um plano persistente em `.moara/plano.md` e orçamento de contexto reduzido para reservar espaço às instruções do servidor. Erros de contexto e encerramento prematuro do modelo são problemas distintos do 429 corrigido aqui.

Migração: `0010_api_key_unlimited_rpm`. O suporte a zero é registrado no schema e a alteração da chave foi auditada. Os arquivos de reversão e a cota anterior ficam no servidor em `tmp/continue-unlimited-20261102`; a imagem anterior é preservada como `moara-core:pre-continue-unlimited-20261102`. Para reverter o comportamento, restaure primeiro a cota positiva da chave e depois a imagem anterior.
