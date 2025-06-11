#!/usr/bin/python3

from absl import flags, app
from os.path import join
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
    self.status = {gpu_id: "idle" for gpu_id in range(num_gpus)}
    self.logs = {gpu_id: [] for gpu_id in range(num_gpus)}
    self.lock = threading.Lock()
    # start monitor thread
    self.monitor_thread = threading.Thread(target = self._monitor_processes)
    self.monitor_thread.daemon = True
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
  def run_alphafold(self, gpu_id, fasta_path, model_preset = "multimer", models_to_relax = 'none', max_template_date = '2020-05-14'):
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
          '--max_template_date={max_template_date}',
          '--model_preset={model_preset}',
          '--db_preset=reduced_dbs',
          f'--data_dir={configs.data_dir}',
          f'--output_dir={join(configs.output_dir, str(gpu_id))}',
          '--use_gpu',
          '--enable_gpu_relax',
          '--models_to_relax={models_to_relax}',
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

def create_interface(manager):
  with gr.Blocks(title = "AlphaFold2 manager") as interface:
    gr.Markdown("# AlphaFold manager tools")
    with gr.Row():
      with gr.Column(scale = 1):

        gr.Markdown('### GPU status')
        gpu_status_outputs = {}
        for gpu_id in manager.status:
          with gr.Row():
            gpu_status_outputs[gpu_id] = gr.Textbox(
              label = f"GPU {gpu_id}",
              value = f"status: intializing",
              interactive = False
            )
        refresh_btn = gr.Button("refresh status")

        gr.Markdown('### GPU logs')
        gpu_id_input = gr.Dropdown(
          choices = list(manager.logs.keys()),
          label = 'GPU selection',
          value = list(manager.logs.keys())[0] if len(manager.logs) else None
        )
        logs_output = gr.Textbox(label = 'logs', lines = 10, interactive = False)
        get_logs_btn = gr.Button("get log")

      with gr.Column(scale = 2):
        gr.Markdown('### submit new task')
        with gr.Row():
          fasta_file = gr.File(label = "FASTA file")
          gpu_selector = gr.Dropdown(
            choices = list(manager.processes.keys()),
            label = 'GPU selection',
            value = list(manager.processes.keys())[0] if len(manager.processes) else None
          )
        with gr.Row():
          model_preset = gr.Dropdown(
            choices = ['monomer', 'monomer_casp14', 'monomer_ptm', 'multimer'],
            label = 'preset model',
            value = 'multimer'
          )
          models_to_relax = gr.Dropdown(
            choices = ['all', 'best', 'none'],
            label = 'models to relax',
            value = 'none'
          )
        with gr.Row():
          max_template_date = gr.Textbox(
            label = 'max template date',
            value = '2020-05-14',
            placeholder = 'YYY-MM-DD'
          )
        submit_btn = gr.Button('submit prediction')
        status_output = gr.Textbox(label = 'submit status', interactive = False)

    def update_status():
      status_dict = manager.get_gpu_status()
      return {
        gpu_status_outputs[gpu_id]: gr.update(value = f"stats: {status}")
        for gpu_id, status in status_dict.items()
      }
    def update_logs(gpu_id):
      return manager.get_gpu_logs(gpu_id)
    def run_prediction(gpu_id, fasta_file, model_preset, models_to_relax, max_template_date):
      if fasta_file is None:
        return "error: please upload fasta file"
      import tempfile
      temp_dir = tempfile.mkdtemp()
      fasta_path = join(temp_dir, "input.fasta")
      with open(fasta_file.name, 'r') as ifs
        with open(fasta_path, 'w') as ofs:
          ofs.write(ifs.read())
      success, message = manager.run_alphafold(
        gpu_id = int(gpu_id),
        fasta_path = fasta_path,
        model_preset = model_preset,
        models_to_relax = models_to_relax,
        max_template_date = max_template_date
      )
      update_status()
      return message
    refresh_btn.click(
      update_status,
      inputs = [],
      outputs = list(gpu_status_outputs.values())
    )
    get_logs_btn.click(
      update_logs,
      inputs = [gpu_id_input],
      outputs = [logs_output]
    )
    submit_btn.click(
      run_prediction,
      inputs = [gpu_selector, fasta_file, model_preset, models_to_relax, max_template_date]
    )
    interface.load(
      update_status,
      inputs = None,
      outputs = list(gpu_status_outputs.values())
    )
  return interface

def main(unused_argv):
  manager = AlphaFoldManager(FLAGS.num_gpus)
  interface = create_interface(manager)
  interface.launch(
    server_name = configs.service_host,
    server_port = configs.service_port,
    share = True
  )

if __name__ == "__main__":
  add_options()
  app.run(main)
