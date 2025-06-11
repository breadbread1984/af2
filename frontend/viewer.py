#!/usr/bin/python3

from flask import Flask, render_template, request, jsonify
import requests
import configs

app = Flask(__name__)

@app.route("/", methods = ['GET'])
def index():
  path = request.args.get('path')
  with open(path, 'r') as f:
    pdb_content = f.read()
  html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>NGL Viewer</title>
        <script src="https://unpkg.com/ngl@2.0.0-dev.34/dist/ngl.js"></script>
        <style>
            #viewport {{
                width: 100%;
                height: 500px;
                background-color: #f0f0f0;
            }}
        </style>
    </head>
    <body>
        <div id="viewport"></div>
        <script>
            // 创建NGL Viewer实例
            const stage = new NGL.Stage("viewport");
            
            // 加载PDB数据
            const pdbData = `{pdb_content}`;
            stage.loadFile(pdbData, {{ext: "pdb"}}).then(component => {{
                // 添加表示形式（卡通+球棍）
                component.addRepresentation("cartoon", {{color: "sstruc"}});
                component.addRepresentation("ball+stick", {{sele: "hetero"}});
                
                // 自动调整视角
                component.autoView();
            }});
            
            // 添加控件
            stage.addControls();
        </script>
    </body>
    </html>
    """
  return html

if __name__ == "__main__":
  app.run(port = configs.viewer_service_port)
