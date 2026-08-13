#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate single-page HTML market sentiment daily report."""
import argparse
import json
from collections import defaultdict
from pathlib import Path


def resolve_paths(workspace: Path = None, out_name: str = None):
    if workspace is None:
        workspace = Path("/Users/zhiqiu/WorkBuddy/2026-08-12-11-38-00")
    workspace = Path(workspace)
    data_path = workspace / "report_data.json"
    if out_name is None:
        # derive date from report_data if available, else fallback
        out_name = "市场情绪日报.html"
    out_path = workspace / out_name
    return data_path, out_path


def fmt_change(v):
    if v is None:
        return "—"
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.2f}%"


def fmt_amount_wan(wan):
    """Convert 万 to 亿/万 with ¥."""
    if wan is None:
        return "—"
    if abs(wan) >= 10000:
        return f"¥{wan/10000:.2f}亿"
    return f"¥{wan:.0f}万"


def fmt_amount_yi(yi):
    if yi is None:
        return "—"
    return f"¥{yi:.2f}亿"


def color_class(v):
    if v is None:
        return "neutral"
    if v > 0:
        return "up"
    if v < 0:
        return "down"
    return "neutral"


def build_svg_theme_bar(themes, max_items=12):
    """Horizontal bar chart for theme frequency."""
    data = themes[:max_items][::-1]  # bottom-up for easy left-to-right top-down
    if not data:
        return ""
    max_count = max(c for _, c in data)
    w, h = 520, 28 * len(data) + 40
    bars = []
    y0 = 20
    for i, (name, count) in enumerate(data):
        y = y0 + i * 28
        bar_w = (count / max_count) * 360
        bars.append(
            f'<text x="10" y="{y+18}" class="theme-label" font-size="12">{name}</text>'
            f'<rect x="90" y="{y+4}" width="{bar_w:.1f}" height="18" rx="3" class="theme-bar"/>'
            f'<text x="{90+bar_w+8}" y="{y+18}" class="theme-count" font-size="12">{count}只</text>'
        )
    return f'<svg viewBox="0 0 {w} {h}" class="svg-chart">' + "".join(bars) + "</svg>"


def build_svg_industry(data, title, top_n=10):
    """Horizontal change% bar chart for industry ranking."""
    rows = data[:top_n] if "领涨" in title or "涨幅" in title else data[-top_n:][::-1]
    if not rows:
        return ""
    max_abs = max(abs(r["change_pct"]) for r in rows) or 1
    w, h = 560, 30 * len(rows) + 40
    bars = []
    y0 = 20
    for i, r in enumerate(rows):
        y = y0 + i * 30
        pct = r["change_pct"]
        bar_w = (abs(pct) / max_abs) * 280
        cls = "ind-up" if pct >= 0 else "ind-down"
        bars.append(
            f'<text x="10" y="{y+19}" class="ind-name" font-size="12">{r["rank"]}. {r["name"]}</text>'
            f'<rect x="110" y="{y+5}" width="{bar_w:.1f}" height="18" rx="3" class="{cls}"/>'
            f'<text x="{110+bar_w+8}" y="{y+19}" class="ind-pct {cls.replace("ind-", "")}" font-size="12">{fmt_change(pct)}</text>'
            f'<text x="420" y="{y+19}" class="ind-leader" font-size="11">龙头 {r["leader"]} {fmt_change(r["leader_change"])}</text>'
        )
    return f'<svg viewBox="0 0 {w} {h}" class="svg-chart">' + "".join(bars) + "</svg>"


def build_svg_dragon_bars(stocks, top_n=15):
    """Horizontal bar chart for dragon-tiger net buy."""
    rows = stocks[:top_n][::-1]
    if not rows:
        return ""
    max_net = max(max(r["net_buy_wan"], 1) for r in rows)
    w, h = 620, 32 * len(rows) + 30
    bars = []
    y0 = 10
    for i, r in enumerate(rows):
        y = y0 + i * 32
        val = r["net_buy_wan"]
        bar_w = (val / max_net) * 360
        bars.append(
            f'<text x="5" y="{y+20}" class="dt-name" font-size="12">{r["name"]} ({r["code"]})</text>'
            f'<rect x="130" y="{y+5}" width="{bar_w:.1f}" height="18" rx="3" class="netbuy-bar"/>'
            f'<text x="{130+bar_w+8}" y="{y+20}" class="dt-amount" font-size="12">{fmt_amount_wan(val)}</text>'
            f'<text x="510" y="{y+20}" class="dt-change {color_class(r["change_pct"])}" font-size="12">{fmt_change(r["change_pct"])}</text>'
        )
    return f'<svg viewBox="0 0 {w} {h}" class="svg-chart">' + "".join(bars) + "</svg>"


