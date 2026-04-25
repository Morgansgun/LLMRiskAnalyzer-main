from llm import gpt_model_call
import json, re

def extract_json_block(s: str) -> str | None:
    if not s:
        return None
    s = s.strip()

    # 去掉代码围栏
    s = re.sub(r"^```json\s*", "", s)
    s = re.sub(r"^```\s*", "", s)
    s = re.sub(r"\s*```$", "", s).strip()

    # 优先抓 JSON 数组 [...]
    m = re.search(r"(\[.*\])", s, re.S)
    if m:
        return m.group(1)

    # 再抓 JSON 对象 {...}
    m = re.search(r"(\{.*\})", s, re.S)
    if m:
        return m.group(1)

    return None



class BrainstormingAgent:
    def __init__(self):
        self.prompt_template = """你是一名核电站/核设施运行维护与缺陷分析专家，熟悉核电设备、系统、运行规程、检修逻辑、故障机理与风险评估表达方式。

下面是当前表格“仅供背景”，不要求你复述：
{{fmea_table}}

你只需要关注“当前这一行”：
{{selected_row}}

当前编辑的列名（中文字段）为： "{{dic}}"
该单元格已有内容： {{dic_key_value}}
用户正在输入（可能是前缀/不完整）： "{{user_text}}"

你的任务：
- 针对当前行的上下文（同一行其它列的内容），为列 "{{dic}}" 生成 5 条高质量、核电领域风格的候选内容（变体）。
- 每条候选必须与核电设备/系统/运行维护/缺陷管理相关，避免泛化（不要写“数据挖掘/机器学习/知识图谱”等泛内容）。
- 不要提问，不要输出多余解释，只输出 JSON。

“按列名自适配”规则（非常重要）：
1) 若 "{{dic}}" == "异常缺陷名称"
   - 输出应为“短标题式缺陷名称”，尽量包含：设备/部件 + 异常类型（如“阀门内漏”“泵振动超限”“冷却水断流”“仪表漂移”“联锁误动作”）
   - content：短语（建议 <= 16 字），避免长句

2) 若 "{{dic}}" == "异常缺陷现象"
   - 输出应描述“可观测现象/报警/趋势/参数变化/现场表现”
   - 建议写法：参数/信号 + 变化 + 触发条件（如“出口温度升高并波动”“差压突降伴随报警”“启停过程中振动显著上升”）

3) 若 "{{dic}}" == "风险或潜在后果"
   - 输出应描述“风险后果链条”，包含：影响对象（安全/可靠性/可用性/法规合规）+ 可能后果
   - 示例：导致系统功能下降、设备损伤扩大、非计划停机、人员/辐射/火灾风险上升、违反技术规范等

4) 若 "{{dic}}" == "原因分析"
   - 输出应为“工程原因/机理假设”，覆盖不同维度：设计/制造/安装/老化磨损/腐蚀/振动/热疲劳/异物/操作维护/仪表误差/环境
   - 每条原因尽量具体，避免空话（如“人为原因”太泛）

5) 若 "{{dic}}" == "干预行动"
   - 输出应为“短期控制/临时措施/运行对策”，优先可立即执行（隔离、切换、降功率、加强监视、增加巡检、临时校验等）
   - 语气偏运行值班/现场处置

6) 若 "{{dic}}" == "消缺行动"
   - 输出应为“根因消除/修复检修措施”，包含：检修动作 + 对象（更换/解体检查/修复/清洗/紧固/复测/试验验证/返厂等）
   - 尽量包含验收/复核要点

7) 若 "{{dic}}" == "相关知识"
   - 输出应为“经验要点/注意事项/判据/常见误区/参考规程点”
   - 可以是简短条目式知识点，不要写百科

多样性要求：
- 5 条必须互不重复，角度不同（不同设备部位/不同机理/不同措施/不同后果链）
- 结合当前行上下文进行“贴合”，不要脱离当前行随便编

输出格式要求：
- 只输出 JSON（不要 markdown、不要多余文本）
- 必须严格为：
{"output":[
  {"reason":"角度/类别(简短)", "content":"候选内容", "comment":"一句简短说明"},
  ...
]}

其中：
- reason：8~20字，说明该候选的角度（如“机理-腐蚀磨损”“处置-临时隔离”“后果-系统功能下降”）
- content：就是候选文本（根据列名写）
- comment：一句话补充说明（可为空，但建议给出）

现在开始输出（只输出 JSON）："""

    def generate_output(self, fmea_table, dic_key_value, selected_row, user_text, dic, model='silicon-qwen2.5-7b', image_info=''):
        user_text = (user_text or "").strip()
        if len(user_text) < 2:
            user_text = user_text + "..."

        # 仍按你要求的 replace 方式注入
        self.prompt_filled = self.prompt_template.replace("{{fmea_table}}", str(fmea_table))
        self.prompt_filled = self.prompt_filled.replace("{{dic_key_value}}", str(dic_key_value))
        self.prompt_filled = self.prompt_filled.replace("{{selected_row}}", str(selected_row))
        self.prompt_filled = self.prompt_filled.replace("{{dic}}", str(dic))
        self.prompt_filled = self.prompt_filled.replace("{{user_text}}", user_text)
        
        # 如果有图片信息，添加到提示末尾
        if image_info:
            self.prompt_filled = self.prompt_filled + image_info

        print("***********************")
        print("LLM agent working")
        print("***********************")
        print("=== PROMPT CHECK ===")
        print("cell key:", dic)
        print("user_text:", repr(user_text))
        print("prompt_head:", self.prompt_filled[:400])
        print("prompt_tail:", self.prompt_filled[-400:])
        print("prompt_len:", len(self.prompt_filled))

        try:
            text_output = gpt_model_call(self.prompt_filled, model=model)
        except Exception as call_err:
            print(f"LLM CALL ERROR: {call_err}")
            return None

        print("=== RAW MODEL OUTPUT (repr) ===")
        print(repr(text_output[:1200]))
        print("=== RAW MODEL OUTPUT (plain) ===")
        print(text_output[:1200])

        json_text = extract_json_block(text_output)
        if not json_text:
            print("NO JSON FOUND IN MODEL OUTPUT")
            return None

        try:
            result_json = json.loads(json_text)

            # 兼容模型直接返回 list 的情况
            if isinstance(result_json, list):
                result_json = {"output": result_json}

            # schema 校验
            if "output" not in result_json or not isinstance(result_json["output"], list):
                print("BAD SCHEMA:", result_json)
                return None

            result_json["output"] = result_json["output"][:5]

        except json.JSONDecodeError as json_err:
            print(f"JSON Decode Error: {json_err}")
            print("EXTRACTED JSON (repr):", repr(json_text[:1200]))
            print("EXTRACTED JSON TAIL (repr):", repr(json_text[-300:]))
            return None

        with open('generation_agent.json', 'w', encoding='utf-8') as file:
            json.dump(result_json, file, indent=4, ensure_ascii=False)

        return result_json


