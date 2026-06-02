import argparse
import csv
import json
import time
from pathlib import Path


def load_config(config_path):
    if not Path(config_path).exists():
        raise FileNotFoundError(f"Missing config file: {config_path}")
    try:
        import yaml

        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        return load_simple_yaml(config_path)


def load_simple_yaml(config_path):
    config = {}
    current_key = None
    with open(config_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.rstrip()
            if not line or line.lstrip().startswith("#"):
                continue
            if line.startswith("  - ") and current_key:
                config.setdefault(current_key, []).append(parse_scalar(line[4:].strip()))
                continue
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                if value:
                    config[key] = parse_scalar(value)
                    current_key = None
                else:
                    config[key] = []
                    current_key = key
    return config


def parse_scalar(value):
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def require_file(path, label):
    if not Path(path).exists():
        raise FileNotFoundError(f"Missing {label}: {path}")


def load_records(data_path):
    require_file(data_path, "evaluation records CSV")
    with open(data_path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_ids(ids_path):
    require_file(ids_path, "record id list")
    with open(ids_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def normalize_record(row):
    return {str(k).strip().lstrip("\ufeff"): (v or "").strip() for k, v in row.items()}


def build_context(records, row_index, target_field, window=2):
    start = max(0, row_index - window)
    end = min(len(records), row_index + window + 1)
    columns = [c for c in records[0].keys() if c != "record_id"]
    lines = [" | ".join(columns)]
    for i in range(start, end):
        row = dict(records[i])
        row[target_field] = "[MASK]"
        values = [(row.get(col, "") or "")[:200] for col in columns]
        prefix = "[当前行] " if i == row_index else ""
        lines.append(prefix + " | ".join(values))
    return "\n".join(lines)


def construct_eval_samples(config):
    records = [normalize_record(row) for row in load_records(config["data_path"])]
    test_ids = set(load_ids(config["test_ids_path"]))
    target_fields = list(config["target_fields"])
    if not records:
        raise ValueError(f"No records found in {config['data_path']}")

    selected = [(idx, row) for idx, row in enumerate(records) if row.get("record_id") in test_ids]
    selected.sort(key=lambda item: item[1].get("record_id", ""))
    samples = []
    for row_index, row in selected:
        for target_field in target_fields:
            masked_row = dict(row)
            masked_row[target_field] = "[MASK]"
            samples.append(
                {
                    "sample_id": f"{row['record_id']}__{target_field}",
                    "record_id": row["record_id"],
                    "target_field": target_field,
                    "ground_truth": row.get(target_field, ""),
                    "masked_row": masked_row,
                    "image": row.get("故障图片", ""),
                    "context": build_context(records, row_index, target_field),
                }
            )
    return samples


def merge_runtime_summary(output_dir, runtime_summary):
    output_path = Path(output_dir) / "summary.json"
    if output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            summary = json.load(f)
    else:
        summary = {}
    summary["runtime"] = runtime_summary
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Evaluate FMEA preprocessing and context-fusion runtime.")
    parser.add_argument("--config", required=True, help="Path to eval_config.yaml")
    parser.add_argument("--repeat", type=int, default=100, help="Number of repeated preprocessing runs")
    args = parser.parse_args()

    if args.repeat <= 0:
        raise ValueError("--repeat must be a positive integer")

    config = load_config(args.config)
    required_keys = ["data_path", "test_ids_path", "output_dir", "target_fields"]
    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        raise KeyError(f"Missing config keys: {', '.join(missing_keys)}")

    output_dir = Path(config["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    total_time = 0.0
    sample_count = 0
    for repeat_index in range(1, args.repeat + 1):
        started = time.perf_counter()
        samples = construct_eval_samples(config)
        elapsed = time.perf_counter() - started
        total_time += elapsed
        sample_count = len(samples)
        rows.append(
            {
                "repeat_index": repeat_index,
                "sample_count": sample_count,
                "preprocessing_time_seconds": f"{elapsed:.4f}",
            }
        )

    result_path = output_dir / "runtime_result.csv"
    with open(result_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["repeat_index", "sample_count", "preprocessing_time_seconds"])
        writer.writeheader()
        writer.writerows(rows)

    avg_time = total_time / args.repeat
    runtime_summary = {
        "repeat": args.repeat,
        "avg_preprocessing_time": round(avg_time, 4),
        "requirement": "<5s",
        "passed": avg_time < 5.0,
    }
    merge_runtime_summary(output_dir, runtime_summary)

    print(f"Repeat: {args.repeat}")
    print(f"Samples per repeat: {sample_count}")
    print(f"Average preprocessing time: {avg_time:.4f}s")
    print("Requirement: <5s")
    print(f"Result: {'PASS' if runtime_summary['passed'] else 'FAIL'}")


if __name__ == "__main__":
    main()
