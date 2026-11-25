#!/usr/bin/env python3
"""Stage entry points. Uses official algorithms with serialization and interface patches."""
import argparse,json,os,pathlib,subprocess,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
STAGES=['00_data_check','01_gaussian_scene','02_image_encoding','03_gaussian_pruning','04_superpoint_partition','05_hierarchical_grouping','06_semantic_aggregation','07_object_part_modeling','08_scene_graph','09_relational_query']
def stage(i):return ROOT/'outputs/relags_baseline'/STAGES[i]
def model(i):return stage(i)/'data/model'
def run(i,job,cmd,expect,inputs=(),cwd='ReLaGS'):
    c=[sys.executable,str(ROOT/'scripts/run_stage.py'),'--stage',STAGES[i],'--job',job,'--cwd',cwd]
    for x in inputs:c+=['--input',str(x)]
    for x in expect:c+=['--expect',str(x)]
    try:subprocess.run(c+['--']+list(map(str,cmd)),check=True,cwd=ROOT)
    finally:subprocess.run([sys.executable,str(ROOT/'scripts/update_report.py')],cwd=ROOT)
def done(i,observations):
    (stage(i)/'status.json').write_text(json.dumps({'status':'completed','observations':observations},indent=2,ensure_ascii=False))
    subprocess.run([sys.executable,str(ROOT/'scripts/update_report.py')],cwd=ROOT)
def prepare(i,source_iteration,src):
    d=model(i);d.mkdir(parents=True,exist_ok=True);pc=d/'point_cloud';pc.mkdir(exist_ok=True)
    dest=pc/f'iteration_{source_iteration}';target=src/'point_cloud'/f'iteration_{source_iteration}'
    assert (target/'point_cloud.ply').is_file(),str(target)
    if not dest.exists():dest.symlink_to(os.path.relpath(target,pc),target_is_directory=True)
    cfg=dict(source_path=str(ROOT/'data'),model_path=str(d),images='images',resolution=1,sh_degree=3,eval=True,white_background=False,data_device='cpu')
    (d/'cfg_args').write_text('Namespace('+', '.join(f'{k}={v!r}' for k,v in cfg.items())+')')
    return d
