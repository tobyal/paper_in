"""Explicit low-cardinality PCA-OBB boundary handling, opt-in for R1 only.

Normal boxes use the official function byte-for-byte. No points, labels or
features are dropped, merged, duplicated, jittered, scaled or padded.
"""
import numpy as np
import open3d as o3d

def degenerate_pca_box(points):
    p=np.asarray(points,dtype=np.float64)
    if p.ndim!=2 or p.shape[1]!=3 or not 1<=len(p)<=3 or not np.isfinite(p).all():
        raise ValueError('Boundary handler requires 1 to 3 finite original/retained points')
    mean=p.mean(0);x=p-mean
    rank=int(np.linalg.matrix_rank(x));R=np.eye(3)
    if rank:
        _,_,vt=np.linalg.svd(x,full_matrices=True)
        first=vt[0].copy()
        if first[np.abs(first).argmax()]<0:first=-first
        if rank==1:
            helper=np.eye(3)[np.abs(first).argmin()]
            second=helper-first*np.dot(first,helper);second/=np.linalg.norm(second)
        else:
            second=vt[1].copy()
            if second[np.abs(second).argmax()]<0:second=-second
        third=np.cross(first,second);third/=np.linalg.norm(third)
        R=np.column_stack([first,second,third])
    projected=x@R;lo=projected.min(0);hi=projected.max(0)
    extent=hi-lo;extent[rank:]=0.0
    center=mean+R@((lo+hi)*.5)
    assert np.allclose(R.T@R,np.eye(3),atol=1e-12) and np.linalg.det(R)>0
    assert np.all(np.abs((p-center)@R)<=extent*.5+1e-10)
    return (center,R,extent,mean),rank

def wrap_official_obb(official,records):
    def repaired(points,labels,obj_ids,remove_outlier=False):
        result={}
        for cid in obj_ids:
            try:
                result[cid]=official(points,labels,[cid],remove_outlier=remove_outlier)[cid]
            except RuntimeError as error:
                raw=np.asarray(points)[np.asarray(labels).reshape(-1)==cid]
                if not len(raw) or not np.isfinite(raw).all():raise
                pcd=o3d.geometry.PointCloud(o3d.utility.Vector3dVector(raw))
                kept=np.arange(len(raw))
                if remove_outlier:
                    _,kept=pcd.remove_statistical_outlier(nb_neighbors=20,std_ratio=2.0)
                    kept=np.asarray(kept,dtype=np.int64)
                retained=raw[kept]
                # An empty singleton SOR result has no box: retain that original
                # point only for its degenerate geometry, preserving the node.
                selected=retained if len(retained) else raw
                if not 1<=len(selected)<=3:raise
                box,rank=degenerate_pca_box(selected);result[cid]=box
                records.append({'cluster_id':int(cid),'original_count':len(raw),'post_outlier_count':len(retained),'used_original_after_empty_sor':not bool(len(retained)),'retained_local_indices':kept.tolist(),'box_points':selected.tolist(),'affine_rank':rank,'center':box[0].tolist(),'rotation':box[1].tolist(),'extent':box[2].tolist(),'mass_center':box[3].tolist(),'orientation_underdetermined':True,'original_error':str(error),'policy':'pca_on_existing_low_cardinality_points_without_padding_or_jitter'})
        return result
    return repaired
