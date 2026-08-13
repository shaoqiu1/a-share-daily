import argparse
import json, time, random, requests, pandas as pd
from pathlib import Path
from collections import Counter
from datetime import datetime, timedelta

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"

EM_SESSION = requests.Session()
EM_SESSION.headers.update({"User-Agent": UA})
EM_MIN_INTERVAL = 1.0
_em_last_call = [0.0]

def em_get(url, params=None, headers=None, timeout=15, **kwargs):
    wait = EM_MIN_INTERVAL - (time.time() - _em_last_call[0])
    if wait > 0:
        time.sleep(wait + random.uniform(0.1, 0.5))
    kwargs.setdefault("proxies", {"http": None, "https": None})
    try:
        return EM_SESSION.get(url, params=params, headers=headers, timeout=timeout, **kwargs)
    finally:
        _em_last_call[0] = time.time()

def eastmoney_datacenter(report_name, columns="ALL", filter_str="", page_size=50,
                         sort_columns="", sort_types="-1") -> list:
    params = {
        "reportName": report_name, "columns": columns,
        "filter": filter_str, "pageNumber": "1", "pageSize": str(page_size),
        "sortColumns": sort_columns, "sortTypes": sort_types,
        "source": "WEB", "client": "WEB",
    }
    r = em_get(DATACENTER_URL, params=params, timeout=15)
    d = r.json()
    if d.get("result") and d["result"].get("data"):
        return d["result"]["data"]
    return []

def daily_dragon_tiger(trade_date):
    data = eastmoney_datacenter(
        "RPT_DAILYBILLBOARD_DETAILSNEW",
        filter_str=f"(TRADE_DATE>='{trade_date}')(TRADE_DATE<='{trade_date}')",
        page_size=500,
        sort_columns="BILLBOARD_NET_AMT", sort_types="-1",
    )
    stocks = []
    for row in data:
        net_buy = (row.get("BILLBOARD_NET_AMT") or 0) / 10000
        stocks.append({
            "code": row.get("SECURITY_CODE", ""),
            "name": row.get("SECURITY_NAME_ABBR", ""),
            "reason": row.get("EXPLANATION", ""),
            "close": row.get("CLOSE_PRICE") or 0,
            "change_pct": round(float(row.get("CHANGE_RATE") or 0), 2),
            "net_buy_wan": round(net_buy, 1),
            "buy_wan": round((row.get("BILLBOARD_BUY_AMT") or 0) / 10000, 1),
            "sell_wan": round((row.get("BILLBOARD_SELL_AMT") or 0) / 10000, 1),
            "turnover_pct": round(float(row.get("TURNOVERRATE") or 0), 2),
        })
    return {"date": trade_date, "total_records": len(stocks), "stocks": stocks}

def ths_hot_reason(date):
    url = (
        f"http://zx.10jqka.com.cn/event/api/getharden/"
        f"date/{date}/orderby/date/orderway/desc/charset/GBK/"
    )
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/117.0.0.0 Safari/537.36"}
    r = requests.get(url, headers=headers, timeout=10, proxies={"http": None, "https": None})
    data = r.json()
    if data.get("errocode", 0) != 0:
        raise RuntimeError(f"同花顺热点错误: {data.get('errormsg', '')}")
    rows = data.get("data") or []
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    rename_map = {
        "name": "名称", "code": "代码", "reason": "题材归因",
        "close": "收盘价", "zhangdie": "涨跌额", "zhangfu": "涨幅%",
        "huanshou": "换手率%", "chengjiaoe": "成交额",
        "chengjiaoliang": "成交量", "ddejingliang": "大单净量",
        "market": "市场",
    }
    return df.rename(columns=rename_map)

def industry_comparison(top_n=20):
    # 东财 push2 实时/延迟行情；实测主域名会被 RST，使用 push2delay 可稳定返回
    url = "https://push2delay.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": "200", "po": "1", "np": "1",
        "fltt": "2", "invt": "2",
        "fid": "f3",
        "fs": "m:90+s:4",  # 申万行业板块
        "fields": "f2,f3,f4,f12,f13,f14,f104,f105,f128,f136,f140,f141,f207",
    }
    headers = {"User-Agent": UA, "Referer": "https://quote.eastmoney.com/"}
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=20, proxies={"http": None, "https": None})
            d = r.json()
            break
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(1 + attempt)
    items = d.get("data", {}).get("diff", [])
    rows = []
    for i, item in enumerate(items):
        rows.append({
            "rank": i + 1,
            "name": item.get("f14", ""),
            "change_pct": item.get("f3", 0),
            "code": item.get("f12", ""),
            "up_count": item.get("f104", 0),
            "down_count": item.get("f105", 0),
            "leader": item.get("f128", ""),
            "leader_code": item.get("f140", ""),
            "leader_change": item.get("f136", 0),
        })
    # 接口默认按 f3 降序，底部直接取最后 top_n
    return {
        "top": rows[:top_n],
        "bottom": rows[-top_n:],
        "total": len(rows),
    }

def get_default_trade_date(today: datetime = None) -> str:
    """Return the most recent A-share trade date as 'YYYY-MM-DD'."""
    from trading_calendar import latest_trading_date
    return latest_trading_date((today or datetime.now()).date())


def save_partial(out, label, workspace: Path):
    out_path = workspace / "report_data.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved partial ({label}) to", out_path)


def fetch_all(trade_date: str, workspace: Path):
    out = {"trade_date": trade_date}
    print(f"Trade date: {trade_date}")
    print("Fetching dragon tiger...")
    out["dragon_tiger"] = daily_dragon_tiger(trade_date)
    save_partial(out, "dragon", workspace)
    print("Fetching THS hot reason...")
    df_hot = ths_hot_reason(trade_date)
    out["hot"] = df_hot.to_dict(orient="records") if not df_hot.empty else []
    # theme frequency
    all_tags = []
    for r in out["hot"]:
        reason = r.get("题材归因") or r.get("reason") or ""
        for t in str(reason).split("+"):
            t = t.strip()
            if t:
                all_tags.append(t)
    out["theme_freq"] = Counter(all_tags).most_common()
    save_partial(out, "hot", workspace)
    print("Fetching industry comparison...")
    try:
        out["industry"] = industry_comparison(20)
    except Exception as e:
        print("Industry fetch failed:", e)
        out["industry"] = {"top": [], "bottom": [], "total": 0, "error": str(e)}
    out["query_time"] = datetime.now().isoformat()
    save_partial(out, "final", workspace)
    print("Dragon count:", out["dragon_tiger"]["total_records"])
    print("Hot count:", len(out["hot"]))
    print("Industry total:", out["industry"].get("total"))
    return out


def main():
    parser = argparse.ArgumentParser(description="Fetch A-share market data")
    parser.add_argument("--date", help="Trade date YYYY-MM-DD; default latest trade date")
    parser.add_argument("--workspace", default="/Users/zhiqiu/WorkBuddy/2026-08-12-11-38-00", help="Working directory")
    args = parser.parse_args()
    workspace = Path(args.workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    trade_date = args.date or get_default_trade_date()
    fetch_all(trade_date, workspace)


if __name__ == "__main__":
    main()
