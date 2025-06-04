#!/bin/bash

# install hmmer tool with command:
# conda install -c bioconda hmmer hhsuite kalign3

DATA_DIR=/home/xieyi/data
OUTPUT_DIR=/home/xieyi/output
ENV_PATH=/home/xieyi/anaconda3/envs/af3
INPUT_PATH=/home/xieyi/data/uniprot/uniprot.fasta

python3 run_alphafold.py \
  --fasta_paths=${INPUT_PATH} \
  --max_template_date=2020-05-14 \
  --model_preset=monomer \
  --db_preset=reduced_dbs \
  --data_dir=${DATA_DIR} \
  --output_dir=${OUTPUT_DIR} \
  --benchmark=false \
  --use_precomputed_msas=false \
  --num_multimer_predictions_per_model=5 \
  --models_to_relax=best \
  --use_gpu_relax=true \
  --uniref90_database_path=${DATA_DIR}/uniref90/uniref90.fasta \
  --mgnify_database_path=${DATA_DIR}/mgnify/mgy_clusters_2022_05.fa \
  --template_mmcif_dir=${DATA_DIR}/pdb_mmcif/mmcif_files \
  --obsolete_pdbs_path=${DATA_DIR}/pdb_mmcif/obsolete.dat \
  --pdb70_database_path=${DATA_DIR}/pdb70/pdb70 \
  --small_bfd_database_path=${DATA_DIR}/small_bfd/bfd-first_non_consensus_sequences.fasta \
  --jackhmmer_binary_path=${ENV_PATH}/bin/jackhmmer \
  --hhblits_binary_path=${ENV_PATH}/bin/hhblits \
  --hhsearch_binary_path=${ENV_PATH}/bin/hhsearch \
  --hmmsearch_binary_path=${ENV_PATH}/bin/hmmsearch \
  --hmmbuild_binary_path=${ENV_PATH}/bin/hmmbuild \
  --kalign_binary_path=${ENV_PATH}/bin/kalign \
  --logtostderr
