# Orientação sobre a própria Moara

A base de orientação `1.0.0` amplia as perguntas reconhecidas sobre identidade, finalidade, funções, uso da interface, fontes, privacidade, aprendizado, integrações, API, modelo, arquitetura, acessos e limitações.

O controlador identifica perguntas naturais e combinadas e mantém contexto em continuações curtas. Perguntas sobre a plataforma têm prioridade sobre um assunto jurídico anterior. Pedidos efetivos de análise, pesquisa jurídica, geração de código ou execução continuam nos fluxos existentes.

As respostas são construídas pela aplicação, sem inferência do modelo, a partir do manifesto institucional ativo, das funções implementadas e dos registros pertinentes. O nome do modelo vem do roteamento da solicitação. A lista de assistentes considera habilitação e autorização. O estado de residência é consultado somente para usuários autorizados a ler observabilidade. Nenhuma pergunta de ajuda cria chaves ou concede permissões.

O SEI e o PJe permanecem descritos como preparados e pendentes de homologação. A explicação sobre fontes distingue conectores institucionais de pesquisa jurídica pública. A explicação de privacidade não promete ausência absoluta de tráfego externo. Recuperação de documentos e evidências não é apresentada como treinamento dos pesos a cada conversa. Dados não confirmados não são preenchidos por suposição.

O manifesto, seu hash, o RBAC, a interface, as funções jurídicas e a configuração da inferência permanecem preservados. Metadados `self_knowledge` informam versão, assuntos e bases da resposta. A ampliação não representa conhecimento automático de toda alteração futura da plataforma: novos recursos devem manter essa base e seus testes coerentes.

Validação: 236 testes automatizados; dez situações de conversa na aplicação autenticada, incluindo continuação e troca de assunto; regressão real de cessão/requisição com MCP e GPU. Os relatórios `docs/runtime/self-knowledge-*.json` registram a imagem testada e a conferência final. Os 83 arquivos da interface e os outros 84 módulos Python são idênticos à imagem anterior.

A implantação usa `moara/infrastructure/self-knowledge-compose.yml` e reinicia somente o gateway. O MCP e a inferência permanecem em execução. A imagem anterior está preservada como `moara-core:pre-self-knowledge-app-20261102`; o wrapper anterior fica em `backups/self-knowledge-20261102/compose-before`. Candidatos privados são interrompidos após a conferência final e preservados para revisão.
