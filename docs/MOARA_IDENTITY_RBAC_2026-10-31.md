# Identidade e acessos da Moara

Implementação de 31/10/2026, America/Manaus. Administração em `/moara/acessos`, também disponível no menu **Identidade e acessos**.

## Fluxo institucional

Ao concluir autenticação de rede, inclusive eventuais fatores adicionais, uma identidade autorizada pelo serviço institucional recebe um cadastro próprio na Moara. O perfil inicial é **Chat e histórico pessoal**. Inclui conversa, pesquisa jurídica dentro do chat, catálogo necessário à seleção do modelo principal, identidade institucional e apenas o histórico do próprio usuário. Não permite gerenciar usuários, modelos, conectores, executar consultas de dados, usar documentos/acervo ou emitir chaves para desenvolvimento.

O papel inicial concede uso do perfil compartilhado `gemma4-12b`, sujeito a estar habilitado e disponível. Não torna públicos os demais modelos nem amplia acesso a fontes e documentos. A lista explícita de perfis de uma chave continua prevalecendo. Usuários locais com esse papel também conseguem conversar, sem depender de vínculo com um grupo de AD.

Permissões concedidas pela Moara são preservadas nos logins seguintes. Um administrador vindo do serviço de autenticação não recebe automaticamente administração na Moara. A criação institucional é auditada. Conta desativada, órgão desativado ou vínculo institucional não confirmado continuam bloqueados pela autoridade existente.

## Administração

A conta institucional verificada **am200401 / SJAM** recebeu explicitamente o papel **Administrador**, com todas as permissões da Moara. A atribuição foi vinculada ao identificador imutável da conta e conferida no serviço institucional assinado, não apenas pelo nome ou e-mail. Também foi habilitada a administração do serviço institucional existente para acessar os cadastros de órgãos/ADs. O administrador anterior foi preservado.

Para conceder acesso:

1. Abra **Identidade e acessos** e busque o usuário pelo nome ou e-mail.
2. Clique em **Permissões**.
3. Mantenha **Chat e histórico pessoal** e selecione as funcionalidades adicionais.
4. Confira o acesso resultante e salve.

Há papéis adicionais para **Documentos e acervo**, **Desenvolvimento e API para VS Code**, **Consulta de dados institucionais** e **Fluxos de trabalho**, além dos perfis de administração, análise, gestão e auditoria existentes. As permissões desses papéis se somam. Perfis antigos como Analista e Gestor têm cobertura ampla, exibida no editor; não são os perfis iniciais de novos usuários. Fontes, documentos e perfis especializados também mantêm suas próprias autorizações.

Salvar permissões ou desativar uma conta invalida suas sessões interativas anteriores. O usuário deve entrar novamente. As APIs reavaliam as permissões efetivas da conta; esconder menus é apenas a apresentação. Credenciais de máquina não podem criar contas ou atribuir papéis. O último administrador ativo não pode ser removido.

Contas institucionais são cadastradas no primeiro acesso. A atualização do cadastro institucional permanece disponível para importação administrativa. Contas locais podem ser criadas com senha temporária e troca obrigatória, sem alterar senhas de rede.

## Validação

126 testes de backend, incluindo padrão mínimo, ausência de promoção automática por papel externo, preservação dos papéis no login, rejeição de permissões antigas excessivas do perfil inicial, administrador completo e manutenção da lista de perfis permitidos de chaves.

Navegador em ambiente isolado e público: login, contexto e histórico preservados; conta local sintética criada com troca de senha; conversa efetiva com perfil mínimo; negação direta nas APIs administrativas, dados, documentos, modelos e desenvolvimento; bloqueio de autoelevação; isolamento de histórico; menus restritos; concessão de desenvolvimento pelo editor de permissões; invalidação de sessão; acesso à página de API; revogação e nova negação; adaptação a celular. A conta sintética é desativada, suas sessões revogadas e conversas arquivadas. Nenhum usuário real é usado como objeto dos testes de concessão/revogação.

A compatibilidade de chaves, streaming e chamadas de ferramentas do editor é novamente verificada com credenciais temporárias, revogadas ao final. Não é feito um login AD com senha pessoal durante os testes: o fluxo AD já existente e sua autoridade foram preservados; a identidade administrativa foi conferida pelo serviço institucional.

## Implantação e reversão

Imagem `moara-core:identity-rbac-20261031`; base preservada `moara-core:pre-identity-rbac-20261031`. Overlay `moara/infrastructure/identity-rbac-compose.yml`. Sem alteração de esquema e sem reiniciar inferência, MCP ou proxy.

O diretório protegido `backups/identity-rbac-20261031` contém o wrapper e as permissões anteriores à implantação. A ativação verifica o candidato e a identidade do administrador antes da mudança e possui reversão em caso de falha. Uma reversão posterior deve restaurar o wrapper anterior, os registros de papéis e as atribuições administrativas do snapshot, além do papel anterior da conta no serviço institucional. Não remover volumes ou históricos.

Evidências em `docs/runtime/identity-rbac-stage.json`, `identity-rbac-public.json`, `identity-rbac-sdk.json`, `identity-rbac-final.json`, `rbac-user.png` e `rbac-admin.png`.
