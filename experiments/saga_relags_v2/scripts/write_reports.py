"""Generate traceable reports from actual frozen experiment artifacts."""
from pathlib import Path
import sys,collections,shutil
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from common import *

objects=read(ROOT/'outputs/A/final_summary.json')['objects'];cats=read(ROOT/'world_model/categories.json');cmap={c['category_id']:c for c in cats};a=collections.Counter(o['extraction_status'] for o in objects);recon=collections.Counter(o['reconstruction_status'] for o in objects);b=read(ROOT/'outputs/B/summary.json');c=read(ROOT/'outputs/C/validation.json');d=read(ROOT/'outputs/D/tests.json');checks=read(ROOT/'outputs/validation/final_checks.json');conflicts=read(ROOT/'outputs/A/extractions/refined/conflicts.json');frozen=read(ROOT/'outputs/A/frozen_manifest.json');provenance=read(ROOT/'inputs/provenance.json');regression=read(ROOT/'outputs/D/nearest_regressions.json')[0];runs=[]
for path in sorted((ROOT/'logs').glob('*/*/result.json')):
    r=read(path);r['log']=str((path.parent/'run.log').relative_to(ROOT));runs.append(r)
write(ROOT/'outputs/validation/runtime_complete.json',runs)
def md(path,text):
    path=ROOT/path;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text.strip()+'\n')
table=['|设备ID / 图中编号|设备名称|类别|有效真实 / 虚拟|提示点|M0候选|最终高斯|重建状态|提取状态|精细可用|额外优化|主要问题|','|---|---|---|---:|---:|---:|---:|---|---|---|---|---|']
for i,o in enumerate(objects,1):table.append('|'+ '|'.join([o['object_id']+f' / O{i:02d}',o['name_zh'],cmap[o['category_id']]['name_zh'],f"{o['effective_real_views']} / {o['effective_virtual_views']}",str(o['prompt_clicks']),str(o['candidate_gaussians']),str(o['gaussian_count']),o['reconstruction_status'],o['extraction_status'],'是' if o['fine_instance_available'] else '否','是' if o['extra_optimization'] else '否',o['note_zh']])+'|')
cat_table=['|类别|数量|可用|局部可用|待改进|重建状态统计|','|---|---:|---:|---:|---:|---|']
for cat in cats:
    rows=[o for o in objects if o['category_id']==cat['category_id']];count=collections.Counter(o['extraction_status'] for o in rows);rs=dict(collections.Counter(o['reconstruction_status'] for o in rows));cat_table.append(f"|{cat['name_zh']}|{len(rows)}|{count['usable']}|{count['partial_usable']}|{count['needs_improvement']}|{rs}|")
