# Login por matrícula e órgão

O formulário apresenta Matrícula, Senha e Órgão, nesta ordem. A lista vem do catálogo público existente `/api/v1/moara/directories/public`, que expõe apenas identificadores e rótulos de diretórios habilitados. O SJAM é selecionado inicialmente quando disponível. Não há lista de servidores AD ou segredos no navegador.

O envio transforma a matrícula e o órgão no identificador `realm\matricula`, já suportado pela autenticação institucional existente. O backend continua responsável pela validação no diretório, vínculo institucional, autorização e eventual autenticação adicional. Não foi alterada a configuração dos Active Directory nem criada uma autenticação paralela. A opção identificada como conta local mantém acesso às contas locais existentes.

O catálogo tem prazo de carregamento, estado de erro e tentativa novamente. Falha de catálogo não é apresentada como senha inválida. A mensagem de credenciais inválidas passa a mencionar matrícula, senha e órgão.

Validação: compilação Angular, inspeção visual do login em celular e verificações de navegador isoladas e públicas. Foram conferidos ordem dos campos, catálogo real, seleção inicial, ausência de transbordamento horizontal, conteúdo do envio com credenciais sintéticas, desafio adicional e regressão dos fluxos de contexto e histórico. Não foi efetuado login real de rede de um servidor, pois suas credenciais não foram fornecidas. A conferência do envio usa interceptação somente no navegador de teste, sem conceder sessão.

Imagem: `moara-core:network-login-20261031`; base exata preservada: `moara-core:pre-network-login-20261031`. Overlay: `moara/infrastructure/network-login-compose.yml`. Apenas o gateway da aplicação é recriado. Nenhuma alteração de banco, proxy, MCP ou inferência. Reversão: restaurar o wrapper de `backups/network-login-20261031/compose-before` e recriar somente `moara-gateway`.

Evidências: `docs/runtime/network-login-stage.json`, `network-login-public.json`, `network-login-mobile.png` e `network-login-desktop.png`.
