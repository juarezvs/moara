# Moara AI — acesso institucional e integrações por unidade

## Acesso

Endereço: **https://moara.am.trf1.gov.br/**, na rede institucional ou VPN com
acesso a `172.19.5.250`. O computador não precisa executar túnel SSH, VS Code,
arquivo hosts ou proxy local. HTTP redireciona para HTTPS.

Na tela de login, selecione a **unidade** e informe somente a **matrícula** e a
**senha da rede**. Para SJAM, a autenticação usa `JFAM` e o controlador
`srvdc1-am.am.trf1.gov.br:636`, com a base
`DC=am,DC=trf1,DC=gov,DC=br`. As contas locais existentes continuam disponíveis.

O chat nativo utiliza o modo **Moara AI · Automático**. Sua visibilidade no chat
usa a concessão nativa `principal_type=user, principal_id=*, permission=read`.
Essa concessão não libera os modelos privados: o gateway autoriza cada perfil,
conta e chave antes de executar a inferência.

As chaves independentes das integrações são administradas em
`https://moara.am.trf1.gov.br/moara/acessos`. Para sistemas, Continue e outros
clientes compatíveis com OpenAI, a URL base é
`https://moara.am.trf1.gov.br/moara/v1`, com `Authorization: Bearer SUA_CHAVE`.
O modelo `auto` respeita os perfis e fontes autorizados em cada chave. A chave
é mostrada uma única vez e pode ser revogada sem afetar as demais.

## Certificado e GPO

O Caddy mantém uma autoridade exclusiva `moara`, denominada
`Moara AI - Autoridade Interna`, e renova o certificado do site automaticamente.
A chave privada permanece no volume `ai-server_caddy_data`; somente o certificado
público foi exportado para `docs/runtime/moara-domain-root-ca.crt`.

- GPO: **Moara AI - Confianca HTTPS**.
- Domínio atendido: **am.trf1.gov.br / JFAM**.
- ID: `57280789-cbe5-40f4-8ebc-44126d3cc24c`.
- SHA-1 do certificado público: `8515DF867D70721461656068ECCB5004626A97B3`.
- Configuração de computador, sem configurações de usuário. Política própria,
  vinculada à raiz do domínio, sem alterar a Default Domain Policy.

A política adiciona somente esse certificado em
`HKLM\SOFTWARE\Policies\Microsoft\SystemCertificates\Root\Certificates`.
Ela não apaga autoridades existentes. A estação de implantação recebeu a GPO e
validou o HTTPS com a confiança padrão do Windows, sem desabilitar TLS.
As demais máquinas recebem a confiança quando a política de computador for
aplicada; herança de GPO bloqueada exige avaliação pelo administrador da OU.

A GPO foi publicada em JFAM. Para máquinas de outros domínios, o administrador
correspondente precisa distribuir a mesma autoridade pública. O script aceita
`-DomainController`, `-DomainName` e `-Credential` próprios de cada domínio:

```powershell
$credential = Get-Credential
.\moara\infrastructure\scripts\publish-moara-trust-gpo.ps1 `
  -DomainController dc.unidade.exemplo `
  -DomainName unidade.exemplo -Credential $credential
```

Nunca distribua `root.key`, chaves do Caddy ou credenciais de consulta do SECP.

## Órgãos e ADs

Administração: **Órgãos e integrações**, na lateral do chat, ou
`/static/moara/directories.html`. Exige sessão de administrador do chat.

Foram importados os **15 órgãos** do cadastro real do SECP, preservando a
situação ativo/inativo. `JFAM`, existente como cadastro legado no SECP, foi
mantido distinto de `SJAM`; não se mesclam identidades entre esses registros.

