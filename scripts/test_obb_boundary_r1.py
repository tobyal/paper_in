"""Meaningful boundary regressions: exact valid boxes and deterministic degenerate boxes."""
import json,pathlib,sys
import numpy as np
import open3d as o3d
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'ReLaGS'))
from scene_graph.network_utils import get_oriented_bounding_boxes as original
from obb_boundary_r1 import wrap_official_obb,degenerate_pca_box
cases={'singleton':np.array([[3.,2.,1.]]),'segment':np.array([[0.,0.,0.],[2.,1.,0.]]),'triangle':np.array([[0.,0.,0.],[2.,0.,0.],[.5,1.,0.]]),'duplicate':np.array([[1.,2.,3.],[1.,2.,3.]])}
results=[]
for name,p in cases.items():
    first,rank=degenerate_pca_box(p);second,_=degenerate_pca_box(p[::-1])
    assert all(np.allclose(x,y,atol=1e-12) for x,y in zip(first,second)),name
    assert np.count_nonzero(first[2])==rank
    results.append({'case':name,'rank':rank,'extent':first[2].tolist(),'pass':True})
rng=np.random.default_rng(42);p=rng.normal(size=(120,3));labels=np.zeros(len(p),dtype=int);records=[]
a=original(p,labels,[0],True)[0];b=wrap_official_obb(original,records)(p,labels,[0],True)[0]
assert all(np.array_equal(x,y) for x,y in zip(a,b)) and not records
records=[];p=cases['singleton'];b=wrap_official_obb(original,records)(p,np.array([7]),[7],True)
assert list(b)==[7] and records[0]['post_outlier_count']==0 and np.array_equal(b[7][0],p[0])
results.append({'case':'normal_3d_cloud_unchanged_bitwise_and_original_id_preserved','pass':True})
out=ROOT/'outputs/relags_obb_repair_r1/00_investigation/metrics/obb_boundary_tests.json'
out.write_text(json.dumps({'status':'passed','cases':results},indent=2));print(out)
