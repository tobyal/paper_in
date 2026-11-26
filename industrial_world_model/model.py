"""Portable, read-only world-model reader and dual-branch query engine.

No SAM, M0 database, historical experiment or renderer is imported by this module.
CLIP is loaded lazily only when a text query is encoded.
"""
import argparse
import json
import re
from pathlib import Path

import numpy as np


ALIASES = {
    '带黑色工件的夹具台': ['loaded_fixture'], '装配夹具台': ['assembly_fixture'],
    '分隔式料架': ['compartment_rack'], '多层料架': ['multi_tier_rack'],
    '立式移动冷风机': ['air_cooler'], '蓝色箱组': ['blue_bins'],
    '物料车': ['material_cart'], '工作台': ['workbench'],
    '料架': ['multi_tier_rack', 'compartment_rack'],
}
ENGLISH = {
    '带黑色工件的夹具台': 'fixture table with black workpiece',
    '装配夹具台': 'assembly fixture table', '分隔式料架': 'compartment rack',
    '多层料架': 'multi-tier rack', '立式移动冷风机': 'standing portable air cooler',
    '蓝色箱组': 'group of blue storage bins', '物料车': 'material cart',
    '工作台': 'workbench', '料架': 'storage rack',
    '蓝色物料箱转运车': 'transport cart with blue material bins',
    '具有灰色布帘的物料车': 'material cart with gray fabric curtains',
    '封闭式物料车': 'enclosed material cart',
}
RELATIONS = {'左侧': 'left_of', '右侧': 'right_of', '附近': 'near',
             '前方': 'in_front_of', '后方': 'behind', '上方': 'above', '下方': 'below'}


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def clean_text(text):
    return re.sub(r'^(找到|查找|寻找|find\s+)', '', text.strip(), flags=re.I).strip(' 。?？')


def parse_query(query):
    """Small explicit grammar. Relation direction is always subject -> anchor."""
    if isinstance(query, dict):
        parsed = dict(query)
        parsed.setdefault('type', 'combined' if 'relation' in parsed else 'semantic')
        if parsed['type'] not in ('semantic', 'spatial', 'combined', 'pair'):
            raise ValueError('Unsupported structured query type')
        if parsed['type'] in ('spatial', 'combined'):
            allowed = set(RELATIONS.values()) | {'same_category'}
            if parsed.get('relation') not in allowed:
                raise ValueError('Unsupported relation')
            if not parsed.get('object'):
                raise ValueError('A relation query requires an anchor object')
        elif parsed['type'] == 'pair':
            if not parsed.get('subject') or not parsed.get('object'):
                raise ValueError('A pair query requires two object selectors')
        elif not parsed.get('text'):
            raise ValueError('A semantic query requires text')
        return parsed
    text = clean_text(query)
    match = re.fullmatch(r'(.+?)(左侧|右侧|附近|前方|后方|上方|下方)(?:有哪些设备|有哪些对象|的(.+))', text)
    if match:
        anchor, relation, subject = match.groups()
        generic = not subject or subject in ('设备', '对象', '物体')
        return dict(type='spatial' if generic else 'combined', subject=None if generic else subject,
                    relation=RELATIONS[relation], object=anchor)
    if any(word in text for word in RELATIONS):
        raise ValueError('Unsupported spatial grammar; use structured subject/relation/object input')
    if not text:
        raise ValueError('Empty query')
    return dict(type='semantic', text=text)


class ClipEncoder:
    def __init__(self, checkpoint, architecture='ViT-B-16', device='cpu'):
        import open_clip
        self.device = device
        self.model = open_clip.create_model(architecture, pretrained=str(checkpoint), device=device)
        self.model.eval().requires_grad_(False)
        self.tokenizer = open_clip.get_tokenizer(architecture)

    def __call__(self, text):
        import torch
        with torch.inference_mode():
            result = self.model.encode_text(self.tokenizer([text]).to(self.device)).float()
            return torch.nn.functional.normalize(result, dim=-1)[0].cpu().numpy()