reused='、'.join(o['name_zh'] for o in objects if o['reused_v1']);difficult='、'.join(o['name_zh'] for o in objects if not o['fine_instance_available'])
report=f'''# SAGA + ReLaGS 工业世界模型 v2：实际实验报告

本次按照 `docs/USER_REQUEST.md` 完整版本执行。33/33 设备均实际处理；{a['usable']} 个 usable、{a['partial_usable']} 个 partial_usable、{a['needs_improvement']} 个 needs_improvement、{a['failed']} 个 failed。30 个精细或局部实例参与常规展示，33 个设备均参与身份及关系查询。无新 SAGA 训练，无几何补造。

审核属于 **Codex 对训练图像、原生3DGS及三向提取结果的视觉检查**，不是独立人工真值。0 个 failed 表示本轮最终没有完全空或完全失去身份的提取结果，并不表示33个完美成功；3个待改进结果明确停用常规精细展示。原始 M0 r29 仍为 draft，没有擅自变更确认状态。

## 1. 输入、冻结与工程保护

- 复用 v1 官方 SAGA iteration_10000、32维亲和特征、尺度门控及K=16平滑结果；原始 1,828,777 个3DGS高斯行号精确对应。关键 SHA256 见 [provenance](inputs/provenance.json)。
- M0 r29 的33对象、8类别、工业坐标保持不变。+X为右、+Y为前、+Z为上；距离均为SfM相对单位，不能解释为米。
- v1亲和训练含74视角（57真实、17虚拟），新提示允许取306训练图像或其既有完整场景虚拟观测。实际提示去重视角 {checks['unique_prompt_views']}；按对象计的视角使用次数：{checks['per_object_view_uses']}。这两种统计不能混为新增训练样本数量。
- 44留出图像没有用于提示、门控或阈值。A冻结时间为 `{frozen['frozen_utc']}`；之后只用留出视角生成最终展示。基础3DGS未重新训练，不声称它符合本次新划分的独立重建评测。
- {checks['protected_file_count']} 个既有文件大小及mtime复核无变化，7个关键文件SHA256不变；全部33个输出PLY逐字段等于对应原始高斯子集，最终ID无重复，合计 {checks['union_gaussian_count']:,} 个高斯。验证见 [final_checks](outputs/validation/final_checks.json)。

## 2. A：全33设备与一轮有限改进

原来9个可用实例的Gaussian ID逐项保持完全相同：{reused}。此前未处理23个及失败料架04重新生成训练视角SAM参考；真实最多3、虚拟最多2，按可见贡献、新增可见候选及方向差异选择，不凑数。新参考采用3×3区域分散安全正提示，通常每图最多7点；有效点受SAM及候选贡献约束。

首轮统一 `(cosine+1)/2 > 0.85` 得到32个非空对象，料架02因掩膜把杆间空洞包入、候选精度门限拒绝全部参考而为空。保留这次初始结果和日志。检查后只对料架02将参考掩膜候选精度门限从0.50放宽至0.40；实际点仍需候选贡献>0.75。frame_000205/207共14点得到14,008个高斯，局部料架身份清楚，判为partial_usable。

料架04的5张初始SAM掩膜都混入相邻灰箱。记录并使用Codex在两张既有训练虚拟图上的10个安全中心料架点（11个提议点中1个贡献不足未用），不是完全自动流程，也不是人工真值。v1为29,926个高斯，v2首轮39,455，修正后25,750；视觉上减少两侧箱体，中央结构仍有缺失，判为partial_usable。具体相机、像素和原因见 [refinement配置](configs/refinement.json) 与 `outputs/A/refinement_prompts/`。

对料架04、蓝箱01/02固定提示比较0.80/0.85/0.90；降低阈值引入漂浮及邻近材料，提高阈值损失箱面和细杆，未见明确净收益。料架04门控±0.1的外观变化很小，继续保留v1尺度估计。没有启动额外训练、候选框扩展、深度尺度新算法或组合参数搜索。诊断阈值图使用已存float16亲和度，边界点可能与正式float32筛选略有差异；它们不是最终实例，不宣称数量即质量。

33对象之间有 {conflicts['conflicting_gaussians']:,} 个冲突Gaussian ID。按存储float16亲和度最大值分配，相等时固定M0顺序。料架08失去6479、料架09失去6895、物料车04失去2个，9个原可用对象没有改变。不同门控/提示的分数尚未校准，料架08/09相邻区域的归属仍需独立核查，不能把无重复当作分割正确率。

所有初始、修正、阈值及门控尝试均保留。最终 [33设备图集](docs/GALLERY.md) 每台有训练RGB、同相机完整原生渲染、M0粗裁剪、SAGA斜/侧/顶视与真实三维投影。M0粗裁剪不是真值。

## 3. 按类别与逐设备结果

全局重建状态：{dict(recon)}。细杆、镂空结构及背侧缺失常已存在于原始3DGS；同一对象可以重建局部而提取可用。下面的状态分别判断，不能合并成单一成功率。

{chr(10).join(cat_table)}

{chr(10).join(table)}

## 4. B：类别共享语义

保留8类、512维CLIP文本/视觉原型、中英文名称及别名。对原有44张M0框裁剪作受控比较；其中26张来自usable设备，使用A的完整场景真实贡献图把背景保留30%并向中灰弱化，其他18张保持原裁剪。保存原图、软背景图、贡献图和两套特征。

通过与D完全相同的 `WorldModel.query()` 验证：16个名称/别名、8个未列入别名的合理英文描述、7个目录外表达，共31项。原始与软背景均31/31满足预期，未体现额外收益，因此保留v1原型。最终解析器再次验证31项，并把类别特征矩阵行序反转后验证ID映射，均通过。这是手写功能检查，不是开放词汇准确率。

英文描述使用0.8文本+0.2视觉相似度、最低0.20、首二分差0.015，并与少量目录外概念文本竞争，以避免把叉车/机器人/人等强行归入8类。该拒识方式是有限工程规则，仍可能拒绝合理长描述或误接纳未覆盖概念。中文依赖已知别名，不承诺通用中文语义推理。

## 5. C：完整设备关系图

保留33节点、2020有向几何边：{c['relation_counts']}。独立从M0角点和中心重新计算期望集合，与v1几何边完全一致；左右/前后互逆、near对称、节点ID、自排除、各类别nearest全部通过。near继续使用AABB间隔<0.35，方向间隔0.02，nearest按完整M0中心、并列容差1e-6。

节点补充独立重建/提取状态、工业位置、可用性、ID/PLY路径、质量记录及仅作辅助的精细几何范围。没有用局部实例中心替换M0关系几何。SoM不再运行，不人为添加support/contain等边。独立实例彩色图含30个精细/局部结果；3个待改进对象用明确的M0位置标签保留。完整原生场景图保留其他设备和遮挡。

## 6. D：先定位设备，再检查精细实例

修复v1把实例可用性提前用于候选过滤的问题。类别/身份/关系首先查全部33节点；之后分别返回renderable与unavailable设备。多个同类参照对象采用结果并集；未知身份、参照缺失、不支持关系、关系空结果有独立状态。查询不运行SAM或SAGA。

真实回归例：`{regression['query']}` 返回蓝色箱组01。其M0中心距离为2.32917，另外两组分别6.43633、6.71078（相对单位）；虽精细结果不可用，仍返回正确ID与M0位置，未返回次近箱组。见 [回归证据](outputs/D/nearest_regressions.json)。

实际查询检查 {d['passed']}/{d['total']} 通过，其中真实场景功能案例 {d['real_cases']}、显式合成边界案例 {d['synthetic_cases']}。合成仅验证全不可用状态与并列最近，不当作工业实验数据。另完成18组查询、各2个留出展示视角，包括8类别、最近/左右/前后/near、局部设备、不可用设备和空关系。红色为冻结Gaussian ID在完整场景中的真实贡献>0.5；黄色框仅M0位置，不是SAM或精细实例。

展示相机按冻结结果的可见性选择，不能当作公平固定测试集。另保存固定列表位置0/14/28/43的4个留出相机及33设备，供后续独立标注；当前没有真值掩膜或IoU。世界模型从 `/tmp` 独立运行类别及关系查询已通过。精细实例索引属于本包；大型CLIP、原生PLY和实例PLY用明确只读引用，搬移作业须按README处理这些依赖。

## 7. 需要明确保留的问题

- {difficult}：相邻材料混入、设备边界含糊或跨材质特征选择不足，保留真实PLY和诊断图，精细常规展示关闭。
- 料架02/04、蓝箱02/03、分隔架及工作台等仍有局部缺失。部分属于原重建遮挡/反光，部分与提示、亲和选择混合影响；无法仅凭现有数据精确分解。
- M0为draft先验，框/类别/设备边界没有独立人工认证；部分“料架”框还包围邻近小架或箱组。
- 互斥归属是工程一致性保证，跨门控亲和度不能当校准概率；输出点数、保留比例及非空查询不构成准确率。
- 原生3DGS的未重建背侧/底部不能通过实例分割恢复。没有几何补全或新图像生成。

## 8. 对12项交付问题的回答

1. 全33个均处理，首轮失败及修正结果均存；最终20可用、10局部可用、3待改进。
2. 各类及每台重建/提取状态分别列于第3节。
3. 直接复用9台，见第2节及 `outputs/A/v1_comparison.json`，ID精确相同。
4. 料架02补充有效参考后从空结果恢复，料架04经已记录视觉点减少相邻箱体。
5. 0.80/0.90阈值、门控±0.1和CLIP软背景原型没有明确收益，未替换基线设置。
6. 原重建薄杆断裂、背面空缺、金属/透明区域漂浮在完整原生渲染中已可见，逐对象记录不强行归因。
7. 料架05/07及蓝箱01仍困难；局部可用对象也保留问题说明，没有继续无限优化。
8. 全2020几何边正确保留并独立复算，未因实例缺失删节点。
9. 最近关系候选范围冲突已修复，真实不可用目标回归及合成边界通过。
10. 纯别名/关系查询仅Python+NumPy，世界模型可从其他工作目录独立运行；描述CLIP及渲染有明确大型只读依赖。
11. 33设备M0与SAGA三向对比、v1/v2十台对比、有限参数诊断、完整实例图与关系缩减案例可作为后续论文实验基础。
12. 分割质量、关系正确性、检索泛化及优于ReLaGS的结论仍需独立人工真值、公平固定视角与外部对照；本次没有宣称这些指标。

## 9. 运行证据与资源

所有实际命令、源代码快照、stdout/stderr、退出码、耗时和5秒GPU采样保存在 `logs/<stage>/<UTC timestamp>/`。完整清单见 [runtime](outputs/validation/runtime_complete.json)。GPU采样属于指定整卡（可能含其他进程），不是本任务独占峰值；短运行可能漏采峰值。总运行秒数不包含检查、编程及视觉审核时间。

|运行|退出状态|秒|日志|
|---|---|---:|---|
'''
for r in runs:report+=f"|{r['stage']}|{r['status']}|{r['seconds']:.2f}|[{r['log']}]({r['log']})|\n"
md('EXPERIMENT_REPORT.md',report)
md('README.md',r'''# SAGA + ReLaGS 工业世界模型 v2

服务器：`/mnt/sda/ubuntu/lkx/papers/paper_in/experiments/saga_relags_v2`。

33个工业设备全部处理：20可用、10局部可用、3待改进。8类语义、33节点/2020几何边、先设备后实例的查询逻辑已完成。复用v1 iteration_10000，无重新训练。M0 r29、原生3DGS和旧工程保持只读。

先看 [结果图集](docs/GALLERY.md)、[实验报告](EXPERIMENT_REPORT.md) 和 [修改记录](MODIFICATION_REPORT.md)。这些是Codex视觉审核及工程验证结果，不是独立人工真值。

## 直接查询

```bash
cd /mnt/sda/ubuntu/lkx/papers/paper_in/experiments/saga_relags_v2
PY="$PWD/../saga_relags_v1/envs/saga/bin/python"
PYTHONDONTWRITEBYTECODE=1 "$PY" world_model/query.py --model "$PWD/world_model" \
  --text '距离装配夹具台 01最近的蓝色箱组' --output "$PWD/outputs/manual_query"
```

返回正确设备ID、M0位置、质量状态、可用性、关系证据和可用实例Gaussian IDs。没有可靠精细实例仍返回设备，不替换次近设备。类别与几何查询只需Python/NumPy；英文描述回退还需torch/open_clip及已有CLIP权重。中文仅支持已知名称/别名及限定关系表达。

## 输入与大型只读依赖

`inputs/provenance.json`记录7个关键哈希和版本；`inputs/manifest.json`记录原数据路径。复用v1环境、官方SAGA源码/检查点、M0候选/坐标、74训练视角记录及原始RGB/混合观测。亲和训练未追加样本，44留出只在A冻结后做展示。

`world_model/`复制类别、图、全部33索引和独立query.py。CLIP权重/原生场景用只读符号链接，实例PLY相对链接到本v2输出。纯类别/几何查询可单独搬移包；描述查询需同时携带CLIP权重；可视化仍调用工程已有原生Renderer。此包不宣称包含可搬移CUDA环境。若搬移全实验，应复制所需大型引用并更新链接，而不是改动旧工程。

## 实际运行顺序与复查

本次结果已冻结，不要在当前 `initial` / `refined` 标签上重做提示或调参。新的研究使用新实验目录/标签；只读检查及查询可以直接复用。源代码的实际命令与当次快照全部保存在logs。

1. `scripts/initialize.py`：一次性输入哈希、ID及旧文件保护快照。
2. `src/prepare_references.py`：24对象新SAM参考；9个原可用对象保留原提示。
3. `src/extract_instances.py --tag initial`，`src/inspect_instances.py --tag initial`：33初始提取与三向检查。
4. `scripts/refine_prompts.py`：只对料架02/04做有记录修正。
5. `src/extract_instances.py --tag refined --references outputs/A/refinement_prompts/records.json`；对应inspection。有限比较命令见logs/A_scale_lower、A_scale_upper、A_bounded_comparison。
6. `scripts/freeze_instances.py`：质量记录、9对象复用比较及最终哈希冻结。
7. `src/build_world_model.py`：B原型比较及C完整图验证/打包。
8. `src/test_queries.py`：真实回归与明确标记的合成边界。
9. `src/final_visualizations.py`：全33图集、彩色实例图、完整场景关系和18查询展示。
10. `scripts/validate_final.py`：原文件保护、原始属性、无重复ID、冻结及实际查询接口核验。

运行器例子：

```bash
PYTHONDONTWRITEBYTECODE=1 "$PY" scripts/run_command.py --stage query_recheck --gpu 0 -- "$PY" src/test_queries.py
```

## 数据入口

|内容|路径|
|---|---|
|33最终ID/PLY/亲和度/提示|`outputs/A/extractions/refined/objects/`|
|初始失败及保留尝试|`outputs/A/extractions/initial/`、`scale_lower/`、`scale_upper/`|
|新SAM原始掩膜/相机/点/日志|`outputs/A/reference_prompts/`、`refinement_prompts/`|
|有限参数比较|`outputs/A/bounded_comparison/`|
|最终质量与可用性|`outputs/A/final_summary.json`、`configs/quality_review.json`|
|B真实裁剪及两套特征|`outputs/B/`|
|33节点、2020边及实例彩色PLY|`outputs/C/`、`outputs/C/visualizations/`|
|查询结果、完整贡献、相机与RGB|`outputs/D/query_*/`|
|64查询测试及保护检查|`outputs/D/tests.json`、`outputs/validation/`|
|查阅版图集|`docs/figures/`、`docs/GALLERY.md`|

场景使用SfM相对单位。彩色实例PLY仅为展示覆盖颜色，原始实例PLY所有属性严格未改。3个待改进对象只在常规查询展示中关闭精细输出，其尝试结果始终保留。
''')
md('MODIFICATION_REPORT.md',f'''# v2 相对 v1 的修改记录

|修改|原因|实际结果|保留决策|
|---|---|---|---|
|全部33设备处理，9旧实例直接复用|v1只处理10台|23新对象加料架04运行，9台ID完全相同|采用|
|可见贡献/新增覆盖选参考，分散正提示|镂空、多材质提示不足|24对象获得新的可追踪SAM及点；并非保证全成功|采用|
|料架02参考精度0.50→0.40，仅该对象|杆间空洞导致参考全部拒绝|0→14,008高斯，实际局部料架可辨|采用；仍需贡献>0.75|
|料架04两虚拟相机10个Codex审核点|SAM混入邻近箱体|明显减少箱体；仍局部缺失|采用；明确视觉辅助|
|0.80/0.85/0.90阈值对照|检查箱面/背景取舍|0.80增漂浮，0.90失结构|保留0.85|
|料架04门控±0.1|检查尺寸门控影响|变化有限，未见明确收益|保留v1门控|
|33对象冲突统一分配|候选范围重叠|13,376冲突；最终互斥；9旧实例不变|采用，保留跨尺度分数未校准限制|
|实例贡献弱化背景CLIP|减少M0框背景|44裁剪/26修改，31项检查两者相同|保留原始原型|
|B用最终D接口验证|v1验证和运行阈值不同|31项及矩阵乱序测试通过|采用|
|有限目录外拒识与不支持关系状态|避免强行归类/忽略条件|别名、描述、未知、边界通过|采用；不声称通用NLU|
|C更新全部节点属性，保留M0关系|局部精细中心可能偏移|33节点2020边独立复核相同|采用；不运行SoM|
|D先查全部设备再获取实例|原可用性预过滤遗漏真正最近设备|真实蓝箱01案例与64项测试通过|采用|
|全33分类图集与真实3D投影|避免只展示好结果|8类图集、18查询、局部/不可用均保留|采用|

核心SAGA特征、训练、尺度网络、原始高斯均未改。新增代码只在v2；旧工程{checks['protected_file_count']}文件保护验证通过。没有新模型、新CUDA、M0修改、几何补造或自动Git发布。

版本证据：SAGA提交 `2d4c5d77c857c956d747e4775d3d72c4ec5dfe16`，SAM提交 `6fdee8f2727f4506cfbbe553e23b895e27956588`（沿用v1环境）。原代码、许可和既有适配保留于v1 third_party/docs；本v2只引用，不复制训练实现。运行快照见logs。

工程问题与未采用尝试不删除：初始料架02无可接受提示、料架04首轮邻箱混入、蓝箱01阈值尝试无净收益均保留。正式冻结实例与诊断float16阈值结果严格区分。当前仍需改进：{difficult}。
''')
gallery='''# 全33设备与关键结果图集

所有图来自实际RGB或原生3DGS，不使用生成图。质量为Codex视觉检查；M0框不是真值。20 usable、10 partial_usable、3 needs_improvement均列出。

[全部33紧凑总览](figures/all_33_compact.jpg) · [独立实例关系图](figures/instance_graph_compact.jpg) · [工业俯视图](figures/industrial_top_plan.png) · [查询示例](figures/query_examples.jpg)

分类图每行依次：训练RGB、同相机完整原生场景、M0粗候选、SAGA斜视、侧视、顶视、真实三维投影。行首含设备ID和两个独立质量状态。图中O01—O33只用于索引，不修改原设备编号。

|类别|数量|完整对照图|
|---|---:|---|
'''
for cat in cats:gallery+=f"|{cat['name_zh']}|{sum(o['category_id']==cat['category_id'] for o in objects)}|[查看](figures/{cat['category_id']}.jpg)|\n"
gallery+='''
## 场景、关系与v1对照

- [完整原生3DGS场景关系图1](figures/full_scene_graph_01.jpg)、[图2](figures/full_scene_graph_02.jpg)。彩色为实际高斯成员，未删除邻近物体。
- [独立实例斜视](figures/instance_graph_oblique.jpg)、[顶视](figures/instance_graph_top.jpg)。3个不可用对象只标M0位置。
- [v1/v2全部10个原对象对比](figures/v1_v2_comparison.jpg)。9台精确复用，料架04保留修正前后。
- [全部18查询](figures/query_gallery.jpg)、[4个关键查询](figures/query_examples.jpg)。红色是真实三维实例投影，黄色框为M0位置。

## 服务器中间数据入口

以下大型中间结果保留在服务器实验目录，查阅图已复制到本地docs/figures。

- `outputs/A/extractions/initial/`：首轮33对象，含空结果。
- `outputs/A/extractions/refined/objects/<object_id>/`：最终原始ID、native PLY、亲和度、提示特征、相机及全部三向图。
- `outputs/A/reference_prompts/`：新SAM候选、掩膜、可见贡献、参考图及像素点；`refinement_prompts/`为已记录修正。
- `outputs/A/bounded_comparison/`：3对象阈值、料架04门控比较；未采用方案也保留。
- `outputs/B/crop_comparison/`：原裁剪、实例贡献与软背景；`validation.json`为实际query接口结果。
- `outputs/C/visualizations/colored_instance_map.ply`：30可用/局部原始高斯的彩色场景，`colored_map_original_gaussian_ids.npy`保留行号对应。
- `outputs/D/query_*/`：18查询原文/result.json、2相机RGB、投影、贡献数组及冻结索引。空/不可用结果也保留。
- `outputs/D/future_evaluation_protocol.json`：后续固定4留出视角/33设备标注入口，尚无真值。
'''
md('docs/GALLERY.md',gallery)
md('docs/IMPLEMENTATION_NOTES.md','''# 方法与边界

本次读取v1 README、完整实验报告、实施说明、图集、配置、A–D源码、记录及根ReLaGS报告。已有ReLaGS在工业场景表现出层次粗并、细碎部件和语义定位不稳定；这些是本路线采用M0设备身份/范围的背景，不构成v2优于ReLaGS的量化证据。

A沿用冻结官方SAGA32维特征、K16平滑与尺度门控，仅调整参考/提示。候选范围固定M0；0.85为(cos+1)/2阈值。多正点最大值可能被一个污染点影响。料架04使用已记录Codex视觉点，不能称全自动。

B是已知8类共享语言表达，不自动发现对象类别；C以工业空间先验为关系来源，仅参考ReLaGS场景图思路，不声称重新复现其自动关系算法。D受限规则解析，全部M0候选优先，实例可用性仅影响最后的精细几何返回。

原始3DGS、M0、v1训练环境及源文件只读。没有调用外部视觉服务。本包的图像和模型是工业数据，继续保留原项目隐私约束。

图集虚拟相机只是观察冻结实例，全部3D显示仍来自实际高斯。RGB查询投影使用完整原生场景的alpha合成，保留遮挡；没有用二维SAM掩膜替代3D投影。原始实际渲染与相机均保留，compact仅为排版裁剪。
''')
md('world_model/README.md','''# Frozen v2 world model

33 equipment nodes, 8 shared categories, 2020 directed geometric edges. 30 fine/partial instances are eligible for normal rendering; all 33 are eligible for identity/relation queries.

`python query.py --model /absolute/path/world_model --text '距离装配夹具台 01最近的蓝色箱组' --output /absolute/path/result`

Alias/geometry queries need Python and NumPy only, with no import from the original project. Free English descriptions additionally load open_clip/torch and `models/open_clip_pytorch_model.bin`. Index arrays and graph/categories are copied here. `instances/*/object.ply` is a relative reference into the v2 outputs; CLIP/native scene links refer to original read-only large files. Materialize those dependencies if moving the package. Native visualization uses the existing project Renderer, not a bundled portable CUDA environment.

Object quality is Codex visual assessment, not human truth. Distances are SfM relative units. A coarse location is never a substitute fine instance. Queries return both unavailable and renderable object lists. No segmentation runs during queries.
''')
print('Reports written',len(objects),'objects;',len(runs),'logged runs')
