"""Explicit language/category matching followed by stored graph filtering."""
import json,re
from pathlib import Path
import numpy as np

class WorldModel:
    def __init__(self,path):
        self.path=Path(path);self.manifest=json.loads((self.path/'manifest.json').read_text());self.categories=json.loads((self.path/'categories.json').read_text());self.graph=json.loads((self.path/'scene_graph.json').read_text());self.objects=self.graph['nodes'];self.byid={o['object_id']:o for o in self.objects};self.features=np.load(self.path/'category_features.npz');self.encoder=None
    def category(self,text):
        cleaned=text.casefold().strip();matches=[]
        for c in self.categories:
            for alias in [c['name_zh'],c['name_en']]+c['aliases']:
                if alias.casefold() in cleaned:matches.append((len(alias),c))
        if matches:
            c=max(matches,key=lambda pair:pair[0])[1];return dict(category_id=c['category_id'],method='known_category_alias',query=text)
        import open_clip,torch
        if self.encoder is None:
            model,_,_=open_clip.create_model_and_transforms('ViT-B-16',pretrained=str(self.path/'models/open_clip_pytorch_model.bin'),device='cpu');self.encoder=model.eval();self.tokenizer=open_clip.get_tokenizer('ViT-B-16')
        with torch.inference_mode():q=self.encoder.encode_text(self.tokenizer([text])).float().numpy()[0]
        q/=max(np.linalg.norm(q),1e-9);scores=.8*(self.features['text']@q)+.2*(self.features['visual']@q);order=np.argsort(-scores);accepted=bool(scores[order[0]]>=.20 and scores[order[0]]-scores[order[1]]>=.015)
        return dict(category_id=self.categories[int(order[0])]['category_id'] if accepted else None,method='CLIP_text_visual',scores=scores.tolist(),query=text,abstained=not accepted)
    def anchors(self,text):
        exact=[]
        for o in self.objects:
            if any(name.casefold().replace(' ','') in text.casefold().replace(' ','') for name in [o['name_zh'],o['name_en'],o['display_id']]):exact.append(o['object_id'])
        if exact:return exact
        match=self.category(text);return [o['object_id'] for o in self.objects if o['category_id']==match['category_id']]
    def query(self,text):
        relation=None;anchor_text=None;target_text=text.strip()
        chinese=[('最近','nearest_to'),('左侧','left_of'),('右侧','right_of'),('前方','in_front_of'),('后方','behind'),('附近','near')]
        for word,rel in chinese:
            match=re.match(r'^(?:找到|查找|位于|距离|靠近)?(.+?)'+word+r'的(.+)$',text.strip())
            if match:anchor_text,target_text=match.groups();relation=rel;break
        if relation is None:
            match=re.match(r'^(?:find\s+)?(.+?)\s+(nearest to|left of|right of|in front of|behind|near)\s+(.+)$',text.strip(),re.I)
            if match:target_text,rel,anchor_text=match.groups();relation={'nearest to':'nearest_to','left of':'left_of','right of':'right_of','in front of':'in_front_of','behind':'behind','near':'near'}[rel.casefold()]
        match=self.category(target_text);all_candidates=[o['object_id'] for o in self.objects if o['category_id']==match['category_id']];available=[oid for oid in all_candidates if self.byid[oid].get('segmentation_available')];anchors=self.anchors(anchor_text) if anchor_text else [];evidence=[]
        if relation:
            evidence=[e for e in self.graph['edges'] if e['subject'] in available and e['object'] in anchors and e['relation']==relation];matched=sorted({e['subject'] for e in evidence})
        else:matched=available
        return dict(query=text,target_text=target_text,category_match=match,relation=relation,anchor_text=anchor_text,anchor_object_ids=anchors,known_category_instances=all_candidates,available_category_candidates=available,unsegmented_category_instances=[oid for oid in all_candidates if oid not in available],matched_object_ids=matched,relation_evidence=evidence,same_category_candidates_before=len(available),matches_after=len(matched),segmentation_rerun=False)
    def gaussian_ids(self,result):
        arrays=[np.load(self.path/self.byid[oid]['gaussian_indices']) for oid in result['matched_object_ids']]
        return np.unique(np.concatenate(arrays)) if arrays else np.zeros(0,np.int64)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--model',type=Path,required=True);p.add_argument('--text',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();wm=WorldModel(a.model);result=wm.query(a.text);a.output.mkdir(parents=True,exist_ok=True);(a.output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');np.save(a.output/'gaussian_indices.npy',wm.gaussian_ids(result));print(json.dumps(result,ensure_ascii=False,indent=2))