def consolidate_dragon_tiger(stocks):
    """Aggregate by stock code: sum net_buy, collect reasons, keep max turnover."""
    by_code = {}
    for s in stocks:
        code = s["code"]
        if code not in by_code:
            by_code[code] = {
                "code": code,
                "name": s["name"],
                "close": s["close"],
                "change_pct": s["change_pct"],
                "net_buy_wan": 0.0,
                "reasons": set(),
                "turnover_pct": s.get("turnover_pct") or 0,
            }
        by_code[code]["net_buy_wan"] += s.get("net_buy_wan") or 0
        by_code[code]["reasons"].add(s.get("reason", ""))
        by_code[code]["turnover_pct"] = max(by_code[code]["turnover_pct"], s.get("turnover_pct") or 0)
    # sort by net buy desc
    result = sorted(by_code.values(), key=lambda x: x["net_buy_wan"], reverse=True)
    for r in result:
        r["reason"] = "；".join(sorted(r["reasons"]))
    return result


def generate(data_path: Path = None, out_path: Path = None):
    if data_path is None:
        data_path, out_path = resolve_paths()
    data = json.loads(Path(data_path).read_text(encoding="utf-8"))
    trade_date = data.get("trade_date", "2026-08-11")
    out_path = Path(out_path)
    dt_stocks = consolidate_dragon_tiger(data["dragon_tiger"]["stocks"])
    total_records = data["dragon_tiger"]["total_records"]
    unique_count = len(dt_stocks)
    total_net_buy = sum(s["net_buy_wan"] for s in dt_stocks)

    themes = data.get("theme_freq", [])
    top_theme = themes[0] if themes else ("—", 0)

    ind_top = data["industry"]["top"]
    ind_bottom = data["industry"]["bottom"]
    top_industry = ind_top[0] if ind_top else {"name": "—", "change_pct": 0}

    # overview: count limit up / limit down among dragon tiger
    limit_up = sum(1 for s in dt_stocks if s["change_pct"] >= 9.9)
    limit_down = sum(1 for s in dt_stocks if s["change_pct"] <= -9.9)

    theme_svg = build_svg_theme_bar(themes)
    ind_top_svg = build_svg_industry(ind_top, "领涨行业 TOP10")
    ind_bottom_svg = build_svg_industry(ind_bottom, "领跌行业 TOP10")
    dt_svg = build_svg_dragon_bars(dt_stocks)

    # HTML template
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>A股市场情绪日报 · {trade_date}</title>
<style>
:root {{
  --bg: #0b0f19;
  --panel: #111827;
  --panel-2: #162033;
  --border: #1f2937;
  --text: #e5e7eb;
  --text-dim: #9ca3af;
  --up: #ef4444;
  --down: #22c55e;
  --neutral: #94a3b8;
  --accent: #f59e0b;
  --bar: #3b82f6;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; background: var(--bg); color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  font-size: 13px; line-height: 1.45;
}}
.container {{ max-width: 1200px; margin: 0 auto; padding: 18px 16px 40px; }}
header {{ border-bottom: 1px solid var(--border); padding-bottom: 14px; margin-bottom: 18px; }}
header h1 {{ margin: 0; font-size: 22px; letter-spacing: 0.5px; }}
header .subtitle {{ color: var(--text-dim); margin-top: 6px; font-size: 12px; }}
.overview {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 20px; }}
.card {{ background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 14px; }}
.card .label {{ color: var(--text-dim); font-size: 11px; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px; }}
.card .value {{ font-size: 22px; font-weight: 700; }}
.card .note {{ color: var(--text-dim); font-size: 11px; margin-top: 4px; }}
.up {{ color: var(--up); }}
.down {{ color: var(--down); }}
.neutral {{ color: var(--neutral); }}
.section {{ margin-top: 22px; }}
.section-title {{ font-size: 15px; font-weight: 700; margin-bottom: 10px; padding-left: 10px; border-left: 3px solid var(--accent); }}
.grid-2 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 16px; }}
.grid-3 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }}
.svg-chart {{ width: 100%; height: auto; display: block; }}
.theme-bar {{ fill: var(--bar); }}
.theme-label {{ fill: var(--text); }}
.theme-count {{ fill: var(--text-dim); }}
.ind-up {{ fill: var(--up); opacity: 0.85; }}
.ind-down {{ fill: var(--down); opacity: 0.85; }}
.ind-name {{ fill: var(--text); }}
.ind-pct {{ font-weight: 600; }}
.ind-leader {{ fill: var(--text-dim); }}
.netbuy-bar {{ fill: var(--bar); }}
.dt-name {{ fill: var(--text); }}
.dt-amount {{ fill: var(--text-dim); }}
.dt-change {{ font-weight: 600; }}
table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
th, td {{ padding: 8px 6px; text-align: right; border-bottom: 1px solid var(--border); white-space: nowrap; }}
th {{ color: var(--text-dim); font-weight: 600; text-align: right; background: var(--panel-2); position: sticky; top: 0; }}
tbody tr:hover {{ background: rgba(255,255,255,0.03); }}
td:first-child, th:first-child {{ text-align: left; padding-left: 10px; }}
.code {{ color: var(--text-dim); font-size: 11px; margin-left: 4px; }}
.reason {{ color: var(--text-dim); font-size: 11px; text-align: left; white-space: normal; max-width: 280px; line-height: 1.35; }}
.scroll {{ max-height: 520px; overflow-y: auto; border: 1px solid var(--border); border-radius: 8px; background: var(--panel); }}
.footer {{ margin-top: 28px; padding-top: 14px; border-top: 1px solid var(--border); color: var(--text-dim); font-size: 11px; line-height: 1.6; }}
.footer strong {{ color: var(--text); }}
@media (max-width: 640px) {{
  body {{ font-size: 14px; }}
  .container {{ padding: 12px 10px 28px; }}
  header h1 {{ font-size: 18px; }}
  .grid-2, .grid-3 {{ grid-template-columns: 1fr; }}
  .overview {{ grid-template-columns: repeat(2, 1fr); gap: 8px; }}
  .card {{ padding: 10px; }}
  .card .value {{ font-size: 18px; }}
  .section-title {{ font-size: 14px; }}
  table {{ font-size: 11px; min-width: 560px; }}
  th, td {{ padding: 6px 4px; }}
  .scroll {{ overflow-x: auto; max-height: none; }}
}}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>A股市场情绪日报 · <span class="up">{trade_date}</span></h1>
    <div class="subtitle">龙虎榜 + 题材热点 + 行业轮动 | 数据抓取时间 {data.get("query_time", "")[:19]}</div>
  </header>

  <div class="overview">
    <div class="card">
      <div class="label">龙虎榜上榜家数</div>
      <div class="value">{unique_count}<span style="font-size:13px;color:var(--text-dim)"> 家</span></div>
      <div class="note">原始记录 {total_records} 条，去重后 {unique_count} 家</div>
    </div>
    <div class="card">
      <div class="label">龙虎榜净买入合计</div>
      <div class="value up">{fmt_amount_wan(total_net_buy)}</div>
      <div class="note">机构/游资上榜席位净额汇总</div>
    </div>
    <div class="card">
      <div class="label">最热题材</div>
      <div class="value">{top_theme[0]}</div>
      <div class="note">同花顺强势股中出现 {top_theme[1]} 只</div>
    </div>
    <div class="card">
      <div class="label">领涨行业</div>
      <div class="value up">{top_industry["name"]} {fmt_change(top_industry["change_pct"])}</div>
      <div class="note">东财行业板块日涨幅第1</div>
    </div>
    <div class="card">
      <div class="label">涨停/跌停（龙虎榜内）</div>
      <div class="value"><span class="up">{limit_up}</span> / <span class="down">{limit_down}</span></div>
      <div class="note">涨跌幅≥9.9% 统计</div>
    </div>
  </div>

  <div class="grid-2">
    <div class="section">
      <div class="section-title">题材热度 TOP{min(12, len(themes))}</div>
      <div class="card">
        {theme_svg}
      </div>
    </div>
    <div class="section">
      <div class="section-title">领涨行业 TOP10</div>
      <div class="card">
        {ind_top_svg}
      </div>
    </div>
  </div>

  <div class="grid-2">
    <div class="section">
      <div class="section-title">领跌行业 TOP10</div>
      <div class="card">
        {ind_bottom_svg}
      </div>
    </div>
    <div class="section">
      <div class="section-title">龙虎榜净买入 TOP15</div>
      <div class="card">
        {dt_svg}
      </div>
    </div>
  </div>

  <div class="section">
    <div class="section-title">龙虎榜全榜单（按净买入降序）</div>
    <div class="scroll">
      <table>
        <thead>
          <tr>
            <th>排名</th>
            <th>股票</th>
            <th>代码</th>
            <th>收盘价</th>
            <th>涨跌幅</th>
            <th>净买入额</th>
            <th>换手率</th>
            <th style="text-align:left">上榜原因</th>
          </tr>
        </thead>
        <tbody>
