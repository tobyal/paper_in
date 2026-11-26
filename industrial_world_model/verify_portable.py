"""Run from the exported folder to verify isolation and saved query reproducibility."""
import json,sys
from pathlib import Path
import numpy as np
from .model import WorldModel


def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve()
    import industrial_world_model.model as reader
    assert Path(reader.__file__).resolve().is_relative_to(root), 'Import must use the packaged reader, not the original project'
    world=WorldModel(root,device='cpu')
    query='找到装配夹具台 01';result=world.query(query)
    assert result['matched_ids']==['obj_8429bc5f3c33'],result['matched_ids']
    assert not any(name.startswith('segment_anything') for name in sys.modules),'SAM must never be imported during queries'
    assert not any(name.startswith('m0') for name in sys.modules),'The reader/query must not import the M0 application'
    world.render(result['matched_ids'],image_id='frame_000221',output=root/'standalone_highlight.jpg')
    import m0.native_3dgs as native
    assert Path(native.__file__).resolve().is_relative_to(root),'Renderer must come from the portable package'
    metadata=dict(passed=True,reader_path=str(Path(reader.__file__).relative_to(root)),native_adapter_path=str(Path(native.__file__).relative_to(root)),objects=len(world.nodes),available=sum(n['available'] for n in world.nodes),relations=len(world.edges),query=query,matched_ids=result['matched_ids'],sam_imported=False,original_m0_database_needed=False,render='standalone_highlight.jpg',query_device='cpu')
    (root/'standalone_validation.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(metadata,ensure_ascii=False))


if __name__=='__main__':main()