| Unidade | Domínio de rede | LDAPS | Situação inicial |
|---|---|---|---|
| SJAC | JFAC | ac.trf1.gov.br:636 | Certificado verificado; habilitado |
| SJAM | JFAM | srvdc1-am.am.trf1.gov.br:636 | Certificado e login real verificados |
| SJDF | JFDF | df.trf1.gov.br:636 | Certificado verificado; habilitado |
| SJGO | JFGO | go.trf1.gov.br:636 | Certificado verificado; habilitado |
| SJMA | JFMA | ma.trf1.gov.br:636 | Certificado verificado; habilitado |
| SJRR | JFRR | rr.trf1.gov.br:636 | Certificado verificado; habilitado |
| SJTO | JFTO | to.trf1.gov.br:636 | Certificado verificado; habilitado |

SJGO recebeu a integração global do SECP cujo domínio é explicitamente JFGO;
ela não é utilizada como alternativa para outras unidades. Para SJAC, foi usada
a URL LDAPS cadastrada, evitando o endereço LDAP sem TLS que divergia no JSON.
Unidades sem configuração de AD no SECP não receberam servidores inventados.

Esses diretórios usam **autenticação direta**: a senha apresentada é validada
como `DOMINIO\matricula` e a própria conexão lê os atributos da conta. A conta
administrativa usada na implantação não fica salva como conta de consulta.
O cadastro também oferece o modo com conta de consulta, cuja senha é cifrada.
Testar o modo direto verifica TLS; o login verifica senha, base, identidade e
grupos. Somente SJAM teve credencial real disponível para testar o login.

Cada identidade se vincula por `(diretório, objectGUID)`. E-mails iguais não
mesclam contas. Novas contas são usuários comuns; a opção de aprovação manual
e a restrição por grupos continuam disponíveis. A unidade escolhida determina
o diretório, sem tentar a senha nos demais ADs.

Inativar o órgão bloqueia seus logins, revoga sessões institucionais e faz o
gateway recusar suas chaves API. Consultas às fontes daquele órgão também são
bloqueadas. Se a validação institucional estiver indisponível, o gateway recusa
a operação, inclusive com chave previamente emitida.

Grupos `org:SIGLA` são gerenciados pelo gateway. A primeira autenticação de uma
nova unidade cria o grupo e habilita os perfis básicos existentes `fast`,
`coding`, `general` e `gemma4-12b`. O administrador pode ajustar suas concessões
na central. Isso não concede acesso a bancos, fontes de outros órgãos ou
perfis especializados. Não exclua esses grupos para inativar uma unidade;
use o controle de ativação do órgão.

## Oracle: cadastros e pendência para consultas

Foram criados **15 cadastros Oracle**, um por órgão: **9 com configurações reais
do SECP** e **6 rascunhos**, sem credenciais inventadas. Credenciais importadas
ficam cifradas na central de conectores. Nenhum dado ou configuração do SECP foi
modificado; a leitura do PostgreSQL do SECP utilizou transação somente de leitura.

As nove conexões configuradas chegaram à verificação de privilégios usando
Oracle Instant Client **19.32**, necessário para o verificador antigo de senha.
O arquivo oficial foi verificado por SHA-256 antes da instalação. Os termos do
pacote ficam preservados em `/opt/oracle/instantclient_19_32/BASIC_LICENSE`.

**As nove contas não passam na política de somente leitura**, pois têm objetos
próprios ou privilégios além dos permitidos. As fontes permanecem inativas e
nenhum objeto/campo foi liberado. Não foram revogados privilégios, alteradas
senhas do SECP, criados usuários nos bancos ou consultadas linhas do SARH.

Para liberar uma fonte, o DBA da seccional deve fornecer uma conta exclusiva,
sem objetos próprios, com `CREATE SESSION` e `SELECT` somente nas tabelas/views
aprovadas. Ela não deve receber escrita, execução de rotinas, privilégios `ANY`
ou funções administrativas. Depois:

1. Em **Fontes de dados**, abra a fonte da unidade e substitua a credencial.
2. Teste a conexão e a política de leitura; descubra os metadados.
3. Selecione os objetos e campos necessários e configure seus grupos/usuários.
4. Ative a fonte. A ativação do órgão continua sendo verificada nas consultas.

