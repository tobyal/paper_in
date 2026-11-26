"""Small behavioral tests for semantics that can silently corrupt a world model."""
import unittest
import numpy as np
from .graph import pair_relations, INVERSE
from .model import QueryEngine, parse_query


class ContractTests(unittest.TestCase):
    def test_actual_extractor_rejects_ambiguous_and_single_view_claims(self):
        import tempfile,contextlib,io
        from pathlib import Path
        from types import SimpleNamespace
        from plyfile import PlyData,PlyElement
        from .association import extract
        from .common import STAGES,read
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def path(stage,*parts):
                base=root/STAGES[stage];base.mkdir(parents=True,exist_ok=True);return base.joinpath(*parts)
            vertex=np.zeros(5,dtype=[('x','f4'),('y','f4'),('z','f4'),('opacity','f4')]);vertex['x']=np.arange(5)
            PlyData([PlyElement.describe(vertex,'vertex')],text=False).write(str(root/'input.ply'))
            objects=[dict(object_id='a',name_en='A',candidate_count=4),dict(object_id='b',name_en='B',candidate_count=3)]
            for oid,ids,scores,observed in [('a',[0,1,2,3],[1,1,1,np.nan],[3,8,1,0]),('b',[0,1,4],[1,1,1],[3,2,2])]:
                folder=path('M2.3',oid);folder.mkdir();np.savez_compressed(folder/'scores.npz',gaussian_ids=np.array(ids),score=np.array(scores),effective_observations=np.array(observed,np.uint16),positive_observations=np.array(observed,np.uint16))
            cfg=dict(score_threshold=.6,minimum_observations=2,minimum_positive_observations=2,conflict_margin=.08,minimum_instance_gaussians=1)
            ctx=SimpleNamespace(out=root,path=path,source=lambda key:root/'input.ply',objects=objects,xyz=np.zeros((5,3)),industrial=np.column_stack([np.arange(5),np.zeros((5,2))]),c={'association':cfg})
            with contextlib.redirect_stdout(io.StringIO()):result=extract(ctx)
            self.assertEqual(np.load(path('M2.4','a','gaussian_ids.npy')).tolist(),[1])
            self.assertEqual(np.load(path('M2.4','b','gaussian_ids.npy')).tolist(),[4])
            self.assertEqual(np.load(path('M2.4','ambiguous_gaussian_ids.npy')).tolist(),[0])
            self.assertEqual(result['overlap_conflicts'],2)
            self.assertEqual(result['unresolved_conflicts'],1)

    def node(self, oid, x, category='material_cart'):
        return dict(object_id=oid, name_zh='物料车 '+oid[-2:], name_en='Material cart '+oid[-2:],
                    category=category, available=True, center=[x,0,0],
                    bbox={'minimum':[x-.1,-.1,-.1], 'maximum':[x+.1,.1,.1]})

    def test_extent_relations_and_inverse(self):
        a,b=self.node('obj_01',0),self.node('obj_02',.4)
        cfg={'axis_separation':.04,'near_distance':.35}
        ab,evidence=pair_relations(a,b,cfg);ba,_=pair_relations(b,a,cfg)
        self.assertAlmostEqual(evidence['aabb_minimum_distance'],.2)
        self.assertEqual({INVERSE[r] for r,_,_ in ab},{r for r,_,_ in ba})
        self.assertIn('near',{r for r,_,_ in ab})
        b=self.node('obj_02',.05)
        rels,_=pair_relations(a,b,cfg)
        self.assertEqual({r for r,_,_ in rels},{'near','same_category'})

    def engine(self):
        nodes=[self.node('obj_01',0),self.node('obj_02',1),self.node('obj_03',2,'multi_tier_rack')]
        edges=[dict(subject_id='obj_01',relation='left_of',object_id='obj_03')]
        return QueryEngine(nodes,np.array([[1.,0],[1.,0],[1.,0]]),np.array([[1.,0],[1.,0],[1.,0]]),edges,
                           dict(visual_weight=.6,text_weight=.4,minimum_joint_similarity=.24,maximum_results=12),lambda text:np.array([1.,0.]))

    def test_no_fallback_for_missing_numbered_name(self):
        self.assertEqual(self.engine().query('找到物料车 99')['outcome'],'empty')

    def test_unavailable_exclusion(self):
        engine=self.engine();engine.nodes[0]['available']=False
        result=engine.query('物料车')
        self.assertEqual(result['matched_ids'],['obj_02'])

    def test_direction_and_category_filter(self):
        parsed=parse_query('找到料架左侧的物料车')
        self.assertEqual(parsed,dict(type='combined',subject='物料车',relation='left_of',object='料架'))
        self.assertEqual(self.engine().query('找到料架左侧的物料车')['matched_ids'],['obj_01'])
        self.assertEqual(self.engine().query('找到物料车左侧的料架')['matched_ids'],[])

    def test_threshold_is_not_lowered(self):
        engine=self.engine();engine.encoder=lambda text:np.array([0.,1.])
        result=engine.query('物料车')
        self.assertEqual(result['outcome'],'empty');self.assertFalse(result['fallback_used'])
        self.assertEqual(len(result['subject_ranking']['candidates']),3)

    def test_invalid_structured_relation(self):
        with self.assertRaises(ValueError):parse_query(dict(subject='物料车',relation='manufactures',object='料架'))


if __name__=='__main__':unittest.main()
