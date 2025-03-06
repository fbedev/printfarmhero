import os
from pathlib import Path
import base64
from stl import mesh  # Requires 'numpy-stl' package
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from io import BytesIO
import numpy as np
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

def generate_stl_preview(stl_path):
    try:
        your_mesh = mesh.Mesh.from_file(stl_path)
        fig = plt.figure(figsize=(5, 5))
        ax = fig.add_subplot(111, projection='3d')
        vectors = your_mesh.vectors
        collection = Poly3DCollection(vectors, facecolors='cyan', linewidths=0.1, edgecolors='black')
        ax.add_collection3d(collection)
        scale = your_mesh.points.flatten()
        ax.auto_scale_xyz(scale, scale, scale)
        ax.set_axis_off()
        buf = BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0, dpi=100)
        buf.seek(0)
        plt.close(fig)
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"Preview generation failed for {stl_path}: {str(e)}")
        return None

def generate_checklist_data(folder_path):
    if not os.path.exists(folder_path):
        return {"error": f"Folder does not exist: {folder_path}"}
    
    folder_name = os.path.basename(os.path.abspath(folder_path))
    checklist_items = []
    file_count = 0
    
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith('.stl'):
                file_count += 1
                stl_path = os.path.join(root, file)
                relative_path = os.path.relpath(stl_path, folder_path)
                preview_base64 = generate_stl_preview(stl_path)
                item_id = relative_path.replace(os.sep, '_').replace('.', '_')
                
                checklist_items.append({
                    "id": item_id,
                    "filename": file,
                    "path": relative_path,
                    "preview": preview_base64
                })
    
    return {
        "folder_name": folder_name,
        "items": checklist_items,
        "file_count": file_count
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate_checklist', methods=['POST'])
def generate_checklist():
    folder_path = request.form.get('folder_path')
    if not folder_path:
        return jsonify({"error": "Please provide a folder path"}), 400
    
    checklist_data = generate_checklist_data(folder_path)
    return jsonify(checklist_data)

# HTML template will be in a separate file
with open('templates/index.html', 'w') as f:
    f.write('''<!DOCTYPE html>
<html>
<head>
    <title>3D Print Checklist Generator</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #333; }
        .stl-item { 
            border: 1px solid #ddd; 
            padding: 10px; 
            margin: 10px 0; 
            display: flex; 
            align-items: center; 
            page-break-inside: avoid;
        }
        .stl-preview { 
            width: 150px; 
            height: 150px; 
            margin-right: 20px; 
        }
        .checkbox-container { margin-right: 20px; }
        .file-path { font-size: 0.9em; color: #666; }
        .print-button, .generate-button {
            padding: 10px 20px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            margin: 10px 10px 10px 0;
        }
        .print-button:hover, .generate-button:hover {
            background-color: #45a049;
        }
        #folder-input {
            padding: 8px;
            width: 300px;
            margin-right: 10px;
        }
        #checklist-container { margin-top: 20px; }
        @media print {
            .print-button, .input-container { display: none; }
        }
    </style>
</head>
<body>
    <h1>3D Print Checklist Generator</h1>
    <div class="input-container">
        <input type="text" id="folder-input" placeholder="Enter folder path">
        <button class="generate-button" onclick="generateChecklist()">Generate Checklist</button>
        <button class="print-button" onclick="window.print()" style="display: none;" id="print-btn">Print Checklist</button>
    </div>
    <div id="checklist-container"></div>

    <script>
        function generateChecklist() {
            const folderPath = document.getElementById('folder-input').value;
            fetch('/generate_checklist', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: `folder_path=${encodeURIComponent(folderPath)}`
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    alert(data.error);
                    return;
                }
                
                const container = document.getElementById('checklist-container');
                container.innerHTML = `<h2>Checklist: ${data.folder_name}</h2>`;
                
                data.items.forEach(item => {
                    const itemHtml = `
                        <div class="stl-item">
                            <div class="checkbox-container">
                                <input type="checkbox" id="${item.id}">
                                <label for="${item.id}"></label>
                            </div>
                            ${item.preview ? 
                                `<img class="stl-preview" src="data:image/png;base64,${item.preview}" alt="${item.filename} preview">` :
                                `<div class="stl-preview">No preview available</div>`
                            }
                            <div>
                                <div>${item.filename}</div>
                                <div class="file-path">${item.path}</div>
                            </div>
                        </div>
                    `;
                    container.innerHTML += itemHtml;
                });
                
                container.innerHTML += `<p>Total STL files found: ${data.file_count}</p>`;
                document.getElementById('print-btn').style.display = 'inline-block';
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred while generating the checklist');
            });
        }
    </script>
</body>
</html>
''')

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8000)