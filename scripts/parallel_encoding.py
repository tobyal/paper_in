#!/usr/bin/env python3
"""Run independent official per-image inference in four disjoint GPU jobs."""
import json,pathlib,subprocess,sys,os,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=ROOT/'ReLaGS/scripts/image_encoding.py';s=p.read_text()
old='    args = parser.parse_args()'
new='    parser.add_argument("--image-list", type=str, default=None, help="Execution-only list of independent frames")\n'+old
if '--image-list' not in s:
    assert s.count(old)==1;s=s.replace(old,new)
    old='    data_listi.sort()';new=old+'\n    if args.image_list is not None:\n        allowed = set(open(args.image_list).read().splitlines())\n        data_listi = [name for name in data_listi if name in allowed]'
    assert s.count(old)==1;s=s.replace(old,new)
    s=s.replace('if len(processed_frames) >= len(data_listi):','if all(frame.split(".")[0] in processed_frames for frame in data_listi):')
    p.write_text(s)
(ROOT/'logs/patches/all_baseline_adaptations.patch').write_text(subprocess.check_output(['git','diff'],cwd=ROOT/'ReLaGS',text=True))
out=ROOT/'outputs/relags_baseline/02_image_encoding'
names=sorted(x.name for x in (ROOT/'data/images').glob('*.jpg'))
jobs=[]
for gpu in range(4):
    manifest=ROOT/'configs'/f'encoding_shard_{gpu}.txt';manifest.write_text('\n'.join(names[gpu::4])+'\n')
    last=pathlib.Path(names[gpu::4][-1]).stem
    cmd=[sys.executable,str(ROOT/'scripts/run_stage.py'),'--stage','02_image_encoding','--job',f'sam_clip_shard_{gpu}','--gpu',str(gpu),'--cwd','ReLaGS','--input',str(p),'--input',str(manifest),'--expect',str(out/'data/language_features'/f'{last}_f.npy'),'--expect',str(out/'data/language_features'/f'{last}_s.npy'),'--','python','scripts/image_encoding.py','--source_path',str(ROOT/'data'),'--save_dir',str(out/'data/language_features'),'--sam_ckpt_path',str(ROOT/'models/sam/sam_vit_h_4b8939.pth'),'--image-list',str(manifest)]
    log=(ROOT/'logs'/f'sam_shard_{gpu}_launcher.log').open('a')
    jobs.append((gpu,subprocess.Popen(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT),log))
results=[]
for gpu,proc,log in jobs:
    rc=proc.wait();log.close();results.append({'gpu':gpu,'exit_code':rc})
(out/'metrics/parallel_encoding.json').write_text(json.dumps(results,indent=2))
if any(r['exit_code'] for r in results):raise SystemExit(1)
subprocess.run([sys.executable,str(ROOT/'scripts/run_stage.py'),'--stage','02_image_encoding','--job','verify_encoding','--gpu','3','--cwd','.','--input',str(ROOT/'scripts/verify_encoding.py'),'--expect',str(out/'metrics/encoding_verification.json'),'--','python','scripts/verify_encoding.py'],cwd=ROOT,check=True)
