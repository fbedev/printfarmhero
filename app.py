import os
from pathlib import Path
import base64
from stl import mesh  # 需要 'numpy-stl' 套件
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
matplotlib.use('Agg')  # 設定為非 GUI 後端
import matplotlib.pyplot as plt

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 設定上傳資料夾
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

import threading
def generate_stl_preview(stl_path):
    try:
        logger.info(f"正在為 {stl_path} 生成預覽")
        your_mesh = mesh.Mesh.from_file(stl_path)
        
        fig = plt.figure(figsize=(5, 5))
        ax = fig.add_subplot(111, projection='3d')

        vectors = your_mesh.vectors
        collection = Poly3DCollection(vectors, facecolors='cyan', linewidths=0.1, edgecolors='black')
        ax.add_collection3d(collection)

        # 獲取邊界框
        min_vals = np.min(your_mesh.points, axis=0)
        max_vals = np.max(your_mesh.points, axis=0)

        # 調整縮放以避免過小顯示
        padding = 10
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
        logger.error(f"預覽生成失敗 {stl_path}: {str(e)}")
        return None

def generate_checklist_data(folder_path):
    if not os.path.exists(folder_path):
        logger.error(f"資料夾不存在: {folder_path}")
        return {"error": f"資料夾不存在: {folder_path}", "items": [], "file_count": 0}
    
    folder_name = os.path.basename(os.path.abspath(folder_path))
    checklist_items = []
    file_count = 0

    logger.info(f"正在掃描資料夾: {folder_path}")
    for root, dirs, files in os.walk(folder_path):
        logger.info(f"檢查目錄: {root}")
        for file in files:
            if file.lower().endswith('.stl'):
                file_count += 1
                stl_path = os.path.join(root, file)
                relative_path = os.path.relpath(stl_path, folder_path)
                preview_base64 = generate_stl_preview(stl_path) or ""
                item_id = relative_path.replace(os.sep, '_').replace('.', '_')

                checklist_items.append({
                    "id": item_id,
                    "filename": file,
                    "path": relative_path,
                    "preview": preview_base64
                })
                logger.info(f"已添加 STL 檔案: {stl_path}，ID: {item_id}")

    response = {
        "folder_name": folder_name,
        "items": checklist_items,
        "file_count": file_count
    }
    logger.info(f"已生成清單資料: {response}")
    return response

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_folder():
    logger.info("收到上傳請求")
    if 'folder' not in request.files:
        return jsonify({"error": "無資料夾檔案部分", "items": [], "file_count": 0}), 400
    
    file = request.files['folder']
    if file.filename == '':
        return jsonify({"error": "未選擇檔案", "items": [], "file_count": 0}), 400
    
    if file and file.filename.endswith('.zip'):
        try:
            zip_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(zip_path)
            extract_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename[:-4])

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)

            checklist_data = generate_checklist_data(extract_path)

            if not checklist_data:
                checklist_data = {"error": "無法生成清單", "items": [], "file_count": 0}

            # 清理
            os.remove(zip_path)
            shutil.rmtree(extract_path, ignore_errors=True)
            
            return jsonify(checklist_data)

        except Exception as e:
            logger.error(f"處理上傳時出錯: {str(e)}")
            return jsonify({"error": f"伺服器錯誤: {str(e)}", "items": [], "file_count": 0}), 500
    
    return jsonify({"error": "請上傳 .zip 檔案", "items": [], "file_count": 0}), 400

