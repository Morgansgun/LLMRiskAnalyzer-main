import re
from io import StringIO
import pandas as pd

# 只改这里：新增“相关知识”
FIELDS = ["异常缺陷名称","异常缺陷现象","风险或潜在后果","干预行动","原因分析","消缺行动","相关知识"]

def iter_tables(md_text: str):
    for html in re.findall(r"<table\b.*?</table>", md_text, flags=re.S | re.I):
        try:
            dfs = pd.read_html(StringIO(html))
        except Exception:
            continue
        for df in dfs:
            yield df

def extract_kv_pairs(df: pd.DataFrame):
    pairs = []
    if df.shape[1] < 2:
        return pairs
    for _, r in df.iterrows():
        k = "" if pd.isna(r.iloc[0]) else str(r.iloc[0]).strip()
        v = "" if pd.isna(r.iloc[1]) else str(r.iloc[1]).strip()
        if k or v:
            k = k.replace("\n", "").replace(" ", "")
            pairs.append((k, v.strip()))
    return pairs

def split_by_entry_heading(md_text: str):
    pat = re.compile(r"(?m)^\s*#\s*\d+(?:\.\d+)+.*$")
    matches = list(pat.finditer(md_text))
    if not matches:
        return [md_text]
    sections = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i+1].start() if i+1 < len(matches) else len(md_text)
        sections.append(md_text[start:end])
    return sections

def md_to_csv_by_heading(md_path: str, out_csv: str):
    text = open(md_path, "r", encoding="utf-8").read()

    records = []
    for sec in split_by_entry_heading(text):
        cur = {k: "" for k in FIELDS}
        started = False

        def flush():
            nonlocal cur, started
            if started and any(cur.values()):
                records.append(cur)
            cur = {k: "" for k in FIELDS}
            started = False

        for df in iter_tables(sec):
            for k, v in extract_kv_pairs(df):
                if not v:
                    continue

                if k == "异常缺陷名称":
                    if started and cur["异常缺陷名称"]:
                        flush()
                    started = True
                    cur["异常缺陷名称"] = v
                    continue

                
                if k in cur:
                    started = True
                    if cur[k]:
                        cur[k] += "\n" + v
                    else:
                        cur[k] = v

        flush()

    pd.DataFrame(records, columns=FIELDS).to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"done: {len(records)} records -> {out_csv}")

if __name__ == "__main__":
    md_to_csv_by_heading("/home/sd/Harddisk/sba/hdxm/LLMRiskAnalyzer-main/dateprocess/File3.mmd", "/home/sd/Harddisk/sba/hdxm/LLMRiskAnalyzer-main/dateprocess/File3.csv")
