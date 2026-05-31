#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 ATM 实验数据集 xlsx 抽取内容，输出 JSON（不调用评估引擎）。

输出包含：原始表头、逐行原始单元格、映射后的标准列字典、以及按样本编号分组的 groups
（与 run_atm_dataset_experiment.py 输入格式一致）。

用法（在 backend 目录下）：
  python scripts/extract_atm_xlsx_to_json.py --excel ../ATM用例模型质量评估实验数据集.xlsx
  python scripts/extract_atm_xlsx_to_json.py --excel ../data.xlsx --sheet Sheet1 --out experiment_output/dataset.json
  python scripts/extract_atm_xlsx_to_json.py --excel ../data.xlsx --print-preview 8
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from atm_experiment_common import (
    BACKEND_ROOT,
    REPO_ROOT,
    build_extract_payload,
    group_rows,
    read_excel_sheet,
)


def _print_preview(payload: dict, max_rows: int) -> None:
    src = payload.get("source", {})
    print("=== 抽取摘要 ===")
    print(f"文件: {src.get('excel')}")
    print(f"工作表: {src.get('sheet')} | 全部表: {src.get('all_sheets')}")
    print(f"表头列数: {len(payload.get('headers', []))}")
    print(f"数据行数: {len(payload.get('rows_raw', []))}")
    print(f"分组样本数: {len(payload.get('groups', []))}")
    hm = payload.get("header_map_resolved") or {}
    print(f"已识别标准列: {list(hm.keys())}")
    print("\n=== 表头（原始）===")
    print(payload.get("headers"))
    print(f"\n=== 前 {max_rows} 行（rows_mapped）===")
    for i, row in enumerate(payload.get("rows_mapped", [])[:max_rows]):
        print(f"--- 行 {i + 1} ---")
        for k, v in row.items():
            if v:
                print(f"  {k}: {v}")
    print(f"\n=== 前 min(5,{len(payload.get('groups',[]))}) 个 groups 摘要 ===")
    for g in payload.get("groups", [])[:5]:
        print(f"  {g.get('样本编号')}: defects={len(g.get('defects',[]))}, declared_n={g.get('declared_n')}")


def main() -> int:
    parser = argparse.ArgumentParser(description="从 xlsx 抽取 ATM 实验数据集为 JSON")
    parser.add_argument(
        "--excel",
        type=str,
        default=str(REPO_ROOT / "ATM用例模型质量评估实验数据集.xlsx"),
        help="输入 xlsx 路径",
    )
    parser.add_argument("--sheet", type=str, default=None, help="工作表名（默认第一个）")
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="输出 JSON（默认 experiment_output/atm_dataset_extracted_时间戳.json）",
    )
    parser.add_argument(
        "--print-preview",
        type=int,
        nargs="?",
        const=5,
        default=None,
        metavar="N",
        help="打印前 N 行映射与分组摘要（不写文件时可单独使用）",
    )
    args = parser.parse_args()

    excel_path = Path(args.excel)
    if not excel_path.is_file():
        print(f"找不到 Excel: {excel_path}", file=sys.stderr)
        return 1

    try:
        header, data_rows, sheet_used, sheet_names = read_excel_sheet(excel_path, args.sheet)
    except Exception as e:
        print(f"读取失败: {e}", file=sys.stderr)
        return 1

    if not header:
        print("工作表为空", file=sys.stderr)
        return 1

    try:
        groups = group_rows(header, data_rows)
    except ValueError as e:
        print(f"分组失败: {e}", file=sys.stderr)
        return 1

    payload = build_extract_payload(excel_path, header, data_rows, sheet_used, sheet_names, groups)
    payload["extracted_at"] = datetime.now().isoformat(timespec="seconds")

    if args.print_preview is not None:
        _print_preview(payload, max(1, args.print_preview))

    out_dir = BACKEND_ROOT / "experiment_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.out:
        out_path = Path(args.out)
        if not out_path.is_absolute():
            out_path = (BACKEND_ROOT / out_path).resolve()
    else:
        out_path = out_dir / f"atm_dataset_extracted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"已写入: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
