import { Injectable,signal } from '@angular/core';
import {UploadProgress,uploadPercent} from './upload-progress';

const MESSAGES:Record<string,string>={
  empty_document:'O arquivo está vazio.',invalid_filename:'O nome do arquivo não é válido.',
  unsupported_document_type:'Escolha um arquivo PDF, DOCX, XLSX, TXT, MD ou CSV.',
  invalid_pdf:'O arquivo não contém um PDF válido.',invalid_office_document:'O arquivo não contém um documento Office válido.',
  utf8_document_required:'O arquivo de texto precisa usar a codificação UTF-8.',
  previous_history_not_linked:'Entre com a conta institucional que possui as conversas anteriores.',
  previous_history_unavailable:'Não foi possível consultar suas conversas anteriores. Tente novamente.',
  previous_history_branch_incomplete:'Esta conversa tem uma estrutura que não pode ser retomada automaticamente. Exporte o original para consulta.',
  previous_conversation_too_large:'Esta conversa excede os limites de continuação. O original foi preservado; exporte-o e selecione os trechos necessários.',
  mfa_verification_failed:'O código não foi aceito ou o desafio expirou. Confira os dados ou reinicie o acesso.',
  interactive_session_required:'Entre na Moara pelo navegador para gerenciar suas chaves.',
  developer_model_not_available:'O modelo principal não está disponível ou autorizado para sua conta.',
  personal_api_key_limit:'Você atingiu o limite de chaves ativas. Revogue uma chave que não utiliza antes de emitir outra.',
  developer_certificate_not_available:'O certificado de conexão ainda não está disponível. A administração pode conferir a integração.',
  authentication_required:'Entre com sua conta para continuar.',session_expired:'Sua sessão expirou. Entre novamente.',
  invalid_credentials:'Confira a matrícula, a senha e o órgão selecionado.',permission_denied:'Sua conta não tem permissão para esta ação.',
  account_disabled:'O acesso desta conta está desativado.',csrf_required:'Atualize a página para renovar sua sessão.',
  rate_limit_exceeded:'Há muitas solicitações. Aguarde um momento e tente novamente.',
  invalid_request:'Confira os campos informados.',identity_publication_changed:'A versão ativa mudou. Atualize antes de publicar.',
  identity_draft_changed:'Este rascunho foi alterado. Reabra a versão antes de salvar.',
  complete_institutional_login_in_existing_chat:'A autenticação não pôde ser concluída. Reinicie o acesso ou procure a administração.',
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
  model_validation_required:'Execute e aprove o benchmark de referência antes de ativar este modelo.',
  assistant_revision_conflict:'A configuração foi alterada por outra sessão. Reabra a assistente antes de publicar.',
  assistant_not_authorized:'Sua conta não tem permissão para esta assistente.',assistant_disabled:'Esta assistente está temporariamente desativada.',
  assistant_tool_not_authorized:'A ferramenta necessária não está autorizada para esta assistente ou para sua conta.',
  assistant_catalog_unavailable:'O catálogo institucional está indisponível. Tente novamente em instantes.'
};
export class ApiError extends Error {
  constructor(public status:number,public code:string,public requestId:string,public fields:string[]=[]){
    super(MESSAGES[code]||(code.includes(' ')&&code.length<=240?code:'Não foi possível concluir esta operação.'));
  }
}
@Injectable({providedIn:'root'})
export class Api {
  csrf=signal('');
  uploadDocument(file:File,title=file.name,groupId:string|null=null,onProgress?:(value:UploadProgress)=>void,signal?:AbortSignal):Promise<{id:string;size_bytes:number;sha256:string}>{
    if(!file.size)return Promise.reject(new Error('O arquivo está vazio.'));
    return new Promise((resolve,reject)=>{
      const xhr=new XMLHttpRequest();const query=new URLSearchParams({filename:file.name,title});
      if(groupId)query.set('group_id',groupId);
      const update=(loaded:number,total:number,phase:UploadProgress['phase'])=>onProgress?.({filename:file.name,loaded,total,percent:uploadPercent(loaded,total),phase});
      const abort=()=>xhr.abort();const cleanup=()=>signal?.removeEventListener('abort',abort);
      xhr.open('POST','/moara/api/v1/platform/documents/upload?'+query);xhr.withCredentials=true;
      xhr.setRequestHeader('Content-Type','application/octet-stream');
      if(this.csrf())xhr.setRequestHeader('X-Moara-CSRF',this.csrf());
      xhr.upload.onprogress=e=>update(e.loaded,e.lengthComputable?e.total:file.size,'sending');
      xhr.upload.onload=()=>update(file.size,file.size,'confirming');
      xhr.onload=()=>{cleanup();let data:any;try{data=JSON.parse(xhr.responseText);}catch{data={};}
        if(xhr.status<200||xhr.status>=300){reject(new ApiError(xhr.status,typeof data.detail==='string'?data.detail:'internal_error',xhr.getResponseHeader('X-Request-ID')||''));return;}
        resolve(data);
      };
      xhr.onerror=()=>{cleanup();reject(new Error('Não foi possível enviar o arquivo. Confira a conexão e tente novamente.'));};
      xhr.onabort=()=>{cleanup();reject(new Error('Envio interrompido. Confira a lista de documentos antes de reenviar.'));};
      if(signal?.aborted){reject(new Error('Envio interrompido.'));return;}
      signal?.addEventListener('abort',abort,{once:true});update(0,file.size,'sending');xhr.send(file);
    });
  }
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
