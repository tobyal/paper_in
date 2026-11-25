#!/usr/bin/env python3
"""Run the unmodified official level-3 predictor independently after full-run failure.

This is a root-only diagnostic, not a substitute for the requested full graph.
"""
import os,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'ReLaGS'));os.chdir(ROOT/'ReLaGS')
import predict_3d_scene_graph as official
official.LEVELS=[3]
official.main()
