#!/usr/bin/env python3
"""Record correspondence between the two actual hierarchy runs without relabeling."""
import json, pathlib
import numpy as np
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = ROOT/'outputs/relags_baseline'
clip = torch.load(BASE/'05_hierarchical_grouping/data/model/sai_nag_3.0.pt', map_location='cpu')
openseg = torch.load(BASE/'06_semantic_aggregation/data/model/sai_nag_openseg.pt', map_location='cpu')
assert len(clip['nag']) == len(openseg['nag'])
records = []
for level, (c, o) in enumerate(zip(clip['nag'], openseg['nag'])):
    c, o = c.numpy().reshape(-1), o.numpy().reshape(-1)
    assert c.shape == o.shape
    pairs = np.unique(np.column_stack([c, o]), axis=0)
    _, clip_matches = np.unique(pairs[:, 0], return_counts=True)
    _, openseg_matches = np.unique(pairs[:, 1], return_counts=True)
    records.append({'level': level, 'gaussians': len(c), 'identical_labels': bool(np.array_equal(c, o)),
                    'different_label_count': int((c != o).sum()),
                    'same_partition_up_to_label_permutation': bool((clip_matches == 1).all() and (openseg_matches == 1).all()),
                    'clip_groups_with_multiple_openseg_matches': int((clip_matches > 1).sum()),
                    'openseg_groups_with_multiple_clip_matches': int((openseg_matches > 1).sum())})
    np.savez_compressed(BASE/'07_object_part_modeling/data'/f'branch_correspondence_level_{level}.npz', clip_to_openseg_label_pairs=pairs)
result = {'levels': records, 'interpretation': 'Read-only comparison. Open-vocabulary queries use their CLIP hierarchy; relation queries use their OpenSeg hierarchy. No IDs are transferred between unequal hierarchies.'}
(BASE/'07_object_part_modeling/metrics/branch_comparison.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
