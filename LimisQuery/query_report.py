#!/usr/bin/env python3
"""Query LIMIS integrated search by report number (exact match on detail tree)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from limis_client import LimisClient, LimisConfig

DEFAULT_USER = "18321261078"
DEFAULT_PASSWORD = "liu15123311854"
DEFAULT_BASE = "http://10.1.228.22"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="LIMIS 综合查询：按报告编号精确匹配并抓取 IntegratedDetail 详情"
    )
    parser.add_argument("report_no", help="报告编号，如 JG018-250187")
    parser.add_argument("--base", default=os.environ.get("LIMIS_BASE", DEFAULT_BASE))
    parser.add_argument("--user", default=os.environ.get("LIMIS_USER", DEFAULT_USER))
    parser.add_argument(
        "--password",
        default=os.environ.get("LIMIS_PASSWORD", DEFAULT_PASSWORD),
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="输出 JSON 路径（默认 output/<报告编号>.json）",
    )
    parser.add_argument(
        "--max-orders",
        type=int,
        default=30,
        help="最多检查多少个候选委托的详情页",
    )
    parser.add_argument(
        "--auth-type",
        default=os.environ.get("LIMIS_AUTH_TYPE", "1"),
        help="综合查询 authType：1样品主体 2副体 3任务 4合同（默认1；程序会自动回退）",
    )
    args = parser.parse_args()

    out = args.output or Path("output") / f"{args.report_no.replace('/', '_')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)

    client = LimisClient(
        LimisConfig(
            base_url=args.base,
            username=args.user,
            password=args.password,
            auth_type=args.auth_type,
        )
    )

    print(f"登录 {args.base}，按报告编号精确匹配: {args.report_no}")
    data = client.find_exact_report(
        args.report_no,
        max_orders_to_scan=args.max_orders,
    )

    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入 {out.resolve()}")

    match = data.get("match", {})
    if not match.get("found"):
        print("未找到完全一致的报告编号。")
        for note in data.get("notes", []):
            print(f"  - {note}")
        return 1

    print("\n--- 匹配结果 ---")
    print(f"报告: {match.get('testingReportNo')} (id={match.get('testingReportId')})")
    print(f"状态: {match.get('report_status')}")
    print(f"委托: {match.get('testingOrderNo')} (id={match.get('testingOrderId')})")
    print(f"详情: {match.get('detail_url')}")

    detail = data.get("detail") or {}
    pages = detail.get("pages") or {}
    if pages.get("raw_delegation", {}).get("fields"):
        print("\n原始委托单字段（节选）:")
        for k, v in list(pages["raw_delegation"]["fields"].items())[:8]:
            print(f"  {k}: {v[:60]}{'...' if len(v) > 60 else ''}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
