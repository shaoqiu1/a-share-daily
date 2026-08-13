#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Daily orchestrator: fetch data, generate HTML report, write metadata."""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

# make sibling modules importable
WORKSPACE = Path("/Users/zhiqiu/WorkBuddy/2026-08-12-11-38-00")
sys.path.insert(0, str(WORKSPACE))

from fetch_data import fetch_all, get_default_trade_date
from generate_report import generate
from trading_calendar import is_trading_day


def copy_to_index(out_path: Path):
    """Copy the dated report to index.html for clean root URL access."""
    index_path = out_path.parent / "index.html"
    index_path.write_bytes(out_path.read_bytes())
    print(f"Copied to index: {index_path}")
    return index_path


def build_meta(report_data: dict, out_path: Path) -> dict:
    """Extract push summary from report_data."""
    from generate_report import consolidate_dragon_tiger

    dt_stocks = consolidate_dragon_tiger(report_data["dragon_tiger"]["stocks"])
    total_net_buy = sum(s["net_buy_wan"] for s in dt_stocks)
    themes = report_data.get("theme_freq", [])
    top_theme, top_theme_count = themes[0] if themes else ("—", 0)
    ind_top = report_data["industry"]["top"]
    top_industry = ind_top[0] if ind_top else {"name": "—", "change_pct": 0}
    return {
        "trade_date": report_data["trade_date"],
        "stock_count": len(dt_stocks),
        "total_net_buy_wan": round(total_net_buy, 1),
        "top_theme": top_theme,
        "top_theme_count": top_theme_count,
        "top_industry": top_industry["name"],
        "top_industry_pct": round(top_industry["change_pct"], 2),
        "html_path": str(out_path),
        "html_filename": out_path.name,
    }


def main():
    parser = argparse.ArgumentParser(description="Daily A-share sentiment report pipeline")
    parser.add_argument("--date", help="Trade date YYYY-MM-DD; default latest trading date")
    parser.add_argument("--workspace", default=str(WORKSPACE), help="Project workspace")
    parser.add_argument("--out-dir", default=str(WORKSPACE / "dist"), help="Deployment directory")
    parser.add_argument("--check-trading", action="store_true", help="Skip if date is not a trading day")
    args = parser.parse_args()

    workspace = Path(args.workspace)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    trade_date = args.date or get_default_trade_date()
    print(f"Target trade date: {trade_date}")

    if args.check_trading and not is_trading_day(trade_date):
        print(f"{trade_date} is not a trading day, skipping.")
        return None

    print("Fetching data...")
    report_data = fetch_all(trade_date, workspace)

    print("Generating HTML...")
    html_name = f"市场情绪日报_{trade_date.replace('-', '')}.html"
    out_path = out_dir / html_name
    generate(data_path=workspace / "report_data.json", out_path=out_path)

    # also copy as index.html so root URL works
    copy_to_index(out_path)

    meta = build_meta(report_data, out_path)
    meta_path = out_dir / "report_meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Metadata:", meta_path)
    print("Done.")
    return meta


if __name__ == "__main__":
    main()
