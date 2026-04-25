import csv
import json
from datetime import datetime
from typing import List, Optional


class AiSuggestion:
    def __init__(self, content="", reason="", comment=""):
        self.content = content
        self.reason = reason
        self.comment = comment

    @classmethod
    def from_dict(cls, data):
        return cls(content=data.get('content', ''), reason=data.get('reason', ''), comment=data.get('comment', ''))

    def to_dict(self):
        return {"content": self.content, "reason": self.reason, "comment": self.comment}


class AiGeneratedContent:
    def __init__(self, status="", suggestions=None):
        self.status = status
        self.suggestions = suggestions if suggestions is not None else []

    @classmethod
    def from_dict(cls, data):
        suggestions = [AiSuggestion.from_dict(s) for s in data.get('suggestions', [])]
        return cls(status=data.get('status', ''), suggestions=suggestions)

    def to_dict(self):
        return {"status": self.status, "suggestions": [s.to_dict() for s in self.suggestions]}


class Cell:
    def __init__(self, value="", ai_generated_content=None):
        self.value = value
        self.ai_generated_content = ai_generated_content if ai_generated_content is not None else AiGeneratedContent()

    @classmethod
    def from_dict(cls, data):
        ai_generated_content = AiGeneratedContent.from_dict(data.get('aiGeneratedContent', {}))
        return cls(value=data.get('value', ''), ai_generated_content=ai_generated_content)

    def to_dict(self):
        return {"value": self.value, "aiGeneratedContent": self.ai_generated_content.to_dict()}


class Entry:
    def __init__(self, entry_id=""):
        self.entry_id = entry_id
        self.cells = {}

    @classmethod
    def from_dict(cls, data):
        entry = cls(entry_id=data.get('entryId', ''))
        entry.cells = {name: Cell.from_dict(cell_data) for name, cell_data in data.get('cells', {}).items()}
        return entry

    def to_dict(self):
        return {"entryId": self.entry_id, "cells": {name: cell.to_dict() for name, cell in self.cells.items()}}

    def simplified_entry_dict(self):
        simple_dict = {"entryId": self.entry_id}
        simple_cells = {}
        for name, cell in self.cells.items():
            simple_cells[name] = cell.value
        simple_dict["cells"] = simple_cells
        return simple_dict

    def add_empty(self, cell_names: List[str]):
        """Create empty cells for given schema (dynamic columns)."""
        self.cells = {}
        for name in cell_names:
            self.cells[name] = Cell(value="", ai_generated_content=AiGeneratedContent(status="", suggestions=[]))


