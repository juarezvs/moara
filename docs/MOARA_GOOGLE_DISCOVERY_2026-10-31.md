# Descoberta web com conferência oficial — 31/10/2026

## Resultado efetivo

Foi implementado um navegador isolado e autenticado, ligado ao MCP como ferramenta `discover_google_references` e como tentativa de descoberta anterior à alternativa web existente, quando a pesquisa oficial inicial não fornece texto suficiente.

**A pesquisa automática pelo Google Modo IA não está operacional nas condições observadas.** No teste real, Chromium iniciou com o sandbox ativo, a entrada `/aimode` redirecionou para `/search?udm=50`, e a navegação foi interrompida porque as instruções públicas do Google desautorizam a rota `/search`. O estado retornado é `provider_access_restricted`, sem candidatos e sem resposta jurídica gerada pelo Google. Não houve resolução de CAPTCHA, login, alteração disfarçada de identidade nem contorno da restrição.

Fontes das condições de acesso: [robots.txt](https://www.google.com/robots.txt) e [termos do Google](https://policies.google.com/terms?hl=pt-BR). O bloqueio é uma condição concreta do provedor, não uma afirmação de que a aplicação concluiu uma pesquisa Google. O estado do serviço e a disponibilidade do provedor são campos separados.

Para tornar a pesquisa Google efetivamente disponível, será necessário um mecanismo de acesso autorizado pelo provedor que permita esse uso. Uma chave ou assinatura Gemini, por si só, não comprova permissão para coletar links e reutilizá-los nesse fluxo. Não foi instalado nem anunciado outro serviço Google como operacional.

## Fluxo e evidências

1. A pesquisa oficial inicial continua prioritária.
2. Na recuperação, o MCP pode chamar o navegador com assunto público limitado ou uma referência normativa tipada; não há parâmetro para documentos ou URL arbitrária.
3. As regras do provedor são recuperadas com TLS válido. Uma cópia comprimida, hash SHA-256, data e decisões de navegação integram o diagnóstico, como política de acesso, sem valor de prova jurídica.
4. Quando disponíveis, apenas URLs candidatas são devolvidas. A resposta gerada do Google não é aceita como evidência, contexto jurídico ou treinamento do modelo.
5. Os conectores existentes recuperam o documento oficial, conferem identificação e pertinência, registram a cópia/hash e preservam as limitações de data, vigência e eficácia. Um domínio oficial com um documento diferente é rejeitado.
6. Se o Google não fornece candidatos utilizáveis, permanece a alternativa de descoberta web existente e a conferência independente. Nenhuma fonte fictícia substitui a consulta fracassada.

As evidências são mantidas pelo fluxo da aplicação, com controle de proprietário. A existência de link em domínio oficial não confirma, sozinha, vigência, tese final, trânsito em julgado ou modulação. Compilações correntes não são apresentadas como redação histórica.

O leitor de regras de acesso preserva delimitadores de consulta, curingas e a regra mais específica, conforme o [protocolo de exclusão de robôs](https://www.rfc-editor.org/rfc/rfc9309.html). Isso evita o problema do leitor padrão que normaliza `/?` como `/` e produziria uma proibição excessiva.

## Isolamento e validação

O navegador não compartilha as redes de dados institucionais, não recebe credenciais de usuários, não persiste perfil/cookies e não publica porta no host. Possui chave própria, sistema de arquivos somente leitura, limites de memória/CPU/processos, uma consulta por vez e limite de frequência. O sandbox Chromium permanece ativo; a única capacidade adicional ao conjunto vazio é `SYS_CHROOT`, necessária ao seu isolamento com o perfil seccomp utilizado.

Foram executados 173 testes unitários. Incluem autenticação, tamanho/tipo de entrada, URLs privadas, domínio falso, leitura de regras de acesso, alternativa quando o Google está restrito e o caminho positivo **simulado** Google → recuperação do documento oficial → conferência de identidade → evidência. Esse teste controlado não é anunciado como uma pesquisa Google real bem-sucedida.

A prova real do navegador/MCP registra a restrição do redirecionamento. A regressão real na aplicação cobre identificação do CTB e recuperação dos critérios do diálogo competitivo, com fontes e hashes reproduzíveis. Os relatórios separam êxito das verificações de segurança e integração do estado indisponível do provedor.

## Operação e reversão

MCP 0.8.0, imagem `moara-core:google-discovery-20261031`; navegador `moara-reference-browser:20261031`. Sobreposição `moara/infrastructure/google-discovery-compose.yml`. Gateway, frontend, banco e inferência permanecem nos serviços e imagens anteriores; não há migração de dados.

O wrapper anterior está em `backups/google-discovery-20261031/compose-before`. A imagem anterior do MCP está em `moara-core:pre-google-mcp-20261031`. Para reverter, restaurar o wrapper e executar `up -d --no-deps moara-legal-mcp`, verificar saúde e parar somente `ai-server-moara-google-browser-1`. Não apagar volumes.

Relatórios: `docs/runtime/google-discovery-stage.json`, `google-discovery-public.json`, `google-app-stage.json`, `google-app-public.json` e `google-discovery-final.json`. As cópias de regras são evidências de política de acesso, não texto normativo brasileiro.
