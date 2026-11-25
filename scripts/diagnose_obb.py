#!/usr/bin/env python3
"""Audit every original OBB independently; failures are retained, never repaired."""
import json, pathlib, sys, os, traceback
import numpy as np
import torch
import open3d as o3d
from plyfile import PlyData, PlyElement
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'ReLaGS'));os.chdir(ROOT/'ReLaGS')
from scene_graph.network_utils import get_oriented_bounding_boxes
base=ROOT/'outputs/relags_baseline/08_scene_graph'
out=base/'diagnostics/obb';out.mkdir(parents=True,exist_ok=True)
ply=ROOT/'outputs/relags_baseline/03_gaussian_pruning/data/model/point_cloud/iteration_0/point_cloud.ply'
v=PlyData.read(ply)['vertex'].data;xyz=np.stack([v[k] for k in ['x','y','z']],axis=1)
nag=torch.load(ROOT/'outputs/relags_baseline/06_semantic_aggregation/data/model/sai_nag_openseg.pt',map_location='cpu')
reports=[]
for level in [2,3]:
    xyz=xyz-xyz.mean(axis=0,keepdims=True)
    labels=nag['nag'][level].numpy();ids,counts=np.unique(labels,return_counts=True)
    failed=[];valid_ids=[];centers=[];rotations=[];extents=[]
    for cid,count in zip(ids,counts):
        try:
            result=get_oriented_bounding_boxes(xyz,labels,[cid],remove_outlier=True)[cid]
            valid_ids.append(int(cid));centers.append(result[0]);rotations.append(result[1]);extents.append(result[2])
        except Exception as error:
            member=np.flatnonzero(labels==cid);pts=xyz[member]
            pc=o3d.geometry.PointCloud();pc.points=o3d.utility.Vector3dVector(pts)
            _,kept=pc.remove_statistical_outlier(nb_neighbors=20,std_ratio=2.0)
            folder=out/f'level_{level}_cluster_{cid}';folder.mkdir(exist_ok=True)
            np.savez_compressed(folder/'raw_points_and_indices.npz',original_gaussian_indices=member,points_centered=pts,official_outlier_kept_local_indices=np.asarray(kept,dtype=np.int64))
            vertices=np.empty(len(pts),dtype=[('x','f4'),('y','f4'),('z','f4')])
            for j,k in enumerate(['x','y','z']):vertices[k]=pts[:,j]
            PlyData([PlyElement.describe(vertices,'vertex')]).write(folder/'failed_input_points.ply')
            failure={'cluster_id':int(cid),'original_points':int(count),'post_outlier_points':len(kept),'error':str(error),'artifacts':str(folder.relative_to(ROOT))}
            (folder/'failure.json').write_text(json.dumps(failure,indent=2));failed.append(failure)
    np.savez_compressed(out/f'level_{level}_valid_obbs.npz',cluster_ids=np.asarray(valid_ids),centers=np.asarray(centers),rotations=np.asarray(rotations),extents=np.asarray(extents))
    report={'level':level,'total_clusters':len(ids),'valid_obbs':len(valid_ids),'failed_obbs':len(failed),'failures':failed}
    reports.append(report);print(json.dumps({k:v for k,v in report.items() if k!='failures'}),flush=True)
(base/'metrics/obb_failure_audit.json').write_text(json.dumps({'status':'diagnosed','no_geometry_fallback_or_node_filter_applied':True,'levels':reports},indent=2))
