import numpy as np
from .common import *
from .model import ClipEncoder, QueryEngine


def run(ctx):
 nodes=read(ctx.path('M4','nodes.json'));features=np.load(ctx.path('M3.4','features.npz'));edges=read(ctx.path('M4','relations.json'))
 encoder=ClipEncoder(ctx.source('clip'),ctx.c['input']['clip_arch'],'cuda');engine=QueryEngine(nodes,features['visual'],features['text'],edges,ctx.c['query'],encoder)
 from .render import Renderer
 renderer=Renderer(ctx)
 cases=[('semantic_racks','找到料架'),('semantic_blue_cart','找到蓝色物料箱转运车'),('semantic_gray_curtain','找到具有灰色布帘的物料车'),('semantic_all_carts','找到物料车'),('semantic_named_cart','找到物料车 01'),('empty_missing_name','找到物料车 99'),('spatial_near_racks','料架附近有哪些设备'),('spatial_left_carts','物料车左侧有哪些对象'),('combined_left_of_rack','找到料架左侧的物料车'),('combined_near_workbench','找到工作台附近的封闭式物料车'),('combined_behind_blue_cart','找到蓝色物料箱转运车后方的设备'),('pair_named',dict(type='pair',subject='物料车 01',object='物料车 02')),('empty_geometry',dict(type='combined',subject='立式移动冷风机',relation='above',object='装配夹具台'))]
 cases += [('pair_fixture_tables',dict(type='pair',subject='装配夹具台 01',object='装配夹具台 02')),('semantic_named_fixture','找到装配夹具台 01')]
 records=[];lookup={n['object_id']:n for n in nodes};reference=read(ctx.out/'config/reference_cameras.json')
 for key,query in cases:
  folder=ctx.path('M5',key);folder.mkdir(exist_ok=True)
  try:
   result=engine.query(query);write(folder/'query.json',result);groups=[];paths=[]
   for k,oid in enumerate(result['matched_ids']):
    node=lookup[oid];ids=ctx.ids(oid,final=True);groups.append((ids,object_color(k+1)));view=renderer.virtual(node['center'],node['bbox']['size']);write(folder/(oid+'_camera.json'),view);path=folder/(oid+'_independent.png');save_image(path,renderer.rgb(view,ids));paths.append(path)
   if groups:
    for im in reference:save_image(folder/(im['image_id']+'_highlight.jpg'),renderer.highlight(im,groups,width=ctx.c['visualization']['width']))
    sheet(paths,folder/'matched_objects.jpg',labels=[lookup[i]['name_en'] for i in result['matched_ids']])
   else:write(folder/'no_match.json',dict(reason=result['reason'],threshold_not_relaxed=True,no_artificial_highlight=True))
   record=dict(case=key,query=query,parsed=result['parsed'],outcome=result['outcome'],matched_ids=result['matched_ids'],total_before_limit=result['matched_count_before_limit'],relation_matches=len(result['relation_matches']),path=str(folder.relative_to(ctx.out)))
  except ValueError as exc:
   record=dict(case=key,query=query,outcome='unsupported',reason=str(exc));write(folder/'unsupported.json',record)
  records.append(record);print('M5 query',key,record['outcome'],record.get('matched_ids',[]),flush=True)
 write(ctx.path('M5','queries.json'),records)
 return dict(queries=len(records),outcomes={outcome:sum(r['outcome']==outcome for r in records) for outcome in ['empty','single','multiple','unsupported']},ground_truth_accuracy_available=False,all_fixed_thresholds=True)