class FMEATable:
    def __init__(self, fmea_id="", project_id="", last_updated=None, column_names: Optional[List[str]] = None):
        self.fmea_id = fmea_id
        self.project_id = project_id
        self.last_updated = last_updated if last_updated is not None else datetime.now()
        self.entries: List[Entry] = []
        self.column_names: List[str] = column_names if column_names is not None else []

    @classmethod
    def from_dict(cls, data):
        table = cls(
            fmea_id=data.get('fmeaId', ''),
            project_id=data.get('projectId', ''),
            last_updated=datetime.fromisoformat(data.get('lastUpdated')) if data.get('lastUpdated') else None,
            column_names=data.get('columns', []) or []
        )
        table.entries = [Entry.from_dict(entry_data) for entry_data in data.get('entries', [])]

        # 兜底：如果没 columns，但 entries 有 cells，就从第一个 entry 推断列名
        if not table.column_names and table.entries and table.entries[0].cells:
            table.column_names = list(table.entries[0].cells.keys())

        return table

    def add_entry(self):
        """Append an empty row following current schema."""
        if not self.column_names:
            # 兜底：从现有 entries 推断
            if self.entries and self.entries[0].cells:
                self.column_names = list(self.entries[0].cells.keys())
            else:
                self.column_names = []  # 没 schema 就加不了有效行

        new_entry = Entry(entry_id=str(len(self.entries)))
        new_entry.add_empty(self.column_names)
        self.entries.append(new_entry)

    def to_dict(self):
        return {
            "fmeaId": self.fmea_id,
            "projectId": self.project_id,
            "lastUpdated": self.last_updated.isoformat() if isinstance(self.last_updated, datetime) else self.last_updated,
            "columns": self.column_names,
            "entries": [entry.to_dict() for entry in self.entries]
        }

    def to_json(self):
        return json.dumps(self.to_dict(), indent=4, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_data):
        """
        Support both:
        - old format: {fmeaId, projectId, lastUpdated, entries:[{cells:{...}}]}
        - new/simple format (optional): {columns:[...], rows:[{col:val,...}, ...]}
        """
        obj = cls()
        obj.fmea_id = json_data.get('fmeaId', '')
        obj.project_id = json_data.get('projectId', '')
        obj.last_updated = datetime.fromisoformat(json_data.get('lastUpdated')) if json_data.get('lastUpdated') else datetime.now()

        # New format
        if 'columns' in json_data and 'rows' in json_data and isinstance(json_data.get('rows'), list):
            obj.column_names = list(json_data.get('columns', []))
            for i, row in enumerate(json_data.get('rows', [])):
                entry = Entry(entry_id=str(i))
                entry.add_empty(obj.column_names)
                for k in obj.column_names:
                    entry.cells[k].value = (row.get(k, '') if isinstance(row, dict) else '')
                obj.entries.append(entry)
            return obj

        # Old format
        obj.column_names = list(json_data.get('columns', [])) if isinstance(json_data.get('columns'), list) else []
        for entry_data in json_data.get('entries', []):
            entry = Entry.from_dict(entry_data)
            obj.entries.append(entry)

        if not obj.column_names and obj.entries and obj.entries[0].cells:
            obj.column_names = list(obj.entries[0].cells.keys())

        return obj

    def to_csv(self, csv_filename):
        """Write current table schema to CSV. Use utf-8-sig for Excel friendliness."""
        column_names = self.column_names or (list(self.entries[0].cells.keys()) if self.entries else [])
        if not column_names:
            # nothing to write
            with open(csv_filename, 'w', encoding='utf-8-sig', newline='') as f:
                f.write("")
            return

        with open(csv_filename, 'w', encoding='utf-8-sig', newline='') as csvfile:
            writer = csv.writer(csvfile, delimiter=',')
            writer.writerow(column_names)
            for entry in self.entries:
                writer.writerow([entry.cells.get(name, Cell("")).value for name in column_names])

    @staticmethod
    def _open_with_fallback_encodings(path: str):
        """
        Try common encodings. Your File1.csv is typically GBK.
        Return a file handle opened in text mode.
        """
        # 优先尝试GB18030（GBK的超集，支持更多中文字符），然后是GBK和UTF-8
        encodings = ['gb18030', 'gbk', 'utf-8-sig', 'utf-8']
        best_enc = None
        best_score = float('inf')  # 替换字符数量，越少越好
        
        for enc in encodings:
            try:
                f = open(path, newline='', encoding=enc)
                sample = f.read(4096)
                f.seek(0)
                # 计算替换字符数量
                replacement_count = sample.count('\ufffd')
                if replacement_count < best_score:
                    best_score = replacement_count
                    if best_enc and best_enc != f:
                        best_enc.close()
                    best_enc = f
                else:
                    f.close()
            except UnicodeDecodeError:
                continue
            except Exception:
                continue
        
        # 如果找到了最佳编码，返回它
        if best_enc:
            best_enc.seek(0)
            return best_enc
        
        # 如果所有编码都失败，最后尝试使用errors='replace'作为兜底
        try:
            return open(path, newline='', encoding='gbk', errors='replace')
        except:
            return open(path, newline='', encoding='utf-8', errors='replace')
    
    @classmethod
    def from_csv(cls, csv_filename):
        desired_order = [
            "异常缺陷名称",
            "异常缺陷现象",
            "风险或潜在后果",
            "干预行动",
            "原因分析",
            "消缺行动",
            "相关知识",
            "故障图片",  # 确保 CSV 中的 "故障图片" 列
        ]

        f = cls._open_with_fallback_encodings(csv_filename)
        with f:
            sample = f.read(4096)
            f.seek(0)

            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=[',', ';', '\t'])
            except Exception:
                class _D: delimiter = ','
                dialect = _D()

            reader = csv.reader(f, delimiter=dialect.delimiter)
            try:
                header = next(reader)
            except StopIteration:
                return cls(column_names=[])

            header = [c.strip().lstrip('\ufeff') for c in header if c is not None]

            # 修复：由于CSV列名可能是乱码（编码问题），我们直接使用desired_order作为列名
            # 假设CSV的前N列按顺序对应desired_order的前N列
            # 直接使用desired_order作为final_cols，不依赖header（因为header可能是乱码）
            final_cols = list(desired_order)  # 直接使用desired_order，确保列名正确
            # 如果CSV有超出desired_order的列，也添加进去（虽然列名可能是乱码，但保留数据）
            if len(header) > len(desired_order):
                for idx in range(len(desired_order), len(header)):
                    final_cols.append(f"额外列{idx}")  # 使用通用名称，避免乱码列名

            obj = cls(column_names=final_cols)

            row_count = 0
            for i, row in enumerate(reader):
                # 使用原始CSV列名创建映射
                row_map = {h: (v or "").strip() for h, v in zip(header, row)}  # 按原始CSV列名映射
                entry = Entry(entry_id=str(i))
                entry.add_empty(final_cols)

                for col_idx, col in enumerate(final_cols):
                    # 如果列在desired_order中，通过位置映射获取数据
                    if col in desired_order:
                        # 找到desired_order中的索引
                        desired_idx = desired_order.index(col)
                        if desired_idx < len(header):
                            # 通过位置获取对应的原始CSV列名
                            original_csv_col = header[desired_idx]
                            # 直接从row列表按位置获取，避免列名匹配问题
                            if desired_idx < len(row):
                                raw_value = row[desired_idx]
                                # 清理值
                                value = (raw_value or "").strip()
                                entry.cells[col].value = value
                            else:
                                entry.cells[col].value = ""
                        else:
                            # 这是新增的列（如"故障图片"），值为空
                            entry.cells[col].value = ""
                    else:
                        # 这是CSV中多出来的列，直接使用原始列名
                        entry.cells[col].value = row_map.get(col, "")

                obj.entries.append(entry)
                row_count += 1

            # 确保使用正确的列名（final_cols），而不是从entries推断
            obj.column_names = final_cols

            return obj

    def to_table_text(self):
        if not self.entries:
            return "No entries available."
        column_names = self.column_names or (self.entries[0].cells.keys() if self.entries else [])
        header = " | ".join(column_names)
        lines = [header]
        for entry in self.entries:
            row = " | ".join(entry.cells.get(name, Cell("")).value for name in column_names)
            lines.append(row)
        return "\n".join(lines)


if __name__ == "__main__":
    csv_filename = "File1.csv"
    table = FMEATable.from_csv(csv_filename)
    print("COLUMNS:", table.column_names)
    print(table.to_table_text()[:1000])
