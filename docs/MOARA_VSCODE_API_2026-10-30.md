# Moara no VS Code — API pessoal

Implantação em 30/10/2026 (America/Manaus).

## Usar

1. Entre na Moara com sua conta institucional e abra **API para VS Code**: https://moara.am.trf1.gov.br/moara/desenvolvimento/api.
2. Clique em **Criar chave pessoal**, dê um nome ao computador e escolha validade e limite. Copie a chave; o valor é exibido somente uma vez.
3. Clique em **Baixar configuração do Continue**. O pacote contém configuração, certificado público institucional, exemplo de variáveis e instruções. Ele não contém sua chave.
4. No VS Code, abra o Continue e sua configuração local. Mescle a entrada `models` do pacote na configuração existente. Preserve outros modelos que desejar manter.
5. Copie o certificado para a pasta pessoal `.continue`. No `.env` dessa pasta, defina `MOARA_API_KEY` com a chave e `MOARA_CA_BUNDLE` com o caminho absoluto do certificado, sem aspas. Nunca inclua esse arquivo em um repositório.
6. Recarregue o VS Code e selecione **Moara Desenvolvedora**. Estão configuradas as funções Chat, edição e aplicação de alterações; ferramentas do modo Agent continuam sujeitas às permissões do editor.

| Campo | Valor |
|---|---|
| Provedor no Continue | `openai` (formato de comunicação) |
| URL base | `https://moara.am.trf1.gov.br/moara/v1` |
| Modelo | `moara-code` |
| Protocolo | Chat Completions; `useResponsesApi: false` |
| Autenticação | `Authorization: Bearer <chave pessoal>` |
| Contexto recomendado do cliente | 4096 tokens |
| Saída recomendada | 1024 tokens |

O endereço `/v1` na raiz do domínio pertence ao gateway anterior. Use a URL base completa acima. A configuração preserva TLS; não desative a validação de certificados.

A inferência utiliza a infraestrutura local, sem cobrança de tokens de provedor externo. Capacidade, contexto, fila e disponibilidade permanecem limitados pelo servidor. Outros modelos eventualmente selecionados no editor podem ter condições próprias. Nenhuma configuração existente do VS Code foi substituída automaticamente.

## Credenciais e permissões

- Emissão pela sessão interativa autenticada, com CSRF; uma chave API não pode emitir outras chaves.
- Chave aleatória, persistida somente como hash, vinculada à conta e às permissões atuais dela.
- Validade entre 1 e 90 dias; limite de 1 a 60 requisições/minuto, padrão 20; máximo de 10 chaves ativas por conta, incluindo chaves administrativas existentes.
- Escopos pessoais: `chat.use`, `profiles.read`, `identity.read`, `development.use`.
- Perfil permitido: `general`, compartilhando o modelo principal residente na GPU. O alias `moara-code` seleciona a assistente desenvolvedora.
- Sem fontes institucionais autorizadas na chave e sem permissões administrativas ou de execução de comandos no servidor. O editor controla seus arquivos e ferramentas locais.
- Listagem e revogação pessoais limitadas à conta proprietária. Desabilitar a conta, remover suas permissões ou revogar a chave bloqueia novos acessos.
- Ações registradas na auditoria; o segredo não é recuperável pela listagem.

## Operação e validação

Imagem do gateway: `moara-core:ide-20261030`; overlay final: `moara/infrastructure/ide-compose.yml`. A publicação recriou somente o gateway. Não houve migração de banco nem reinício dos serviços de inferência ou do MCP jurídico.

Backup criptografado anterior à publicação: `moara-before-migration-20261031T030155Z.tar.enc`. Restauração isolada verificada, com contagens PostgreSQL, integridade SQLite, hashes de arquivos/configurações e CA conferidos. A cópia tem data UTC; a implantação ocorreu no dia 30 em Manaus.

Validações: 89 testes automatizados do backend; cliente OpenAI SDK real; modelos e alias; geração de código na GPU; streaming com identificadores estáveis; chamadas de ferramenta, argumentos em streaming e retorno do resultado; execução funcional do código gerado em contêiner sem rede; bloqueio de administração e de perfis não autorizados; revogação; interface desktop/mobile e preservação do chat. O pacote Continue foi validado estruturalmente e baixado pelo navegador. Isso não equivale a executar todas as funções de todas as extensões de VS Code.

Evidências: `docs/runtime/ide-sdk-stage.json`, `docs/runtime/ide-sdk-public.json`, `docs/runtime/ide-ui-public.json`. As credenciais sintéticas de teste são revogadas ao fim dos testes. Não são fornecidas chaves pessoais em relatórios.

Runners: `infrastructure/site-entry/run_ide_sdk.py` e `run_ide_browser.py`; `--stage` seleciona candidato privado. O SDK é instalado em diretório isolado de testes, sem instalação na imagem de produção. Código gerado é executado separadamente, sem credenciais e sem rede.

Rollback: restaurar `backups/ide-20261030/compose-before` sobre o wrapper no servidor, validar `compose.sh config --quiet` e executar `compose.sh up -d --no-deps moara-gateway`. As chaves e a auditoria permanecem no banco; o painel pessoal fica indisponível na imagem anterior. Não use `compose down`.

Referências de configuração: https://docs.continue.dev/reference e https://docs.continue.dev/customize/model-providers/top-level/openai.
