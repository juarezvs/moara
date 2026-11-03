# Administração da Moara 2.0

O portal está em https://moara.am.trf1.gov.br/moara/. Os menus obedecem às
permissões existentes; ocultar um botão não substitui a autorização no backend.

## Assistentes e identidade

Em **Assistentes institucionais**, administradores com `profiles.manage` podem
habilitar/desabilitar especialidades, editar instruções e selecionar ferramentas
dentro da lista central permitida. A publicação exige a revisão atual e cria uma
nova versão auditada. Uma edição concorrente retorna conflito; recarregue antes
de publicar. Carregar uma versão antiga no formulário não modifica a ativa até
a nova publicação.

Essas configurações não alteram as permissões do usuário nem as políticas
centrais. Por exemplo, habilitar leitura de dados em uma especialidade não
concede `data.query`. A aplicação autoriza os encaminhamentos entre especialidades.

O manifesto 2.0 está no módulo **Identidade institucional**, com histórico,
hash e operações de rascunho/publicação. Não cadastrar nomes de aprovadores,
autoria ou etimologia sem informação institucional confirmada. Trocar o modelo
não muda a identidade publicada.

## Dados e evidências

Preservar os controles dos conectores existentes: catálogo permitido, finalidade,
limites, credencial restrita e autorização efetiva do usuário. PJe e SEI não são
conectores REST genéricos habilitados com a URL de seus portais.

As evidências jurídicas são privadas, criptografadas e protegidas contra
alteração/exclusão/truncamento no runtime. Pertencem ao usuário e, quando criada
por chave de integração, à chave originadora. Exportar uma evidência reproduz
o que foi consultado naquele momento; não faz uma nova conferência da lei hoje.

## Homologação de PJe e SEI

O cadastro preparado aponta para https://sei.trf1.jus.br/ e
https://pje1g.trf1.jus.br/. As leituras estão desabilitadas e não há requisição
externa no endpoint preparado. Para ativar futuramente, são necessários:

1. Mecanismo oficial e ambiente de homologação fornecidos pelo tribunal.
2. Autenticação de serviço/usuário e escopos efetivos para cada operação de leitura.
3. Definição de vínculo entre usuário, unidade e processos/documentos acessíveis.
4. Validação de paginação, limites, indisponibilidade e trilha auditável com casos autorizados.
5. Homologação institucional antes de alterar o estado de conexão.

O contrato preparado oferece somente operações de leitura. Não habilita escrita,
assinatura, tramitação ou publicação. Não usar automação de navegador para
contornar os mecanismos oficiais ainda pendentes.

## Operação diária

O painel da visão geral, mediante `status.read`, apresenta residência do principal
e embeddings, transporte, fila e VRAM física. Uma GPU de 12 GB não permite inferir
capacidade para seis modelos grandes; o compartilhamento evita essa carga.
Verificar uso de memória do driver, indisponibilidade de fontes e respostas 429.

O módulo jurídico ainda não certifica vigência/eficácia nem oferece pesquisa
jurisprudencial completa. Não substituir seus estados por “lei atualizada” ou
habilitar conclusões jurídicas apenas por existir uma data no documento oficial.

Backups, atualização e reversão estão no [guia de operação](MOARA_2_OPERATIONS.md).
