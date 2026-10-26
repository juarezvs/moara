import { Injectable,signal } from '@angular/core';

const MESSAGES:Record<string,string>={
  authentication_required:'Entre com sua conta para continuar.',session_expired:'Sua sessão expirou. Entre novamente.',
  invalid_credentials:'Confira o e-mail e a senha.',permission_denied:'Sua conta não tem permissão para esta ação.',
  account_disabled:'O acesso desta conta está desativado.',csrf_required:'Atualize a página para renovar sua sessão.',
  rate_limit_exceeded:'Há muitas solicitações. Aguarde um momento e tente novamente.',
  invalid_request:'Confira os campos informados.',identity_publication_changed:'A versão ativa mudou. Atualize antes de publicar.',
  identity_draft_changed:'Este rascunho foi alterado. Reabra a versão antes de salvar.',
  complete_institutional_login_in_existing_chat:'Conclua a autenticação institucional no chat e volte para esta página.',
  legacy_auth_unavailable:'O serviço de autenticação institucional está temporariamente indisponível.',
  invalid_identity_document:'O manifesto tem campos inválidos ou perguntas duplicadas.',
  password_change_required:'Defina sua senha antes de continuar.',internal_error:'Não foi possível concluir esta operação.',
  inference_rejected:'O modelo não pôde atender esta solicitação. Aguarde um momento ou selecione outro perfil autorizado.',
  inference_unavailable:'O serviço do modelo está temporariamente indisponível. Tente novamente.',
  no_compatible_execution_available:'Nenhum perfil autorizado disponível atende aos recursos desta solicitação.',
  estimated_context_budget_exceeded:'A conversa excede o contexto do perfil. Reduza o conteúdo ou inicie uma nova conversa.',
  profile_not_authorized:'Este perfil não está autorizado para sua conta ou chave.',
  model_has_enabled_profiles:'Desative os perfis vinculados antes de remover este modelo.',
  execution_configuration_not_provisioned:'Escolha um modelo e uma configuração de execução já validados.',
  preserved_legacy_model_protected:'Este modelo está protegido pela preservação da migração.',
  profile_already_exists:'Já existe um perfil com esse identificador.',
  model_validation_required:'Execute e aprove o benchmark de referência antes de ativar este modelo.'
};
export class ApiError extends Error {
  constructor(public status:number,public code:string,public requestId:string,public fields:string[]=[]){
    super(MESSAGES[code]||(code.includes(' ')&&code.length<=240?code:'Não foi possível concluir esta operação.'));
  }
}
@Injectable({providedIn:'root'})
export class Api {
  csrf=signal('');
  async request<T>(path:string,method='GET',body?:unknown,timeout=30000):Promise<T>{
    const headers:Record<string,string>={};
    if(body!==undefined)headers['Content-Type']='application/json';
    if(!['GET','HEAD'].includes(method)&&this.csrf())headers['X-Moara-CSRF']=this.csrf();
    let response:Response;
    try{response=await fetch('/moara/api/v1'+path,{method,credentials:'same-origin',headers,signal:AbortSignal.timeout(timeout),
      body:body===undefined?undefined:JSON.stringify(body)});}
    catch{throw new Error('O servidor não respondeu a tempo. Confira a conexão e tente novamente.');}
    if(!response.ok){
      const data=await response.json().catch(()=>({}));
      throw new ApiError(response.status,typeof data.detail==='string'?data.detail:'internal_error',response.headers.get('X-Request-ID')||'',data.fields||[]);
    }
    return response.json() as Promise<T>;
  }
}
