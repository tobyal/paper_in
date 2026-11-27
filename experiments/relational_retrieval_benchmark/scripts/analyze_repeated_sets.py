from common import *
import collections
result={}
for method in ['thgs','relags','ours']:
    groups=collections.defaultdict(list)
    for q in read(ROOT/'configs/benchmark_queries.json'):
        ids=np.load(ROOT/'outputs'/method/q['query_id']/'gaussian_indices.npy');key=hashlib.sha256(ids.astype(np.int64).tobytes()).hexdigest();groups[key].append(dict(query_id=q['query_id'],subject=q['subject_category'],predicate=q['predicate'],anchor=q['object_category'],count=len(ids)))
    result[method]=[dict(queries=rows,different_target_categories=len({r['subject'] for r in rows})) for rows in groups.values() if len(rows)>1]
write(ROOT/'evaluation/metrics/repeated_gaussian_sets.json',result);print(result)
