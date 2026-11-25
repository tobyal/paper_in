"""Finish exports and official queries after the isolated full graph succeeds."""
import concurrent.futures,json,pathlib,shutil,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/relags_obb_repair_r1';BASE=ROOT/'outputs/relags_baseline'
assert json.loads((OUT/'08_scene_graph/metrics/obb_repair.json').read_text())['status']=='completed'
audit=json.loads((OUT/'08_scene_graph/data/audit_latest.json').read_text())['directory']
def run(stage,job,cmd,expect,inputs):
    args=[sys.executable,str(ROOT/'scripts/run_stage_repair.py'),'--stage',stage,'--job',job,'--cwd','.']
    for p in inputs:args+=['--input',str(p)]
    for p in expect:args+=['--expect',str(p)]
    subprocess.run(args+['--']+list(map(str,cmd)),cwd=ROOT,check=True)
q=OUT/'09_relational_query';oldq=BASE/'09_relational_query'
for folder in ['data','visualizations']:
    for source in sorted((oldq/folder).glob('open_*')):
        target=q/folder/source.name
        if not target.exists():target.symlink_to(source.resolve())
shutil.copy2(oldq/'metrics/query_open_summary.json',q/'metrics/query_open_summary.json')
(q/'metrics/open_query_reuse.json').write_text(json.dumps({'status':'reused_not_rerun','queries':12,'source':str(oldq),'reason':'CLIP NAG, Gaussian scene, query configuration and all open-query inputs are unchanged. Only six relational queries are newly executed in R1.'},indent=2))
jobs=[
('08_scene_graph','export_full_graph',[sys.executable,ROOT/'scripts/export_scene_graph.py','--audit',audit,'--output',OUT/'08_scene_graph'],[OUT/'08_scene_graph/metrics/scene_graph_summary.json'],[ROOT/'scripts/export_scene_graph.py']),
('08_scene_graph','project_full_graph',[sys.executable,ROOT/'scripts/project_scene_graph.py','--audit',audit,'--gaussians',OUT/'08_scene_graph/data/model/point_cloud/iteration_0/point_cloud.ply','--output',OUT/'08_scene_graph'],[OUT/'08_scene_graph/metrics/graph_projection_summary.json'],[ROOT/'scripts/project_scene_graph.py']),
('09_relational_query','six_relational_queries',[sys.executable,ROOT/'scripts/query_baseline.py','--clip-model',BASE/'05_hierarchical_grouping/data/model','--graph-model',OUT/'08_scene_graph/data/model','--output',q,'--mode','relational'],[q/'metrics/query_relational_summary.json',q/'metrics/query_summary.json'],[ROOT/'scripts/query_baseline.py',ROOT/'configs/industrial_queries.json',OUT/'08_scene_graph/data/model/jina_edges_predicted.pt'])]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    tasks=[pool.submit(run,*job) for job in jobs]
    for task in tasks:task.result()
print('Full graph exports and all six official relational queries completed')
