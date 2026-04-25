from openai import OpenAI
from dotenv import load_dotenv
import os
import together

load_dotenv()
together.api_key = os.getenv('TOGETHER_API_KEY')
gpt_call_count = 0

# ✅ SiliconFlow（硅基流动）OpenAI 兼容地址
silicon_client = OpenAI(
    api_key=os.getenv("SILICONFLOW_API_KEY"),  # 你的硅基流动 key
    base_url="https://api.siliconflow.cn/v1"
)



def gpt_model_call(prompt, model='silicon-qwen2.5-7b'):

    model_config = {
        'Llama_3': ('meta-llama/Llama-3-70b-chat-hf', 2000),
        'Mixtral-8x22B': ("mistralai/Mixtral-8x22B-Instruct-v0.1", 4048),
        'WizardLM-2': ("microsoft/WizardLM-2-8x22B", 2000),
        'gpt-3.5': ("gpt-3.5-turbo-0125", 2700),
        'gpt-4': ("gpt-4-0125-preview", 2700),

        # ✅ 新增：硅基流动 Qwen2.5-7B-Instruct
        'silicon-qwen2.5-7b': ("Qwen/Qwen2.5-7B-Instruct", 2700),
    }

    model_name, max_tokens = model_config.get(model)

    global gpt_call_count
    gpt_call_count += 1

    if model in ['silicon-qwen2.5-7b']:
        model_response = silicon_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": 
                 "You must respond with ONLY a valid JSON object.\n"
                "The JSON MUST have exactly this top-level key: output.\n"
                "output MUST be a list of exactly 5 objects.\n"
                "Each object MUST have keys: reason, content, comment.\n"
                "Do NOT include any other keys (no 'response').\n"
                "Do NOT use markdown or code fences."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=max_tokens,
        )
        return model_response.choices[0].message.content

    else:
        model_response = together.Complete.create(
            prompt=prompt,
            model=model_name,
            max_tokens=max_tokens,
            temperature=0,
            stop=["\n\n"]
        )
        return model_response['output']['choices'][0]['text'].strip()





# def gpt_model_call(prompt, model='Mixtral-8x22B'):

#     model_config = {
#         'Llama_3': ('meta-llama/Llama-3-70b-chat-hf', 2000),
#         'Mixtral-8x22B': ("mistralai/Mixtral-8x22B-Instruct-v0.1", 4048),
#         'WizardLM-2': ("microsoft/WizardLM-2-8x22B", 2000),
#         'gpt-3.5': ("gpt-3.5-turbo-0125", 2700),
#         'gpt-4': ("gpt-4-0125-preview", 2700),
#         "qwen-plus": ("qwen-plus", 2700),
#         "qwen-max": ("qwen-max", 2700),
#     }
#     model_name, max_tokens = model_config.get(model)

#     global gpt_call_count
#     gpt_call_count += 1

#     if model in ['gpt-4']:
#         model_response = client.chat.completions.create(
#             model=model_name,
#             response_format={"type": "json_object"},
#             messages=[
#                 {"role": "system", "content": "You are a helpful assistant designed to output JSON."},
#                 {"role": "user", "content": prompt}
#             ]
#         )
#         model_output = model_response.choices[0].message.content

#     elif model in ['gpt-3.5']:
#         model_response = client.chat.completions.create(
#             model=model_name,
#             response_format={"type": "json_object"},
#             messages=[
#                 {"role": "system", "content": "You are a helpful assistant designed to output JSON."},
#                 {"role": "user", "content": prompt}
#             ]
#         )
#         model_output = model_response.choices[0].message.content
    
#     elif model in ["qwen-plus", "qwen-max"]:
#         model_response = qwen_client.chat.completions.create(
#             model=model_name,
#             messages=[
#                 {"role": "system", "content": "You are a helpful assistant designed to output JSON."},
#                 {"role": "user", "content": prompt}
#             ],
#             temperature=0,
#             max_tokens=max_tokens
#         )
#         model_output = model_response.choices[0].message.content

#     else:
#         model_response = together.Complete.create(
#             prompt=prompt,
#             model=model_name,
#             max_tokens=max_tokens,
#             temperature=0,
#             stop=["\n\n"]
#         )
#         model_output = model_response['output']['choices'][0]['text'].strip()
#     return model_output
