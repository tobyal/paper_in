#!/usr/bin/env python3
import pathlib,subprocess,json
ROOT=pathlib.Path(__file__).resolve().parents[1];REPO=ROOT/'ReLaGS'
def patch(name,old,new):
    p=REPO/name;s=p.read_text()
    if new in s:return
    assert s.count(old)==1,(name,old[:80],s.count(old));p.write_text(s.replace(old,new,1))
patch('utils/vlm_utils.py','import torch\n','import os\nfrom pathlib import Path\nimport torch\n')
patch('utils/vlm_utils.py','pretrained="laion2b_s34b_b88k",','pretrained=os.environ.get("RELAGS_CLIP_CHECKPOINT", "laion2b_s34b_b88k"),\n                cache_dir=str(Path(__file__).resolve().parents[2] / "models/openclip_text"),')
patch('utils/vlm_utils.py','pretrained="openai",','pretrained="openai",\n                cache_dir=str(Path(__file__).resolve().parents[2] / "models/openclip_text"),')
patch('predict_3d_scene_graph.py','import sys\n','import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))\nimport relags_audit as baseline_audit\nfrom relags_relationships import load_relationship_embeddings\n')
patch('predict_3d_scene_graph.py','from scene_graph.scan3r_dataset import relationship_jina_feature\n','# Inference does not require the authors\' local 3DSSG training dataset files.\n')
patch('predict_3d_scene_graph.py','    model = load_model(args.checkpoint)','    relationship_jina_feature, _ = load_relationship_embeddings(REL_NAMES)\n    model = load_model(args.checkpoint)')
patch('predict_3d_scene_graph.py','        num_edges = edge_index_np.shape[1]','        baseline_audit.save("08_scene_graph", f"level_{level}_graph_inputs", {"original_cluster_ids": list(obb_preds.keys()), "centers": centers, "rotations": Rs, "extents": extents, "node_geometry": node_geom_feat, "node_language": node_clip_feat, "edge_index": edge_index_np, "neighbor_thresh": args.neighbor_thresh})\n        num_edges = edge_index_np.shape[1]')
patch('predict_3d_scene_graph.py','        top3 = torch.topk(sims, k=NEIGHBOR_TOPK, dim=-1).indices','        baseline_audit.save("08_scene_graph", f"level_{level}_edge_predictions", {"edge_features": edge_feat, "relation_similarities": sims, "relation_names": REL_NAMES, "src": all_edge_src, "dst": all_edge_dst})\n        top3 = torch.topk(sims, k=NEIGHBOR_TOPK, dim=-1).indices')
logs=ROOT/'logs/patches';logs.mkdir(parents=True,exist_ok=True)
(logs/'all_baseline_adaptations.patch').write_text(subprocess.check_output(['git','diff','--no-ext-diff'],cwd=REPO,text=True))
(logs/'graph_interface_notes.json').write_text(json.dumps({'purpose':'Remove inference dependency on hardcoded training dataset paths; reuse identical official Jina task/dtype/dimension on the exact REL_NAMES from predictor; local model cache and serialization only','core_network_unchanged':True,'graph_neighbor_threshold_unchanged':True,'preserved_possible_index_issue':'Official edge keys use OBB row indices. Raw original_cluster_ids map is saved for audit; no prediction or selection logic is corrected silently.'},indent=2))
print('Graph inference interfaces and audit outputs patched')
