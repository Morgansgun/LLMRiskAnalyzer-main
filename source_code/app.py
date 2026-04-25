from flask import Flask, jsonify, request, render_template, send_file, send_from_directory
from agents import BrainstormingAgent
from FEMA_data_model import FMEATable, AiSuggestion
import json
import os
import shutil
from werkzeug.utils import secure_filename
from datetime import datetime

# 设置 Flask 应用
app = Flask(__name__)

# 设置静态文件夹路径
app.config['STATIC_FOLDER'] = 'C:/Users/22788/Desktop/LLMRiskAnalyzer-main/source_code/static'  # 静态资源文件夹路径
app.config['IMAGE_FOLDER'] = 'C:/Users/22788/Desktop/LLMRiskAnalyzer-main/image/dataimage/czjyz_lw'  # 图片文件夹路径

# 为静态文件提供服务 (CSS, JS, 图片等)
@app.route('/static/<filename>')
def serve_static_file(filename):
    return send_from_directory(app.config['STATIC_FOLDER'], filename)

# 为图片提供服务
@app.route('/images/<filename>')
def serve_image(filename):
    return send_from_directory(app.config['IMAGE_FOLDER'], filename)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_fmea_data', methods=['GET'])
def get_fmea_table():
    # 获取 FMEA 数据的逻辑
    csv_filename = 'C:/Users/22788/Desktop/LLMRiskAnalyzer-main/dateprocess/F.csv'
    table = FMEATable.from_csv(csv_filename)
    result = table.to_dict()
    return jsonify(result)

@app.route('/add_entry', methods=['POST'])
def add_entry():
    data = request.get_json()
    table = FMEATable.from_json(data)
    table.add_entry()

    return jsonify(table.to_dict())

@app.route('/generate_suggestions', methods=['POST'])
def generate_suggestions():
    data = request.get_json()

    # 生成建议的逻辑
    row_index = int(data.get('rowIndex', 0))
    cell_key = data.get('cellKey', '')
    user_text = data.get('userText', '')
    cells_data = data.get('cellsData', {})
    image_url = data.get('imageUrl', '')  # 获取图片URL

    if 'table' in data and isinstance(data['table'], dict) and 'columns' in data['table'] and 'rows' in data['table']:
        table = FMEATable.from_json(data['table'])
    else:
        table = FMEATable.from_json(data.get('fmea_data', {}))

    suggestions = generate_suggestions_for_cell(table, row_index, cell_key, user_text, cells_data, image_url)

    if 0 <= row_index < len(table.entries):
        entry = table.entries[row_index]
        if cell_key in entry.cells:
            ai_content = entry.cells[cell_key].ai_generated_content
            ai_content.suggestions = suggestions
            ai_content.status = "generated"

    return jsonify(table.to_dict())

def generate_suggestions_for_cell(table, row_index, cell_key, user_text, cells_data, image_url=''):
    # 生成建议的逻辑
    if row_index < 0 or row_index >= len(table.entries):
        return []
    
    entry = table.entries[row_index]
    dic_key_value = entry.cells.get(cell_key, {}).value if cell_key in entry.cells else ''
    
    # 构建当前行的文本表示
    selected_row = {}
    for key, value in cells_data.items():
        # 限制每个字段的长度，避免提示词过长
        if value:
            # 只取前500个字符，避免单个字段过长
            selected_row[key] = value[:500] + ('...' if len(value) > 500 else '')
        else:
            selected_row[key] = value
    
    # 构建简化的表格文本：只包含当前行和前后各2行作为上下文（最多5行）
    context_rows = 2  # 前后各2行
    start_idx = max(0, row_index - context_rows)
    end_idx = min(len(table.entries), row_index + context_rows + 1)
    
    column_names = table.column_names or (list(table.entries[0].cells.keys()) if table.entries else [])
    header = " | ".join(column_names)
    lines = [header]
    
    # 只添加上下文行
    for i in range(start_idx, end_idx):
        entry = table.entries[i]
        row_values = []
        for col_name in column_names:
            cell_value = entry.cells.get(col_name, {}).value if col_name in entry.cells else ''
            # 限制每个单元格的值长度
            if cell_value:
                cell_value = cell_value[:200] + ('...' if len(cell_value) > 200 else '')
            row_values.append(cell_value)
        row_text = " | ".join(row_values)
        # 标记当前行
        if i == row_index:
            row_text = f"[当前行] {row_text}"
        lines.append(row_text)
    
    fmea_table = "\n".join(lines)
    
    # 创建agent并生成建议
    agent = BrainstormingAgent()
    
    # 如果有图片，在提示中添加图片信息
    image_info = ''
    if image_url:
        image_path = os.path.join(app.config['IMAGE_FOLDER'], image_url)
        if os.path.exists(image_path):
            image_info = f'\n\n重要提示：当前行有故障图片（文件名：{image_url}），图片已上传到服务器。请在生成建议时考虑图片中显示的故障现象、设备状态等信息，使建议更加贴合实际情况。'
    
    result = agent.generate_output(
        fmea_table=fmea_table,
        dic_key_value=dic_key_value[:500] if dic_key_value else '',  # 限制当前单元格值长度
        selected_row=str(selected_row),
        user_text=user_text[:200] if user_text else '',  # 限制用户输入长度
        dic=cell_key,
        image_info=image_info  # 传递图片信息
    )
    
    if result and 'output' in result:
        suggestions = []
        for item in result['output']:
            suggestions.append(AiSuggestion(
                content=item.get('content', ''),
                reason=item.get('reason', ''),
                comment=item.get('comment', '')
            ))
        return suggestions
    
    return []

@app.route('/upload_image', methods=['POST'])
def upload_image():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '没有文件'}), 400
    
    file = request.files['file']
    row_index = request.form.get('rowIndex')
    col_key = request.form.get('colKey')
    
    if file.filename == '':
        return jsonify({'success': False, 'error': '未选择文件'}), 400
    
    if file:
        # 生成唯一文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = secure_filename(file.filename)
        name, ext = os.path.splitext(filename)
        new_filename = f"{timestamp}_{name}{ext}"
        
        # 保存文件
        file_path = os.path.join(app.config['IMAGE_FOLDER'], new_filename)
        file.save(file_path)
        
        return jsonify({'success': True, 'filename': new_filename})
    
    return jsonify({'success': False, 'error': '上传失败'}), 500

@app.route('/delete_image', methods=['POST'])
def delete_image():
    data = request.get_json()
    filename = data.get('filename', '')
    
    if not filename:
        return jsonify({'success': False, 'error': '文件名不能为空'}), 400
    
    file_path = os.path.join(app.config['IMAGE_FOLDER'], filename)
    
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    else:
        return jsonify({'success': False, 'error': '文件不存在'}), 404

@app.route('/download_fmea_csv', methods=['POST'])
def download_fmea_csv():
    data = request.get_json()
    table = FMEATable.from_json(data)
    table.to_csv('download.csv')

    try:
        return send_file('download.csv', as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=8000)