# Todo: new agent
class CompletingAgent:
    def __init__(self):
        self.prompt_template = """You are an expert FMEA engineer.

You MUST generate suggestions for the FMEA field: "{dic}" for the CURRENT ROW ONLY.

Context:
- Current row (text): {selected_row}
- Existing cell value: {dic_key_value}
- User typed a PARTIAL prefix: "{user_text}"

Task:
- Complete the partial prefix into 5 realistic FMEA {dic} variants for the current row context.
- The variants MUST be specific to the current process step (itemFunction) implied by the current row.
- Do NOT ask questions. If information is missing, make reasonable assumptions from the row context.

Important constraints:
- If the process step is related to cooking/preparation, focus on food safety failure modes (e.g., undercooking, cross-contamination, improper temperature, poor hygiene, wrong time/temperature).
- Do NOT output generic AI/ML workflow items (data mining, NLP, knowledge graph, etc.).
- Do NOT output procurement/sourcing issues unless the process step is clearly "Ingredient Sourcing".
- All 5 variants MUST be DISTINCT (different aspect: process, equipment, human error, environment, measurement/monitoring).
- Keep them short:
  - content: <= 8 words (a failure-mode phrase)
  - reason: <= 8 words
  - comment: <= 16 words

Return ONLY JSON in this exact format (no markdown, no extra text):
{{"output":[
  {{"reason":"...", "content":"...", "comment":"..."}},
  {{"reason":"...", "content":"...", "comment":"..."}},
  {{"reason":"...", "content":"...", "comment":"..."}},
  {{"reason":"...", "content":"...", "comment":"..."}},
  {{"reason":"...", "content":"...", "comment":"..."}}
]}}"""

    def generate_output(self, fmea_table, dic_key_value, selected_row, dic, model='silicon-qwen2.5-7b'):
        self.prompt_filled = self.prompt_template.replace("{{fmea_table}}", fmea_table)
        self.prompt_filled = self.prompt_filled.replace("{{dic_key_value}}", dic_key_value)
        self.prompt_filled = self.prompt_filled.replace("{{selected_row}}", selected_row)
        self.prompt_filled = self.prompt_filled.replace("{{dic}}", dic)

        # print(input_text)
        print("***********************")
        print("LLM agent working")
        print("***********************")
        try:
            text_output = gpt_model_call(self.prompt_filled, model=model)
            print(text_output)
        except Exception as e:
            print(f"Error: {e}")

            return None

        try:
            # Parse the text output into a JSON object
            result_json = json.loads(text_output)
            print(result_json)
        except json.JSONDecodeError as json_err:
            print(f"JSON Decode Error: {json_err}")
            return None

        # Write the JSON data to a file
        with open('generation_agent.json', 'w') as file:
            json.dump(result_json, file, indent=4)
        print("Result:\n")
        print(text_output)
        return result_json