def execute(i):
    if i==0:
        run(0,'scene_audit',['python',ROOT/'scripts/audit_scene.py'],[stage(0)/'metrics/scene_audit.json',stage(1)/'data/compatibility_audit.json'],[ROOT/'scripts/audit_scene.py',stage(0)/'data/migration_manifest.json'],cwd='.')
    elif i==1:
        d=model(1);d.mkdir(parents=True,exist_ok=True)
        cmd=['python','train.py','-s',ROOT/'data','-m',d,'--eval','-r','2','--iterations','30000','--save_iterations','7000','30000','--test_iterations','7000','30000','--checkpoint_iterations','7000','15000','30000','--ip','127.0.0.1','--port','16926']
        checkpoints=sorted(d.glob('chkpnt*.pth'),key=lambda p:int(p.stem.removeprefix('chkpnt')))
        if checkpoints and not (d/'point_cloud/iteration_30000/point_cloud.ply').exists():cmd+=['--start_checkpoint',checkpoints[-1]]
        run(1,'train_2dgs',cmd,[d/'point_cloud/iteration_30000/point_cloud.ply',d/'chkpnt30000.pth'],[ROOT/'external/2d-gaussian-splatting/train.py',ROOT/'data/scene_information/camera_split.json',stage(0)/'data/migration_manifest.json'],cwd='external/2d-gaussian-splatting')
        run(1,'render_2dgs',['python',ROOT/'scripts/render_views.py','--model',d,'--iteration','30000','--output',stage(1)/'visualizations/reconstruction','--all-test'],[stage(1)/'visualizations/reconstruction/metrics.json'],[d/'point_cloud/iteration_30000/point_cloud.ply',ROOT/'scripts/render_views.py'])
        done(1,'官方 2DGS 完成 30000 步并保存检查点；44 留出视角完成官方 ReLaGS 渲染器验证。重建实际质量见可视化和指标。')
    elif i==2:
        out=stage(2)/'data/language_features';out.mkdir(parents=True,exist_ok=True)
        link=ROOT/'data/language_features'
        if not link.exists():link.symlink_to(os.path.relpath(out,link.parent),target_is_directory=True)
        run(2,'sam_clip',['python','scripts/image_encoding.py','--source_path',ROOT/'data','--save_dir',out,'--sam_ckpt_path',ROOT/'models/sam/sam_vit_h_4b8939.pth'],[out/'frame_000350_f.npy',out/'frame_000350_s.npy'],[ROOT/'ReLaGS/scripts/image_encoding.py',ROOT/'models/openclip_vit_b16/open_clip_pytorch_model.bin',ROOT/'models/sam/sam_vit_h_4b8939.pth'])
        run(2,'verify_encoding',['python',ROOT/'scripts/verify_encoding.py'],[stage(2)/'metrics/encoding_verification.json'],[ROOT/'scripts/verify_encoding.py',out/'frame_000350_f.npy'],cwd='.')
        # OpenSeg has its own independent command after validating the official model interface.
    elif i==3:
        d=prepare(3,30000,model(1))
        run(3,'mwp',['python','max_weight_pruning.py','-s',ROOT/'data','-m',d,'-r','1','--contribution_threshold','0.0005'],[d/'point_cloud/iteration_0/point_cloud.ply',d/'removed_gaussians.ply',stage(3)/'data/audit_latest.json'],[model(1)/'point_cloud/iteration_30000/point_cloud.ply',ROOT/'ReLaGS/max_weight_pruning.py'])
        run(3,'render_pruned',['python',ROOT/'scripts/render_views.py','--model',d,'--iteration','0','--output',stage(3)/'visualizations/pruned','--all-test'],[stage(3)/'visualizations/pruned/metrics.json'],[d/'point_cloud/iteration_0/point_cloud.ply',ROOT/'scripts/render_views.py'])
        run(3,'compare_pruning',['python',ROOT/'scripts/compare_pruning.py'],[stage(3)/'metrics/pruning_comparison.json'],[stage(1)/'visualizations/reconstruction/metrics.json',stage(3)/'visualizations/pruned/metrics.json',ROOT/'scripts/compare_pruning.py'],cwd='.')
        done(3,'已保存最大贡献、保留/移除索引、两组 PLY 和 44 留出视角。细结构损失需结合裁剪前后统一相机比较。')
    elif i==4:
        d=prepare(4,0,model(3))
        run(4,'neighbors',['python','sp_partition.py','-m',d,'--iteration','0','-a'],[d/'neighbor.pt'],[model(3)/'point_cloud/iteration_0/point_cloud.ply',ROOT/'ReLaGS/sp_partition.py'])
        run(4,'initial_partition_diagnostic',['python','sp_partition.py','-m',d,'--iteration','0','-a','-k','neighbor.pt','--pcp_regularization','0.1','--pcp_spatial_weight','0.1'],[d/'nag-l1.pt'],[d/'neighbor.pt',ROOT/'ReLaGS/sp_partition.py'])
        run(4,'export_initial_partition',['python',ROOT/'scripts/export_hierarchy.py','--model',d,'--labels',d/'nag-l1.pt','--output',stage(4)],[stage(4)/'metrics/hierarchy_statistics.json'],[d/'nag-l1.pt',ROOT/'scripts/export_hierarchy.py'])
        run(4,'export_id_projections',['python',ROOT/'scripts/export_id_projections.py','--model',d,'--labels',d/'nag-l1.pt','--output',stage(4)],[stage(4)/'metrics/id_projection_summary.json'],[d/'nag-l1.pt',ROOT/'scripts/export_id_projections.py'])
        done(4,'官方初始邻接图完成；额外保存同一官方 Cut Pursuit 在原始邻接上的诊断划分。此诊断划分不替代 Stage 05 的重加权划分。')
    elif i==5:
        # Execution scheduling only: the dense semantic maps and the OpenSeg
        # encoder share GPU 3. Let that independent encoder release its memory.
        encoder_status=stage(2)/'metrics/openseg_all.json'
        announced=False
        while encoder_status.exists():
            encoding=json.loads(encoder_status.read_text())
            if encoding.get('status')!='running':break
            try:os.kill(encoding['pid'],0)
            except ProcessLookupError:break
            if not announced:
                print('Waiting for the current OpenSeg encoder to release GPU 3 before hierarchy processing.',flush=True)
                announced=True
            time.sleep(20)
        d=prepare(5,0,model(3));nb=d/'neighbor.pt'
        if not nb.exists():nb.symlink_to(os.path.relpath(model(4)/'neighbor.pt',d))
        run(5,'graph_reweight',['python','graph_weight.py','-s',ROOT/'data','-m',d,'--iteration','0','-r','1','--config','configs/lerf.yml','--level','1'],[d/'neighbor_new.pt'],[nb,ROOT/'ReLaGS/graph_weight.py',ROOT/'ReLaGS/configs/lerf.yml',stage(2)/'metrics/encoding_verification.json'])
        run(5,'reweighted_partition',['python','sp_partition.py','-m',d,'--iteration','0','-a','-k','neighbor_new.pt','--pcp_regularization','0.1','--pcp_spatial_weight','0.1'],[d/'nag-l1.pt'],[d/'neighbor_new.pt',ROOT/'ReLaGS/sp_partition.py'])
        run(5,'hierarchy_clip_rofa',['python','merge_proj.py','-s',ROOT/'data','-m',d,'--iteration','0','-r','1','--thres_connect','0.9,0.7,0.7','--thres_merge','20','--tau','3','--vlm_type','clip'],[d/'sai_nag_3.0.pt'],[d/'nag-l1.pt',ROOT/'ReLaGS/merge_proj.py',stage(2)/'metrics/encoding_verification.json'])
        run(5,'export_hierarchy',['python',ROOT/'scripts/export_hierarchy.py','--model',d,'--labels',d/'sai_nag_3.0.pt','--output',stage(5)],[stage(5)/'metrics/hierarchy_statistics.json'],[d/'sai_nag_3.0.pt',ROOT/'scripts/export_hierarchy.py'])
        run(5,'export_id_projections',['python',ROOT/'scripts/export_id_projections.py','--model',d,'--labels',d/'sai_nag_3.0.pt','--output',stage(5)],[stage(5)/'metrics/id_projection_summary.json'],[d/'sai_nag_3.0.pt',ROOT/'scripts/export_id_projections.py'])
        done(5,'按官方顺序完成邻接重加权、Cut Pursuit 和三级合并；各层投影标签、邻接、成员与统一相机颜色渲染已保存。')
    elif i==6:
        verification=json.loads((stage(2)/'metrics/openseg_verification.json').read_text());assert verification['status']=='verified' and verification['images']==350
        d=prepare(6,0,model(3));n=d/'nag-l1.pt'
        if not n.exists():n.symlink_to(os.path.relpath(model(5)/'nag-l1.pt',d))
        run(6,'hierarchy_openseg_rofa',['python','merge_proj.py','-s',ROOT/'data','-m',d,'--iteration','0','-r','1','--thres_connect','0.9,0.7,0.7','--thres_merge','20','--tau','3','--vlm_type','openseg'],[d/'sai_nag_openseg.pt'],[n,ROOT/'ReLaGS/merge_proj.py',stage(2)/'metrics/openseg_verification.json'])
        for vlm in ['clip','openseg']:
            sources=sorted((stage(6)/'data').glob(f'*/{vlm}_level_3_raw_observations.pt'));assert sources
            source=sources[-1].parent;out=stage(6)/'data/replay'
            run(6,f'replay_{vlm}',['python',ROOT/'scripts/replay_rofa.py','--observations',source,'--output',out,'--vlm',vlm],[out/f'{vlm}_replay_metrics.json'],[source/f'{vlm}_level_3_raw_observations.pt',ROOT/'scripts/replay_rofa.py'])
        run(6,'visualize_rofa',['python',ROOT/'scripts/visualize_rofa.py','--model',d],[stage(6)/'metrics/rofa_summary.json'],[d/'sai_nag_openseg.pt',model(5)/'sai_nag_3.0.pt',ROOT/'scripts/visualize_rofa.py'])
        done(6,'CLIP 和 OpenSeg 均通过官方 ROFA；保留原始多视角观测及异常值决策，单独重放与原结果数值一致。')
    elif i==7:
        for vlm,src,name in [('clip',model(5),'sai_nag_3.0.pt'),('openseg',model(6),'sai_nag_openseg.pt')]:
            out=stage(7)/vlm
            run(7,f'export_{vlm}',['python',ROOT/'scripts/export_hierarchy.py','--model',src,'--labels',src/name,'--output',out],[out/'metrics/hierarchy_statistics.json'],[src/name,ROOT/'scripts/export_hierarchy.py'])
            run(7,f'export_{vlm}_ids',['python',ROOT/'scripts/export_id_projections.py','--model',src,'--labels',src/name,'--output',out],[out/'metrics/id_projection_summary.json'],[src/name,ROOT/'scripts/export_id_projections.py'])
        run(7,'compare_branches',['python',ROOT/'scripts/compare_hierarchy_branches.py'],[stage(7)/'metrics/branch_comparison.json'],[model(5)/'sai_nag_3.0.pt',model(6)/'sai_nag_openseg.pt',ROOT/'scripts/compare_hierarchy_branches.py'],cwd='.')
        done(7,'对象/部件层级为官方分组导出，不包含人为纠正。两种特征分支均保存成员索引、父子关系、特征统计、PLY 和相同参考相机图。')
    elif i==8:
        d=prepare(8,0,model(3));n=d/'sai_nag_openseg.pt'
        if not n.exists():n.symlink_to(os.path.relpath(model(6)/'sai_nag_openseg.pt',d))
        run(8,'predict_graph',['python','predict_3d_scene_graph.py','--root_pred',d,'--iteration','0','--vlm_type','openseg','--neighbor_thresh','5.0','--checkpoint',ROOT/'models/relags/graph_transformer_512_80.pth'],[d/'jina_edges_predicted.pt',d/'combined_edges_predicted.pt'],[n,ROOT/'ReLaGS/predict_3d_scene_graph.py',ROOT/'models/relags/graph_transformer_512_80.pth'])
        source=pathlib.Path(json.loads((stage(8)/'data/audit_latest.json').read_text())['directory'])
        run(8,'export_graph',['python',ROOT/'scripts/export_scene_graph.py','--audit',source,'--output',stage(8)],[stage(8)/'metrics/scene_graph_summary.json'],[source/'level_3_edge_predictions.pt',ROOT/'scripts/export_scene_graph.py'],cwd='.')
        run(8,'project_graph',['python',ROOT/'scripts/project_scene_graph.py','--audit',source,'--gaussians',model(3)/'point_cloud/iteration_0/point_cloud.ply','--output',stage(8)],[stage(8)/'metrics/graph_projection_summary.json'],[source/'level_3_edge_predictions.pt',source/'level_2_pre_obb.pt',ROOT/'scripts/project_scene_graph.py',ROOT/'configs/reference_views.json'],cwd='.')
        done(8,'官方 GNN 关系推理完成，原始边向量、27 类余弦分数和 top3 已保存。图中关系属于预测，不是工业场景真值。')
    elif i==9:
        common=['python',ROOT/'scripts/query_baseline.py','--clip-model',model(5),'--graph-model',model(8),'--output',stage(9)]
        run(9,'open_vocabulary_queries',common+['--mode','open'],[stage(9)/'metrics/query_open_summary.json'],[model(5)/'sai_nag_3.0.pt',ROOT/'scripts/query_baseline.py',ROOT/'configs/industrial_queries.json'])
        run(9,'relational_queries',common+['--mode','relational'],[stage(9)/'metrics/query_relational_summary.json'],[model(8)/'sai_nag_openseg.pt',model(8)/'jina_edges_predicted.pt',ROOT/'scripts/query_baseline.py',ROOT/'configs/industrial_queries.json'])
        assert json.loads((stage(9)/'metrics/query_summary.json').read_text())['status']=='executed'
        done(9,'固定工业对象/部件与关系查询已调用官方选择函数。保存全量分数、候选、索引、三维子集及统一视角；空结果与低阈值回退原样记录。')
    else:raise ValueError('This stage is executed by its specific export/graph/query entry point; see report')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',type=int,nargs='+',required=True);a=p.parse_args()
    for s in a.stage:execute(s)
