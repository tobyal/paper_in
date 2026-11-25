"""Generate an honest live M0 status report without treating test flags as human truth."""
import json
from .settings import ROOT, ASSETS
from .validation import quality
from .storage import Store, now


def generate():
    s=Store(ROOT).read();images={x['image_id']:x for x in json.loads((ASSETS/'images.json').read_text())}
    q=quality(s,ROOT,images)
    lines=['# M0 数据状态报告','',f'生成时间：{now()}；数据修订：r{s["revision"]}。','',
           '本报告反映当前正式工作目录的实际记录。自动测试副本位于 logs/m0_contract_qa_*，其确认标志只验证软件状态转换，不是人工真值。','',
           '| 步骤 | 人工完成状态 | 自动检查阻断项 |','|---|---|---|']
    for step in q['steps']:lines.append(f'| {step["step"]:02d} | {"完成" if step["complete"] else "待人工标注 / 复核"} | {step["errors"]} |')
    lines+=['','## 实际数据',f'- 对象：{q["counts"]["objects"]}；人工确认对象：{q["counts"]["confirmed_objects"]}。',
            f'- 建模掩膜：{q["counts"]["prior_masks"]}；留出掩膜：{q["counts"]["heldout_masks"]}。',
            f'- 可冻结：{q["can_freeze"]}；最近冻结版本：{s["last_frozen_version"] or "无"}。','',
            '## 待处理项']
    lines += [f'- Step {i["step"]} [{i["severity"]}] {i["message"]}' for i in q['issues']]
    lines+=['','## 数据边界','- priors/ 仅供 M1–M5 建模读取；ground_truth/ 仅供独立评价读取。',
            '- 基础几何、COLMAP、原始划分和 SAM 权重的来源校验保存在 .assets/source_manifest.json。',
            '- 未继承旧 SAM/语言特征/分组/对象定位/关系/地面/区域标注。',
            '- 所有候选描述和掩膜仍需真实人工审核。运行通过不等于标注正确。','']
    (ROOT/'M0_REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    return q


if __name__=='__main__':print(json.dumps(generate(),ensure_ascii=False,indent=2))