# 寫入 HTML 模板 (繁體中文與簡潔風格)
with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write('''<!DOCTYPE html>
<html>
<head>
    <title>3D列印清單生成器</title>
    <meta charset="UTF-8">
    <style>
        body {
            font-family: 'Noto Sans TC', sans-serif;
            margin: 0;
            padding: 20px;
            background: #ffffff;
            color: #333333;
            line-height: 1.6;
        }
        h1 {
            font-size: 1.8em;
            font-weight: 500;
            margin-bottom: 20px;
            text-align: center;
            color: #222222;
        }
        .container {
            max-width: 1000px;
            margin: 0 auto;
        }
        .input-container {
            padding: 15px 0;
            border-bottom: 1px solid #e0e0e0;
            margin-bottom: 20px;
        }
        .stl-item {
            padding: 15px 0;
            display: flex;
            align-items: center;
            border-bottom: 1px solid #f0f0f0;
            page-break-inside: avoid;
        }
        .stl-preview {
            width: 120px;
            height: 120px;
            margin-right: 20px;
            object-fit: contain;
        }
        .checkbox-container input[type="checkbox"] {
            width: 18px;
            height: 18px;
            margin-right: 20px;
            cursor: pointer;
        }
        .file-info {
            flex: 1;
        }
        .file-path {
            font-size: 0.9em;
            color: #666666;
            margin-top: 5px;
        }
        .button {
            padding: 10px 20px;
            border: 1px solid #333333;
            border-radius: 4px;
            background: none;
            cursor: pointer;
            font-size: 1em;
            margin-right: 10px;
            transition: background 0.2s ease;
        }
        .button:hover {
            background: #f5f5f5;
        }
        .button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        #folder-input {
            padding: 8px;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            font-size: 1em;
        }
        #checklist-container {
            margin-top: 20px;
        }
        .error-message {
            color: #d32f2f;
            padding: 10px 0;
        }
        .status-message {
            color: #666666;
            padding: 10px 0;
            text-align: center;
        }
        .loading-container {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.1);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 1000;
        }
        .loading-box {
            background: #ffffff;
            padding: 20px;
            border-radius: 4px;
            width: 250px;
            text-align: center;
            border: 1px solid #e0e0e0;
        }
        .progress-bar {
            width: 100%;
            height: 10px;
            background: #f0f0f0;
            border-radius: 5px;
            overflow: hidden;
            margin: 10px 0;
        }
        .progress {
            width: 0%;
            height: 100%;
            background: #333333;
            transition: width 0.3s ease;
        }
        .progress-text {
            color: #333333;
            font-size: 0.9em;
        }
        .credits {
            position: fixed;
            bottom: 10px;
            right: 10px;
            color: #666666;
            font-size: 0.8em;
        }
        @media print {
            .input-container, .button, .loading-container, .credits {
                display: none;
            }
            .stl-item {
                border: none;
                border-bottom: 1px solid #e0e0e0;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>3D列印清單生成器</h1>
        <div class="input-container">
            <input type="file" id="folder-input" name="folder" accept=".zip">
            <button class="button" id="generate-btn">生成清單</button>
            <button class="button" onclick="window.print()" style="display: none;" id="print-btn">列印清單</button>
        </div>
        <div id="checklist-container">
            <p class="status-message">上傳包含 STL  .zip 檔案。</p>
        </div>
    </div>

    <div class="loading-container" id="loading">
        <div class="loading-box">
            <h3>處理檔案中</h3>
            <div class="progress-bar">
                <div class="progress" id="progress"></div>
            </div>
            <p class="progress-text" id="progress-text">正在啟動...</p>
        </div>
    </div>

    <div class="credits">由 楊閔竣 製作 - 2025</div>

    <script>
        document.getElementById('generate-btn').addEventListener('click', uploadFolder);
        const loadingContainer = document.getElementById('loading');
        const progressBar = document.getElementById('progress');
        const progressText = document.getElementById('progress-text');

        function uploadFolder() {
            const fileInput = document.getElementById('folder-input');
            const file = fileInput.files[0];
            const container = document.getElementById('checklist-container');
            const generateBtn = document.getElementById('generate-btn');
            
            if (!file) {
                container.innerHTML = '<p class="error-message">請選擇一個 .zip 檔案上傳。</p>';
                return;
            }
            
            container.innerHTML = '';
            generateBtn.disabled = true;
            loadingContainer.style.display = 'flex';
            progressBar.style.width = '0%';
            progressText.textContent = '開始上傳...';

            const formData = new FormData();
            formData.append('folder', file);
            
            let progress = 0;
            const interval = setInterval(() => {
                progress += Math.random() * 10;
                if (progress > 90) progress = 90;
                updateProgress(progress);
            }, 500);

            fetch('/upload', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                clearInterval(interval);
                if (!response.ok) {
                    throw new Error(`HTTP 錯誤！狀態: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                updateProgress(100);
                setTimeout(() => {
                    loadingContainer.style.display = 'none';
                    generateBtn.disabled = false;
                    renderChecklist(data);
                }, 500);
            })
            .catch(error => {
                clearInterval(interval);
                loadingContainer.style.display = 'none';
                generateBtn.disabled = false;
                container.innerHTML = `<p class="error-message">錯誤: ${error.message}</p>`;
            });
        }

        function updateProgress(percentage) {
            progressBar.style.width = `${percentage}%`;
            progressText.textContent = `進度: ${Math.round(percentage)}% - 預計剩餘時間: ${estimateTime(percentage)}`;
        }

        function estimateTime(percentage) {
            if (percentage === 0) return '計算中...';
            const elapsed = performance.now() / 1000;
            const totalEstimated = (elapsed * 100) / percentage;
            const remaining = totalEstimated - elapsed;
            return remaining > 0 ? `${Math.round(remaining)}秒剩餘` : '完成中...';
        }

        function renderChecklist(data) {
            const container = document.getElementById('checklist-container');
            console.log('伺服器回應:', data);
            
            if (!data || typeof data !== 'object') {
                container.innerHTML = '<p class="error-message">無效的伺服器回應</p>';
                return;
            }
            
            if (data.error) {
                container.innerHTML = `<p class="error-message">${data.error}</p>`;
                return;
            }
            
            if (!data.items || !Array.isArray(data.items) || data.items.length === 0) {
                container.innerHTML = '<p class="error-message">上傳的 zip 中未找到 STL 檔案。</p>';
                return;
            }
            
            container.innerHTML = `<h2>清單: ${data.folder_name || '未知'}</h2>`;
            
            data.items.forEach((item, index) => {
                if (!item || !item.id || !item.filename || !item.path) {
                    console.warn(`索引 ${index} 處的項目無效:`, item);
                    return;
                }
                const itemHtml = `
                    <div class="stl-item">
                        <div class="checkbox-container">
                            <input type="checkbox" id="${item.id}">
                            <label for="${item.id}"></label>
                        </div>
                        ${item.preview ? 
                            `<img class="stl-preview" src="data:image/png;base64,${item.preview}" alt="${item.filename} 預覽">` :
                            `<div class="stl-preview">無預覽可用</div>`
                        }
                        <div class="file-info">
                            <div>${item.filename}</div>
                            <div class="file-path">${item.path}</div>
                        </div>
                    </div>
                `;
                container.innerHTML += itemHtml;
            });
            
            container.innerHTML += `<p>總共找到 STL 檔案數量: ${data.file_count || 0}</p>`;
            document.getElementById('print-btn').style.display = 'inline-block';
        }
    </script>
</body>
</html>
''')

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))
