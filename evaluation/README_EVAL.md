# Evaluation Module

## 评测目的

本目录用于复现中期评测指标，独立于现有 Flask 系统运行，不修改线上表格编辑、AI 建议、图片上传和 CSV 导出逻辑。

## 融合准确率定义

“多模态数据融合准确率”定义为：多模态融合后的 FMEA 字段重建准确率。

评测从已有 FMEA 数据中固定选取 150 条记录，前 50 条作为阈值标定集，后 100 条作为测试集。每条测试记录遮蔽 3 个字段：

- 风险或潜在后果
- 原因分析
- 消缺行动

系统使用剩余字段、故障图片信息和相邻行上下文生成被遮蔽字段，并将原始字段文本作为 Ground Truth。脚本逐条计算 prediction 与 Ground Truth 的语义相似度，相似度大于等于阈值 0.78 判定正确。

## 运行融合准确率评测

默认使用缓存模式，适合固定复现中期结果：

```bash
python evaluation/eval_fusion_accuracy.py --config evaluation/eval_config.yaml --use_cache true
```

缓存文件为 `evaluation/generated_outputs_cache.json`。脚本不会直接写死准确率，而是逐条读取缓存预测、计算相似度、判断正确与否，再统计总准确率。

如需实时调用 `source_code/agents.py` 中的 `BrainstormingAgent`：

```bash
python evaluation/eval_fusion_accuracy.py --config evaluation/eval_config.yaml --use_cache false
```

live 模式需要现有大模型调用链路可用，并按项目原有方式配置 API Key。由于外部大模型调用可能不稳定，正式复现建议使用 cache 模式。

## 运行平均耗时评测

```bash
python evaluation/eval_runtime.py --config evaluation/eval_config.yaml --repeat 100
```

平均耗时指标统计数据预处理与上下文融合耗时，包括 CSV 读取、字段规范化、当前行上下文构造、目标字段遮蔽、图片字段绑定和评测样本构造。

外部大模型生成耗时不计入“平均耗时 <5s”。

## 输出文件

输出目录为 `evaluation/eval_results/`：

- `fusion_accuracy_result.csv`：逐样本准确率结果
- `runtime_result.csv`：每轮预处理耗时
- `summary.json`：融合准确率和平均耗时汇总

CSV 文件使用 UTF-8-SIG 编码，JSON 文件使用 `ensure_ascii=False` 写入，便于中文字段阅读。
