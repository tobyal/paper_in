"""Wait for this recorded training attempt, then extract/render its final checkpoint."""
import json,time,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];attempt=sorted((ROOT/'logs/A_affinity_training').iterdir())[-1]
print('WAITING FOR RECORDED TRAINING',attempt,flush=True)
while not (attempt/'result.json').exists():
    command=json.loads((attempt/'command.json').read_text())
    if not Path('/proc/'+str(command['pid'])).exists():raise RuntimeError('Recorded training process disappeared without completion record')
    time.sleep(10)
result=json.loads((attempt/'result.json').read_text());assert result['exit_code']==0,result
for stage,script in [('A_final_extraction','src/extract_instances.py'),('A_final_render','src/render_instances.py')]:
    subprocess.run([sys.executable,str(ROOT/'scripts/run_command.py'),'--stage',stage,'--gpu','1','--',sys.executable,'-u',str(ROOT/script),'--iteration','10000'],cwd=ROOT,check=True)
