# SAGA + ReLaGS industrial experiment

- This directory implements the user's SAGA + ReLaGS request. The older unchanged-ReLaGS and M1–M5 method restrictions do not define this new method.
- All new source, configuration, environments, adaptations, logs and outputs stay here. Existing M0, raw scene, images, old implementations and outputs are read-only.
- Snapshot the actual latest M0 revision; preserve original object IDs and Gaussian row IDs. Explicitly define category IDs if M0 lacks them.
- Reuse official SAGA v2 contrastive loss, scale gate, local feature smoothing and affinity segmentation. Never report a coarse-box subset as a successful instance.
- No external transmission of industrial images without authorization. Lack of a local authorized VLM must remain an explicit limitation; geometry-only relationships are allowed.
- Held-out images do not participate in training, prompting or parameter selection. Internal prompt/projection consistency is not ground-truth accuracy.
- Preserve failures, parameter choices and honest visual quality assessments. Do not stop other GPU jobs.