'''
    for i, s in enumerate(dt_stocks, 1):
        cls = color_class(s["change_pct"])
        html += f'''          <tr>
            <td>{i}</td>
            <td><strong>{s["name"]}</strong></td>
            <td class="code">{s["code"]}</td>
            <td>{s["close"]:.2f}</td>
            <td class="{cls}">{fmt_change(s["change_pct"])}</td>
            <td class="{cls}">{fmt_amount_wan(s["net_buy_wan"])}</td>
            <td>{s["turnover_pct"]:.2f}%</td>
            <td class="reason">{s["reason"]}</td>
          </tr>
'''

    html += f'''        </tbody>
      </table>
    </div>
  </div>

  <div class="footer">
    <strong>数据来源：</strong><br>
    · 龙虎榜数据：东方财富 Choice 数据 / 东方财富数据中心龙虎榜 API（reportName=RPT_DAILYBILLBOARD_DETAILSNEW），统计交易日 {trade_date} 全部上榜记录；<br>
    · 题材归因：同花顺「强势股」接口（10jqka）reason 标签，按「+」拆分后做词频统计；<br>
    · 行业板块：东方财富 push2delay 行业板块行情接口（fs=m:90+s:4），含行业涨跌幅、上涨/下跌家数、领涨股；<br>
    · 金额单位：人民币，龙虎榜按「万元」原始口径展示，≥1亿自动转换为「亿元」；涨跌幅按 A 股惯例：红涨绿跌。<br>
    <div style="margin-top:6px">本报告仅供复盘参考，不构成投资建议。</div>
  </div>
</div>
</body>
</html>'''

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"Report saved: {out_path}")
    print(f"Unique dragon-tiger stocks: {unique_count}, total net buy: {fmt_amount_wan(total_net_buy)}")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Generate A-share sentiment HTML report")
    parser.add_argument("--workspace", default="/Users/zhiqiu/WorkBuddy/2026-08-12-11-38-00", help="Working directory")
    parser.add_argument("--out-dir", help="Output directory; default workspace")
    parser.add_argument("--out-name", help="Output HTML filename; default 市场情绪日报_<date>.html")
    args = parser.parse_args()
    workspace = Path(args.workspace)
    data_path = workspace / "report_data.json"
    # read trade_date from data to name file
    trade_date = "20260811"
    try:
        trade_date = json.loads(data_path.read_text(encoding="utf-8")).get("trade_date", trade_date).replace("-", "")
    except Exception:
        pass
    out_dir = Path(args.out_dir) if args.out_dir else workspace
    out_dir.mkdir(parents=True, exist_ok=True)
    out_name = args.out_name or f"市场情绪日报_{trade_date}.html"
    out_path = out_dir / out_name
    generate(data_path=data_path, out_path=out_path)


if __name__ == "__main__":
    main()
