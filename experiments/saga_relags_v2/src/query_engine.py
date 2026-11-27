"""Equipment identity/geometry query first; fine-instance availability second."""
import json,re
from pathlib import Path
import numpy as np

def clean(text):return re.sub(r'\s+',' ',text.strip().casefold()).rstrip('。.?？')
def compact(text):return re.sub(r'\s+','',clean(text))

class WorldModel:
    def __init__(self,path,features_path=None):
        self.path=Path(path);self.categories=json.loads((self.path/'categories.json').read_text());self.graph=json.loads((self.path/'scene_graph.json').read_text())
        self.objects=self.graph['nodes'];self.byid={o['object_id']:o for o in self.objects};self.features=np.load(features_path or self.path/'category_features.npz')
        feature_ids=self.features['category_ids'].tolist();assert len(feature_ids)==len(set(feature_ids))
        self.feature_row={cid:i for i,cid in enumerate(feature_ids)};assert set(feature_ids)=={c['category_id'] for c in self.categories}
        self.encoder=None;self.query_cache={}
        self.outside_descriptions=['a person or a human worker','a forklift truck','an industrial robot arm','a motor car or truck','a mountain landscape','a living animal','a tree or flower','a ceiling lamp','a computer or smartphone','a factory wall or floor']
    def _encode(self,texts):
        import open_clip,torch
        if self.encoder is None:
            model,_,_=open_clip.create_model_and_transforms('ViT-B-16',pretrained=str(self.path/'models/open_clip_pytorch_model.bin'),device='cpu');self.encoder=model.eval();self.tokenizer=open_clip.get_tokenizer('ViT-B-16')
        with torch.inference_mode():q=self.encoder.encode_text(self.tokenizer(texts)).float().numpy()
        return q/np.maximum(np.linalg.norm(q,axis=1,keepdims=True),1e-9)
    def category(self,text):
        key=clean(text)
        if key in self.query_cache:return dict(self.query_cache[key])
        matches=[]
        for c in self.categories:
            if any(compact(alias)==compact(key) for alias in [c['name_zh'],c['name_en']]+c['aliases']):matches.append(c['category_id'])
        if len(matches)==1:return dict(category_id=matches[0],method='exact_known_alias',query=text,abstained=False)
        if matches:return dict(category_id=None,method='ambiguous_alias',query=text,abstained=True)
        # A relation, object number or unsupported command must never leak into semantic category fallback.
        if re.search(r'\d|[左右前后上下旁间内外]侧|上面|下面|之间|包含|支撑|连接|\b(?:under|above|between|inside|supports?|connected|left|right|nearest|behind|near)\b',key):
            return dict(category_id=None,method='not_a_category_expression',query=text,abstained=True)
        if re.search(r'[\u4e00-\u9fff]',key):return dict(category_id=None,method='unknown_chinese_expression',query=text,abstained=True)
        q=self._encode([text])[0];scores=.8*(self.features['text']@q)+.2*(self.features['visual']@q);order=np.argsort(-scores)
        if not hasattr(self,'outside_vectors'):self.outside_vectors=self._encode(self.outside_descriptions)
        outside=self.outside_vectors@q;ood=int(outside.argmax());accepted=bool(scores[order[0]]>=.20 and scores[order[0]]-scores[order[1]]>=.015 and scores[order[0]]>outside[ood])
        result=dict(category_id=self.features['category_ids'][order[0]].item() if accepted else None,method='CLIP_text_visual_with_outside_catalog_competitors',query=text,scores=scores.tolist(),category_order=self.features['category_ids'].tolist(),top_gap=float(scores[order[0]]-scores[order[1]]),outside_best=self.outside_descriptions[ood],outside_similarity=float(outside[ood]),abstained=not accepted)
        self.query_cache[key]=result;return dict(result)
    def identify(self,text):
        k=compact(text);exact=[o['object_id'] for o in self.objects if any(compact(v)==k for v in [o['object_id'],o['name_zh'],o['name_en'],o['display_id']])]
        if exact:return exact,dict(method='exact_equipment_identity',status='ok')
        if re.search(r'\d',k):return [],dict(method='equipment_identity',status='unknown_equipment')
        c=self.category(text);ids=[o['object_id'] for o in self.objects if o['category_id']==c['category_id']]
        return ids,dict(method='category',status='ok' if ids else 'unknown_category',category_match=c)
    def parse(self,text):
        t=re.sub(r'^(?:请)?(?:找到|查找|查询|显示)\s*','',text.strip());t=re.sub(r'^(?:find|show)\s+','',t,flags=re.I);t=t.rstrip('。.?？')
        if re.search(r'之间|上[方面]|下[方面]|内部|里面|支撑|包含|连接|属于|\b(?:above|under|below|between|inside|supports?|connected|contains?|on top of)\b',t,re.I):
            return dict(status='unsupported_relation_expression',relation=None,anchor_text=None,target_text=None)
        chinese=[('最近','nearest_to'),('左侧|左边','left_of'),('右侧|右边','right_of'),('前方|前面','in_front_of'),('后方|后面','behind'),('附近|旁边','near')]
        for word,relation in chinese:
            match=re.fullmatch(r'(?:位于|距离|靠近)?(.+?)(?:'+word+r')的(.+)',t)
            if match:return dict(status='ok',relation=relation,anchor_text=match[1],target_text=match[2])
        m=re.fullmatch(r'(.+?)\s+(nearest to|left of|right of|in front of|behind|near)\s+(.+)',t,re.I)
        if m:return dict(status='ok',relation={'nearest to':'nearest_to','left of':'left_of','right of':'right_of','in front of':'in_front_of','behind':'behind','near':'near'}[m[2].casefold()],anchor_text=m[3],target_text=m[1])
        if re.search(r'最近|左[侧边]|右[侧边]|前[方面]|后[方面]|附近|旁边|之间|上面|下面|内部|里面|支撑|包含|连接|属于|的.*(?:物料车|料架|工作台)|\b(?:nearest|left|right|behind|near|above|under|below|between|inside|supports?|connected|contains?)\b',t,re.I):
            return dict(status='unsupported_relation_expression',relation=None,anchor_text=None,target_text=None)
        return dict(status='ok',relation=None,anchor_text=None,target_text=t)
    def query(self,text):
        parsed=self.parse(text);result=dict(query=text,**parsed,matched_object_ids=[],objects=[],relation_evidence=[],renderable_object_ids=[],unavailable_object_ids=[],segmentation_rerun=False,geometry_scope='all M0 equipment nodes',reference_semantics='union over explicitly listed matching anchors')
        if parsed['status']!='ok':return result
        candidates,match=self.identify(parsed['target_text']);result.update(target_match=match,known_category_instances=candidates,same_category_candidates_before=len(candidates))
        if not candidates:result['status']=match['status'];return result
        anchors=[];evidence=[]
        if parsed['relation']:
            anchors,am=self.identify(parsed['anchor_text']);result.update(anchor_match=am,anchor_object_ids=anchors)
            if not anchors:result['status']='reference_not_found';return result
            evidence=[e for e in self.graph['edges'] if e['subject'] in candidates and e['object'] in anchors and e['relation']==parsed['relation']]
            matched=sorted({e['subject'] for e in evidence})
        else:matched=candidates
        result.update(matched_object_ids=matched,matches_after=len(matched),relation_evidence=evidence,status='ok' if matched else 'no_relation_match')
        for oid in matched:
            o=self.byid[oid];available=bool(o.get('segmentation_available') and o.get('gaussian_indices'))
            item={k:o.get(k) for k in ['object_id','category_id','name_zh','name_en','bbox','reconstruction_status','extraction_status','quality_record']}
            item.update(fine_instance_available=available,gaussian_indices=o.get('gaussian_indices') if available else None,location_source='M0 r29',representation='SAGA_instance' if available else 'M0_location_only')
            result['objects'].append(item);result['renderable_object_ids' if available else 'unavailable_object_ids'].append(oid)
        return result
    def gaussian_ids(self,result):
        arrays=[np.load(self.path/self.byid[oid]['gaussian_indices']) for oid in result['renderable_object_ids']]
        return np.unique(np.concatenate(arrays)) if arrays else np.zeros(0,np.int64)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--model',type=Path,required=True);p.add_argument('--text',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    wm=WorldModel(a.model);result=wm.query(a.text);a.output.mkdir(parents=True,exist_ok=True);(a.output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');np.save(a.output/'gaussian_indices.npy',wm.gaussian_ids(result));print(json.dumps(result,ensure_ascii=False,indent=2))
