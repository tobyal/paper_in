"""Retry uninformative local VLM answers without inventing relationships."""
import sys,json,base64,urllib.request,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from common import read,write
rows=[]
for folder in sorted((ROOT/'outputs/C/som').iterdir()):
    parsed=read(folder/'parsed_response.json')
    if len(parsed.get('observation',''))>=20:continue
    tags=read(folder/'tags.json');prompt='The image shows numbered industrial devices. Describe briefly what is actually visible at each yellow number, including its shape and color. Then say whether any TWO DIFFERENT numbered whole devices physically support or contain each other. Adjacent devices and overlapping image silhouettes do not establish contact. An empty relations list is expected if there is no visible evidence. Do not use left/right/near. Return JSON with observations [{tag: integer, visible_description: string}], relations [{subject_tag: integer, relation: string, object_tag: integer, evidence: string}], and observation: a nonempty overall explanation. Numbers to examine: '+str([t['tag'] for t in tags])
    payload=dict(model='qwen3.5:9b',prompt=prompt,images=[base64.b64encode((folder/'som.jpg').read_bytes()).decode()],format='json',stream=False,think=False,options=dict(temperature=0,num_ctx=8192,num_predict=1600),keep_alive='1m');write(folder/'grounding_retry_request.json',{k:v for k,v in payload.items() if k!='images'});start=time.time()
    request=urllib.request.Request('http://127.0.0.1:11434/api/generate',json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=600) as response:raw=json.load(response)
        write(folder/'grounding_retry_raw.json',raw);parsed=json.loads(raw['response']);write(folder/'grounding_retry_parsed.json',parsed);rows.append(dict(image_id=folder.name,seconds=time.time()-start,informative=bool(parsed.get('observations')) and len(parsed.get('observation',''))>=20,relations=parsed.get('relations',[])))
    except Exception as exc:rows.append(dict(image_id=folder.name,error=repr(exc),informative=False))
    print('SOM GROUNDING RETRY',rows[-1],flush=True)
write(ROOT/'outputs/C/grounding_review.json',dict(retries=rows,automatic_graph_additions=False,note='Original empty/incomplete answers preserved. Retry relations are hypotheses pending independent evidence review.'))
