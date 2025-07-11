#!/usr/bin/python3

from absl import flags, app
from shutil import rmtree, copyfile
from os import makedirs, listdir
from os.path import join, exists, splitext
import re
import pandas as pd
from datetime import datetime
import threading
import subprocess
import time
import gradio as gr
from gradio.routes import mount_gradio_app
from fastapi import FastAPI
from fastapi.responses import FileResponse
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
      if exists(join(configs.output_dir, str(gpu_id))):
        rmtree(join(configs.output_dir, str(gpu_id)))
      makedirs(join(configs.output_dir, str(gpu_id)))
      process = subprocess.Popen(
        [
          'python3',
          'docker/run_docker.py',
          f'--fasta_paths={fasta_path}',
          f'--max_template_date={max_template_date}',
          f'--model_preset={model_preset}',
          '--db_preset=reduced_dbs',
          f'--data_dir={configs.data_dir}',
          f'--output_dir={join(configs.output_dir, str(gpu_id))}',
          '--use_gpu',
          '--enable_gpu_relax',
          f'--models_to_relax={models_to_relax}',
          f'--gpu_devices={gpu_id}',
        ]
      )
      with self.lock:
        self.processes[gpu_id] = process
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
    # 1) interface
    gr.Markdown("# AlphaFold manager tools")
    with gr.Row():
      with gr.Column(scale = 1):
        with gr.Tab('gpu status') as gpu_status_tab:
          with gr.Column():

            gr.Markdown('### GPU status')
            gpu_status_outputs = {}
            for gpu_id in manager.status:
              with gr.Row():
                gpu_status_outputs[gpu_id] = gr.Textbox(
                  label = f"GPU {gpu_id}",
                  value = f"status: intializing",
                  interactive = False
                )

        with gr.Tab('gpu logs') as gpu_logs_tab:
          with gr.Column():
            gr.Markdown('### GPU logs')
            gpu_id_input = gr.Dropdown(
              choices = list(manager.logs.keys()),
              label = 'GPU selection',
              value = list(manager.logs.keys())[0] if len(manager.logs) else None
            )
            logs_output = gr.Textbox(label = 'logs', lines = 10, interactive = False)

      with gr.Column(scale = 2):
        with gr.Tab('submit') as submit_tab:
          with gr.Column():
            gr.Markdown('### Submit New Task')
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

        with gr.Tab('view') as view_tab:
          with gr.Column():
            gr.Markdown('### Prediction Viewer')
            view_gpu_selector = gr.Dropdown(
              choices = list(manager.processes.keys()),
              label = 'GPU selection',
              value = list(manager.processes.keys())[0] if len(manager.processes) else None
            )
            with gr.Row():
              download = gr.File(label = 'download')
              view_btn = gr.Button(value = 'visualize')
            results = gr.Dataframe(headers = ['rank', 'path'], datatype = ['str', 'str'], interactive = False)
    # 2) callbacks
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
      with open(fasta_file.name, 'r') as ifs:
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
    def list_results(gpu_id):
      pattern = r"ranked_([0-9]{1,}+)"
      output_dir = join(configs.output_dir, str(gpu_id), 'input')
      ranks = list()
      names = list()
      if exists(output_dir):
        for f in listdir(output_dir):
          stem, ext = splitext(f)
          if ext != '.pdb': continue
          res = re.match(pattern, stem)
          if res is None: continue
          ranks.append(res[1])
          names.append(join(output_dir, f))
      return gr.Dataframe(headers = ['rank', 'path'], datatype = ['str', 'str'], interactive = False, value = [[rank, name] for rank, name in zip(ranks, names)])
    def prepare_files(df, evt: gr.SelectData):
      row_index = evt.index[0]
      clicked_row_values = evt.row_value
      pdb_path = clicked_row_values[1]
      with open(pdb_path, 'r') as f:
        pdb_content = f.read()
      copyfile(pdb_path, 'selected.pdb')
      html = f"""<!DOCTYPE html>
    <html>
        <head>
            <meta charset="utf-8">
            <title>NGL Viewer</title>
            <!-- 引入NGL Viewer库 -->
            <script src="https://cdn.jsdelivr.net/npm/ngl@0.10.4/dist/ngl.js"></script>
            <style>
                #viewport {{ width: 100%; height: 500px; }}
            </style>
        </head>
        <body>
            <div id="viewport"></div>
            <script>
                // 创建查看器实例
                var stage = new NGL.Stage("viewport");
                content = `{pdb_content}`;
                // 定义加载PDB内容的函数
                var stringBlob = new Blob([content], {{type: 'text/plain'}});
                stage.loadFile(stringBlob, {{ext: "pdb", defaultRepresentation: true}});
            </script>
        </body>
    </html>
        """
      with open('selected.html', 'w') as f:
        f.write(html)
      return 'selected.pdb'
    def py_openwindows():
      # dummy callback
      pass
    js_openwindows = """
    () => {
        // 创建新窗口
        window.open('/selected.html', '_blank');
        return true;
    }
    """
    # 3) events
    gpu_status_tab.select(
      update_status,
      inputs = [],
      outputs = list(gpu_status_outputs.values())
    )
    gpu_logs_tab.select(
      update_logs,
      inputs = [gpu_id_input],
      outputs = [logs_output]
    )
    gpu_id_input.change(
      update_logs,
      inputs = [gpu_id_input],
      outputs = [logs_output]
    )
    submit_btn.click(
      run_prediction,
      inputs = [gpu_selector, fasta_file, model_preset, models_to_relax, max_template_date],
      outputs = [status_output]
    )
    view_tab.select(
      list_results,
      inputs = [view_gpu_selector],
      outputs = [results]
    )
    view_gpu_selector.change(
      list_results,
      inputs = [view_gpu_selector],
      outputs = [results]
    )
    interface.load(
      update_status,
      inputs = None,
      outputs = list(gpu_status_outputs.values())
    )
    results.select(
      prepare_files,
      inputs = [results],
      outputs = [download]
    )
    view_btn.click(
      fn = py_openwindows,
      inputs = None,
      outputs = None,
      js = js_openwindows
    )
  return interface

application = FastAPI()

@application.get("/selected.html")
def selected():
  return FileResponse("selected.html")

def main(unused_argv):
  global application
  import uvicorn
  manager = AlphaFoldManager(FLAGS.num_gpus)
  interface = create_interface(manager)
  application = mount_gradio_app(app = application, blocks = interface, path = "/")
  uvicorn.run(
    application,
    host = configs.service_host,
    port = configs.manager_service_port
  )

if __name__ == "__main__":
  add_options()
  app.run(main)
