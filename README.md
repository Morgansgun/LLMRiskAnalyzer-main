# 核电 FMEA 智能辅助分析系统

本项目是一个基于 Flask + 大语言模型的核电 FMEA 辅助分析系统，支持 FMEA 表格浏览与编辑、AI 候选建议生成、故障图片绑定、CSV 导出，以及中期指标评测复现。

## 1. 运行环境

建议环境：

- Windows 10/11
- Python 3.10 或 3.11
- pip
- 可访问大模型 API 的网络环境

项目主要依赖在：

```text
source_code/requirements.txt
```

其中包括 Flask、OpenAI SDK、Together SDK、python-dotenv、numpy 等。

## 2. 安装依赖

在项目根目录执行：

```bash
cd C:\Users\22788\Desktop\LLMRiskAnalyzer-main
python -m venv .venv
.\.venv\Scripts\activate
pip install -r source_code\requirements.txt
```

如果已经使用 Anaconda，也可以先创建环境：

```bash
conda create -n fmea-llm python=3.10
conda activate fmea-llm
pip install -r source_code\requirements.txt
```

## 3. 配置 API Key

AI 建议功能会调用 `source_code/llm.py` 中的大模型接口。请在项目根目录新建 `.env` 文件：

```env
SILICONFLOW_API_KEY=API_KEY
TOGETHER_API_KEY=Together_API_KEY
```

当前默认模型为：

```text
Qwen/Qwen2.5-7B-Instruct
```

对应配置位于：

```text
source_code/llm.py
```

如果只运行 cache 模式的评测脚本，不需要 API Key。

## 4. 启动系统

进入后端目录并启动 Flask：

```bash
cd LLMRiskAnalyzer-main\source_code
python app.py
```

启动成功后，在浏览器访问：

```text
http://127.0.0.1:8000
```

主要功能：

- 加载 FMEA 表格数据
- 编辑 FMEA 单元格
- 调用 AI 生成候选建议
- 上传和绑定故障图片
- 导出 CSV

注意：当前 `source_code/app.py` 中静态文件、图片目录和数据文件路径使用了本机绝对路径。如果项目移动到其他目录，需要同步修改 `STATIC_FOLDER`、`IMAGE_FOLDER` 和 `get_fmea_data()` 中的 CSV 路径。

## 5. 数据文件

系统默认读取：

```text
dateprocess/F.csv
```

备用或示例数据位于：

```text
source_code/dataset/
```

FMEA 数据包含字段：

- 异常缺陷名称
- 异常缺陷现象
- 风险或潜在后果
- 干预行动
- 原因分析
- 消缺行动
- 相关知识
- 故障图片

## 6. 运行评测模块

评测模块位于：

```text
evaluation/
```

### 融合准确率评测

默认使用缓存结果复现中期指标：

```bash
python evaluation/eval_fusion_accuracy.py --config evaluation/eval_config.yaml --use_cache true
```

预期输出：

```text
Total samples: 300
Correct samples: 270
Threshold: 0.78
Fusion Accuracy: 90.00%
Requirement: >80%
Result: PASS
```

如果使用实时大模型生成：

```bash
python evaluation/eval_fusion_accuracy.py --config evaluation/eval_config.yaml --use_cache false
```

live 模式需要 API Key，并且结果可能受模型服务稳定性影响。

### 平均耗时评测

```bash
python evaluation/eval_runtime.py --config evaluation/eval_config.yaml --repeat 100
```

该指标只统计 CSV 读取、字段规范化、上下文融合、字段遮蔽、图片字段绑定和样本构造耗时，不包含外部大模型生成耗时。

评测输出位于：

```text
evaluation/eval_results/
```

包括：

- `fusion_accuracy_result.csv`
- `runtime_result.csv`
- `summary.json`

更详细说明见：

```text
evaluation/README_EVAL.md
```

## 7. 常见问题

### 1）端口被占用

默认端口是 `8000`。如果端口被占用，可以修改 `source_code/app.py` 最后一行：

```python
app.run(debug=True, port=8000)
```

### 2）AI 建议为空或报错

请检查：

- `.env` 是否存在
- `SILICONFLOW_API_KEY` 是否正确
- 网络是否能访问模型服务
- `source_code/llm.py` 中模型名称是否可用

### 3）中文 CSV 打开乱码

系统导出的 CSV 使用 UTF-8-SIG，Excel 通常可以直接识别。如果仍然乱码，可以用 UTF-8 编码方式导入。

### 4）移动项目目录后图片或静态资源加载失败

请修改 `source_code/app.py` 中的绝对路径配置，确保指向当前机器上的真实目录。
