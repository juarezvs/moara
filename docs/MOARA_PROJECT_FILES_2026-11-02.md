# Arquivos e pastas dos projetos

A Moara usa dois ambientes de arquivos, escolhidos pelo usuário.

## VS Code: a pasta aberta é o projeto

O Continue instalado neste computador já usa a API Moara e o modelo moara-code, com ferramentas habilitadas. A configuração pessoal recebeu uma regra para trabalhar na pasta aberta, sem caminho fixo. A configuração anterior foi preservada em um backup na mesma pasta pessoal. Chaves e certificado existentes foram mantidos.

Abra o projeto com **Arquivo → Abrir Pasta**, selecione **Moara Desenvolvedora** no Continue e escolha **Agent**. Se a configuração já estava aberta, recarregue a janela do VS Code. Em um workspace com várias pastas, use a pasta do arquivo ativo ou identifique qual projeto deseja alterar.

Exemplo: “Leia o projeto, crie uma pasta tests, implemente os testes da função total e execute-os.”

As ferramentas de leitura, criação, edição e terminal são do Continue/VS Code. A chave autentica inferência; não concede acesso remoto do servidor às unidades do computador. As permissões efetivas das ferramentas permanecem sob controle do editor. O modo Chat não disponibiliza ferramentas. Não foi criado um servidor de arquivos exposto na rede.

O pacote baixado em **API para VS Code** inclui as regras atualizadas. Ao mesclar o config.yaml, inclua também a seção rules, preservando configurações existentes.

## Portal: arquivos do projeto selecionado

Em **Espaço de trabalho → MOARA DEV**, crie ou abra um projeto. A seção Arquivos e pastas permite criar pastas, editar arquivos, renomear, mover e excluir caminhos. Pastas vazias são preservadas. As operações criam versões.

No campo **Solicitação**, descreva a alteração e clique **Aplicar solicitação aos arquivos**. A Desenvolvedora lista e lê os arquivos, chama ferramentas de escrita/substituição/movimentação e a aplicação salva uma versão ao concluir. A resposta apresenta as operações realizadas. O fluxo antigo de proposta e revisão continua disponível.

A exclusão pelo agente depende da opção explícita **Permitir excluir arquivos nesta solicitação**. A exclusão manual apresenta confirmação. Use **Histórico de versões** e **Restaurar arquivos de uma versão** para recuperar os arquivos em uma nova versão.

Nenhum caminho recebido do modelo é usado como caminho do sistema operacional do servidor. Os arquivos do portal continuam no armazenamento criptografado de recursos. Alterações exigem proprietário, sessão interativa e permissões de desenvolvimento e espaço de trabalho. Chaves pessoais de inferência não dão acesso aos arquivos do portal.

Uma solicitação usa uma cópia de trabalho e até 12 rodadas de ferramentas. Caminhos relativos, conflitos entre arquivos e pastas, hashes na edição e versão do recurso são conferidos pela aplicação. Uma versão modificada por outro usuário ou aba gera conflito. Falhas de inferência e limites não gravam o conjunto parcial de alterações. Antes de salvar, a sessão é conferida novamente. A execução de código continua no fluxo de sandbox existente, separado da edição.

O armazenamento de projetos do portal mantém seus limites existentes: até 64 arquivos de texto, tamanho individual até 200 kB, conteúdo total dos arquivos até 1 MB e corpo completo do recurso até 150 kB. O limite mais restritivo prevalece. Os caminhos portáveis atuais não aceitam segmentos ocultos. Para projetos grandes e configurações como .gitignore/.github, use o workspace local do VS Code; esta entrega não amplia o limite do modelo nem esses limites do armazenamento.

## Verificação

Os relatórios na pasta runtime registram os testes automatizados, testes reais de navegador, operações de ferramentas com a chave pessoal e presença dos modelos em GPU. O teste local usa arquivos sintéticos, uma implementação controlada dos contratos de ferramentas e a API real; não automatiza a interface do VS Code. O teste do portal usa uma sessão de navegador real, autenticação e o agente real.

Documentação primária do Continue:

- [Ferramentas e modo Agent](https://docs.continue.dev/ide-extensions/agent/how-it-works)
- [Configuração e regras](https://docs.continue.dev/reference)
