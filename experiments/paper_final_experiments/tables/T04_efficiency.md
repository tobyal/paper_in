# T04_efficiency

| Method | Offline_record | Online query (s) | Render two views (s) | End-to-end (s) |
| --- | --- | --- | --- | --- |
| LangSplat | Not recorded: complete historical training | 0.346610 | 0.053795 | 0.406716 |
| THGS | 497.84 s hierarchy only; feature/2DGS costs excluded | 0.010730 | 0.044890 | 0.055572 |
| ReLaGS | 103.63 s coordinate-aligned graph only; historical upstream excluded | 0.106590 | 0.021297 | 0.127786 |
| Ours | 1852.45 s shared training; other stages separately listed | 0.002580 | 0.017453 | 0.020073 |

Offline records are partial and NOT comparable totals. Same A6000 GPU0; 2 views, 938x528, 1 warmup + 3 CUDA-synchronized repeats, query medians averaged. Loading and export IO excluded. LangSplat query includes pixel decoding/postprocessing; Ours exact known aliases avoid online CLIP.
