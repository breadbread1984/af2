#!/bin/bash

# install hmmer tool with command:
# conda install -c bioconda hmmer hhsuite kalign3

DATA_DIR=/home/xieyi/data
OUTPUT_DIR=/home/xieyi/output
ENV_PATH=/home/xieyi/anaconda3/envs/af3
INPUT_PATH=/home/xieyi/alphafold/test_inputs/test.fasta

python3 docker/run_docker.py \
  --fasta_paths=${INPUT_PATH} \
  --max_template_date=2020-05-14 \
  --model_preset=multimer \
  --db_preset=reduced_dbs \
  --data_dir=${DATA_DIR} \
  --output_dir=${OUTPUT_DIR} \
  --use_gpu \
  --enable_gpu_relax \
  --models_to_relax=all \
  --gpu_devices=all
