# Upstream attribution and licenses

This project reproduces **ReLaGS: Relational Language Gaussian Splatting**, by the authors of the [official DFKI-AV repository](https://github.com/dfki-av/ReLaGS), for an industrial scene. The original project and paper remain the authors' work.

- ReLaGS: commit `52cc0c98b0ccf9afebea31901bf79246650286b3`; original [CC BY-NC-SA 4.0 license](licenses/ReLaGS_LICENSE). `patches/relags_baseline.patch` records the source adaptations and instrumentation; it remains subject to the upstream license.
- Official 2D Gaussian Splatting: commit `f3e3b9fa67bbd1c75e05167ff37391d8dab2a678`; original [Gaussian-Splatting license](licenses/external_2d-gaussian-splatting_LICENSE.md). The supplied patch changes only Matplotlib canvas access. Nested dependencies retain their own licenses.
- SAM, OpenCLIP, OpenSeg, Jina and GNN weights are not redistributed here; model origins and revisions are recorded in the environment and reports.

No repository-wide permissive license is asserted for the industrial imagery or third-party components. Read the corresponding upstream notices for their conditions. The official paper is linked, not redistributed.
