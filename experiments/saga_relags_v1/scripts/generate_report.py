"""Report observed artifacts and validation, including failed/limited outputs."""
import sys,collections,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from common import *
manifest=read(ROOT/'world_model/manifest.json');iteration=manifest['iteration'];a=read(ROOT/f'outputs/A/extractions/iteration_{iteration}/summary.json');quality=read(ROOT/f'outputs/A/extractions/iteration_{iteration}/quality_review.json');qmap={r['object_id']:r for r in quality['objects']};b=read(ROOT/'outputs/B/summary.json');btest=read(ROOT/'outputs/B/validation.json');c=read(ROOT/'outputs/C/summary.json');d=read(ROOT/'outputs/D/summary.json');checks=read(ROOT/'outputs/validation/checks.json');portable=read(ROOT/'outputs/validation/portable_render.json');calib=read(ROOT/'outputs/A/scale_evidence/summary.json');training=np.genfromtxt(ROOT/'outputs/A/saga_model/training_metrics.csv',delimiter=',',names=True);runs=[]
for path in sorted((ROOT/'logs').glob('*/*/result.json')):r=read(path);r['record_path']=str(path.relative_to(ROOT));runs.append(r)
train_run=[r for r in runs if r['stage']=='A_affinity_training'][-1];counts=collections.Counter(e['relation'] for e in read(ROOT/'outputs/C/scene_graph.json')['edges']);usable=[o for o in quality['objects'] if o['usable_for_queries']];failed=[o for o in quality['objects'] if not o['usable_for_queries']];total_selected=sum(r['gaussian_count'] for r in a['objects'] if 'gaussian_count' in r)
lines=['# SAGA + ReLaGS 工业世界模型实验总结','',f'生成时间：{datetime.datetime.now(datetime.timezone.utc).isoformat()}。实验目录：`{ROOT}`。','',
'## 实际结果','',f'- A完成官方SAGA {iteration:,}步共享亲和训练；尝试10个对象，{len(usable)}个通过当前用途的视觉审核，{len(failed)}个保留为失败/待改进结果。通过审核表示设备级查询展示可用，不等于完整精细网格或具有真值认证的分割。',f'- B构建{b["categories"]}类512维共享语义，使用{b["visual_crops"]}张真实训练图像裁剪；{btest["correct"]}/{btest["total"]}个小规模表达检查正确。',f'- C包含{c["nodes"]}个M0节点、{c["geometric_edges"]}条有向几何关系。SoM本地模型已实际运行，可靠视觉语义新增边为{c["accepted_visual_edges"]}；关系查询主要由几何支持。',f'- D实际运行{d["class_queries"]}个类别查询和{d["relation_queries"]}个关系查询，保存高斯集合、全场景高亮、原始留出RGB的红色投影掩膜。','',
'## 技术路线及复用边界','',
'A使用SAGA v2官方32维亲和特征、尺度门控、对比损失、K=16局部平滑、渲染点击特征及(cos+1)/2阈值筛选。M0替代对象发现、实例身份与粗空间搜索；没有用粗框中的全部高斯冒充分割。B使用已知8类知识、别名和已有CLIP。C保留ReLaGS的编号视觉提示、关系到固定三维ID的映射和多视角证据融合思想，省去2DGS、THGS、群组匹配及GNN。D只查询已经构建的知识，不重新运行SAM/SAGA。','',
'参考：[SAGA官方固定版本](https://github.com/Jumpat/SegAnyGAussians/tree/2d4c5d77c857c956d747e4775d3d72c4ec5dfe16)、[SAGA论文](https://arxiv.org/abs/2312.00860)、[ReLaGS论文](https://arxiv.org/html/2603.17605v1)、[ReLaGS SoM代码](https://github.com/dfki-av/ReLaGS/tree/main/scene_graph/som)。本实验为工业先验适配和方法集成，不将原论文创新归为新算法。','',
'## 数据、环境与兼容性','',
'最新M0保存版本r29，33个对象、8类；原formal review flag仍为draft，保留原样。原生3DGS共1,828,777个Gaussian。训练观测74个：57真实、17已有完整场景虚拟图；44个原始留出图像不参与本次亲和训练、提示和调参。没有使用旧LangSplat特征、旧SAM结果或M2最终实例。','',
'新venv隔离官方SAM与SAGA扩展，基础Torch等库继承既有只读运行环境；Python3.10.13、Torch2.2+cu118、CUDA11.8、A6000。数据包可独立读取，CUDA环境仍需按README安装；未宣称环境完全可搬移。','',
f'必要适配包括RGB顺序、CPU序列化、逐相机主点缩放及半像素约定、深度反投影行列坐标、精确邻域缓存和日志/恢复。原损失、门控网络和平滑表达式保留。74个相机的抽样投影最大误差为{max(v["projection_max_error_pixels"] for v in calib["views"]):.6f}像素。原始Gaussian行序已检查，训练后位置/尺度/旋转/透明度与原PLY逐字段一致。','',
'## A：实例分割','',
f'训练耗时{train_run["seconds"]:.1f}秒；Torch训练峰值分配{max(training["peak_allocated_bytes"])/2**30:.2f} GiB。整卡显存采样包含原有进程和短时本地VLM，另见日志。保存1,000、2,500、5,000、10,000步完整状态；原始高斯属性未优化。学习率0.0025，采样1000条射线，特征维度32，空间平滑K=16。','',
'重新生成官方SAM自动监督，并加入24张经过可见性与视觉检查的辅助参考掩膜。4张混入邻近设备的高置信度提示被剔除，全部失败掩膜和原始自动掩膜保留。两个带工件夹具台各补两个覆盖物/黑色主体正点击；这些点击坐标明确记录于配置。全部提示仅来自训练观测。','',
'分割采用阈值0.85；设备尺寸经训练尺度分布映射到尺度门控，多个正点击取相似度并集，再施加M0范围约束。重叠候选按学习到的亲和度分配，不做高斯中心投票。','',
'| 对象 | 候选高斯 | 最终高斯 | 查询可用 | 实际检查 |','|---|---:|---:|---|---|']
for r in a['objects']:
    q=qmap[r['object_id']];lines.append(f'| {r["name_zh"]} / `{r["object_id"]}` | {r.get("candidate_gaussians",0)} | {r.get("gaussian_count",0)} | {"是" if q["usable_for_queries"] else "否"} | {q["assessment_zh"]} |')
