from dataclasses import dataclass,field
from uuid import UUID
from fastapi import HTTPException

PERMISSIONS=frozenset({
    'chat.use','history.read','history.manage','files.use','identity.read','identity.draft','identity.publish',
    'models.read','models.manage','models.install','models.remove','profiles.read','profiles.manage','benchmarks.run',
    'connectors.read','connectors.manage','data.query','groups.manage','users.read','users.manage','roles.assign',
    'workspace.use','knowledge.use','documents.use','development.use','development.execute','workflows.use',
    'api_keys.manage','audit.read','jobs.read','jobs.cancel','jobs.manage','status.read',
})
BASE={'workspace.use','knowledge.use','documents.use','development.use','workflows.use','chat.use','history.read','history.manage','files.use','identity.read','profiles.read','connectors.read','data.query','jobs.read','jobs.cancel'}
ROLES={
    'user':('Chat e histórico pessoal',{'chat.use','history.read','history.manage','profiles.read','identity.read'}),
    'documents':('Documentos e acervo',{'workspace.use','documents.use','knowledge.use','files.use'}),
    'developer':('Desenvolvimento e API para VS Code',{'development.use'}),
    'data_analyst':('Consulta de dados institucionais',{'connectors.read','data.query','jobs.read','jobs.cancel'}),
    'workflow_operator':('Fluxos de trabalho',{'workspace.use','workflows.use','jobs.read','jobs.cancel'}),
    'analyst':('Analista',BASE|{'models.read'}),
    'manager':('Gestor',BASE|{'status.read'}),
    'administrator':('Administrador',{'*'}),
    'ai_administrator':('Administrador de IA',BASE|{'models.read','models.manage','models.install','models.remove','profiles.manage','benchmarks.run','status.read','jobs.manage'}),
    'connector_administrator':('Administrador de Conectores',BASE|{'connectors.manage','groups.manage','users.read','status.read','jobs.manage'}),
    'auditor':('Auditor',{'identity.read','profiles.read','models.read','audit.read','status.read','jobs.read'}),
}

@dataclass
class Actor:
    user_id:UUID
    subject:str
    name:str
    email:str|None
    roles:tuple[str,...]
    permissions:frozenset[str]
    key_id:UUID|None=None
    allowed_profiles:tuple[str,...]|None=None
    allowed_sources:tuple[str,...]|None=None
    legacy_token:str|None=field(default=None,repr=False)
    upstream_key:str|None=field(default=None,repr=False)
    upstream_client_id:str|None=None
    session_id:UUID|None=None
    csrf:str|None=field(default=None,repr=False)
    auth_source:str='legacy'
    password_change_required:bool=False
    preferences:dict=field(default_factory=dict)
    owner_profiles_manage:bool=False

    def can(self,permission):return '*' in self.permissions or permission in self.permissions
    def require(self,permission):
        if not self.can(permission):raise HTTPException(403,'permission_denied')
    def public(self):
        return {'id':str(self.user_id),'subject':self.subject,'name':self.name,'email':self.email,
            'roles':list(self.roles),'permissions':sorted(self.permissions),'auth_source':self.auth_source,
            'password_change_required':self.password_change_required,'csrf_token':self.csrf,
            'preferences':{'theme':self.preferences.get('theme','light'),'welcome_seen':bool(self.preferences.get('welcome_seen',False))}}
