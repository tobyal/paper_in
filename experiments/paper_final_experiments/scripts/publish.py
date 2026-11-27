from common import *
import collections,shutil,datetime
verify_locks();ext=read(ROOT/'E01_external_comparison/metrics/summary.json');abl=read(ROOT/'E02_ablation/metrics/summary.json');names=dict(langsplat='LangSplat',thgs='THGS',relags='ReLaGS',ours='Ours',box_gated='Box-based',no_relation='Ours w/o Relation',box_all33='Box-based (all 33)',sam_original='Multi-view SAM (19 available)',sam_common='Multi-view SAM (shared 17)',ours_common='Ours (shared 17)');lookup={r['method']:r for r in abl}
def table(stem,rows,note):
    csvwrite(ROOT/'tables'/f'{stem}.csv',rows);cols=list(rows[0]);md='| '+' | '.join(cols)+' |\n| '+' | '.join(['---']*len(cols))+' |\n'+'\n'.join('| '+' | '.join(str(r.get(k,'')) for k in cols)+' |' for r in rows)
    (ROOT/'tables'/f'{stem}.md').write_text('# '+stem+'\n\n'+md+'\n\n'+note+'\n')
    with (ROOT/'tables'/f'{stem}.tsv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=cols,delimiter='\t');w.writeheader();w.writerows(rows)
    def esc(v):return str(v).replace('_',r'\_').replace('%',r'\%').replace('&',r'\&')
    tex='\\begin{tabular}{'+'l'*len(cols)+'}\n\\hline\n'+' & '.join(esc(k) for k in cols)+r' \\'+'\n\\hline\n'+'\n'.join(' & '.join(esc(r.get(k,'')) for k in cols)+r' \\' for r in rows)+'\n\\hline\n\\end{tabular}\n'
    (ROOT/'tables'/f'{stem}.tex').write_text(tex);return md
note='SAM-assisted Pseudo-GT, not independent human GT. 23 valid queries / 44 valid query-view pairs from frozen 25 / 50. Mean over valid views within query, then equal query weight; empty prediction Precision=0. External methods lack equipment M0 priors; Ours uses them.'
t1=table('T01_external',[dict(Method=names[r['method']],**{'Projection mIoU (%)':f'{100*r["iou"]:.2f}','Precision (%)':f'{100*r["precision"]:.2f}','Recall (%)':f'{100*r["recall"]:.2f}'}) for r in ext],note)
rels=read(ROOT/'E01_external_comparison/metrics/per_relation.json');rr=[]
for rel in ['left_of','right_of','in_front_of','behind','near']:
    a={r['method']:r for r in rels if r['relation']==rel};rr.append(dict(Relation=rel,Queries=a['ours']['valid_queries'],Views=a['ours']['valid_views'],**{names[m]:f'{100*a[m]["iou"]:.2f}' for m in ['langsplat','thgs','relags','ours']},Best=names[max(a,key=lambda m:a[m]['iou'])]))
t2=table('T02_relations',rr,'Projection IoU (%); equal query weight within relation. Best column is computed from actual values. '+note)
t3=table('T03_ablation',[dict(Configuration=names[m],Refined='No' if m=='box_gated' else 'Yes',Relation='No' if m=='no_relation' else 'Yes',**{'mIoU (%)':f'{100*lookup[m]["iou"]:.2f}','Precision (%)':f'{100*lookup[m]["precision"]:.2f}','Recall (%)':f'{100*lookup[m]["recall"]:.2f}'}) for m in ['box_gated','no_relation','ours']], 'Box-based and Ours have identical matched and renderable equipment IDs; only Gaussian membership differs. '+note)
supp=table('S01_supplementary_ablation',[dict(Configuration=names[m],**{'mIoU (%)':f'{100*lookup[m]["iou"]:.2f}','Precision (%)':f'{100*lookup[m]["precision"]:.2f}','Recall (%)':f'{100*lookup[m]["recall"]:.2f}'},Evaluated_views=44) for m in ['box_all33','sam_original','sam_common','ours_common']], 'All33 is an availability supplement, not the controlled main ablation. Historical SAM has 19 available devices, Ours has 30; shared17 pairs use exactly the same device availability and retain all 23 queries / 44 views, including zero predictions. Historical observation supervision differs (SAM 91 real object-views; SAGA shared74 real/virtual scene views plus frozen prompts); not an equal-observation training ablation.')
online=read(ROOT/'E06_computational_efficiency/online.json');logs=read(ROOT/'E06_computational_efficiency/historical_runs.json');stage=lambda name:sum(r['seconds'] for r in logs if r['stage']==name and r['exit_code']==0)
thgs=sum(stage(s) for s in ['thgs_neighbors','thgs_reweight','thgs_partition','thgs_hierarchy']);align=stage('relags_coordinate_alignment')
offline={'langsplat':'Not recorded: complete historical training','thgs':f'{thgs:.2f} s hierarchy only; feature/2DGS costs excluded','relags':f'{align:.2f} s coordinate-aligned graph only; historical upstream excluded','ours':f'{stage("A_affinity_training"):.2f} s shared training; other stages separately listed'}
t4=table('T04_efficiency',[dict(Method=names[r['method']],Offline_record=offline[r['method']],**{'Online query (s)':f'{r["query_seconds"]:.6f}','Render two views (s)':f'{r["render_seconds"]:.6f}','End-to-end (s)':f'{r["end_to_end_seconds"]:.6f}'}) for r in online], 'Offline records are partial and NOT comparable totals. Same A6000 GPU0; 2 views, 938x528, 1 warmup + 3 CUDA-synchronized repeats, query medians averaged. Loading and export IO excluded. LangSplat query includes pixel decoding/postprocessing; Ours exact known aliases avoid online CLIP.')
table('S02_ours_construction',[dict(Experiment=r['experiment'],Stage=r['stage'],Seconds=round(r['seconds'],6),Source=r['source']) for r in read(ROOT/'E06_computational_efficiency/ours_stage_costs.json')], 'Historical wall times include differing cache/reuse states. Final v2 extraction reused 9 existing objects and cached feature maps; it is not training from scratch. B/C v2 was timed jointly; do not invent individual stage times. M0 human preparation time was not recorded.')
table('S03_storage',[dict(Asset=r['asset'],Bytes=r['bytes'],MiB=round(r['MiB'],3),Source=r['source']) for r in read(ROOT/'E06_computational_efficiency/storage.json')], 'Storage from actual file sizes; model paths stay on server.')
stats=read(ROOT/'E04_relation_retrieval/query_statistics.json');qstats=[]
for r in stats:qstats.append(dict(query_id=r['query_id'],category_candidates=r['same_category_candidates_before'],relation_targets=r['matches_after'],fine_available=len(r['renderable_object_ids']),unavailable=len(r['unavailable_object_ids']),returned_ids=';'.join(r['renderable_object_ids']),matched_ids=';'.join(r['matched_object_ids'])))
csvwrite(ROOT/'E04_relation_retrieval/query_statistics.csv',qstats)
qp=read(ROOT/'E02_ablation/metrics/per_query.json');qm={m:{r['query_id']:r for r in qp if r['method']==m and r['valid_views']} for m in lookup};comparison=[]
for qid,r in qm['ours'].items():comparison.append(dict(query_id=qid,fine_minus_box_iou_pp=100*(r['iou']-qm['box_gated'][qid]['iou']),relation_gain_iou_pp=100*(r['iou']-qm['no_relation'][qid]['iou'])))
write(ROOT/'E02_ablation/mechanism_deltas.json',comparison);csvwrite(ROOT/'E02_ablation/mechanism_deltas.csv',comparison)

# Independent human-review material exposes RGB and reference only, no method masks.
queries={q['query_id']:q for q in read(BENCH/'configs/benchmark_queries.json')};review=[]
for s in read(BENCH/'evaluation/pseudo_ground_truth/sample_manifest.json'):
    d=ROOT/'E01_external_comparison/human_review'/s['query_id']/s['camera_id'];source=BENCH/s['mask_path'];d.mkdir(parents=True,exist_ok=True)
    for name,p in [('original_rgb.png',BENCH/s['original_rgb']),('reference_mask.png',source),('reference_overlay.jpg',source.parent/'overlay.jpg'),('sam_prompts.json',source.parent/'sam_prompts.json')]:shutil.copy2(p,d/name)
    record=dict(query=queries[s['query_id']],target_object_ids=s['target_ids'],current_reference_review=s,independent_human_review_status='not_confirmed',instruction='Review original RGB, target identity, visible extent and gaps. Do not consult any method prediction. Any edited reference must create a new version and evaluate every method on the same sample set.');write(d/'review.json',record);review.append(dict(query_id=s['query_id'],camera_id=s['camera_id'],path=str(d.relative_to(ROOT))))
write(ROOT/'E01_external_comparison/human_review/manifest.json',review)
captions={
'F04_dataset':('工业场景数据及设备空间先验','Industrial scene dataset and equipment spatial priors.','真实RGB、原生3DGS、306训练/44留出相机及33设备的粗框和八类分布。M0仍为历史draft状态；坐标使用SfM相对单位。','Real RGB observations, the native Gaussian scene, 306 training and 44 held-out cameras, and 33 coarse equipment priors in eight categories. Camera points use the industrial frame; sparse Gaussian centers in the camera plot are for visualization. M0 remains historically marked draft.'),
'F05_external_comparison':('空间关系引导工业实例检索的外部对比','Qualitative comparison of spatial relation-guided industrial instance retrieval.','六个真实案例覆盖五种关系，包含外部方法有效的Q001、复杂夹具Q003及本文精细实例不可用的Q019。绿为SAM辅助参考，红为各方法预测，青框为参照类别M0位置，仅用于阅读。','Six cases cover five relations, including strong external performance (Q001), complex fixtures (Q003), and unavailable fine output (Q019). Green denotes SAM-assisted reference masks, red frozen predictions, and cyan coarse reference-category boxes for explanation only. Each row uses identical camera and image extent.'),
'F06_entity_construction':('工业先验引导的三维关系实体构建','Industrial prior-guided construction of 3D relation entities.','四台设备的粗候选、真实尺度门控亲和度与精细实例采用相同相机和裁剪。亲和度来自冻结float16数据，正式筛选使用已保存索引；O09另有6479个冲突高斯重新分配。数量减少不代表分割精度。','Coarse candidates, actual gated affinities and refined entities share camera and crop per equipment item. Affinity colors use frozen float16 values; exact stored selection indices define threshold membership. O09 loses 6,479 Gaussians during inter-instance conflict assignment. Count reduction is not an accuracy measure.'),
'F07_relation_retrieval':('工业空间关系表达与关系约束检索','Industrial spatial relation representation and relation-constrained retrieval.','完整身份表达和工业俯视布局对应33节点、2020边；30个可用精细/局部实例，3个位置节点保留。Q006先匹配6个物料车，再以全部料架参照集合筛出1个目标；图中只绘制该查询的实际关系。','The scene representation contains 33 identity nodes and 2,020 directed relations, with 30 fine/partial instances and three location-only nodes. Q006 reduces six material-cart candidates to one by union-over-anchors relation filtering. Only actual representative query edges are drawn; object colors/IDs remain consistent.'),
'F08_ablation':('精细实体和空间关系约束的消融结果','Qualitative ablation of refined entities and spatial relation constraints.','相同可用性门控下比较粗框、无关系和完整方法。Q006/Q007体现剔除背景收益；Q011保留精细提取造成召回下降的反例；Q024说明同类设备筛选。','Box-based and full Ours share equipment availability. Q006/Q007 show gains from removing contamination, Q011 retains a counterexample with lost structure, and Q024 illustrates same-category disambiguation. All masks use identical fixed cameras and the same contribution threshold.'),
'F09_multiview_application':('多视角关系检索及工业应用展示','Multi-view relational retrieval and industrial application examples.','Q003和Q006各只执行一次三维检索，再从三方向渲染相同高斯集合。最近查询N02使用M0中心距离；困难案例区分局部重建与不可用精细输出。不可用蓝箱的尝试结果仅作诊断，不参与正式查询。','Each of Q003 and Q006 is retrieved once and its unchanged Gaussian set rendered from three directions. N02 ranks cooler candidates by M0 center distance in SfM units. Difficult cases distinguish partial reconstruction from unavailable fine output. The blue-bin extraction attempt is diagnostic and is excluded from normal query output.')}
write(ROOT/'configs/captions.json',{k:dict(title_zh=v[0],title_en=v[1],caption_zh=v[2],caption_en=v[3]) for k,v in captions.items()})
gallery=['# 论文实验图集\n\n所有图片来自实际RGB、冻结预测或原生3DGS渲染。参考为SAM-assisted Pseudo-GT，未经独立人工真值认证。\n\n[完整外部25查询](../E01_external_comparison/GALLERY.md) · [完整消融25查询](../E02_ablation/GALLERY.md) · [实验报告](../EXPERIMENT_REPORT.md)\n']
index=['# 图表索引\n\n|编号|论文图名|实验|文件|原始数据|脚本|\n|---|---|---|---|---|---|']
for m in read(ROOT/'figures/manifest.json'):
    f=m['figure'];zh,en,cz,ce=captions[f];gallery.append(f'## {f}: {zh}\n\n{en}\n\n![{f}](../{m["png"]})\n\n{cz}\n\n{ce}\n\n实验：{m["experiment"]}。实际案例与文件哈希见[来源](../figures/{f}/sources.json)及[布局](../figures/{f}/layout.json)。[可编辑SVG](../{m["svg"]}) · [独立子图](../figures/{f}/subplots/)\n');index.append(f'|{f[:3]}|{zh}|{m["experiment"]}|[PNG]({m["png"]}) / [SVG]({m["svg"]})|[来源](figures/{f}/sources.json)|[plot_figures.py](scripts/plot_figures.py)|')
    (ROOT/'figures'/f/'CAPTION.md').write_text(f'# {zh}\n\n{en}\n\n{cz}\n\n{ce}\n')
for f,e in [('T01_external','E01'),('T02_relations','E01'),('T03_ablation','E02'),('T04_efficiency','E06')]:index.append(f'|{f[:3]}|{f}|{e}|[表格](tables/{f}.md) / CSV / TSV / LaTeX|{e} 原始JSON与逐视角指标|[publish.py](scripts/publish.py)|')
(ROOT/'docs/GALLERY.md').write_text('\n\n'.join(gallery));(ROOT/'FIGURE_INDEX.md').write_text('\n'.join(index)+'\n\nF01—F03仅导出真实素材，见 [manifest](method_figure_assets/manifest.json)。大型数组及模型保留服务器；图像来源路径为权威远程绝对路径。\n')
finegain=100*(lookup['ours']['iou']-lookup['box_gated']['iou']);relgain=100*(lookup['ours']['iou']-lookup['no_relation']['iou']);positive=sum(x['fine_minus_box_iou_pp']>1e-9 for x in comparison);negative=sum(x['fine_minus_box_iou_pp']<-1e-9 for x in comparison)
entityrows=read(ROOT/'E03_entity_construction/summary.json');entitytable=table('S04_entity_intermediates',[dict(ID=x['display_id'],Equipment=x['name_en'],Candidates=x['candidate_gaussians'],Pre_conflict=x['before_conflicts'],Final=x['final_gaussians'],Conflict_removed=x['lost_conflicts'],Fine_available=x['quality']['fine_instance_available']) for x in entityrows], 'Numbers describe processing, not segmentation accuracy. O11 is a preserved unsuccessful extraction attempt, not normal fine query output.')
report=f'''# 面向工业场景的空间关系引导三维高斯实例检索：论文补充实验

## 1. 目标及论文定位

本轮实际完成E01—E06、F04—F09、T01—T04，并为F01—F03导出真实素材。方法主体仍为冻结saga_relags_v2；第一阶段为工业先验引导的关系实体构建，第二阶段为工业空间关系建模与实例检索。没有重新训练、修改M0、改变核心算法或根据评价结果调整阈值。关键结论是：**关系约束贡献明确；精细提取提高Precision，但明显牺牲Recall，平均IoU收益很小。**

## 2. 数据与设置

单个真实工业车间，原生3DGS 1,828,777高斯；306训练图像、44留出图像。33设备、8类别、30精细/局部可用实例，3个仅保留身份位置。M0 r29保持历史draft状态；不将本次整理解释为人工认证。原生重建本身早于此划分，不宣称独立重建测试。

冻结25查询、每条2固定真实视角、29不同相机、938×528分辨率。继续使用冻结SAM-assisted Pseudo-GT，23查询/44查询—视角进入主指标。Q005/Q025各两视角、Q009/Q010各一视角因参考不可靠排除；所有方法/消融使用相同集合。Q019空精细输出仍计零。先在查询内平均视角，再等权平均查询。空预测Precision=0，正常空结果与运行失败分开记录。本轮各实际预测任务均成功；不存在把空预测当作运行错误而剔除的情况。

冻结配置和源代码/检查点哈希见configs/FROZEN.json；源码版本见source_data/repositories.json，原参考锁和查询配置见source_data。全部新写入本目录。现有人工GT目录只有接口说明，没有独立人工确认掩膜。新增E01_external_comparison/human_review保存50样本原图、参考、叠加、提示和待核查元数据，不附方法预测，也不改变当前参考。

## 3. E01 整体外部对比

目的：比较共同关系任务下的实际工业检索效果。实现：evaluate.py直接读取冻结二值掩膜，从TP/FP/FN独立重算，逐视角相机和尺寸验证通过，三个总体指标与上一轮相差小于1e-12。

{t1}

{t2}

ReLaGS复核实际检查816,661行高斯、两层标签/父子一致性/语义行号、全局旋转、25查询节点并集和50次完整场景重渲染；保存的二值掩膜逐像素相同。未发现明确工程错配，保留原0.35% mIoU及14次官方阈值回退。相关原始证据见E01_external_comparison/relags_engineering_audit.json。不能据此证明其学习关系适合当前工业定义：数据域、设备粒度、官方最多3主体与多参照集合语义仍有差异。

本表为有工业先验条件的应用对比，Ours使用M0身份/类别/空间，外部方法没有设备先验，且基础3DGS/2DGS不同；不能把优势全部归为SAGA精细提取。Q001外部方法也表现良好；Q019中Ours为0，而LangSplat查询均值63.08%、THGS55.66%，反例保留在F05和全图集。

## 4. E02 主要机制消融

实际执行ablation.py：Box-based与Ours使用完全相同目标身份与精细可用性门控，前者返回M0全部候选高斯；w/o Relation使用冻结类别接口返回所有可用同类精细实例。均采用完整原生场景贡献>0.5，保留遮挡，无孤立物体掩膜替代评价。完整Ours预测复用并验证高斯索引相同。

{t3}

精细实体使mIoU增加{finegain:.2f}个百分点，Precision增加{100*(lookup['ours']['precision']-lookup['box_gated']['precision']):.2f}个百分点，但Recall降低{100*(lookup['box_gated']['recall']-lookup['ours']['recall']):.2f}个百分点。23有效查询中{positive}条IoU提高、{negative}条降低，其余相同。Q007料架有明显收益；Q011和同目标Q022从粗框70.67%下降到精细47.05%，显示已重建结构也可能被筛除。不能以清除高斯数量代替准确率。空间关系使mIoU增加{relgain:.2f}个百分点，主要减少错误同类设备；Recall基本不变。

{supp}

全部33粗框可用时mIoU达到68.07%，高于完整Ours63.70%；其Recall90.94%而Precision72.51%。这是可用性和粗细范围一起变化的补充结果，不能混为主消融。Q019粗框可见而精细输出禁用，揭示当前质量门控带来的实际代价。

额外复用早期多视角SAM融合：原生坐标、33个粗框及候选行号逐项相同，历史提示视角无留出交集。SAM原有19可用设备，与Ours共享17设备。共享门控下SAM21.62%、Ours46.01%，但观测监督不同，不能宣称严格等训练数据算法消融。所有23/44样本仍参与，未只保留SAM成功样例。兼容性、全部7配置预测、逐查询/关系指标及差值均保存在E02_ablation。

## 5. E03 工业关系实体构建

实际导出5台：O01装配夹具台、O09镂空料架、O07物料车、O24局部重建分隔料架，以及不可用O11蓝箱诊断。复用冻结iteration_10000真实门控亲和值、有效点、原始SAM掩膜及三向原生渲染。没有合成亲和热图，也无需重算已经保存的提取过程。输入/输出/质量和源哈希见每对象provenance.json。

{entitytable}

同相机、同裁剪比较粗候选、亲和度和精细集合。affinity为历史float16存储；正式阈值前后集合使用已保存索引，避免量化边界误差。actual_intermediates.npz记录候选原始/工业坐标、分数、阈值选择、最终选择与冲突丢失。O09冲突分配移除6479个高斯，须与亲和阈值剔除分开。提示仅来自训练视角；新图不调整提示。O24保留已重建局部而不补造背面。O11诊断尝试仍混入/缺失，不进入普通精细输出。

## 6. E04 空间关系与同类设备区分

真实query.py重新执行全部25查询，与原冻结raw_query逐项相同；每条保存全部同类候选、所有参照、关系边、匹配设备、不可用设备及返回集合。33节点、2020有向边完整保留，图中只绘制少数真实关系。设备颜色和O01—O33索引跨图一致，3个不可用实例通过粗空间节点显示。

25查询的类别候选总数{sum(r['category_candidates'] for r in qstats)}，关系目标总数{sum(r['relation_targets'] for r in qstats)}，精细可用目标使用次数{sum(r['fine_available'] for r in qstats)}。这是候选筛选量，不是准确率。Q006由6物料车筛为1；Q011由3装配夹具台筛为1；Q024保留符合near条件的多个物料车。多参照按已有并集语义，图和trace列出所有参照，不偷偷挑一个编号参照。身份参考也基于M0，不能描述为独立人工定位认证。

## 7. E05 多视角与工业应用

Q003复杂夹具和Q006物料车各执行一次3D查询，固定设备ID及高斯集合，斜/侧/顶三个方向分别保存完整场景、红色目标/青色参照、独立实例、贡献数组和相机。各视角固定ID哈希一致；不是每图重新做SAM。完整场景保持其他设备遮挡，孤立渲染仅用于展示。图中的统一局部裁剪记录在sources.json，不改变相机或集合。

另外实际运行5条nearest_to查询，导出所有同类候选中心距离和排序，并用M0中心欧氏距离独立验证返回集合，包括1e-6并列规则；单位为SfM相对单位。N05最近设备为O11蓝箱，精细不可用，保持空输出，没有替换次近设备。N02用于主图；所有5条完整数据留在E05_multiview_application/nearest。

困难案例区分原始重建缺失、亲和提取结构损失及定位成功但精细不可用；当前证据不足以对所有缺失做准确归因。自由视角中仍可见浮点、模糊和未采集侧面缺失；多视角图用于三维身份一致性展示，不证明几何补全或新视角质量提高。

## 8. E06 效率和共享特征复用

{t4}

全部时间直接来自真实日志，在线边界验证通过，未为快得分改变输出数量或分辨率。在线数字是每条2视角、1预热、3次CUDA同步测量的中位数再平均；不含加载/导出I/O。LangSplat含像素特征解码/后处理，Ours命中已知别名，不等价自由语言编码。旧环境/调试失败不当作正常查询失败。

共享SAGA训练1852.45s（30.87min），v1提取10台25.24s；v2新增训练0，首次全33提取40.89s，修订提取7.77s，新增参考79.15s。v2提取复用9台既有结果和已缓存特征，不能称为从零生成33实例只需7.77s。SAM全景预处理250.57s，mask尺度118.03s；v1类别语义8.63s；v2 B/C合计13.65s，未单独计时不强拆。v1图构建53.67s还包括历史本地SoM辅助，不等同当前几何图独立成本。完整89条历史运行记录、原路径、失败记录、存储开销见E06，S02/S03便于论文引用。M0人工准备时间没有记录，应作为额外先验成本说明。复用结论仅限同一车间场景。

## 9. 结论与局限

当前证据支持“明确的设备身份和空间关系可减少工业重复设备的检索混淆”；在当前先验条件下，关系约束带来17.18个百分点mIoU收益。精细实体主要体现为Precision提升，平均IoU仅提高0.75个百分点，且有显著Recall损失，不能写成全面优于粗框。不可用设备和错误剔除是后续重点，而不是继续增加复杂模块。

评价仍受单场景、M0共享身份/几何、非随机设计查询、SAM参考边界偏好、6不可靠视角排除、重建不完整及先验不对等影响。Q011/Q022等不同句子可能命中同一实体，相互不独立；因此未根据23查询做泛化显著性结论。相邻料架冲突亲和值跨尺度未校准。原生3DGS/2DGS的重建质量和表示差异也影响外部比较。正式人工真值需要独立确认，已有待核查包；本轮已有实际伪参考数值，不再填写Pending GT替代结果。

## 10. 图表、素材和复现

F04数据，F05外部比较，F06实体机制，F07关系筛选，F08消融，F09三维多视角及应用。主图选择包含外部有效、本文受限和精细筛选损失案例。25条外部对比和25条消融完整双视角图集另存，不仅展示胜例。T01—T04均保存CSV、Markdown、TSV和LaTeX；S01—S04保存补充表。正式图为450dpi PNG及可编辑文字SVG，含独立子图、布局、来源和双语图注。

F01—F03仅整理真实素材到method_figure_assets，未冒充完成正式方法图。原始大数组、模型和完整渲染保留服务器，轻量Git版本记录路径。具体入口见FIGURE_INDEX.md与docs/GALLERY.md。所有命令、源码快照、运行时和GPU采样见logs；GPU采样是整卡用量，不能误称本进程峰值。最终保护及输出检查见source_data/final_validation.json。
'''
(ROOT/'EXPERIMENT_REPORT.md').write_text(report)
(ROOT/'README.md').write_text('''# Paper final experiments: industrial relational instance retrieval

实际完成 E01—E06。冻结 v2 / 25 queries / SAM-assisted Pseudo-GT；主指标23查询、44视角。

优先看 [正式图集](docs/GALLERY.md)、[实验报告](EXPERIMENT_REPORT.md)、[图表索引](FIGURE_INDEX.md)。

实测 mIoU：Box-based 62.95%，w/o Relation 46.52%，Ours 63.70%。精细提取主要提高Precision，明显损失Recall；允许33粗框输出时68.07%，作为可用性补充单列。外部方法旧数值独立重算一致。ReLaGS50次重渲染一致，未发现索引或坐标错误。

## Re-run on the authoritative server

```bash
cd /mnt/sda/ubuntu/lkx/papers/paper_in/experiments/paper_final_experiments
export PYTHONDONTWRITEBYTECODE=1
PY=../saga_relags_v1/envs/saga/bin/python
$PY scripts/run_stage.py E02 $PY scripts/ablation.py
$PY scripts/run_stage.py SAM_supplement $PY scripts/sam_supplement.py
$PY scripts/run_stage.py evaluate $PY scripts/evaluate.py
$PY scripts/run_stage.py E03 $PY scripts/export_entities.py
$PY scripts/run_stage.py E04_E05 $PY scripts/export_applications.py
$PY scripts/run_stage.py nearest_display $PY scripts/refine_nearest_display.py
$PY scripts/run_stage.py E06 $PY scripts/efficiency.py
$PY scripts/run_stage.py figures $PY scripts/plot_figures.py
$PY scripts/run_stage.py publish $PY scripts/publish.py
$PY scripts/run_stage.py validate $PY scripts/validate.py
```

ReLaGS audit uses `../../envs/relags/bin/python scripts/audit_relags.py` through run_stage.py. Initialization is one-shot; do not overwrite configs/FROZEN.json. Prediction scripts resume by completed result.json. New scientific changes should use another version, not overwrite frozen v2 or benchmark.

Independent human GT does not yet exist. The 50-sample RGB/reference-only review package stays under E01_external_comparison/human_review. Formal figures use English labels, editable SVG text, and configs/captions.json for bilingual captions; layout/source metadata is per figure.

Models, PLY, response/affinity arrays and full renders remain on the server. Git archive contains code/configs/reports/tables/figure assets and lightweight masks/metadata only. Server references and SHA256 are recorded, and v1/v2/benchmark are read-only dependencies.
''')
print('Tables, bilingual captions, report and 50 human-review packages generated',flush=True)
