#!/usr/bin/python3

from absl import flags, app
from datetime import datetime
import threading
import time
import gradio as gr

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
      

def main(unused_argv):
  
