"""PyG Data.keys property-to-method compatibility; no graph/math change."""
from common import *
import re,subprocess
source=ROOT/'third_party/THGS';changes=[]
rules={'sp_partition.py':[r'nag\[0\]\.keys',r'nag\[1\]\.keys'],'ext/spt/data/data.py':[r'\bself\.keys',r'\bother\.keys'],'ext/spt/data/nag.py':[r'self\[0\]\.keys'],'ext/spt/transforms/point.py':[r'\bdata\.keys'],'ext/spt/transforms/data.py':[r'\bdata\.keys',r'nag\[self.level\]\.keys'],'ext/spt/transforms/partition.py':[r'\bd1\.keys']}
for name,patterns in rules.items():
    path=source/name;text=path.read_text();before=text
    for pattern in patterns:text=re.sub(pattern+r'(?![\w(])',lambda m:m.group()+'()',text)
    if text!=before:path.write_text(text);changes.append(name)
(ROOT/'docs/patches').mkdir(parents=True,exist_ok=True);diff=subprocess.check_output(['git','-C',str(source),'diff'],text=True);(ROOT/'docs/patches/thgs_pyg_compat.patch').write_text(diff)
write(ROOT/'docs/patches/thgs_pyg_compat.json',dict(files=changes,reason='THGS bundled SPT expects PyG Data.keys property; installed PyG 2.5 uses keys() method',scope='Enumeration only; no segmentation, graph weights, thresholds or query logic changed'))
print('Compatibility patch',changes)