class QueryEngine:
    def __init__(self, nodes, visual, text, edges, config, encoder):
        self.nodes, self.visual, self.text = nodes, visual, text
        self.edges, self.config, self.encoder = edges, config, encoder
        self.by_id = {n['object_id']: n for n in nodes}

    def resolve(self, selector):
        """Return ranking including rejected candidates; never relax the threshold."""
        text = clean_text(selector)
        translated = ENGLISH.get(text, text)
        if translated == text and re.search('[\u4e00-\u9fff]', text):
            for key in sorted(ENGLISH, key=len, reverse=True):
                translated = translated.replace(key, ENGLISH[key])
            translated = translated.replace('具有', 'with ').replace('灰色布帘', 'gray fabric curtains').replace('封闭式', 'enclosed ').replace('的', ' ')
        if re.search('[\u4e00-\u9fff]', translated):
            raise ValueError('Chinese phrase outside the documented small dictionary; supply English text or structured selectors')
        exact = [n['object_id'] for n in self.nodes if text.casefold() in
                 (n['object_id'].casefold(), n['name_zh'].casefold(), n['name_en'].casefold())]
        categories = next((v for k, v in ALIASES.items() if k in text), None)
        if text in {n['category'] for n in self.nodes}:
            categories = [text]
        numbered = bool(re.search(r'\d+$', text)) or text.startswith('obj_')
        # Strip IDs/numbers from the embedding prompt; exact selector still governs eligibility.
        prompt_text = self.by_id[exact[0]]['name_en'] if exact else re.sub(r'\s*\d+$', '', translated)
        feature = self.encoder('A photo of ' + prompt_text + '.')
        v = self.visual @ feature
        t = self.text @ feature
        joint = self.config['visual_weight'] * v + self.config['text_weight'] * t
        rows = []
        for k, node in enumerate(self.nodes):
            reason = None
            if not node['available']: reason = 'Upstream instance/visual evidence unavailable'
            elif (exact or numbered) and node['object_id'] not in exact: reason = 'Exact name/ID selector mismatch'
            elif categories and node['category'] not in categories: reason = 'Explicit category mismatch'
            elif joint[k] < self.config['minimum_joint_similarity']: reason = 'Below fixed joint similarity threshold'
            rows.append(dict(object_id=node['object_id'], name=node['name_zh'], category=node['category'],
                             visual_score=float(v[k]), text_score=float(t[k]), joint_score=float(joint[k]),
                             eligible=reason is None, rejection_reason=reason))
        rows.sort(key=lambda r: r['joint_score'], reverse=True)
        return dict(selector=selector, encoded_text='A photo of ' + prompt_text + '.',
                    explicit_categories=categories, exact_name_or_id=bool(exact or numbered),
                    candidates=rows, matched_ids=[r['object_id'] for r in rows if r['eligible']])

    def query(self, query):
        parsed = parse_query(query)
        result = dict(query=query, parsed=parsed, threshold=self.config['minimum_joint_similarity'],
                      scores_are_probabilities=False, fallback_used=False, relation_matches=[])
        if parsed['type'] == 'semantic':
            result['subject_ranking'] = self.resolve(parsed['text'])
            ids = result['subject_ranking']['matched_ids']
        else:
            anchor = self.resolve(parsed['object'])
            result['anchor_ranking'] = anchor
            subjects = self.resolve(parsed['subject']) if parsed.get('subject') else None
            result['subject_ranking'] = subjects
            allowed = set(subjects['matched_ids'] if subjects else [n['object_id'] for n in self.nodes if n['available']])
            anchors = set(anchor['matched_ids'])
            edges = [e for e in self.edges if e['subject_id'] in allowed and e['object_id'] in anchors
                     and (parsed['type'] == 'pair' or e['relation'] == parsed['relation'])]
            result['relation_matches'] = edges
            matched = {e['subject_id'] for e in edges}
            ids = [i for i in (subjects['matched_ids'] if subjects else sorted(matched)) if i in matched]
        result['matched_count_before_limit'] = len(ids)
        result['matched_ids'] = ids[:self.config['maximum_results']]
        result['outcome'] = 'empty' if not ids else 'single' if len(ids) == 1 else 'multiple'
        result['reason'] = 'No object satisfies the fixed semantic/geometry conditions' if not ids else None
        return result


class WorldModel:
    def __init__(self, root, device='cpu'):
        self.root = Path(root).resolve()
        self.manifest = load_json(self.root / 'manifest.json')
        self.nodes = load_json(self.root / self.manifest['nodes'])
        self.edges = load_json(self.root / self.manifest['relations'])
        self.features = np.load(self.root / self.manifest['features'])
        self.device = device
        self._engine = None

    def get_object(self, object_id):
        return next(n for n in self.nodes if n['object_id'] == object_id)

    def gaussian_ids(self, object_id):
        return np.load(self.root / self.get_object(object_id)['gaussian_indices'])

    def relationships(self, subject_id, object_id=None):
        return [e for e in self.edges if e['subject_id'] == subject_id and
                (object_id is None or e['object_id'] == object_id)]

    def query(self, query):
        if self._engine is None:
            encoder = ClipEncoder(self.root / self.manifest['clip_checkpoint'], self.manifest['clip_arch'], self.device)
            self._engine = QueryEngine(self.nodes, self.features['visual'], self.features['text'],
                                       self.edges, self.manifest['query_config'], encoder)
        return self._engine.query(query)

    def render(self, object_ids, image_id=None, output=None, independent=False):
        """Optional native CUDA render, loading only this package's full scene."""
        from types import SimpleNamespace
        from m0.native_3dgs import GaussianModel
        from .render import Renderer
        from PIL import Image
        state = load_json(self.root / self.manifest['prior_snapshot'])
        native = GaussianModel(3)
        native.load_ply(str(self.root / self.manifest['scene_ply']))
        renderer = Renderer(SimpleNamespace(state=state), model=native)
        ids = np.unique(np.concatenate([self.gaussian_ids(i) for i in object_ids])) if object_ids else np.empty(0, np.int64)
        if image_id:
            im = next(c for c in load_json(self.root / self.manifest['cameras']) if c['image_id'] == image_id)
        elif object_ids:
            boxes = [self.get_object(i)['bbox'] for i in object_ids]
            lo = np.min([b['minimum'] for b in boxes], 0)
            hi = np.max([b['maximum'] for b in boxes], 0)
            im = renderer.virtual((lo + hi) / 2, hi - lo)
        else:
            raise ValueError('Provide a camera or a non-empty object list')
        pixels = renderer.rgb(im, ids, width=960) if independent else renderer.highlight(im, [(ids, [1, .3, .05])], width=960)
        if output: Image.fromarray(pixels).save(output)
        return pixels


def main():
    p = argparse.ArgumentParser()
    p.add_argument('model')
    p.add_argument('--query')
    p.add_argument('--structured', help='Path to a JSON query')
    p.add_argument('--device', default='cpu')
    p.add_argument('--output')
    a = p.parse_args()
    model = WorldModel(a.model, a.device)
    query = load_json(a.structured) if a.structured else a.query
    result = model.query(query) if query else dict(objects=len(model.nodes), relations=len(model.edges), manifest=model.manifest)
    value = json.dumps(result, ensure_ascii=False, indent=2)
    if a.output: Path(a.output).write_text(value, encoding='utf-8')
    else: print(value)


if __name__ == '__main__':
    main()
