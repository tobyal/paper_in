"""Generate a concise report from real stage summaries, including failed attempts."""
import argparse
from .common import *

DESCRIPTIONS={
 'M1':('原生 PLY、M0 r29、350 个 RGB/COLMAP 相机','scene/、object_candidates/、objects.json、visualization/'),
 'M2.1':('M1 候选、306 个训练相机、完整场景','all_view_rankings.json、selected_views.json、full_scene_depth/、各对象投影框'),
 'M2.2':('选定原始 RGB、三维框投影、通用 SAM 权重','images/、embeddings/、全部候选掩膜/低分辨率 logits、observations.json'),
 'M2.3':('候选高斯、接受的 SAM 掩膜、完整场景深度','各对象 scores.npz、逐视角 votes.npz、unknown_gaussian_ids.npy、score_overview.jpg'),
 'M2.4':('完整得分、统一阈值和冲突规则','instances.json、对象 PLY/索引、处理前后索引、overlap_conflicts.json'),
 'M2.5':('最终实例、输入 SAM 掩膜、完整场景','consistency.json、贡献/投影/差异图、独立渲染、candidate_vs_instance.jpg'),
 'M2.6':('最终实例、完整原生场景','gaussian_to_object.npy、label_lookup.json、semantic_native_3dgs.ply、语义地图'),
 'M3.1':('接受的原始图像和掩膜、同一 CLIP','对象裁剪/掩膜裁剪、逐视角特征、model.json'),
 'M3.2':('逐视角视觉特征、分割/观测质量','cosine_similarity.npy、weights.npy、aggregation.json、visual_features.npy'),
 'M3.3':('M0 原始英文名称/描述、兼容 CLIP 文本分支','text_inputs.json、text_features.npy'),
 'M3.4':('最终实例、聚合视觉和文本特征','objects.json、features.npz、视觉/文本相似度矩阵'),
 'M4':('最终实例几何、固定工业坐标、双分支特征','nodes.json、relations.json、pair_geometry.json、距离/位置矩阵、图可视化'),
 'M5':('对象双分支语义、已构建场景图、查询','queries.json、每项查询的解析/完整候选得分/关系筛选/独立和高亮图'),
 'package':('上述最终几何/实例/语义/场景图/证据','manifest.json、geometry/、objects/、semantics/、graph/、evidence/、独立读取代码')}


