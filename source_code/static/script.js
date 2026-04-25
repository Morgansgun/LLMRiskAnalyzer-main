document.addEventListener('DOMContentLoaded', function () {
    // ✅ 你要求的列顺序（以你的文件为主）
    const DESIRED_COLUMNS = [
      "异常缺陷名称",
      "异常缺陷现象",
      "风险或潜在后果",
      "干预行动",
      "原因分析",
      "消缺行动",
      "相关知识",
      "故障图片"  // 添加故障图片列
    ];

    // Global state
    let raw_data = null;              // raw data returned by backend (whatever shape)
    let normalized = null;            // { columns: [...], rows: [...] }
    let userText = '';

    // Download CSV
    const downloadBtn = document.getElementById('downloadCSVButton');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', function () {
            fetch('/download_fmea_csv', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(raw_data)   // send raw data to backend
            })
            .then(response => {
                if (response.ok) return response.blob();
                throw new Error('Network response error.');
            })
            .then(blob => {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = 'download.csv';
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
            })
            .catch(error => console.error('Error downloading the file:', error));
        });
    }

    // Add New Entry
    const addBtn = document.getElementById('addNewEntryButton');
    if (addBtn) {
        addBtn.addEventListener('click', function () {
            fetch('/add_entry', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(raw_data)
            })
            .then(response => response.json())
            .then(updatedData => {
                raw_data = updatedData;
                normalized = normalizeData(updatedData);
                renderHeader(normalized.columns);
                populateTable(normalized.rows, normalized.columns);
            })
            .catch(error => console.error('Error adding new entry:', error));
        });
    }

    // Fetch initial data
    fetchData();

    function fetchData() {
        fetch('/get_fmea_data')
            .then(resp => resp.json())
            .then(data => {
                raw_data = data;
                normalized = normalizeData(data);
                renderHeader(normalized.columns);
                populateTable(normalized.rows, normalized.columns);
            })
            .catch(err => console.error('Error fetching data:', err));
    }

    // ✅ Normalize backend data to {columns, rows}
    function normalizeData(data) {
        // New target format: { columns: [...], rows: [ {col:val,...}, ... ] }
        if (data && Array.isArray(data.columns) && Array.isArray(data.rows)) {
            // ✅ 新格式也强制列顺序（如果后端未来也返回 columns/rows）
            const givenCols = data.columns.slice();
            const columns = [
                ...DESIRED_COLUMNS.filter(c => givenCols.includes(c)),
                ...givenCols.filter(c => !DESIRED_COLUMNS.includes(c))
            ];
            return { columns, rows: data.rows };
        }

        // Old format (current project): { entries: [ { cells: {key:{value,...}} } ] }
        if (data && Array.isArray(data.entries) && data.entries.length > 0 && data.entries[0].cells) {
            const cellKeys = Object.keys(data.entries[0].cells);

            // ✅ 强制列顺序：你要的顺序在前，多余列追加到末尾
            const columns = [
                ...DESIRED_COLUMNS.filter(c => cellKeys.includes(c)),
                ...cellKeys.filter(c => !DESIRED_COLUMNS.includes(c))
            ];

            const rows = data.entries.map(e => {
                const rowObj = {};
                columns.forEach(k => rowObj[k] = (e.cells[k] && e.cells[k].value) ? e.cells[k].value : '');
                return rowObj;
            });

            return { columns, rows };
        }

        // Fallback: empty
        return { columns: [], rows: [] };
    }

    // Render dynamic header
    function renderHeader(columns) {
        const headerRow = document.getElementById('tableHeaderRow');
        if (!headerRow) {
            console.warn("Missing #tableHeaderRow in HTML <thead>.");
            return;
        }

        headerRow.innerHTML = '';

        // Operation column
        const thOp = document.createElement('th');
        thOp.className = 'medium';
        thOp.textContent = '';
        headerRow.appendChild(thOp);

        // Dynamic columns
        columns.forEach(col => {
            const th = document.createElement('th');
            th.className = 'wide';
            th.textContent = col;
            headerRow.appendChild(th);
        });
    }

    // Populate table with data
    function populateTable(rows, columns) {
        const table = document.getElementById('fmeaTable');
        if (!table) return;

        const tableBody = table.getElementsByTagName('tbody')[0];
        tableBody.innerHTML = '';  // Reset table body

        rows.forEach((rowObj, rowIndex) => {
            const row = tableBody.insertRow();
            row.classList.add('normal-row');
            row.dataset.rowIndex = rowIndex;

            // Operation cell
            const opCell = row.insertCell();
            opCell.innerHTML = `<button class="editButton">Edit</button>
                                <button class="saveChange">Save</button>
                                <button class="cancelChange">Cancel</button>`;

            // Data cells
            columns.forEach(colKey => {
                const cell = row.insertCell();
                cell.classList.add('cell-data');
                cell.dataset.colKey = colKey;

                // For "故障图片", render image with upload/delete buttons
                if (colKey === "故障图片") {
                    const imgUrl = rowObj[colKey] ?? '';
                    cell.classList.add('image-cell');
                    
                    // 创建容器
                    const container = document.createElement('div');
                    container.style.position = 'relative';
                    container.style.display = 'inline-block';
                    
                    // 隐藏的文件输入（每个单元格一个）
                    const fileInput = document.createElement('input');
                    fileInput.type = 'file';
                    fileInput.accept = 'image/*';
                    fileInput.style.display = 'none';
                    fileInput.dataset.rowIndex = rowIndex;
                    fileInput.dataset.colKey = colKey;
                    fileInput.onchange = (e) => {
                        const file = e.target.files[0];
                        if (file) {
                            uploadImage(rowIndex, colKey, file);
                        }
                        // 重置input，允许重复上传同一文件
                        e.target.value = '';
                    };
                    cell.appendChild(fileInput);
                    
                    if (imgUrl && imgUrl.trim() !== '') {
                        // 显示图片
                        const imgElement = document.createElement('img');
                        imgElement.src = `/images/${imgUrl}`;
                        imgElement.alt = '故障图片';
                        imgElement.style.maxWidth = '150px';
                        imgElement.style.maxHeight = '150px';
                        imgElement.style.display = 'block';
                        imgElement.style.marginBottom = '5px';
                        imgElement.style.cursor = 'pointer';
                        imgElement.onerror = function() {
                            this.style.display = 'none';
                            container.innerHTML = '<span style="color: #999;">图片加载失败</span>';
                            const uploadBtn = document.createElement('button');
                            uploadBtn.textContent = '重新上传';
                            uploadBtn.style.cssText = 'padding: 5px 10px; background: #007bff; color: white; border: none; cursor: pointer; border-radius: 3px; font-size: 12px; margin-left: 5px;';
                            uploadBtn.onclick = (e) => {
                                e.stopPropagation();
                                triggerImageUpload(rowIndex, colKey);
                            };
                            container.appendChild(uploadBtn);
                        };
                        container.appendChild(imgElement);
                        
                        // 删除按钮
                        const deleteBtn = document.createElement('button');
                        deleteBtn.textContent = '删除';
                        deleteBtn.className = 'delete-image-btn';
                        deleteBtn.style.cssText = 'padding: 5px 10px; background: #dc3545; color: white; border: none; cursor: pointer; border-radius: 3px; font-size: 12px;';
                        deleteBtn.onclick = (e) => {
                            e.stopPropagation();
                            if (confirm('确定要删除这张图片吗？')) {
                                deleteImage(rowIndex, colKey);
                            }
                        };
                        container.appendChild(deleteBtn);
                    } else {
                        // 上传按钮
                        const uploadBtn = document.createElement('button');
                        uploadBtn.textContent = '上传图片';
                        uploadBtn.className = 'upload-image-btn';
                        uploadBtn.style.cssText = 'padding: 5px 10px; background: #007bff; color: white; border: none; cursor: pointer; border-radius: 3px; font-size: 12px;';
                        uploadBtn.onclick = (e) => {
                            e.stopPropagation();
                            triggerImageUpload(rowIndex, colKey);
                        };
                        container.appendChild(uploadBtn);
                    }
                    
                    cell.appendChild(container);
                } else {
                    cell.textContent = rowObj[colKey] ?? '';
                }
            });

            setupEditButtons(row, rowIndex, columns);
        });
    }

    function setupEditButtons(row, rowIndex, columns) {
        const editButton = row.querySelector('.editButton');
        const saveButton = row.querySelector('.saveChange');
        const cancelButton = row.querySelector('.cancelChange');

        saveButton.style.display = 'none';
        cancelButton.style.display = 'none';

        editButton.addEventListener('click', function () {
            toggleEdit(row, true, columns);
        });

        saveButton.addEventListener('click', function () {
            saveChanges(row, rowIndex, columns);
            toggleEdit(row, false, columns);
        });

        cancelButton.addEventListener('click', function () {
            populateTable(normalized.rows, normalized.columns);
        });
    }

    function toggleEdit(row, isEditing, columns) {
        const displayState = isEditing ? 'none' : '';
        const editState = isEditing ? '' : 'none';

        row.querySelectorAll('.cell-data').forEach((cell) => {
            const colKey = cell.dataset.colKey;
            
            // 跳过故障图片列（它有自己的编辑方式）
            if (colKey === "故障图片") {
                return;
            }

            if (isEditing) {
                const textarea = document.createElement('textarea');
                textarea.classList.add('editTextArea');
                // 获取当前单元格的文本内容（排除按钮等元素）
                const currentText = Array.from(cell.childNodes)
                    .filter(node => node.nodeType === Node.TEXT_NODE)
                    .map(node => node.textContent)
                    .join('')
                    .trim() || cell.textContent.trim();
                textarea.value = currentText;
                textarea.dataset.colKey = colKey;
                
                // 添加右键事件监听器
                textarea.addEventListener('contextmenu', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    requestAISuggestions(row, colKey, textarea.value);
                });

                cell.textContent = '';
                cell.appendChild(textarea);
            } else {
                const textarea = cell.querySelector('.editTextArea');
                if (textarea) {
                    cell.textContent = textarea.value;
                    textarea.remove();
                }
            }
        });

        row.querySelector('.editButton').style.display = displayState;
        row.querySelector('.saveChange').style.display = editState;
        row.querySelector('.cancelChange').style.display = editState;
    }
    
    // 请求AI建议
    function requestAISuggestions(row, colKey, userText) {
        // 获取行索引：优先使用dataset，否则从表格中查找
        let rowIndex = parseInt(row.dataset.rowIndex);
        if (isNaN(rowIndex)) {
            const tbody = row.parentNode;
            rowIndex = Array.from(tbody.children).indexOf(row);
        }
        
        const cellsData = {};
        
        // 收集当前行的所有数据
        row.querySelectorAll('.cell-data').forEach(cell => {
            const key = cell.dataset.colKey;
            if (key && key !== "故障图片") {
                const textarea = cell.querySelector('.editTextArea');
                cellsData[key] = textarea ? textarea.value : cell.textContent;
            }
        });
        
        // 获取故障图片URL（如果有）
        const imageCell = row.querySelector(`[data-col-key="故障图片"]`);
        let imageUrl = '';
        if (imageCell) {
            const img = imageCell.querySelector('img');
            if (img) {
                imageUrl = img.src.replace(/^.*\/images\//, '');
            }
        }
        
        // 显示加载提示（在文本框附近）
        const textarea = row.querySelector(`.editTextArea[data-col-key="${colKey}"]`);
        if (textarea) {
            showAISuggestionTooltip(textarea, '正在生成建议，请稍候...', 'info');
        }
        
        fetch('/generate_suggestions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                rowIndex: rowIndex,
                cellKey: colKey,
                userText: userText,
                cellsData: cellsData,
                imageUrl: imageUrl,  // 传递图片URL给后端
                fmea_data: raw_data
            })
        })
        .then(response => response.json())
        .then(data => {
            raw_data = data;
            normalized = normalizeData(data);
            
            // #region agent log
            fetch('http://127.0.0.1:7243/ingest/e421af0f-eb99-40f0-9802-139c8aef95a7',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'script.js:389',message:'generate_suggestions response received',data:{has_entries:!!data.entries,entries_count:data.entries?.length||0,row_index:rowIndex,cell_key:colKey,has_cell:!!(data.entries?.[rowIndex]?.cells?.[colKey])},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
            // #endregion
            
            // 显示AI建议 - 修复：使用正确的字段名 aiGeneratedContent (驼峰命名)
            if (data.entries && data.entries[rowIndex] && data.entries[rowIndex].cells && data.entries[rowIndex].cells[colKey]) {
                const cell = data.entries[rowIndex].cells[colKey];
                const aiContent = cell.aiGeneratedContent || cell.ai_generated_content; // 兼容两种命名
                
                // #region agent log
                fetch('http://127.0.0.1:7243/ingest/e421af0f-eb99-40f0-9802-139c8aef95a7',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'script.js:396',message:'checking aiContent',data:{has_aiContent:!!aiContent,aiContent_keys:aiContent?Object.keys(aiContent):[],suggestions_count:aiContent?.suggestions?.length||0},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
                // #endregion
                
                if (aiContent && aiContent.suggestions && aiContent.suggestions.length > 0) {
                    // 在文本框附近显示建议
                    const textarea = row.querySelector(`.editTextArea[data-col-key="${colKey}"]`);
                    if (textarea) {
                        displayAISuggestionsNearTextarea(aiContent.suggestions, colKey, textarea);
                    } else {
                        // 如果找不到textarea，使用侧边栏显示
                        displayAISuggestions(aiContent.suggestions, colKey);
                    }
                } else {
                    // 如果没有建议，显示提示
                    const textarea = row.querySelector(`.editTextArea[data-col-key="${colKey}"]`);
                    if (textarea) {
                        showAISuggestionTooltip(textarea, '未生成建议，请重试', 'error');
                    }
                }
            } else {
                // #region agent log
                fetch('http://127.0.0.1:7243/ingest/e421af0f-eb99-40f0-9802-139c8aef95a7',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'script.js:410',message:'data structure mismatch',data:{data_keys:Object.keys(data),has_entries:!!data.entries,entries_length:data.entries?.length||0},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
                // #endregion
                console.error('Data structure mismatch:', data);
            }
        })
        .catch(error => {
            console.error('Error generating suggestions:', error);
            const textarea = row.querySelector(`.editTextArea[data-col-key="${colKey}"]`);
            if (textarea) {
                showAISuggestionTooltip(textarea, '生成建议时出错，请重试', 'error');
            }
        });
    }
    
    // 在文本框附近显示AI建议（浮动提示框）
    function displayAISuggestionsNearTextarea(suggestions, colKey, textarea) {
        // 移除之前的提示框
        const existingTooltip = document.getElementById('ai-suggestion-tooltip');
        if (existingTooltip) {
            existingTooltip.remove();
        }
        
        // 创建新的提示框
        const tooltip = document.createElement('div');
        tooltip.id = 'ai-suggestion-tooltip';
        tooltip.style.cssText = `
            position: absolute; /* 相对于整页定位，随页面一起滚动 */
            background: white;
            border: 2px solid #007bff;
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 10000;
            max-width: 500px;
            max-height: 400px;
            overflow-y: auto;
            font-size: 14px;
        `;
        
        // 保存 textarea 引用到 tooltip，以便按钮点击时能找到
        tooltip.dataset.textareaId = textarea.id || `textarea-${Date.now()}`;
        if (!textarea.id) {
            textarea.id = tooltip.dataset.textareaId;
        }
        
        let html = `<div style="display: flex; justify-content: flex-end; align-items: center; margin-bottom: 10px;">
            <button onclick="document.getElementById('ai-suggestion-tooltip').remove()" style="background: #dc3545; color: white; border: none; cursor: pointer; border-radius: 3px; padding: 3px 8px; font-size: 12px;">×</button>
        </div>`;
        
        if (suggestions && suggestions.length > 0) {
            suggestions.forEach((suggestion, index) => {
                const content = suggestion.content || '';
                const reason = suggestion.reason || `建议 ${index + 1}`;
                const comment = suggestion.comment || '';
                // 使用 data 属性保存内容，避免转义问题
                html += `<div style="margin-bottom: 12px; padding: 10px; border: 1px solid #ddd; border-radius: 5px; background: #f8f9fa;">
                    <strong style="color: #495057;">${reason}</strong><br/>
                    <div style="margin: 5px 0; color: #212529;">${content}</div>
                    ${comment ? `<small style="color: #6c757d;">${comment}</small><br/>` : ''}
                    <button class="apply-suggestion-btn" data-content="${content.replace(/"/g, '&quot;').replace(/'/g, '&#39;')}" data-textarea-id="${tooltip.dataset.textareaId}" style="margin-top: 5px; padding: 5px 10px; background: #28a745; color: white; border: none; cursor: pointer; border-radius: 3px; font-size: 12px;">使用此建议</button>
                </div>`;
            });
        } else {
            html += '<p>暂无建议</p>';
        }
        
        tooltip.innerHTML = html;
        document.body.appendChild(tooltip);
        
        // 为所有"使用此建议"按钮添加事件监听器
        tooltip.querySelectorAll('.apply-suggestion-btn').forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                const content = this.dataset.content;
                const textareaId = this.dataset.textareaId;
                const targetTextarea = document.getElementById(textareaId);
                if (targetTextarea) {
                    targetTextarea.value = content;
                    targetTextarea.focus();
                    // 触发 input 事件，确保其他监听器能捕获到变化
                    targetTextarea.dispatchEvent(new Event('input', { bubbles: true }));
                    // 关闭提示框
                    tooltip.remove();
                }
            });
        });
        
        // 定位提示框在文本框附近（优先显示在下方，其次上方），考虑页面滚动
        const textareaRect = textarea.getBoundingClientRect();
        const tooltipRect = tooltip.getBoundingClientRect();

        // 默认贴在文本框下方，左对齐（加上页面滚动偏移）
        let left = textareaRect.left + window.scrollX;
        let top = textareaRect.bottom + 8 + window.scrollY;

        // 如果右侧超出视口，则向左收缩
        if (left + tooltipRect.width > window.scrollX + window.innerWidth - 10) {
            left = Math.max(
                window.scrollX + 10,
                window.scrollX + window.innerWidth - tooltipRect.width - 10
            );
        }

        // 如果底部超出视口，则改为显示在上方
        if (top + tooltipRect.height > window.scrollY + window.innerHeight - 10) {
            top = textareaRect.top - tooltipRect.height - 8 + window.scrollY;
        }

        // 最终安全边界（顶部不要太靠近窗口边缘）
        if (top < window.scrollY + 10) top = window.scrollY + 10;

        tooltip.style.left = `${left}px`;
        tooltip.style.top = `${top}px`;
        
        // 点击外部关闭
        setTimeout(() => {
            const closeOnClickOutside = (e) => {
                if (!tooltip.contains(e.target) && !textarea.contains(e.target)) {
                    tooltip.remove();
                    document.removeEventListener('click', closeOnClickOutside);
                }
            };
            document.addEventListener('click', closeOnClickOutside);
        }, 100);
    }
    
    // 显示简单的提示消息
    function showAISuggestionTooltip(textarea, message, type = 'info') {
        const tooltip = document.createElement('div');
        tooltip.id = 'ai-suggestion-tooltip';
        tooltip.style.cssText = `
            position: absolute; /* 相对于整页定位，随页面一起滚动 */
            background: ${type === 'error' ? '#f8d7da' : '#d1ecf1'};
            border: 1px solid ${type === 'error' ? '#f5c6cb' : '#bee5eb'};
            border-radius: 5px;
            padding: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            z-index: 10000;
            color: ${type === 'error' ? '#721c24' : '#0c5460'};
            font-size: 14px;
        `;
        tooltip.textContent = message;
        document.body.appendChild(tooltip);
        
        const textareaRect = textarea.getBoundingClientRect();
        let left = textareaRect.right + 10 + window.scrollX;
        let top = textareaRect.top + window.scrollY;

        // 右侧和底部边界处理
        const tooltipRect = tooltip.getBoundingClientRect();
        if (left + tooltipRect.width > window.scrollX + window.innerWidth - 10) {
            left = window.scrollX + window.innerWidth - tooltipRect.width - 10;
        }
        if (top + tooltipRect.height > window.scrollY + window.innerHeight - 10) {
            top = textareaRect.bottom - tooltipRect.height + window.scrollY;
        }

        tooltip.style.left = `${left}px`;
        tooltip.style.top = `${top}px`;
        
        setTimeout(() => {
            tooltip.remove();
        }, 3000);
    }
    
    
    // 应用建议（保留作为备用，但主要使用事件监听器）
    window.applySuggestion = function(suggestionText) {
        // 优先查找有焦点的文本框
        let targetTextarea = document.querySelector('.editTextArea:focus');
        // 如果没找到，查找最近使用的文本框（通过 tooltip 的 data 属性）
        if (!targetTextarea) {
            const tooltip = document.getElementById('ai-suggestion-tooltip');
            if (tooltip && tooltip.dataset.textareaId) {
                targetTextarea = document.getElementById(tooltip.dataset.textareaId);
            }
        }
        // 如果还是没找到，查找所有编辑中的文本框，取第一个
        if (!targetTextarea) {
            targetTextarea = document.querySelector('.editTextArea');
        }
        
        if (targetTextarea) {
            targetTextarea.value = suggestionText;
            targetTextarea.focus();
            // 触发 input 事件
            targetTextarea.dispatchEvent(new Event('input', { bubbles: true }));
            // 关闭提示框
            const tooltip = document.getElementById('ai-suggestion-tooltip');
            if (tooltip) {
                tooltip.remove();
            }
        }
    };
    
    // 触发图片上传
    function triggerImageUpload(rowIndex, colKey) {
        const row = document.querySelectorAll('#fmeaTable tbody tr')[rowIndex];
        if (row) {
            const cell = row.querySelector(`[data-col-key="${colKey}"]`);
            if (cell) {
                const fileInput = cell.querySelector('input[type="file"]');
                if (fileInput) {
                    fileInput.click();
                }
            }
        }
    }
    
    // 上传图片
    function uploadImage(rowIndex, colKey, file) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('rowIndex', rowIndex);
        formData.append('colKey', colKey);
        
        fetch('/upload_image', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // 更新本地数据
                if (normalized && normalized.rows[rowIndex]) {
                    normalized.rows[rowIndex][colKey] = data.filename;
                }
                if (raw_data && raw_data.entries && raw_data.entries[rowIndex]) {
                    if (!raw_data.entries[rowIndex].cells[colKey]) {
                        raw_data.entries[rowIndex].cells[colKey] = {value: '', aiGeneratedContent: {status: '', suggestions: []}};
                    }
                    raw_data.entries[rowIndex].cells[colKey].value = data.filename;
                }
                // 保存到后端
                saveImageToBackend(rowIndex, colKey, data.filename);
                // 重新渲染表格
                populateTable(normalized.rows, normalized.columns);
            } else {
                alert('图片上传失败：' + (data.error || '未知错误'));
            }
        })
        .catch(error => {
            console.error('Error uploading image:', error);
            alert('图片上传失败，请重试');
        });
    }
    
    // 保存图片信息到后端
    function saveImageToBackend(rowIndex, colKey, filename) {
        if (raw_data && raw_data.entries && raw_data.entries[rowIndex]) {
            if (!raw_data.entries[rowIndex].cells[colKey]) {
                raw_data.entries[rowIndex].cells[colKey] = {value: '', aiGeneratedContent: {status: '', suggestions: []}};
            }
            raw_data.entries[rowIndex].cells[colKey].value = filename;
            
            // 可选：立即保存到后端（如果需要持久化）
            // fetch('/update_entry', {
            //     method: 'POST',
            //     headers: { 'Content-Type': 'application/json' },
            //     body: JSON.stringify(raw_data)
            // });
        }
    }
    
    // 删除图片
    function deleteImage(rowIndex, colKey) {
        const filename = normalized.rows[rowIndex] ? normalized.rows[rowIndex][colKey] : '';
        if (!filename) {
            alert('没有图片可删除');
            return;
        }
        
        fetch('/delete_image', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                rowIndex: rowIndex,
                colKey: colKey,
                filename: filename
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // 更新本地数据
                if (normalized && normalized.rows[rowIndex]) {
                    normalized.rows[rowIndex][colKey] = '';
                }
                if (raw_data && raw_data.entries && raw_data.entries[rowIndex]) {
                    if (raw_data.entries[rowIndex].cells[colKey]) {
                        raw_data.entries[rowIndex].cells[colKey].value = '';
                    }
                }
                // 重新渲染表格
                populateTable(normalized.rows, normalized.columns);
            } else {
                alert('图片删除失败：' + (data.error || '未知错误'));
            }
        })
        .catch(error => {
            console.error('Error deleting image:', error);
            alert('图片删除失败，请重试');
        });
    }

    function saveChanges(row, rowIndex, columns) {
        const textAreas = row.querySelectorAll('.editTextArea');

        // update normalized rows
        textAreas.forEach((textarea) => {
            const colKey = textarea.dataset.colKey;
            normalized.rows[rowIndex][colKey] = textarea.value;
        });

        // also update raw_data if old-format entries
        if (raw_data && Array.isArray(raw_data.entries) && raw_data.entries[rowIndex] && raw_data.entries[rowIndex].cells) {
            textAreas.forEach((textarea) => {
                const colKey = textarea.dataset.colKey;
                if (raw_data.entries[rowIndex].cells[colKey]) {
                    raw_data.entries[rowIndex].cells[colKey].value = textarea.value;
                }
            });
        }

        populateTable(normalized.rows, normalized.columns);
    }
});
