import argparse
import csv
import json
import math
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_CODE_DIR = REPO_ROOT / "source_code"
if str(SOURCE_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_CODE_DIR))

_EMBEDDING_MODEL = None
_EMBEDDING_MODEL_NAME = None
_USING_EMBEDDINGS = False


def str_to_bool(value):
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {value}")


def require_file(path, label):
    if not Path(path).exists():
        raise FileNotFoundError(f"Missing {label}: {path}")


def load_config(config_path):
    require_file(config_path, "config file")
    try:
        import yaml

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    except ImportError:
        config = load_simple_yaml(config_path)
    return config


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


def load_records(data_path):
    require_file(data_path, "evaluation records CSV")
    with open(data_path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_ids(ids_path):
    require_file(ids_path, "record id list")
    with open(ids_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def load_cache(cache_path):
    require_file(cache_path, "generated output cache")
    with open(cache_path, "r", encoding="utf-8") as f:
        cache_items = json.load(f)
    if not isinstance(cache_items, list):
        raise ValueError(f"Cache must be a JSON list: {cache_path}")
    return {item.get("sample_id"): item for item in cache_items}


def normalize_record(row):
    return {str(k).strip().lstrip("\ufeff"): (v or "").strip() for k, v in row.items()}


def build_context_rows(records, row_index, target_field=None, window=2):
    start = max(0, row_index - window)
    end = min(len(records), row_index + window + 1)
    columns = [c for c in records[0].keys() if c != "record_id"] if records else []
    lines = [" | ".join(columns)]
    for i in range(start, end):
        row = dict(records[i])
        if target_field:
            row[target_field] = "[MASK]"
        values = [(row.get(col, "") or "")[:200] for col in columns]
        prefix = "[当前行] " if i == row_index else ""
        lines.append(prefix + " | ".join(values))
    return "\n".join(lines)


def build_masked_row(row, target_field):
    masked = dict(row)
    masked[target_field] = "[MASK]"
    return masked


def generate_live_prediction(records, row_index, target_field):
    try:
        from agents import BrainstormingAgent
    except Exception as exc:
        raise RuntimeError(f"Unable to import BrainstormingAgent from source_code/agents.py: {exc}") from exc

    row = records[row_index]
    masked_row = build_masked_row(row, target_field)
    image_info = ""
    image_name = row.get("故障图片", "")
    if image_name:
        image_info = f"\n\n当前行绑定故障图片：{image_name}。请结合图片文件名所代表的故障信息生成候选内容。"

    agent = BrainstormingAgent()
    result = agent.generate_output(
        fmea_table=build_context_rows(records, row_index, target_field=target_field),
        dic_key_value="",
        selected_row=str(masked_row),
        user_text="",
        dic=target_field,
        image_info=image_info,
    )
    if not result or "output" not in result or not result["output"]:
        return "", []

    candidates = [str(item.get("content", "")).strip() for item in result["output"] if isinstance(item, dict)]
    return (candidates[0] if candidates else ""), candidates


def _load_embedding_model(model_name):
    global _EMBEDDING_MODEL, _EMBEDDING_MODEL_NAME, _USING_EMBEDDINGS
    if _EMBEDDING_MODEL_NAME == model_name:
        return _EMBEDDING_MODEL
    _EMBEDDING_MODEL_NAME = model_name
    try:
        from sentence_transformers import SentenceTransformer

        try:
            _EMBEDDING_MODEL = SentenceTransformer(model_name, local_files_only=True)
        except TypeError:
            _EMBEDDING_MODEL = SentenceTransformer(model_name)
        _USING_EMBEDDINGS = True
    except Exception:
        _EMBEDDING_MODEL = None
        _USING_EMBEDDINGS = False
    return _EMBEDDING_MODEL


def compute_text_similarity(pred_text, gt_text, embedding_model=None):
    pred_text = (pred_text or "").strip()
    gt_text = (gt_text or "").strip()
    if not pred_text or not gt_text:
        return 0.0

    if embedding_model:
        model = _load_embedding_model(embedding_model)
        if model is not None:
            try:
                vectors = model.encode([pred_text, gt_text], normalize_embeddings=True)
                score = float(sum(float(a) * float(b) for a, b in zip(vectors[0], vectors[1])))
                return round(max(0.0, min(1.0, score)), 4)
            except Exception:
                pass

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        vectors = TfidfVectorizer(analyzer="char", ngram_range=(1, 3)).fit_transform([pred_text, gt_text])
        score = float(cosine_similarity(vectors[0], vectors[1])[0][0])
    except Exception:
        score = lexical_similarity(pred_text, gt_text)
    return round(max(0.0, min(1.0, score)), 4)


def lexical_similarity(a, b):
    a_set = set(a)
    b_set = set(b)
    if not a_set or not b_set:
        return 0.0
    return len(a_set & b_set) / math.sqrt(len(a_set) * len(b_set))


def write_summary(output_dir, fusion_summary):
    output_path = Path(output_dir) / "summary.json"
    if output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            summary = json.load(f)
    else:
        summary = {}
    summary["fusion_accuracy"] = fusion_summary
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def warn_if_expected_mismatch(config, total_samples, correct_samples, accuracy):
    expected_total = config.get("expected_total")
    expected_correct = config.get("expected_correct")
    expected_accuracy = config.get("expected_accuracy")
    if expected_total is not None and int(expected_total) != total_samples:
        print(f"WARNING: expected_total={expected_total}, actual_total={total_samples}")
    if expected_correct is not None and int(expected_correct) != correct_samples:
        print(f"WARNING: expected_correct={expected_correct}, actual_correct={correct_samples}")
    if expected_accuracy is not None and abs(float(expected_accuracy) - accuracy) > 1e-6:
        print(f"WARNING: expected_accuracy={expected_accuracy}, actual_accuracy={accuracy:.4f}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate multimodal FMEA field reconstruction accuracy.")
    parser.add_argument("--config", required=True, help="Path to eval_config.yaml")
    parser.add_argument("--use_cache", type=str_to_bool, default=True, help="true: read cached predictions; false: call BrainstormingAgent")
    args = parser.parse_args()

    config = load_config(args.config)
    required_keys = ["data_path", "test_ids_path", "cache_path", "output_dir", "target_fields", "threshold"]
    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        raise KeyError(f"Missing config keys: {', '.join(missing_keys)}")

    records = [normalize_record(row) for row in load_records(config["data_path"])]
    test_ids = set(load_ids(config["test_ids_path"]))
    target_fields = list(config["target_fields"])
    threshold = float(config["threshold"])
    output_dir = Path(config["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    if not records:
        raise ValueError(f"No records found in {config['data_path']}")
    for field in ["record_id", *target_fields]:
        if field not in records[0]:
            raise KeyError(f"Missing required field in eval CSV: {field}")

    cache = load_cache(config["cache_path"]) if args.use_cache else {}
    selected = [(idx, row) for idx, row in enumerate(records) if row.get("record_id") in test_ids]
    selected.sort(key=lambda item: item[1].get("record_id", ""))
    if not selected:
        raise ValueError("No test records matched test_ids.txt")

    result_rows = []
    correct_samples = 0
    for row_index, row in selected:
        record_id = row["record_id"]
        for target_field in target_fields:
            sample_id = f"{record_id}__{target_field}"
            ground_truth = row.get(target_field, "")
            if args.use_cache:
                if sample_id not in cache:
                    raise KeyError(f"Missing cached prediction for sample_id: {sample_id}")
                prediction = str(cache[sample_id].get("prediction", "") or "")
            else:
                prediction, _ = generate_live_prediction(records, row_index, target_field)

            similarity = compute_text_similarity(prediction, ground_truth, config.get("embedding_model"))
            is_correct = similarity >= threshold
            correct_samples += int(is_correct)
            result_rows.append(
                {
                    "sample_id": sample_id,
                    "record_id": record_id,
                    "target_field": target_field,
                    "ground_truth": ground_truth,
                    "prediction": prediction,
                    "similarity": f"{similarity:.4f}",
                    "threshold": f"{threshold:.2f}",
                    "is_correct": str(is_correct).lower(),
                }
            )

    result_path = output_dir / "fusion_accuracy_result.csv"
    with open(result_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["sample_id", "record_id", "target_field", "ground_truth", "prediction", "similarity", "threshold", "is_correct"],
        )
        writer.writeheader()
        writer.writerows(result_rows)

    total_samples = len(result_rows)
    accuracy = correct_samples / total_samples if total_samples else 0.0
    fusion_summary = {
        "task": "masked_fmea_field_reconstruction",
        "total_records": len(selected),
        "target_fields": target_fields,
        "total_samples": total_samples,
        "correct_samples": correct_samples,
        "threshold": threshold,
        "top1_accuracy": round(accuracy, 4),
        "requirement": ">80%",
        "passed": accuracy > 0.8,
    }
    write_summary(output_dir, fusion_summary)

    print(f"Total samples: {total_samples}")
    print(f"Correct samples: {correct_samples}")
    print(f"Threshold: {threshold:.2f}")
    print(f"Fusion Accuracy: {accuracy * 100:.2f}%")
    print("Requirement: >80%")
    print(f"Result: {'PASS' if fusion_summary['passed'] else 'FAIL'}")
    if not _USING_EMBEDDINGS:
        print("Similarity backend: TF-IDF fallback")
    warn_if_expected_mismatch(config, total_samples, correct_samples, accuracy)


if __name__ == "__main__":
    main()
