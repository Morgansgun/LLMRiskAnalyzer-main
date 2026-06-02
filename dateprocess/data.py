import re
from io import StringIO
import pandas as pd

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

# 设备标签提取：找第一个像 “3DEG / 3RRI225VN / 4KRT036MA” 的 token
TAG_RE = re.compile(r"\b\d*[A-Z]{2,}[A-Z0-9]{0,10}\b")

def extract_device_tag(name: str) -> str:
    if not name:
        return "UNKNOWN"
    # 压缩空白，避免奇怪断行
    s = re.sub(r"\s+", " ", name.strip())
    m = TAG_RE.search(s)
    if not m:
        return "UNKNOWN"
    return m.group(0)

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


    df = pd.DataFrame(records, columns=FIELDS)
    df["_device_tag"] = df["异常缺陷名称"].apply(extract_device_tag)


    df["_unknown"] = (df["_device_tag"] == "UNKNOWN").astype(int)
    df = df.sort_values(by=["_unknown", "_device_tag", "异常缺陷名称"], kind="stable")

    # 去掉临时列再输出
    df = df.drop(columns=["_device_tag", "_unknown"])
    df.to_csv(out_csv, index=False, encoding="utf-8-sig")

    print(f"done: {len(df)} records -> {out_csv}")

if __name__ == "__main__":
    md_to_csv_by_heading(
        "C:/Users/22788/Desktop/LLMRiskAnalyzer-main/dateprocess/File.md",
        "C:/Users/22788/Desktop/LLMRiskAnalyzer-main/dateprocess/F.csv"
    )
