"""Official LangSplat inference without the evaluation script's required GT files."""
from common import *
import torch,cv2,argparse,ast,traceback,importlib.util
check_frozen();load_start=time.perf_counter();assets=read(ROOT/'inputs/assets.json')['paths'];source=Path(assets['langsplat_source']);sys.path.insert(0,str(source));local_clip_weights()
from scene.gaussian_model import GaussianModel
from gaussian_renderer import render
from arguments import PipelineParams
from autoencoder.model import Autoencoder
spec=importlib.util.spec_from_file_location('official_openclip_encoder',source/'eval/openclip_encoder.py');clip_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(clip_module);OpenCLIPNetwork=clip_module.OpenCLIPNetwork
models=[];opt=argparse.Namespace(include_feature=True)
for path in assets['langsplat_models']:
    params,iteration=torch.load(path,map_location='cuda');g=GaussianModel(3);g.restore(params,opt,mode='test');models.append(g)
ae=Autoencoder([256,128,64,32,3],[16,32,64,128,256,256,512]).cuda();ae.load_state_dict(torch.load(assets['autoencoder'],map_location='cuda'));ae.eval();vlm=OpenCLIPNetwork('cuda');pipe=PipelineParams(argparse.ArgumentParser());bg=torch.zeros(3,device='cuda');sync();load_seconds=time.perf_counter()-load_start

def exact_majority(mask):
    # Integral-image implementation of the official smooth(), including its
    # h-1/w-1 exclusive boundary and tie-to-zero behavior. Verified below.
    h,w=mask.shape;integral=np.pad(mask.astype(np.int64),((1,0),(1,0))).cumsum(0).cumsum(1)
    y=np.arange(h);x=np.arange(w);loy=np.maximum(0,y-3);hiy=np.minimum(y+4,h-1);lox=np.maximum(0,x-3);hix=np.minimum(x+4,w-1)
    n=integral[hiy[:,None],hix]-integral[loy[:,None],hix]-integral[hiy[:,None],lox]+integral[loy[:,None],lox];area=(hiy-loy)[:,None]*(hix-lox)
    return (2*n>area).astype(np.uint8)
tree=ast.parse((source/'eval/utils.py').read_text());function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='smooth');scope={'np':np};exec(compile(ast.Module(body=[function],type_ignores=[]),'official_smooth','exec'),scope)
rng=np.random.default_rng(42)
for shape in [(5,7),(30,49),(79,91)]:
    for _ in range(3):
        mask=rng.integers(0,2,shape,dtype=np.uint8);assert np.array_equal(exact_majority(mask),scope['smooth'](mask))
write(ROOT/'outputs/langsplat/postprocessing_validation.json',dict(official_file=str(source/'eval/utils.py'),sha256=sha(source/'eval/utils.py'),bitwise_equal_cases=9,algorithm='unchanged majority vote; vectorized integer sums',threshold=.4))
views=read(ROOT/'configs/evaluation_views.json')['cameras'];native={k:camera_native(c) for k,c in views.items()};records=[]
for q in read(ROOT/'configs/benchmark_queries.json'):
    dest=ROOT/'outputs/langsplat'/q['query_id'];dest.mkdir(parents=True,exist_ok=True)
    if (dest/'result.json').exists() and read(dest/'result.json')['status']=='completed':records.append(read(dest/'result.json'));continue
    try:
        def execute():
            sync();start=time.perf_counter();vlm.set_positives([q['query_en']]);sync();query_time=time.perf_counter()-start;render_time=0;output=[]
            for iid in q['evaluation_camera_ids']:
                sync();t=time.perf_counter()
                with torch.no_grad():latent=torch.stack([render(native[iid],g,pipe,bg,opt)['language_feature_image'].permute(1,2,0) for g in models])
                sync();render_time+=time.perf_counter()-t;t=time.perf_counter()
                with torch.no_grad():
                    shape=latent.shape;decoded=ae.decode(latent.reshape(-1,3)).reshape(*shape[:3],512);raw=vlm.get_max_across(decoded)[:,0].cpu().numpy();del decoded
                smoothed=np.stack([.5*(cv2.filter2D(r,-1,np.ones((30,30))/900)+r) for r in raw]);normalized=smoothed-smoothed.min(axis=(1,2),keepdims=True);normalized/=normalized.max(axis=(1,2),keepdims=True)+1e-9;normalized=np.clip(normalized*2-1,0,1);masks=np.stack([exact_majority((r>.4).astype(np.uint8)) for r in normalized]);chosen=int(smoothed.max(axis=(1,2)).argmax())
                sync();query_time+=time.perf_counter()-t
                output.append(dict(iid=iid,raw=raw,smoothed=smoothed,normalized=normalized,masks=masks,chosen=chosen,latent=latent.cpu().numpy()))
            sync();return output,dict(query=query_time,render=render_time,end_to_end=time.perf_counter()-start)
        with torch.no_grad():
            execute();samples=[]
            for _ in range(3):output,sample=execute();samples.append(sample)
        timing={k:dict(samples_seconds=[s[k] for s in samples],median_seconds=float(np.median([s[k] for s in samples]))) for k in samples[0]};timing.update(warmup=1,repetitions=3,query_includes='text encoding, per-view AE decoding, CLIP relevancy and official segmentation',render_includes='three native latent feature rasters per view',export_io_excluded=True)
        exported=[]
        for item in output:
            iid=item['iid'];chosen=item['chosen'];row=export_view('langsplat',q,views[iid],item['smoothed'][chosen],item['masks'][chosen],dict(selected_level=chosen+1,threshold=.4));folder=dest/iid
            np.savez_compressed(folder/'all_levels.npz',raw=item['raw'],smoothed=item['smoothed'],normalized=item['normalized'],masks=item['masks'],rendered_latent=item['latent']);save(folder/'heatmap.jpg',cv2.cvtColor(cv2.applyColorMap((item['smoothed'][chosen]*255).clip(0,255).astype(np.uint8),cv2.COLORMAP_TURBO),cv2.COLOR_BGR2RGB));row['selected_level']=chosen+1;exported.append(row)
        record=dict(query=q,status='completed',empty_result=all(r['mask_pixels']==0 for r in exported),output_kind='official per-view semantic masks; no invented 3D instance conversion',timing=timing,views=exported)
    except Exception as e:traceback.print_exc();record=dict(query=q,status='failed',error=repr(e),traceback=traceback.format_exc())
    write(dest/'result.json',record);records.append(record);write(ROOT/'outputs/langsplat/summary.json',dict(method='LangSplat',model_load_seconds=load_seconds,queries=records,completed=sum(r['status']=='completed' for r in records),total=25));print(q['query_id'],record['status'],flush=True)
