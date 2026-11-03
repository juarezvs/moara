import '@angular/compiler';
import {describe,it,expect,vi,afterEach} from 'vitest';
import {Api} from './api';
import {uploadPercent,UploadProgress} from './upload-progress';
class FakeXHR {
 static last:FakeXHR;upload:any={};status=201;responseText='{"id":"document-qa"}';headers:Record<string,string>={};body:unknown;url='';onload:any;onerror:any;onabort:any;withCredentials=false;
 constructor(){FakeXHR.last=this;}
 open(method:string,url:string){expect(method).toBe('POST');this.url=url;}
 setRequestHeader(key:string,value:string){this.headers[key]=value;}
 getResponseHeader(){return 'qa-request';}
 send(body:unknown){this.body=body;}
 abort(){this.onabort?.();}
}
afterEach(()=>vi.unstubAllGlobals());
describe('streaming document upload',()=>{
 it('sends the file itself and reports actual transport progress, distinct from confirmation',async()=>{
  vi.stubGlobal('XMLHttpRequest',FakeXHR);const api=new Api();api.csrf.set('csrf-qa');const progress:UploadProgress[]=[];
  const file=new File([new Uint8Array(9*1024*1024)],'large.pdf');
  const promise=api.uploadDocument(file,file.name,null,value=>progress.push(value));const xhr=FakeXHR.last;
  expect(xhr.body).toBe(file);expect(xhr.headers['X-Moara-CSRF']).toBe('csrf-qa');expect(xhr.url).toContain('/documents/upload?');
  xhr.upload.onprogress({loaded:file.size/2,total:file.size,lengthComputable:true});expect(progress.at(-1)?.percent).toBe(50);expect(progress.at(-1)?.phase).toBe('sending');
  xhr.upload.onload();expect(progress.at(-1)?.percent).toBe(100);expect(progress.at(-1)?.phase).toBe('confirming');
  xhr.onload();expect(await promise).toEqual({id:'document-qa'});
 });
 it('never reports an aborted request as a completed document',async()=>{
  vi.stubGlobal('XMLHttpRequest',FakeXHR);const controller=new AbortController();const promise=new Api().uploadDocument(new File(['abc'],'qa.txt'),'qa',null,undefined,controller.signal);
  controller.abort();await expect(promise).rejects.toThrow('interrompido');
 });
 it('keeps unknown and incomplete byte counts below a claimed completion',()=>{
  expect(uploadPercent(0,0)).toBe(0);expect(uploadPercent(99,100)).toBe(99);expect(uploadPercent(200,100)).toBe(100);
 });
});