def run(ctx):
 rows={s:read(ctx.path(s,'summary.json')) for s in STAGES if ctx.path(s,'summary.json').exists()}
 lines=['# 工业空间先验与原生 3DGS 世界模型：首次实现实验报告','',
        '实验：2026-11-26，M0 revision 29；这是新 M1—M5 方法的独立实验，不是原始 ReLaGS Baseline 0 的替换。原生场景、M0 和旧实验均未作为写入目标。', '',
        '使用 350 张原始 RGB 与原有 COLMAP，相机分为 306 训练/44 留出；本次建模仅用训练图像，没有独立标注真值，不报告真实分割准确率或查询准确率。单位为 SfM 相对单位。', '',
        '用户已授权采用当前完成的标注。数据库正式状态仍为 draft，地面参考 formal flag 未确认；33 个对象正式 confirmed 数为 0。原始状态完整保存，不擅自改标为已确认。缺失英文描述时只编码已有英文名称。', '',
        '|阶段|实际状态|耗时秒|PyTorch 峰值显存 GiB|主要真实统计|','|---|---|---:|---:|---|']
 for s in STAGES:
  r=rows.get(s,{});stats=r.get('result',{});brief={k:v for k,v in stats.items() if isinstance(v,(int,float)) and not isinstance(v,bool)}
  lines.append(f'|{s}|{r.get("status","未运行")}|{r.get("seconds",0):.1f}|{r.get("torch_peak_allocated_bytes",0)/2**30:.2f}|{json.dumps(brief,ensure_ascii=False)}|')
 lines+=['','每次执行的命令、代码快照、配置、完整日志、时间及 GPU 采样位于 `runs/<stage>/<attempt>/`。GPU CSV 是整张卡的使用情况，包含共享进程；表中峰值是当前 PyTorch 进程分配量。','', '## 模块与可检查结果','']
 for s,(inputs,outputs) in DESCRIPTIONS.items():
  lines += [f'- **{s}**：输入 {inputs}。输出 [`{STAGES[s]}/`]({STAGES[s]}/)：{outputs}。']
  p=ctx.path(s,'README.md')
  if s!='package':p.write_text(f'# {s}\n\n输入：{inputs}。\n\n输出：{outputs}。\n\n运行：`python -m industrial_world_model.run --config configs/industrial_world_model.json --stage {s}`\n\n实际状态和统计：`summary.json`。完整日志/配置/代码快照在输出根目录 `runs/{s}/`。中间数据不等同独立真值。\n',encoding='utf-8')
 if ctx.path('M2.4','instances.json').exists():
  instances=ctx.instances();selected=ctx.selected();obs=ctx.segmentation();lines+=['','## 对象结果','', '|对象|选择/接受视角|候选/最终高斯|状态|','|---|---:|---:|---|']
  for o in instances:lines.append(f'|{o["name_zh"]}|{len(selected[o["object_id"]])}/{sum(r["accepted"] for r in obs[o["object_id"]])}|{o["candidate_count"]}/{o["gaussian_count"]}|{o["status"]}|')
  lines+=['','未通过最低观测要求的对象保留 ID 和失败原因；其最终实例为空或标记 unavailable，M4/M5 不以 M0 粗框替代真实提取结果。','']
 if ctx.path('M5','queries.json').exists():
  lines+=['## 代表性查询','', '|查询|实际结果|返回数|关系依据数|','|---|---|---:|---:|']
  for r in read(ctx.path('M5','queries.json')):lines.append(f'|{r["case"]}: {json.dumps(r["query"],ensure_ascii=False)}|{r["outcome"]}|{len(r.get("matched_ids",[]))}|{r.get("relation_matches",0)}|')
 lines+=['','## 已知问题与解释边界','',
 '- 视角选择先按投影面积和图像覆盖取每对象最多 30 个候选，再检查完整场景深度与方向差异；尚未评估可见性的其他相机在排名中明确标记。遮挡严重、薄结构或边缘对象可能因此缺少有效视角。',
 '- 深度是完整原生 3DGS 的透明度归一化 Z/Z² 矩，不是真实测量表面深度。多层半透明区域和细杆会导致深度方差大或可见性不足；当前保守门限可能漏掉有效结构。',
 '- SAM box prompt 仍可能把相邻物体、空隙或背景作为对象；保存了三个候选、置信度、可见中心支持率和拒绝原因。没有逐设备特殊修正。',
 '- 最终实例按高斯中心多视角支持筛选；没有有效观测的高斯为未知。至少两次有效和正向观测的要求会使单视角对象不可用，也可能损失背面或遮挡部件。',
 '- 归属冲突按有效支持差值裁决；不足则不分配。未使用局部去噪，处理前后索引一致，保留可能断开的设备结构。',
 '- 重投影 IoU/覆盖率比较的是作为输入的 SAM 掩膜，只诊断内部一致性；低覆盖通常与可见性保守筛选、细杆和 SAM 背景混入有关，不能称为真实准确率。',
 '- ROFA 启发的聚合使用视角质量加权、归一化平均和样本数/离散度门控的 median-MAD 过滤，并非官方 ROFA 的逐行复现。少视角时不强行做统计异常剔除。',
 '- 场景图采用实际提取高斯的工业坐标 AABB。包围范围因漏提或残留离群点而改变，会直接影响 left/right/front/behind/near 等关系。阈值和每条边的几何依据均已保存。',
 '- +X 为右、+Y 为前、+Z 为上，与渲染相机无关；near 是 AABB 最小距离。关系仅表示几何，不推断工艺、功能、连接或运行状态。',
 '- 查询使用兼容 CLIP 的视觉/文本双分支和固定阈值，已知名称/类别显式筛选。中文解析仅覆盖文档示例和有限词典；任意外观描述可用英文或结构化输入。不降低阈值补结果，相似度不是概率。',
 '- 当前目标是完整可检查基础版本。后续优先检查观测不足对象的视角策略、SAM 背景污染和深度门限，再分析细结构/遮挡部件的关联完整性。未做参数寻优、消融、正式评测或额外模型训练。','', '## 保留的失败和验证','']
 failures=[]
 for p in sorted((ctx.out/'runs').glob('*/*/result.json')):
  r=read(p)
  if r['status'] in ['failed','interrupted']:failures.append(f'- `{p.parent.relative_to(ctx.out)}`：{r.get("error")}')
 lines+=failures or ['- 无运行异常记录。']
 if (ctx.out/'validation.json').exists():lines += ['- 实际数据验证：`validation.json`，检查对象/高斯 ID、未知状态、得分一致性、冲突不强分配、完整分辨率掩膜、真实实例范围、关系互逆、特征范数和独立模型路径。']
 if ctx.path('package','standalone_validation.json').exists():lines += ['- 独立加载验证通过：原工程和 M0 数据库环境路径设为无效，仍使用包内代码/权重进行 CPU 查询和原生 CUDA 高亮渲染；查询未导入 SAM。记录为 `final_world_model/standalone_validation.json`。']
 if (ctx.out/'verification/native_projection_occlusion.json').exists():lines += ['- 原生光栅化集成检查通过：非中心主点 K 的投影中心与光栅峰值一致；同视线后方高斯不参与可见投票。记录为 `verification/native_projection_occlusion.json`。']
 if (ctx.out/'inspection.json').exists():
  lines+=['','## 实际可视化检查','']+[f'- {v}' for v in read(ctx.out/'inspection.json')['findings']]
 (ctx.out/'EXPERIMENT_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 for prefix,stages in [('M2_object_modeling',[s for s in STAGES if s.startswith('M2')]),('M3_semantic_fusion',[s for s in STAGES if s.startswith('M3')])]:write(ctx.out/prefix/'summary.json',{s:rows.get(s,{'status':'not_run'}) for s in stages})
 return ctx.out/'EXPERIMENT_REPORT.md'

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--config',default='configs/industrial_world_model.json');a=p.parse_args();print(run(Context(a.config)))
