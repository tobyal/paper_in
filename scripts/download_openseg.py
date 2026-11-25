#!/usr/bin/env python3
import json,pathlib,subprocess,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
d=json.loads((ROOT/'references/openseg_objects.json').read_text())
prefix='detection/projects/openseg/colab/exported_model/'
records=[]
for x in d['items']:
    name=x['name']
    if name.endswith('/'):continue
    p=ROOT/'models/openseg'/name.removeprefix(prefix);p.parent.mkdir(parents=True,exist_ok=True)
    url='https://storage.googleapis.com/cloud-tpu-checkpoints/'+name
    if not p.exists() or p.stat().st_size!=int(x['size']):
        subprocess.run(['curl','-fL','--retry','5','--retry-delay','3','--proxy','http://127.0.0.1:17891','-o',str(p),url],check=True)
    assert p.stat().st_size==int(x['size'])
    h=hashlib.sha256(p.read_bytes()).hexdigest();records.append({'url':url,'path':str(p),'bytes':p.stat().st_size,'sha256':h,'gcs_generation':x.get('generation'),'gcs_md5':x.get('md5Hash')})
(ROOT/'models/openseg/download_manifest.json').write_text(json.dumps(records,indent=2))
print(json.dumps(records,indent=2))
