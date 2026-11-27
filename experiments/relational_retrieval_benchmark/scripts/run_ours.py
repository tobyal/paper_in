from common import *
import importlib.util,traceback
check_frozen();start=time.perf_counter()
spec=importlib.util.spec_from_file_location('frozen_v2_query',V2/'world_model/query.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);wm=module.WorldModel(V2/'world_model')
from industrial_world_model.render import Renderer
from m0.native_3dgs import subset_model
class Ctx:project=PROJECT;state=read(ROOT/'inputs/m0_state.json')
renderer=Renderer(Ctx());sync();load_seconds=time.perf_counter()-start;views=read(ROOT/'configs/evaluation_views.json')['cameras'];records=[]
for q in read(ROOT/'configs/benchmark_queries.json'):
    dest=ROOT/'outputs/ours'/q['query_id'];dest.mkdir(parents=True,exist_ok=True)
    if (dest/'result.json').exists() and read(dest/'result.json')['status']=='completed':records.append(read(dest/'result.json'));continue
    try:
        def query():
            raw=wm.query(q['query_zh']);return raw,wm.gaussian_ids(raw)
        def project(result):return [renderer.contribution(views[iid],result[1]) for iid in q['evaluation_camera_ids']]
        (raw,ids),responses,timing=timed_pipeline(query,project)
        np.save(dest/'gaussian_indices.npy',ids);write(dest/'raw_query.json',raw)
        if len(ids):subset_model(renderer.model,ids).save_ply(str(dest/'selected_gaussians.ply'))
        record=dict(query=q,status='completed',query_status=raw['status'],empty_result=not len(ids),selected_gaussians=len(ids),matched_object_ids=raw['matched_object_ids'],renderable_object_ids=raw['renderable_object_ids'],unavailable_object_ids=raw['unavailable_object_ids'],fine_output_status=('unavailable' if not raw['renderable_object_ids'] else 'partial_unavailable') if raw['unavailable_object_ids'] else 'available',timing=timing,views=[export_view('ours',q,views[iid],soft,soft>.5) for iid,soft in zip(q['evaluation_camera_ids'],responses)])
    except Exception as e:traceback.print_exc();record=dict(query=q,status='failed',error=repr(e),traceback=traceback.format_exc())
    write(dest/'result.json',record);records.append(record);write(ROOT/'outputs/ours/summary.json',dict(method='Ours',model_load_seconds=load_seconds,queries=records,completed=sum(r['status']=='completed' for r in records),total=25));print(q['query_id'],record['status'],record.get('selected_gaussians'),flush=True)

