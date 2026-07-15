#!/usr/bin/env python3
"""
HTML 대시보드를 즉시 생성.
- Yahoo Finance에서 주가/환율 업데이트
- 4월 10일 이후 배당금을 자동 누적 반영
- 네트워크 불가 시 기본값 사용
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yieldmax_dividend_alert as ym

# GitHub Actions 등 서버 환경에서는 경로를 현재 디렉토리 기준으로 변경
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ym.HTML_FILE = os.path.join(SCRIPT_DIR, "yieldmax_dashboard.html")
ym.LOG_DIR = os.path.join(SCRIPT_DIR, "logs")
ym.DIVIDEND_ADDITIONS_FILE = os.path.join(ym.LOG_DIR, "dividend_additions.json")
os.makedirs(ym.LOG_DIR, exist_ok=True)

# Yahoo Finance에서 최신 목요일 종가 + 환율 업데이트 시도
print("📈 주가/환율 업데이트 중...")
ym.fetch_prices_from_yahoo()
print()

# ── 4월 10일 이후 전체 배당 데이터 (YieldMax 웹사이트 기준) ──
# 이 데이터는 메인 스크립트 실행 시 자동 스크래핑되지만,
# 네트워크 없이 대시보드만 갱신할 때를 위해 하드코딩

all_distributions_full = [
    # === CONY (4/10 이후 → 7/10까지) ===
    {"ticker": "CONY", "amount": 0.3833, "declared_date": "04/15/2026", "ex_date": "04/16/2026", "record_date": "04/16/2026", "payable_date": "04/17/2026", "roc": "0.00%"},
    {"ticker": "CONY", "amount": 0.4161, "declared_date": "04/22/2026", "ex_date": "04/23/2026", "record_date": "04/23/2026", "payable_date": "04/24/2026", "roc": "96.54%"},
    {"ticker": "CONY", "amount": 0.5307, "declared_date": "04/29/2026", "ex_date": "04/30/2026", "record_date": "04/30/2026", "payable_date": "05/01/2026", "roc": "81.77%"},
    {"ticker": "CONY", "amount": 0.4464, "declared_date": "05/06/2026", "ex_date": "05/07/2026", "record_date": "05/07/2026", "payable_date": "05/08/2026", "roc": "20.17%"},
    {"ticker": "CONY", "amount": 0.5631, "declared_date": "05/13/2026", "ex_date": "05/14/2026", "record_date": "05/14/2026", "payable_date": "05/15/2026", "roc": "0.00%"},
    {"ticker": "CONY", "amount": 0.3427, "declared_date": "05/20/2026", "ex_date": "05/21/2026", "record_date": "05/21/2026", "payable_date": "05/22/2026", "roc": "96.49%"},
    {"ticker": "CONY", "amount": 0.3345, "declared_date": "05/27/2026", "ex_date": "05/28/2026", "record_date": "05/28/2026", "payable_date": "05/29/2026", "roc": "19.42%"},
    {"ticker": "CONY", "amount": 0.2791, "declared_date": "06/03/2026", "ex_date": "06/04/2026", "record_date": "06/04/2026", "payable_date": "06/05/2026", "roc": "0.00%"},
    {"ticker": "CONY", "amount": 0.2681, "declared_date": "06/10/2026", "ex_date": "06/11/2026", "record_date": "06/11/2026", "payable_date": "06/12/2026", "roc": "0.00%"},
    {"ticker": "CONY", "amount": 0.2858, "declared_date": "06/17/2026", "ex_date": "06/18/2026", "record_date": "06/18/2026", "payable_date": "06/22/2026", "roc": "95.68%"},
    {"ticker": "CONY", "amount": 0.2598, "declared_date": "06/24/2026", "ex_date": "06/25/2026", "record_date": "06/25/2026", "payable_date": "06/26/2026", "roc": "95.43%"},
    {"ticker": "CONY", "amount": 0.2389, "declared_date": "07/01/2026", "ex_date": "07/02/2026", "record_date": "07/02/2026", "payable_date": "07/06/2026", "roc": "0.00%"},
    {"ticker": "CONY", "amount": 0.2794, "declared_date": "07/08/2026", "ex_date": "07/09/2026", "record_date": "07/09/2026", "payable_date": "07/10/2026", "roc": "95.87%"},

    # === MSTY (4/10 이후 → 7/10까지) ===
    {"ticker": "MSTY", "amount": 0.3038, "declared_date": "04/15/2026", "ex_date": "04/16/2026", "record_date": "04/16/2026", "payable_date": "04/17/2026", "roc": "98.21%"},
    {"ticker": "MSTY", "amount": 0.5211, "declared_date": "04/22/2026", "ex_date": "04/23/2026", "record_date": "04/23/2026", "payable_date": "04/24/2026", "roc": "99.05%"},
    {"ticker": "MSTY", "amount": 0.4886, "declared_date": "04/29/2026", "ex_date": "04/30/2026", "record_date": "04/30/2026", "payable_date": "05/01/2026", "roc": "99.09%"},
    {"ticker": "MSTY", "amount": 0.5553, "declared_date": "05/06/2026", "ex_date": "05/07/2026", "record_date": "05/07/2026", "payable_date": "05/08/2026", "roc": "99.10%"},
    {"ticker": "MSTY", "amount": 0.5363, "declared_date": "05/13/2026", "ex_date": "05/14/2026", "record_date": "05/14/2026", "payable_date": "05/15/2026", "roc": "0.00%"},
    {"ticker": "MSTY", "amount": 0.3136, "declared_date": "05/20/2026", "ex_date": "05/21/2026", "record_date": "05/21/2026", "payable_date": "05/22/2026", "roc": "41.70%"},
    {"ticker": "MSTY", "amount": 0.2979, "declared_date": "05/27/2026", "ex_date": "05/28/2026", "record_date": "05/28/2026", "payable_date": "05/29/2026", "roc": "18.63%"},
    {"ticker": "MSTY", "amount": 0.2459, "declared_date": "06/03/2026", "ex_date": "06/04/2026", "record_date": "06/04/2026", "payable_date": "06/05/2026", "roc": "0.00%"},
    {"ticker": "MSTY", "amount": 0.2117, "declared_date": "06/10/2026", "ex_date": "06/11/2026", "record_date": "06/11/2026", "payable_date": "06/12/2026", "roc": "0.00%"},
    {"ticker": "MSTY", "amount": 0.2286, "declared_date": "06/17/2026", "ex_date": "06/18/2026", "record_date": "06/18/2026", "payable_date": "06/22/2026", "roc": "96.87%"},
    {"ticker": "MSTY", "amount": 0.1883, "declared_date": "06/24/2026", "ex_date": "06/25/2026", "record_date": "06/25/2026", "payable_date": "06/26/2026", "roc": "28.96%"},
    {"ticker": "MSTY", "amount": 0.1549, "declared_date": "07/01/2026", "ex_date": "07/02/2026", "record_date": "07/02/2026", "payable_date": "07/06/2026", "roc": "0.00%"},
    {"ticker": "MSTY", "amount": 0.2061, "declared_date": "07/08/2026", "ex_date": "07/09/2026", "record_date": "07/09/2026", "payable_date": "07/10/2026", "roc": "95.06%"},

    # === YBIT (4/10 이후 → 7/10까지) ===
    {"ticker": "YBIT", "amount": 0.2778, "declared_date": "04/15/2026", "ex_date": "04/16/2026", "record_date": "04/16/2026", "payable_date": "04/17/2026", "roc": "95.46%"},
    {"ticker": "YBIT", "amount": 0.2692, "declared_date": "04/22/2026", "ex_date": "04/23/2026", "record_date": "04/23/2026", "payable_date": "04/24/2026", "roc": "93.34%"},
    {"ticker": "YBIT", "amount": 0.3319, "declared_date": "04/29/2026", "ex_date": "04/30/2026", "record_date": "04/30/2026", "payable_date": "05/01/2026", "roc": "0.00%"},
    {"ticker": "YBIT", "amount": 0.3201, "declared_date": "05/06/2026", "ex_date": "05/07/2026", "record_date": "05/07/2026", "payable_date": "05/08/2026", "roc": "35.57%"},
    {"ticker": "YBIT", "amount": 0.2356, "declared_date": "05/13/2026", "ex_date": "05/14/2026", "record_date": "05/14/2026", "payable_date": "05/15/2026", "roc": "0.00%"},
    {"ticker": "YBIT", "amount": 0.1833, "declared_date": "05/20/2026", "ex_date": "05/21/2026", "record_date": "05/21/2026", "payable_date": "05/22/2026", "roc": "12.81%"},
    {"ticker": "YBIT", "amount": 0.1913, "declared_date": "05/27/2026", "ex_date": "05/28/2026", "record_date": "05/28/2026", "payable_date": "05/29/2026", "roc": "24.49%"},
    {"ticker": "YBIT", "amount": 0.1648, "declared_date": "06/03/2026", "ex_date": "06/04/2026", "record_date": "06/04/2026", "payable_date": "06/05/2026", "roc": "0.00%"},
    {"ticker": "YBIT", "amount": 0.1497, "declared_date": "06/10/2026", "ex_date": "06/11/2026", "record_date": "06/11/2026", "payable_date": "06/12/2026", "roc": "0.00%"},
    {"ticker": "YBIT", "amount": 0.1513, "declared_date": "06/17/2026", "ex_date": "06/18/2026", "record_date": "06/18/2026", "payable_date": "06/22/2026", "roc": "0.00%"},
    {"ticker": "YBIT", "amount": 0.1443, "declared_date": "06/24/2026", "ex_date": "06/25/2026", "record_date": "06/25/2026", "payable_date": "06/26/2026", "roc": "91.27%"},
    {"ticker": "YBIT", "amount": 0.1488, "declared_date": "07/01/2026", "ex_date": "07/02/2026", "record_date": "07/02/2026", "payable_date": "07/06/2026", "roc": "0.00%"},
    {"ticker": "YBIT", "amount": 0.1718, "declared_date": "07/08/2026", "ex_date": "07/09/2026", "record_date": "07/09/2026", "payable_date": "07/10/2026", "roc": "0.00%"},
]

# 누적배당금 업데이트 (4/10 이후 배당 반영)
print("💰 누적배당금 업데이트 중...")
ym.update_cumulative_dividends(all_distributions_full)
print()

# 최근 배당 (이번 주)
sample_recent = [d for d in all_distributions_full if d["payable_date"] == "07/10/2026"]
if not sample_recent:
    # fallback: 가장 최근 3건
    sample_recent = all_distributions_full[:3]

account_dividends = ym.calculate_dividends(sample_recent)
html_path = ym.generate_html_dashboard(sample_recent, all_distributions_full, account_dividends)
print(f"✅ 대시보드 생성 완료: {html_path}")