Os endpoints importados usam TCP/1521, conforme o SECP; o transporte não é
silenciosamente promovido a TCPS. Para TCPS, são necessários endpoint e cadeia
corretos. O modo OCI é usado no TCP legado; o caminho TCPS continua com a
validação TLS do driver thin. Não há alternativa automática que desative TLS.

## Operação

As redes Docker que sobrepunham as faixas das seccionais foram migradas para
`10.93.0.0/16` em sub-redes /24. A bridge padrão usa `10.94.0.0/24`, e futuras
redes automáticas usam `10.95.0.0/16`. As redes isoladas de conectores e controle
continuam em `10.91` e `10.92`. A política SSRF foi recalculada mantendo a
proteção dos destinos internos, sem bloquear as redes das seccionais.

Sockets systemd `moara-https.socket` e `moara-http.socket` escutam apenas no IP
institucional em 443/80 e encaminham para Caddy em loopback 8443/8080.
As regras de entrada correspondentes foram adicionadas na interface `eno1`.
SSH continua por chave e os serviços internos não foram publicados.

Use sempre todos os overlays, por exemplo com o wrapper:

```sh
sh moara/infrastructure/scripts/compose.sh config --quiet
sh moara/infrastructure/scripts/compose.sh ps
python3 moara/infrastructure/scripts/check-delivery.py
```

O overlay `public-site-compose.yml` é obrigatório: contém endereço público,
origens, configuração de rede e modo OCI. O build Oracle usa
`Dockerfile.oracle.integration`; não o substitua por um build thin genérico.
Para obter o artefato oficial, use `connectors/deployment/prepare-oracle-client.py`.

Manutenção local seleciona explicitamente o administrador original em
`secrets/moara_maintenance_admin_id`, pois há mais de um administrador no chat.
Ela não altera suas contas ou senhas e não cria endpoint público de manutenção.

A exclusão da credencial temporária de implantação
`C:\ServerIA\ai-server\secrets\ad-bootstrap.credential.xml` foi recusada pela
revisão automática, inclusive em uma tentativa restrita ao arquivo local. Ela
permanece cifrada com DPAPI do Windows e ignorada pelo Git. A aplicação não a
utiliza; os diretórios importados não armazenam a senha dessa conta.

## Validação e recuperação

Antes das mudanças foi criado e restaurado em isolamento o backup
`moara-before-migration-20261020T235542Z.tar.enc`, SHA-256
`c3791488c78c034778e8bea8c1e192ffa832ed3f50386f235614efe930ea33bb`.
Foram verificados PostgreSQL, SQLite, arquivos e autoridades do Caddy. A migração
de rede preservou os mesmos volumes dos 25 serviços.

Evidências em `docs/runtime`: importação do SECP, GPO, migração de rede,
verificação Oracle, aceitação de diretórios, integração do gateway e navegador.
O teste real de inferência respondeu `42` a `17 + 25`, selecionando o perfil
`fast` / Qwen3 8B. Uma amostra levou 79,42 s em CPU; isso não é um SLA ou
benchmark. O teste de navegador removeu somente o chat sintético que criou.

Foram preservadas imagens `ai-webui:before-public-site`,
`moara-core:before-public-site` e `ai-connector-hub:before-public-site` para
recuperação. A configuração original do daemon e o inventário de redes/volumes
ficam em `secrets/network-migration/`. Uma reversão exige coordenar a interface,
o gateway e o cadastro institucional; não restaure somente o gateway antigo
mantendo novas contas AD sem os mesmos controles de autorização.

Não remova volumes nem regenere a autoridade do Caddy durante atualizações:
isso perderia dados ou exigiria redistribuir a confiança. Para desfazer a
publicação, desative os dois sockets, retire somente as regras de firewall
Moara, desvincule a GPO própria e remova somente o registro DNS Moara. Mantenha
a autoridade e os dados até terminar a recuperação validada.
