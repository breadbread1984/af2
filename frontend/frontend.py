#!/usr/bin/python3

from absl import flags, app
from datetime import datetime
import threading
import subprocess
import time
import gradio as gr
import configs

FLAGS = flags.FLAGS

def add_options():
  flags.DEFINE_integer('num_gpus', default = 2, help = 'number of gpus')

class AlphaFoldManager(object):
  def __init__(self, num_gpus):
    self.processes = {gpu_id: None for gpu_id in range(num_gpus)}
    self.status = {gpu_id: "idle", for gpu_id in range(num_gpus)}
    self.logs = {gpu_id: [] for gpu_id in range(num_gpus)}
    self.lock = threading.Lock()
    # start monitor thread
    self.monitor_thread = threading.Thread(target = self._moniter_processes, deamon = True)
    self.monitor_thread.start()
  def _monitor_processes(self):
    while True:
      for gpu_id, process in self.processes.items():
        if process is not None:
          if process.poll() is not None:
            # process already finished
            return_code = process.returncode
            status = "finished" if return_code == 0 else f"failed(code:{return_code})"
            with self.lock:
              self.status[gpu_id] = status
              self.logs[gpu_id].append(f"{datetime.now()}: process finished, status {status}")
              self.processes[gpu_id] = None
      time.sleep(5)
  def run_alphafold(self, gpu_id, fasta_path):
    if gpu_id not in self.processes:
      return False, f"invalid GPU ID: {gpu_id}"
    if self.status[gpu_id] != 'idle':
      return False, f"GPU {gpu_id} is busy, status: {self.status[gpu_id]}"
    try:
      process = subprocess.Popen(
        [
          'python3',
          'docker/run_docker.py',
          f'--fasta_paths={fasta_path}',
          '--max_template_date=2020-05-14',
          '--model_preset=multimer',
          '--db_preset=reduced_dbs',
          f'--data_dir={configs.data_dir}',
          f'--output_dir={join(configs.output_dir, str(gpu_id))}',
          '--use_gpu',
          '--enable_gpu_relax',
          '--models_to_relax=none',
          f'--gpu_devices={gpu_id}',
        ]
      )
      with self.lock:
        self.process[gpu_id] = process
        self.status[gpu_id] = 'running'
        self.logs[gpu_id].append(f"{datetime.now()}: start new AlphaFold task")
      threading.Thread(target = self._collect_logs, args = (gpu_id, process), daemon = True).start()
      return True, f"started task on GPU {gpu_id}, output directory: {join(configs.output_dir, str(gpu_id))}"
    except Exception as e:
      return False, f"failed to start AlphaFold: {str(e)}"
  def _collect_logs(self, gpu_id, process):
    for line in process.stdout:
      with self.lock:
        self.logs[gpu_id].append(f"{datetime.now()}: {line.strip()}")
  def get_gpu_status(self):
    return {gpu_id: self.status[gpu_id] for gpu_id in self.status}
  def get_gpu_logs(self, gpu_id):
    if gpu_id in self.logs:
      return '\n'.join(self.logs[gpu_id])
    return "no log"

def main(unused_argv):
  
