axios.interceptors.request.use(function (config) {
    $.LoadingOverlay('show');
    return config;
});

axios.interceptors.response.use(function(response) {
        $.LoadingOverlay('hide');
        return response;
    },
    function(error) {
        $.LoadingOverlay('hide');
        return Promise.reject(error);
    });

document.getElementById('form-pesquisa-repercussao-geral').addEventListener('submit', e => {
    e.preventDefault();

    console.log('Recuperando temas...');
    axios.get(`listarProcesso.asp?${$('#form-pesquisa-repercussao-geral').serialize()}`)
        .then(resposta => {
            if (resposta.data.erro) {
                alert(resposta.data.mensagem);
            } else {
                $('#conteudo-dinamico').html(resposta.data);
            }
        })
        .catch(erro => {
            console.log('Erro ao recuperar temas...', erro);
            alert('Erro ao efetuar a pesquisa! Tente novamente dentro de 2 minutos. Se o erro persistir, entre em contato com nosso atendimento.')
        });
});

function validaCaptcha(liberado) {
    if (liberado) {
		$("#botao-pesquisar").prop("disabled", false);
	} else {
		$("#botao-pesquisar").prop("disabled", true);
	}
}

let campoTituloTema = document.querySelector('#txtTituloTema');
document.querySelectorAll('.operadores button').forEach(function(botao) {
    botao.addEventListener('click', function(e) {
        campoTituloTema.value = `${campoTituloTema.value} ${this.dataset.operador} `;
        campoTituloTema.focus();
    });
});

document.querySelector('#mais-relatores').addEventListener('click', function(e) {
    let tipo = 'A';
    if (this.checked) {
        tipo = 'X';
    }

    axios.get(`listarMinistro.asp?tipoMinistro=${tipo}`)
        .then(resposta => {
            $('#ministro').html(resposta.data);
        });
});