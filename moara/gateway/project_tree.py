"""Pure virtual project operations. The resource store supplies atomic versioning."""
import hashlib
from fastapi import HTTPException
from .platform_contracts import validate_files

def sha(text):
    return hashlib.sha256(text.encode('utf8')).hexdigest()

def path(value):
    # Reuse the same portable paths accepted by exports and the sandbox.
    validate_files({value:''})
    return value

def folders(files, directories=()):
    result=set(directories)
    for name in list(files)+list(result):
        path(name)
        result.update('/'.join(name.split('/')[:n]) for n in range(1,len(name.split('/'))))
    if len(result)>256:raise HTTPException(422,'too_many_project_directories')
    names=list(files)+list(result)
    if len({n.casefold() for n in names})!=len(names):raise HTTPException(422,'conflicting_project_path')
    for name in result:
        if any(name.casefold().startswith(f.casefold()+'/') for f in files):
            raise HTTPException(422,'conflicting_project_path')
    return sorted(result)

def validate_directories(files, directories):
    if not isinstance(directories,list) or any(not isinstance(p,str) for p in directories):
        raise HTTPException(422,'invalid_project_directories')
    if len(directories)!=len(set(directories)):raise HTTPException(422,'duplicate_project_path')
    folders(files,directories)

def tree(body):
    files=body.get('files',{})
    return {'files':[{'path':p,'bytes':len(v.encode()),'sha256':sha(v)} for p,v in sorted(files.items())],
            'directories':folders(files,body.get('directories',[]))}

def apply(body,operations):
    files=dict(body.get('files',{}));directories=set(folders(files,body.get('directories',[])))
    for op in operations:
        if not isinstance(op,dict) or set(op)-{'op','path','destination','content','expected_sha256','old','new','recursive'}:
            raise HTTPException(422,'invalid_project_operation')
        name=path(op.get('path'));action=op.get('op')
        exists=name in files or name in directories
        if action=='write':
            if name in directories:raise HTTPException(409,'path_is_directory')
            if name in files and op.get('expected_sha256')!=sha(files[name]):
                raise HTTPException(409,'file_changed_read_before_write')
            files[name]=op.get('content')
        elif action=='replace':
            if name not in files:raise HTTPException(404,'project_file_not_found')
            old,new=op.get('old'),op.get('new')
            if not isinstance(old,str) or not old or not isinstance(new,str) or files[name].count(old)!=1:
                raise HTTPException(409,'replacement_must_match_once')
            if op.get('expected_sha256')!=sha(files[name]):raise HTTPException(409,'file_changed_read_before_write')
            files[name]=files[name].replace(old,new,1)
        elif action=='mkdir':
            if exists:raise HTTPException(409,'project_path_exists')
            directories.add(name)
        elif action in ('move','delete'):
            if not exists:raise HTTPException(404,'project_path_not_found')
            members=[p for p in files if p==name or p.startswith(name+'/')]
            children=[p for p in directories if p==name or p.startswith(name+'/')]
            if action=='delete' and name in directories and (members or len(children)>1) and op.get('recursive') is not True:
                raise HTTPException(409,'directory_not_empty')
            if action=='move':
                dest=path(op.get('destination'))
                if dest.casefold()==name.casefold() or dest.casefold().startswith(name.casefold()+'/'):
                    raise HTTPException(409,'invalid_move_destination')
                if any(p.casefold()==dest.casefold() or p.casefold().startswith(dest.casefold()+'/') for p in list(files)+list(directories)):
                    raise HTTPException(409,'project_destination_exists')
                renamed={dest+p[len(name):]:files[p] for p in members}
                for p in members:del files[p]
                files.update(renamed)
                directories.difference_update(children)
                directories.update(dest+p[len(name):] for p in children)
            else:
                for p in members:del files[p]
                directories.difference_update(children)
        else:raise HTTPException(422,'unsupported_project_operation')
        validate_files(files)
        directories=set(folders(files,directories))
    return {**body,'files':files,'directories':sorted(directories)}
