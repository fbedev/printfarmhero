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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def generate_stl_preview(stl_path):
    try:
        logger.info(f"Generating preview for: {stl_path}")
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
                preview_base64 = generate_stl_preview(stl_path)
                item_id = relative_path.replace(os.sep, '_').replace('.', '_')
                
                checklist_items.append({
                    "id": item_id,
                    "filename": file,
                    "path": relative_path,
                    "preview": preview_base64 if preview_base64 else ""
                })
                logger.info(f"Added STL file: {stl_path} with ID: {item_id}")
    
    if not checklist_items:
        logger.warning("No STL files found in the uploaded folder")
    
    response = {
        "folder_name": folder_name,
        "items": checklist_items,
        "file_count": file_count
    }
    logger.info(f"Generated checklist data: folder_name={folder_name}, items_count={len(checklist_items)}, file_count={file_count}")
    return response

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_folder():
    logger.info("Received upload request")
    if 'folder' not in request.files:
        logger.error("No folder file part in request")
        return jsonify({"error": "No folder file part", "items": [], "file_count": 0}), 400
    
    file = request.files['folder']
    if file.filename == '':
        logger.error("No selected file")
        return jsonify({"error": "No selected file", "items": [], "file_count": 0}), 400
    
    if file and file.filename.endswith('.zip'):
        try:
            # Save the uploaded zip file
            zip_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(zip_path)
            logger.info(f"Saved zip file to: {zip_path}")
            
            # Extract the zip file
            extract_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename[:-4])
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
            logger.info(f"Extracted zip to: {extract_path}")
            
            # Generate checklist from extracted folder
            checklist_data = generate_checklist_data(extract_path)
            
            # Clean up
            os.remove(zip_path)
            shutil.rmtree(extract_path, ignore_errors=True)
            logger.info("Cleaned up temporary files")
            
            return jsonify(checklist_data)
        except Exception as e:
            logger.error(f"Error processing upload: {str(e)}")
            return jsonify({"error": f"Error processing upload: {str(e)}", "items": [], "file_count": 0}), 500
    else:
        logger.error("Uploaded file is not a zip")
        return jsonify({"error": "Please upload a .zip file", "items": [], "file_count": 0}), 400

# HTML template with enhanced diagnostics
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
        @media print {
            .print-button, .input-container { display: none; }
        }
    </style>
</head>
<body>
    <h1>3D Print Checklist Generator</h1>
    <div class="input-container">
        <input type="file" id="folder-input" name="folder" accept=".zip">
        <button class="generate-button" onclick="uploadFolder()">Generate Checklist</button>
        <button class="print-button" onclick="window.print()" style="display: none;" id="print-btn">Print Checklist</button>
    </div>
    <div id="checklist-container"></div>

    <script>
        function uploadFolder() {
            const fileInput = document.getElementById('folder-input');
            const file = fileInput.files[0];
            if (!file) {
                alert('Please select a zip file');
                return;
            }
            
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
                const container = document.getElementById('checklist-container');
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
                
                if (!data.items || !Array.isArray(data.items)) {
                    container.innerHTML = '<p class="error-message">No STL files found or invalid items data</p>';
                    console.error('Items missing or not an array:', data.items);
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
                const container = document.getElementById('checklist-container');
                container.innerHTML = `<p class="error-message">An error occurred: ${error.message}</p>`;
            });
        }
    </script>
</body>
</html>
''')

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
