import os
from pathlib import Path
import base64
from stl import mesh  # Requires 'numpy-stl' package
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from io import BytesIO
import numpy as np
from flask import Flask, render_template, request, jsonify, send_from_directory
import zipfile
import shutil
import logging

app = Flask(__name__)
import matplotlib
matplotlib.use('Agg')  # Set the backend to Agg (non-GUI)
import matplotlib.pyplot as plt

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

import threading
def generate_stl_preview(stl_path):
    try:
        logger.info(f"Generating preview for: {stl_path}")
        your_mesh = mesh.Mesh.from_file(stl_path)
        
        fig = plt.figure(figsize=(5, 5))
        ax = fig.add_subplot(111, projection='3d')

        vectors = your_mesh.vectors
        collection = Poly3DCollection(vectors, facecolors='cyan', linewidths=0.1, edgecolors='black')
        ax.add_collection3d(collection)

        # Get bounding box
        min_vals = np.min(your_mesh.points, axis=0)
        max_vals = np.max(your_mesh.points, axis=0)

        # Adjust scaling to prevent tiny dots
        padding = 10  # Adjust padding if needed
        ax.set_xlim([min_vals[0] - padding, max_vals[0] + padding])
        ax.set_ylim([min_vals[1] - padding, max_vals[1] + padding])
        ax.set_zlim([min_vals[2] - padding, max_vals[2] + padding])

        ax.set_axis_off()

        buf = BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0, dpi=100)
        buf.seek(0)
        plt.close(fig)
        
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    except Exception as e:
        logger.error(f"Preview generation failed for {stl_path}: {str(e)}")
        return None
def generate_checklist_data(folder_path):
    if not os.path.exists(folder_path):
        logger.error(f"Folder does not exist: {folder_path}")
        return {"error": f"Folder does not exist: {folder_path}", "items": [], "file_count": 0}
    
    folder_name = os.path.basename(os.path.abspath(folder_path))
    checklist_items = []
    file_count = 0

    logger.info(f"Scanning folder: {folder_path}")
    for root, dirs, files in os.walk(folder_path):
        logger.info(f"Checking directory: {root}")
        for file in files:
            if file.lower().endswith('.stl'):
                file_count += 1
                stl_path = os.path.join(root, file)
                relative_path = os.path.relpath(stl_path, folder_path)
                preview_base64 = generate_stl_preview(stl_path) or ""  # Ensure preview is always a string
                item_id = relative_path.replace(os.sep, '_').replace('.', '_')

                checklist_items.append({
                    "id": item_id,
                    "filename": file,
                    "path": relative_path,
                    "preview": preview_base64
                })
                logger.info(f"Added STL file: {stl_path} with ID: {item_id}")

    response = {
        "folder_name": folder_name,
        "items": checklist_items,
        "file_count": file_count
    }
    logger.info(f"Generated checklist data: {response}")  # Log full response
    return response

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_folder():
    logger.info("Received upload request")
    if 'folder' not in request.files:
        return jsonify({"error": "No folder file part", "items": [], "file_count": 0}), 400
    
    file = request.files['folder']
    if file.filename == '':
        return jsonify({"error": "No selected file", "items": [], "file_count": 0}), 400
    
    if file and file.filename.endswith('.zip'):
        try:
            zip_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(zip_path)
            extract_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename[:-4])

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)

            checklist_data = generate_checklist_data(extract_path)

            # Ensure a valid response is always returned
            if not checklist_data:
                checklist_data = {"error": "Failed to generate checklist", "items": [], "file_count": 0}

            # Cleanup
            os.remove(zip_path)
            shutil.rmtree(extract_path, ignore_errors=True)
            
            return jsonify(checklist_data)

        except Exception as e:
            logger.error(f"Error processing upload: {str(e)}")
            return jsonify({"error": f"Server error: {str(e)}", "items": [], "file_count": 0}), 500
    
    return jsonify({"error": "Please upload a .zip file", "items": [], "file_count": 0}), 400

# Updated HTML template
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
        #folder-input { margin-right: 10px; }
        #checklist-container { margin-top: 20px; }
        .error-message { color: red; }
        .status-message { color: #333; }
        @media print {
            .print-button, .input-container { display: none; }
        }
    </style>
</head>
<body>
    <h1>3D Print Checklist Generator</h1>
    <div class="input-container">
        <input type="file" id="folder-input" name="folder" accept=".zip">
        <button class="generate-button" id="generate-btn">Generate Checklist</button>
        <button class="print-button" onclick="window.print()" style="display: none;" id="print-btn">Print Checklist</button>
    </div>
    <div id="checklist-container">
        <p class="status-message">Please upload a .zip file containing your STL folder structure.</p>
    </div>

    <script>
        document.getElementById('generate-btn').addEventListener('click', uploadFolder);

        function uploadFolder() {
            const fileInput = document.getElementById('folder-input');
            const file = fileInput.files[0];
            const container = document.getElementById('checklist-container');
            
            if (!file) {
                container.innerHTML = '<p class="error-message">Please select a .zip file to upload.</p>';
                return;
            }
            
            container.innerHTML = '<p class="status-message">Uploading and processing your zip file...</p>';
            document.getElementById('print-btn').style.display = 'none';
            
            const formData = new FormData();
            formData.append('folder', file);
            
            fetch('/upload', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('Server response:', data);
                container.innerHTML = '';
                
                if (!data || typeof data !== 'object') {
                    container.innerHTML = '<p class="error-message">Invalid server response</p>';
                    console.error('Invalid data format:', data);
                    return;
                }
                
                if (data.error) {
                    container.innerHTML = `<p class="error-message">${data.error}</p>`;
                    return;
                }
                
                if (!data.items || !Array.isArray(data.items) || data.items.length === 0) {
                    container.innerHTML = '<p class="error-message">No STL files found in the uploaded zip.</p>';
                    return;
                }
                
                container.innerHTML = `<h2>Checklist: ${data.folder_name || 'Unknown'}</h2>`;
                
                data.items.forEach((item, index) => {
                    if (!item || !item.id || !item.filename || !item.path) {
                        console.warn(`Invalid item at index ${index}:`, item);
                        return;
                    }
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
                
                container.innerHTML += `<p>Total STL files found: ${data.file_count || 0}</p>`;
                document.getElementById('print-btn').style.display = 'inline-block';
            })
            .catch(error => {
                console.error('Fetch error:', error);
                container.innerHTML = `<p class="error-message">An error occurred: ${error.message}</p>`;
            });
        }
    </script>
</body>
</html>
''')

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))
