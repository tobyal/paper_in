#!/usr/bin/env python3
"""Apply auditable output hooks and path/error-reporting adapters, no algorithm replacements."""
import pathlib,subprocess,json,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1];REPO=ROOT/'ReLaGS'
notes=[]
def edit(name,changes):
    p=REPO/name;text=p.read_text();original=text
    for old,new in changes:
        if new in text:continue
        if text.count(old)!=1:raise ValueError((name,'anchor count',text.count(old),old[:100]))
        text=text.replace(old,new,1)
    if text!=original:p.write_text(text)
    notes.append({'file':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
imp='import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))\nimport relags_audit as baseline_audit\n'
edit('submodules/diff-surfel-rasterization-trace-maxcontrib/setup.py',[
    ("    packages=['diff_surfel_rasterization_trace_maxcontrib'],", "    packages=['diff_surfel_rasterization_trace_maxcontrib'],\n    package_dir={'diff_surfel_rasterization_trace_maxcontrib': 'diff_surfel_rasterization_trace'},")])
edit('max_weight_pruning.py',[
('import os\n','import os\n'+imp),
('    new_gaussians = gaussians.filter_gaussians(mask)', '    baseline_audit.save("03_gaussian_pruning", "max_contribution_and_indices", {"max_contribution": gaussians.get_max_contribution, "keep_mask": mask, "kept_indices": torch.where(mask)[0], "removed_indices": torch.where(~mask)[0], "threshold": contribution_threshold})\n    gaussians.filter_gaussians(~mask).save_ply(os.path.join(dataset.model_path, "removed_gaussians.ply"))\n    new_gaussians = gaussians.filter_gaussians(mask)')])
edit('graph_weight.py',[
('import os\n','import os\n'+imp),
('    neg_dist = torch.clamp(neg_dist, 0, neg_b)','    baseline_audit.save("05_hierarchical_grouping", "raw_edge_evidence", {"neighbors": knn, "original_distances": ori_distance, "negative_evidence": neg_dist, "positive_evidence": pos_dist})\n    neg_dist = torch.clamp(neg_dist, 0, neg_b)')])
edit('merge_proj.py',[
('import argparse\n','import argparse\n'+imp),
('        sp_feature_list = [[] for _ in range(sp_uni.shape[0])]', '        sp_feature_list = [[] for _ in range(sp_uni.shape[0])]\n        audit_view_ids = [[] for _ in range(sp_uni.shape[0])]\n        self._audit_rofa = []'),
('                    sp_feature_list[sp].append(feat)', '                    sp_feature_list[sp].append(feat)\n                    audit_view_ids[sp].append(view_idx)'),
('        # Filter outliers and compute final features using our statistical method', '        baseline_audit.save("06_semantic_aggregation", f"{self.args.vlm_type}_level_{feature_level}_raw_observations", {"features": sp_feature_list, "view_ids": audit_view_ids, "view_names": [v.image_name for v in views], "gaussian_to_cluster": gau2sp, "tau": self.args.tau})\n\n        # Filter outliers and compute final features using our statistical method'),
('                features = torch.stack(sp_feature_list[sp], dim=0)', '                features = torch.stack(sp_feature_list[sp], dim=0)\n                self._audit_cluster = sp'),
('            return F.normalize(features[0], p=2, dim=-1)', '            self._audit_rofa.append({"cluster": self._audit_cluster, "keep_mask": torch.ones(1, dtype=torch.bool), "observation_count": 1})\n            return F.normalize(features[0], p=2, dim=-1)'),
('        filtered_feats = features[keep_mask]', '        self._audit_rofa.append({"cluster": self._audit_cluster, "keep_mask": keep_mask.detach().cpu(), "mean_similarity": mean_sim.detach().cpu(), "mu": mu.item(), "sigma": sigma.item(), "observation_count": len(features)})\n        filtered_feats = features[keep_mask]'),
('        return F.normalize(torch.stack(sp_features, dim=0), p=2, dim=-1)', '        aggregated = F.normalize(torch.stack(sp_features, dim=0), p=2, dim=-1)\n        baseline_audit.save("06_semantic_aggregation", f"{self.args.vlm_type}_level_{feature_level}_rofa", {"decisions": self._audit_rofa, "aggregated_features": aggregated})\n        return aggregated'),
('        return torch.stack(labels).transpose(0, 1)  # (N, M)', '        point_labels = torch.stack(labels).transpose(0, 1)\n        baseline_audit.save("05_hierarchical_grouping", f"{self.args.vlm_type}_level_{feature_level}_projected_labels", {"labels": point_labels, "view_names": [v.image_name for v in views]})\n        return point_labels  # (N, M)'),
('            seg_labels = self.assign_seg_label_torch(', '            baseline_audit.save("05_hierarchical_grouping", f"{self.args.vlm_type}_level_{i+1}_adjacency", {"seg_ids": self.seg_ids, "seg_members": self.seg_members, "seg_adj": seg_adj, "direct_neighbors": self.seg_direct_neighbors})\n            seg_labels = self.assign_seg_label_torch('),
('            nag.append(pt_prim_label - 1)', '            baseline_audit.save("05_hierarchical_grouping", f"{self.args.vlm_type}_level_{i+1}_grouping", {"labels": pt_prim_label - 1, "superpoint_group_labels": seg_labels})\n            nag.append(pt_prim_label - 1)'),
('    everything_seg(args)','    from utils.general_utils import safe_state\n    safe_state(False)  # Explicit reproducible RNG state; same initializer as graph_weight.py\n    everything_seg(args)')])
edit('scripts/image_encoding.py',[
('            pretrained=self.config.clip_model_pretrained,  # e.g., laion2b_s34b_b88k','            pretrained=os.environ.get("RELAGS_CLIP_CHECKPOINT", self.config.clip_model_pretrained),  # Exact same pretrained weights, optional project-local path'),
('        except:\n            # raise ValueError(timer)\n            print(f"Error in image {data_list[i]}")\n            continue','        except Exception:\n            import traceback\n            traceback.print_exc()\n            print(f"Error in image {data_list[i]}")\n            raise'),
('processed_frames = [f.split(\'_f\')[0] for f in os.listdir(save_dir) if f.endswith(\'_f.npy\')]', 'processed_frames = [f[:-6] for f in os.listdir(save_dir) if f.endswith("_f.npy") and os.path.exists(os.path.join(save_dir, f[:-6]+"_s.npy"))]'),
('            for data_path in data_list:', '            img_list = []  # Reset only the image-loading buffer on resume.\n            for data_path in data_list:'),
('        except ValueError as e:\n            print(f"Error in image {e}")\n            img_list = []\n            continue','        except ValueError as e:\n            print(f"Error in image {e}")\n            raise')])
logs=ROOT/'logs/patches';logs.mkdir(parents=True,exist_ok=True)
(logs/'instrumentation_and_io.patch').write_text(subprocess.check_output(['git','diff','--no-ext-diff'],cwd=REPO,text=True))
(logs/'patch_manifest.json').write_text(json.dumps({'purpose':'Intermediate serialization, fixed RNG seed, local identical pretrained weights, complete-pair resume validation and visible errors; no core equation/threshold changes','files':notes},indent=2))
print(json.dumps(notes,indent=2))
