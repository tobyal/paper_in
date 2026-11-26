"""Validate actual saved arrays/identity mappings without changing their results."""
import argparse
import numpy as np
from PIL import Image
from .common import Context,read,write
from .graph import INVERSE


def run(ctx):
    from plyfile import PlyData
    checks=[];all_ids=[];observations=ctx.segmentation();labels=np.load(ctx.path('M2.6','gaussian_to_object.npy'));native=PlyData.read(ctx.source('ply'))['vertex'].data
    for k,instance in enumerate(ctx.instances(),1):
        oid=instance['object_id'];a=np.load(ctx.path('M2.3',oid,'scores.npz'));ids=ctx.ids(oid,True)
        assert np.array_equal(a['gaussian_ids'],ctx.ids(oid))
        assert np.array_equal(a['effective_observations'],a['positive_observations']+a['negative_observations'])
        unknown=a['effective_observations']==0
        assert np.isnan(a['score'][unknown]).all() and np.isfinite(a['score'][~unknown]).all()
        assert np.allclose(a['score'][~unknown],a['positive_weight'][~unknown]/a['total_weight'][~unknown])
        local=np.searchsorted(a['gaussian_ids'],ids);cfg=ctx.c['association']
        assert (a['score'][local]>=cfg['score_threshold']).all()
        assert (a['effective_observations'][local]>=cfg['minimum_observations']).all()
        assert (a['positive_observations'][local]>=cfg['minimum_positive_observations']).all()
        assert np.array_equal(np.load(ctx.path('M2.4',oid,'before_local_denoising_ids.npy')),np.load(ctx.path('M2.4',oid,'after_local_denoising_ids.npy')))
        assert len(ids)==instance['gaussian_count']
        exported=PlyData.read(ctx.out/instance['ply'])['vertex'].data
        assert exported.dtype==native.dtype and np.array_equal(exported,native[ids]),'Instance PLY must preserve every source native attribute'
        if instance['valid']:
            assert (labels[ids]==k).all();all_ids.extend(ids.tolist());points=ctx.industrial[ids]
            assert np.allclose(points.min(0),instance['bbox']['minimum']) and np.allclose(points.max(0),instance['bbox']['maximum'])
        for r in observations[oid]:
            if not r.get('mask_path'):continue
            im=ctx.image_map[r['image_id']]
            assert Image.open(ctx.out/r['mask_path']).size==(im['width'],im['height'])
            assert im['split']=='train'
        checks.append(dict(object_id=oid,available=instance['valid'],gaussians=len(ids),checks_passed=True))
    assert len(all_ids)==len(set(all_ids))==int((labels>0).sum())
    ambiguous=np.load(ctx.path('M2.4','ambiguous_gaussian_ids.npy'));assert not np.isin(ambiguous,all_ids).any()
    semantic=PlyData.read(ctx.path('M2.6','semantic_native_3dgs.ply'))['vertex'].data
    assert semantic.dtype==native.dtype and len(semantic)==len(native)
    background=labels<=0
    for field in native.dtype.names:
        unchanged=background if field.startswith(('f_dc_','f_rest_')) else slice(None)
        assert np.array_equal(semantic[field][unchanged],native[field][unchanged]),field
    features=np.load(ctx.path('M3.4','features.npz'))
    for key in ['visual','text']:
        norms=np.linalg.norm(features[key],axis=1);assert np.isfinite(norms).all();assert ((norms<1e-6)|np.isclose(norms,1,atol=1e-5)).all()
    edges=read(ctx.path('M4','relations.json'));keys={(e['subject_id'],e['relation'],e['object_id']) for e in edges}
    assert len(keys)==len(edges)
    for a,r,b in keys:assert a!=b and (b,INVERSE[r],a) in keys
    from .model import WorldModel
    world=WorldModel(ctx.path('package'))
    for n in world.nodes:
        assert np.array_equal(world.gaussian_ids(n['object_id']),ctx.ids(n['object_id'],True))
        for view in n['views']:
            assert (world.root/view['mask']).is_file() and (world.root/view['image']).is_file()
    result=dict(passed=True,objects=checks,unique_labeled_gaussians=len(all_ids),unknown_observations_preserved=True,
                ambiguous_gaussians_unassigned=True,all_saved_masks_original_resolution=True,all_semantic_inputs_training_split=True,
                node_geometry_computed_from_final_ids=True,inverse_and_symmetric_edges_checked=len(edges),feature_norms_valid=True,
                portable_object_and_evidence_paths_valid=True,instance_ply_all_native_attributes_preserved=True,semantic_map_geometry_and_background_appearance_unchanged=True)
    write(ctx.out/'validation.json',result);return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',default='configs/industrial_world_model.json');a=p.parse_args()
    result=run(Context(a.config));print({k:v for k,v in result.items() if k!='objects'})
