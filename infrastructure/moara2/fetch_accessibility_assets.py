"""Fetch pinned official OpenDyslexic assets, keeping attribution and OFL."""
import base64,hashlib,json,pathlib,urllib.request
root=pathlib.Path(__file__).resolve().parents[2]
target=root/'moara/web/public/fonts/opendyslexic';target.mkdir(parents=True,exist_ok=True)
blobs={
 'OpenDyslexic-Regular.woff2':'4ee220be7e9b551ad100468bd08ba35f6f9fe2f8',
 'OpenDyslexic-Bold.woff2':'b5fd5e4f4b0977495d39bb3220096aef50120e31',
 'OFL.txt':'bb867823f2408fb8d2b3af5cb118b4bc0cd61972',
}
sources={}
for name,expected in blobs.items():
    url='https://api.github.com/repos/antijingoist/opendyslexic/git/blobs/'+expected
    request=urllib.request.Request(url,headers={'User-Agent':'Moara-accessibility-build/1.0'})
    with urllib.request.urlopen(request,timeout=30) as response:metadata=json.load(response)
    raw=base64.b64decode(metadata['content'])
    if len(raw)>512000 or hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()!=expected:raise RuntimeError('Font source integrity mismatch')
    (target/name).write_bytes(raw)
    sources[name]={'url':url,'git_blob':expected,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
(target/'SOURCE.json').write_text(json.dumps({'project':'OpenDyslexic','source':'https://github.com/antijingoist/opendyslexic',
 'commit':'1824da5c0e41dc3e13ffc7f3a636dcaf695d61b7','license':'SIL Open Font License 1.1','assets':sources},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'assets_downloaded':len(sources),'total_bytes':sum(v['bytes'] for v in sources.values())}))