lines+=['',f'所有尝试合计选择{total_selected:,}个互不重复的Gaussian行。对象索引、原生PLY、全场景亲和度、点击向量、投影贡献、三向渲染及粗框参照保存在`outputs/A/extractions/iteration_{iteration}/`。较早检查点和补点前后尝试单独保留。','',
'## B：类别共享语义','',
'每类保存中英文名、同义表达、共有视觉描述、归一化文本与图像向量。同类对象共用类别表示，实例身份由M0和场景图区分。中文主要使用明确别名，英文可用CLIP相似度回退；这不是通用开放词汇类别发现。8个检查样例只是功能检查，不能解释为统计识别准确率。','',
'## C：几何图与视觉关系检查','',f'关系数：`{dict(counts)}`。+X为右，+Y为前，+Z为上，使用SfM相对单位。左右/前后需要工业轴向包围区间间隔超过0.02；near为包围区间距离小于0.35；nearest_to按参照对象和目标类别，在全部33个对象中比较中心距离，保留并列。显示图仅抽取少量可读关系，全图保留全部证据。','',
'SoM在3个真实训练视角上使用M0已知ID和可见粗候选轮廓标号。服务器本地qwen3.5:9b进行了3次初始推理及2次描述补查，没有工业图像外传。初始两次说明过于简略，补查中仍出现冷风机/工作台识别混淆；这部分不能视为可靠的对象识别验证。没有获得满足多视角和几何接触条件的支撑/包含边，未强行补造关系，也不能据此断言场景不存在此类关系。','',
'本次设备级节点通常是彼此独立的完整设备，架内物料、设备部件未另立节点，也限制了包含/支撑关系的可表达范围。C的可用成果是带证据的几何场景图，视觉语义关系提升仍需后续验证。','',
'彩色实例PLY保留真实Gaussian结构；三维关系线PLY与原场景同坐标；展示图由完整原生3DGS渲染叠加真实实例颜色和三维中心投影连线生成。路径：`outputs/C/visualizations/`。','',
'## D：语言与关系查询','',
'类别候选只包含审核可用的实例；所有M0节点可作为参照。关系查询的参照可为类别或具体设备名称，满足多个条件时允许多结果。演示文本按真实图中能够区分同类设备的条件选择，执行时只传文本给统一解析器，不传预设答案。','',
'| 查询 | 同类候选数 | 返回数 | 返回对象 |','|---|---:|---:|---|']
for r in d['queries']:lines.append(f'| {r["query"]} | {r["candidates_before"]} | {r["matches_after"]} | '+', '.join(r['matched_object_ids'])+' |')
lines+=['',
'每个查询保存两个留出视角，投影由完整场景alpha合成后的目标贡献大于0.5产生，保留真实遮挡。最初仅按框面积选展示相机，产生了被遮挡目标几乎不可见的图；该图集保存在outputs/D_history/bbox_only_display_selection。最终使用冻结实例在44个留出相机下的实际可见贡献选择展示相机，没有据此修改实例、提示或阈值。红色区域来自固定三维实例，而非直接复制输入SAM掩膜。没有独立人工真值，不报告IoU准确率；训练提示一致性仅保留为内部检查。','',
'## 验证及失败保留','',
f'整体产物检查：`{checks["passed"]}`。检查{checks["protected_outputs_checked"]}个既有输出文件的大小/修改时间及受保护输入源码哈希，旧文件改动{len(checks["protected_source_changes"])+len(checks["protected_outputs_changed"])}项；旧输出新增{len(checks["protected_outputs_added"])}项。独立包查询退出码{checks["standalone_query_exit_code"]}；独立包渲染最大贡献误差{portable["max_absolute_contribution_error"]:.8g}、掩膜一致性{portable["binary_mask_iou"]:.8f}。这项一致性验证接口实现，不是分割精度。','',
'保留的工程失败包括旧SAM接口不兼容、第一次批量提取缺少MiniCam特征尺寸字段、OpenCV绘图输入内存布局不连续；均已定位并只在新方案内修复。语义分割失败对象、受污染提示和VLM不充分回复分别保留，无粗框结果替换。另保存独立彩色Gaussian实例图，减少背景遮挡对空间关系查看的影响；完整场景图仍保留。完整运行记录如下。','',
'| 阶段 | 状态 | 秒数 | 日志记录 |','|---|---|---:|---|']
for r in runs:lines.append(f'| {r["stage"]} | {r["status"]} | {r["seconds"]:.1f} | `{r["record_path"]}` |')
lines+=['','## 后续可改进点','',
'优先处理料架的镂空细杆、被遮挡底部及邻近结构混入；进一步检查SAM跨材质的一致性和提示粒度。物料车与冷风机的背面模糊、漂浮高斯部分来自原3DGS，应与分割错误区分。语义关系需要更清楚的局部SoM证据和具有独立节点的真实接触案例；当前几何图受粗M0边界及相对单位影响。语言接口可扩充别名和解析形式，但不应把8类范围内的功能检查夸大为通用语言理解。','',
'最终包：`world_model/`。详细运行命令、断点恢复和查看路径见`README.md`。本次没有改动旧Web、原M0及旧研究模块，也没有重新训练基础3DGS。','']
(ROOT/'EXPERIMENT_REPORT.md').write_text('\n'.join(lines));write(ROOT/'outputs/summary.json',dict(usable_objects=len(usable),failed_objects=len(failed),categories=8,graph_nodes=c['nodes'],geometry_edges=c['geometric_edges'],visual_edges=c['accepted_visual_edges'],class_queries=d['class_queries'],relation_queries=d['relation_queries'],training_seconds=train_run['seconds'],validated=checks['passed'] and portable['passed']))
print('REPORT WRITTEN',ROOT/'EXPERIMENT_REPORT.md')
