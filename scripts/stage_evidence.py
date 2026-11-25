"""Only describe metrics that actually exist; never promote a planned artifact to a result."""
import json,pathlib
def read(p):
    try:return json.loads(p.read_text())
    except (FileNotFoundError,json.JSONDecodeError):return None
def evidence(root,i,base):
    lines=[]
    if i==0:
        m=read(base/'data/migration_manifest.json')
        if m:lines.append(f'已记录 {len(m)} 个复制文件，共 {sum(x["bytes"] for x in m):,} 字节；各文件源/目标/SHA256/用途见根目录 TSV。原视频、350 张原始提取图、350 张去畸变图及 COLMAP 均为独立副本。')
        lines.append('未找到原论文完整正文；保留已有报告、图表和实验说明，不补造相机/无人机型号或工业设备规格。旧语义与编辑结果仅作参考，不作为新模块输入。')
    elif i==1:
        for folder,label in [('checkpoint7000','7000 步预览（非最终结果）'),('reconstruction','30000 步最终重建')]:
            m=read(base/'visualizations'/folder/'metrics.json')
            if m:lines.append(f'{label}：{m["gaussians"]:,} 个二维高斯；{m["views"]} 个相机；平均 PSNR={m["mean_psnr"]:.4f} dB，SSIM={m["mean_ssim"]:.5f}。输入 RGB 归一化到 [0,1]；官方函数直接比较浮点渲染与真值，使用约半分辨率相机，计算指标前未将渲染量化为 PNG。')
        lines.append('首次训练在 7000 步可视化处因 Matplotlib 移除 tostring_rgb 失败；只更换画布 RGB 读取 API 后重新训练，原失败日志保留。此时尚未保存首次 7000 检查点，未伪称从失败点恢复。')
    elif i==2:
        pairs=list((base/'data/language_features').glob('*_f.npy'));complete=sum((p.parent/(p.name[:-6]+'_s.npy')).exists() for p in pairs)
        openseg=len(list((base/'data/language_features_openseg').glob('*_f_openseg.npy')))
        lines.append(f'当前实际文件对：SAM/CLIP {complete}/350；OpenSeg {openseg}/350。最终完整性以 encoding_verification.json / openseg_verification.json 为准。')
        m=read(base/'metrics/encoding_diagnostics.json') or read(base/'metrics/encoding_diagnostics_partial.json')
        if m:lines.append(f'已诊断 {m["images"]} 帧：SAM 标签图中原本无像素的掩膜 {m["masks_already_absent"]} 个；半分辨率映射额外丢失 {m["masks_lost_to_half_resolution"]} 个。保存逐掩膜索引、丢失位置图和 OpenSeg 特征 PCA 显示图。PCA 仅用于显示，不进入算法。')
        lines.append('TensorFlow 2.15.1 与本地 cuDNN 8.7 不匹配的失败已保留；2.14.1/CUDA 11.8 单帧验证通过。先在三张 GPU 编码，几何阶段结束后改为四份独立帧清单；已完成文件对复用。所有参数与逐帧计算保持一致，切换记录与中断日志完整保留。')
    elif i==3:
        m=read(base/'metrics/pruning_comparison.json')
        if m:lines.append(f'裁剪前 {m["gaussians_before"]:,}，保留 {m["kept"]:,}，移除 {m["removed"]:,}（{m["removed_fraction"]:.2%}）。44 视角 PSNR {m["before_psnr"]:.4f} → {m["after_psnr"]:.4f} dB；SSIM {m["before_ssim"]:.5f} → {m["after_ssim"]:.5f}。逐相机最大贡献、总贡献、索引与删除 PLY 均保留。')
        lines.append('裁剪前后图与放大差值只能反映重建变化；细管/细杆是否被误删还需结合图像和被删高斯检查，不能由总体 PSNR 代替细结构真值。')
    elif i in [4,5,7]:
        paths=[base/'metrics/hierarchy_statistics.json'] if i!=7 else [base/v/'metrics/hierarchy_statistics.json' for v in ['clip','openseg']]
        for p in paths:
            m=read(p)
            if m:
                lines.append(f'统计来源 `{p.relative_to(root)}`：')
                for x in m['levels']:lines.append(f'- 层 {x["level"]}：{x["clusters"]} 个组，中位成员数 {x["cluster_size_quantiles"][2]:.1f}；小于 20 点的组 {x["clusters_under_20"]}；非唯一父组 {x["non_unique_parent_count"]}。')
        lines.append('分组数、组大小与父子一致性为诊断量；尚不能单独判定设备过分割/欠分割。对象级与部件级指官方层次候选，不把几何组直接当作已确认设备实例。')
        if i==7:
            m=read(base/'metrics/branch_comparison.json')
            if m:
                for x in m['levels']:lines.append(f'CLIP/OpenSeg 分支层 {x["level"]}：逐点标签完全相同={x["identical_labels"]}；忽略标签编号后的划分相同={x["same_partition_up_to_label_permutation"]}。不跨分支套用未经核验的组 ID。')
    elif i==6:
        m=read(base/'metrics/rofa_summary.json')
        if m:
            for x in m:lines.append(f'{x["vlm"]} 层 {x["level"]}：{x["observations"]} 条多视角观测，保留 {x["retained"]}，排除 {x["rejected"]}；无观测组 {x["empty_clusters"]}。')
        for vlm in ['clip','openseg']:
            replay=read(base/'data/replay'/f'{vlm}_replay_metrics.json')
            if replay:lines.append(f'{vlm} 官方 ROFA 独立重放最大绝对误差 {max(x["max_abs_replay_error"] for x in replay):.8g}。')
        lines.append('保留率颜色图统一使用原参考相机；紫红色表示没有语义观测。离群值少不代表特征准确，工业重复设备和遮挡仍需检查。')
    elif i==8:
        audit=read(base/'metrics/obb_failure_audit.json')
        if audit:
            for x in audit['levels']:lines.append(f'官方 OBB 逐组诊断：层 {x["level"]} 共 {x["total_clusters"]} 个组，成功 {x["valid_obbs"]}，失败 {x["failed_obbs"]}。失败点云、原始高斯索引与异常见 `diagnostics/obb/`。')
        root=read(base/'diagnostics/root_only/metrics/scene_graph_summary.json')
        if root:
            for x in root:lines.append(f'独立根层诊断（不代表完整图成功）：{x["nodes"]} 节点，{x["edges"]} 条预测有向边，保留全部分数、JSON、PLY 和八相机投影。位置：`diagnostics/root_only/`。')
        m=read(base/'metrics/scene_graph_summary.json')
        if m:
            for x in m:lines.append(f'层 {x["level"]}：{x["nodes"]} 个节点、{x["edges"]} 条有向边；索引映射恒等={x["index_mapping_identity"]}；top1 关系分布 `{x["top1_relation_counts"]}`。')
        lines.append('只完成权重加载探针时，不算场景图已执行。官方网络在 3DSSG 训练；保留距离阈值 5.0、默认 z 轴重力及原 COLMAP 单位。工业场景缺少公制尺度/重力标定，方向与距离关系的可信度受限，暂不旋转/缩放来改善结果。')
        m=read(base/'metrics/graph_projection_summary.json')
        if m:lines.append('统一参考相机投影已保存：每视角最多显示两端中心均落在画面内的 20 条最高余弦关系边；未做遮挡判断。原始投影、完整边集及图坐标到原 COLMAP 坐标的平移均保留，不用显示筛选替换原图。')
    elif i==9:
        m=read(base/'metrics/query_summary.json')
        if m:
            q=m['queries'];lines.append(f'实际执行 {len(q)} 个查询；空结果 {sum(x.get("empty_result",False) for x in q)}；完整关系查询未执行，其阈值回退统计不适用。保存全量相似度、候选、索引、选中高斯 PLY 和统一相机叠加图。')
        lines.append('保持官方 root/leaf 筛选、相似度间隙切分及关系查询回退规则。空结果不手动补选；低置信回退不解释为确定定位。没有查询真值时不报告定位准确率。')
        blocked=read(base/'metrics/relational_query_blocked.json')
        if blocked:lines.append('六个关系查询未执行：完整 L2/L3 场景图在 OBB 步骤失败，所需关系文件不存在。没有用独立根层诊断冒充完整图。依赖、计划命令及原因见 `metrics/relational_query_blocked.json`。')
        m=read(base/'metrics/floor_marking_confusion.json')
        if m:lines.append(f'实际细粒度问题：floor 与 yellow floor marking 的选中高斯集合 Jaccard={m["prediction_set_jaccard"]:.5f}；第 345 帧两个投影完全一致。该数值是两次预测的重合度，不是真值 IoU；黄色标线在此例未从大块地面中分离。')
    notes=base/'NOTES.md'
    if notes.exists():lines.append(notes.read_text())
    return '\n\n'.join(lines)
