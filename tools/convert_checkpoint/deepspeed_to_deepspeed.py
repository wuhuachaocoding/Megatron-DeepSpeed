#!/usr/bin/env python

import argparse
import os
import torch
from collections import OrderedDict
from deepspeed_checkpoint import ARGS_KEY, DeepSpeedCheckpoint

MODEL_KEY = 'model'
ARGS_KEY = 'args'
LANGUGAGE_MODEL_KEY = 'language_model'
EMBEDDING_KEY = 'embedding'
ENCODER_KEY = 'encoder'
WORD_EMBEDDINGS_FOR_HEAD_KEY = 'word_embeddings_for_head'
WORD_EMBEDDINGS_KEY = 'word_embeddings'
FINAL_LAYER_NORM_KEY ='final_layernorm'
CHECKPOINT_VERSION_KEY = 'checkpoint_version'
CHECKPOINT_VERSION_VALUE = 3.0
ITERATION_KEY = 'iteration'

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input_folder', default=None, type=str, help='Input DeepSpeed Checkpoint folder')
    parser.add_argument('--output_folder', default=None, type=str, help='Output Megatron checkpoint folder')
    parser.add_argument('--target_tp', default=1, type=int, help='Target TP degree')
    parser.add_argument('--target_pp', default=1, type=int, help='Target PP degree')
    args = parser.parse_args()
    print(f'args = {args}')
    return args


def _create_checkpoint_path(base_folder, tp_rank, layer_id):
    ckpt_file = f'{layer_id}-model_{tp_rank:02d}-model_states.pt'
    ckpt_path = os.path.join(base_folder, ckpt_file)
    return ckpt_path


def _save_checkpoint(file_path, chkpt_sd):
    dir, _ = os.path.split(file_path)
    os.makedirs(dir, exist_ok=True)
    torch.save(chkpt_sd, file_path)


def _create_transformer_layer_checkpoint(ds_checkpoint, base_folder, tp_index, pp_index):
    sd_list = ds_checkpoint.get_transformer_state(tp_index, pp_index)
    layer_id_list = ds_checkpoint.get_pp_transformer_map(pp_index)
    assert len(sd_list) == len(layer_id_list)
    for sd, layer_id in zip(sd_list, layer_id_list):
        ckpt_path = _create_checkpoint_path(base_folder, tp_index, layer_id)
        _save_checkpoint(ckpt_path, sd)


def _create_embedding_layer_checkpoint(ds_checkpoint, base_folder, tp_index):
    sd = ds_checkpoint.get_embedding_state(tp_index)
    layer_id = ds_checkpoint.get_embedding_layer_id()
    ckpt_path = _create_checkpoint_path(base_folder, tp_index, layer_id)
    _save_checkpoint(ckpt_path, sd)


def _create_final_norm_layer_checkpoint(ds_checkpoint, base_folder, tp_index):
    sd = ds_checkpoint.get_final_norm_state(tp_index)
    layer_id = ds_checkpoint.get_final_norm_layer_id()
    ckpt_path = _create_checkpoint_path(base_folder, tp_index, layer_id)
    _save_checkpoint(ckpt_path, sd)

def _create_latest_file(base_folder, file_name, latest_tag):
    file_path = os.path.join(base_folder, file_name)
    os.makedirs(base_folder, exist_ok=True)
    with open(file_path, 'w') as f:
        f.write(str(latest_tag))

def main():
    print(f'Convert DeepSpeed Checkpoint to DeepSpeed Checkpoint')

    args = parse_arguments()
    print(f'Converting DeepSpeed checkpoint in {args.input_folder} to DeepSpeed checkpoint in {args.output_folder}')

    ds_checkpoint = DeepSpeedCheckpoint(args.input_folder, args.target_tp, args.target_pp)
    iteration = ds_checkpoint.get_iteration()
    latest_tag = f'global_step{iteration}'
    _create_latest_file(args.output_folder, 'latest_checkpointed_iteration.txt', iteration)
    _create_latest_file(args.output_folder, 'latest', latest_tag)
    base_folder = os.path.join(args.output_folder, latest_tag)
    for i in range(0, ds_checkpoint.tp_degree):
        _create_embedding_layer_checkpoint(ds_checkpoint, base_folder, i)
        _create_final_norm_layer_checkpoint(ds_checkpoint, base_folder, i)
        for j in range(0, ds_checkpoint.pp_degree):
            _create_transformer_layer_checkpoint(ds_checkpoint, base_folder, i, j)

if __name__ == "__main__":
    main()
