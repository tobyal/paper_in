#!/usr/bin/env python3
"""Final input-copy, isolation and actual-output audit; expected graph failure stays visible."""
import hashlib,json,pathlib,os,datetime
ROOT=pathlib.Path(__file__).resolve().parents[1];BASE=ROOT/'outputs/relags_baseline'
manifest=json.loads((BASE/'00_data_check/data/migration_manifest.json').read_text())
source_names={x['source'] for x in manifest};inventory={}
with (BASE/'00_data_check/data/source_inventory.jsonl').open() as f:
    for line in f:
        if not line.strip():continue
        row=json.loads(line)
        if row['path'] in source_names:inventory[row['path']]=row
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
    return h.hexdigest()
destination_failures=[];source_changes=[];source_stat_unavailable=[]
for row in manifest:
    dest=pathlib.Path(row['destination']);source=pathlib.Path(row['source'])
    if not dest.exists() or dest.stat().st_size!=row['bytes'] or sha(dest)!=row['sha256']:destination_failures.append(str(dest))
    old=inventory.get(str(source))
    if old:
        stat=source.lstat() if old.get('symlink') else source.stat()
        if stat.st_size!=old['bytes'] or stat.st_mtime_ns!=old['mtime_ns']:source_changes.append(str(source))
    else:source_stat_unavailable.append(str(source))
links=[];outside=[]
for folder in ['data','outputs','models']:
    for path,dirs,files in os.walk(ROOT/folder,followlinks=False):
        for name in dirs+files:
            p=pathlib.Path(path)/name
            if not p.is_symlink():continue
            target=p.resolve();item={'path':str(p.relative_to(ROOT)),'target':str(target),'exists':target.exists()}
            links.append(item)
            if not target.is_relative_to(ROOT) or not target.exists():outside.append(item)
metadata_collisions=[];running=[]
for p in BASE.glob('*/metrics/*.json'):
    try:d=json.loads(p.read_text())
    except (OSError,json.JSONDecodeError):continue
    if not isinstance(d,dict) or 'job' not in d:continue
    if d.get('status')=='running':running.append({'stage':d['stage'],'job':d['job']})
    for name in d.get('expected_outputs',[]):
        output=pathlib.Path(name);output=output if output.is_absolute() else ROOT/output
        if output.resolve()==p.resolve():metadata_collisions.append(str(p))
encoding=json.loads((BASE/'02_image_encoding/metrics/encoding_verification.json').read_text())
openseg=json.loads((BASE/'02_image_encoding/metrics/openseg_verification.json').read_text())
diagnostics=json.loads((BASE/'02_image_encoding/metrics/encoding_diagnostics.json').read_text())
replay={name:json.loads((BASE/f'06_semantic_aggregation/data/replay/{name}_replay_metrics.json').read_text()) for name in ['clip','openseg']}
branches=json.loads((BASE/'07_object_part_modeling/metrics/branch_comparison.json').read_text())
graph=json.loads((BASE/'08_scene_graph/metrics/predict_graph.json').read_text())
root_graph=json.loads((BASE/'08_scene_graph/diagnostics/root_only/metrics/scene_graph_summary.json').read_text())
query=json.loads((BASE/'09_relational_query/metrics/query_summary.json').read_text())
checks={'all_copied_files_match_sha256':not destination_failures,'inventoried_original_sources_unchanged_size_mtime':not source_changes,
        'runtime_data_model_output_links_internal_and_valid':not outside,'metadata_result_names_isolated':not metadata_collisions,'no_running_stage_jobs':not running,
        'fresh_encoding_350_verified':encoding['images']==openseg['images']==diagnostics['images']==350 and encoding['status']==openseg['status']==diagnostics['status']=='verified',
        'rofa_replay_exact':all(x['max_abs_replay_error']==0 for rows in replay.values() for x in rows),
        'branch_labels_identical':all(x['identical_labels'] for x in branches['levels']),
        'full_graph_failure_preserved':graph['status']=='failed',
        'root_diagnostic_present':len(root_graph)==1 and root_graph[0]['level']==3,
        'open_queries_12_relations_explicitly_missing':len(query['queries'])==12 and query['status']=='partial' and query['missing_modes']==['relational']}
result={'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'verified_with_documented_full_graph_failure' if all(checks.values()) else 'audit_failed',
        'checks':checks,'migration_files':len(manifest),'migration_bytes':sum(x['bytes'] for x in manifest),
        'destination_failures':destination_failures,'source_changes':source_changes,'source_inventory_not_available_for':source_stat_unavailable,
        'links':links,'external_or_broken_links':outside,'metadata_collisions':metadata_collisions,'running_jobs':running,
        'scope':'This validates copied inputs and retained results. It does not claim complete relation reconstruction or semantic accuracy.'}
# The current audit is itself running; exclude its execution bookkeeping.
result['running_jobs']=[x for x in running if x['job']!='final_integrity_check']
checks['no_running_stage_jobs']=not result['running_jobs']
result['status']='verified_with_documented_full_graph_failure' if all(checks.values()) else 'audit_failed'
(BASE/'00_data_check/metrics/final_integrity.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k not in ['links','source_inventory_not_available_for']},indent=2))
assert all(checks.values()),checks
