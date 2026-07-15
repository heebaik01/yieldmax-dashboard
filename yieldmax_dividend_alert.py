#!/usr/bin/env python3
"""
YieldMax ETF 주간 배당금(Distribution) 알림 스크립트
- CONY, MSTY, YBIT의 최신 배당금 정보를 가져와 HTML 대시보드 + macOS 알림으로 표시
- 매주 금요일 실행되도록 설계됨
- 현재 주가는 Yahoo Finance에서 목요일 종가 기준으로 자동 업데이트
- 참조: https://yieldmaxetfs.com/
"""

import requests
from bs4 import BeautifulSoup
import subprocess
import json
import os
import re
import webbrowser
from datetime import datetime, timedelta

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

# ──────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────
ETFS = {
    "CONY": "https://yieldmaxetfs.com/our-etfs/cony",
    "MSTY": "https://yieldmaxetfs.com/our-etfs/msty",
    "YBIT": "https://yieldmaxetfs.com/our-etfs/ybit",
}

# 각 계좌별 보유 수량 (엑셀 기준)
HOLDINGS = {
    "아빠": {"CONY": 181, "MSTY": 407, "YBIT": 40},
    "엄마": {"CONY": 70, "MSTY": 69, "YBIT": 27},
    "시윤": {"CONY": 40, "MSTY": 52, "YBIT": 20},
}

# 계좌별 투자 포트폴리오 정보 (엑셀 '계좌별 수익' 탭 기준)
# 누적배당금: 엑셀에 수기 입력된 마지막 날짜(2026-04-10)까지의 세후 합계
# 이후 배당금은 웹사이트에서 자동으로 가져와 누적 반영됨
PORTFOLIO_BASE_DATE = "04/10/2026"  # 엑셀 마지막 업데이트 날짜 (이 날짜 포함까지가 기준)

PORTFOLIO = {
    "아빠": {
        "투자금액_원화": 90_929_999,
        "ETF": {
            "CONY": {"수량": 181, "매수평단": 96.45, "매수금액": 17_456.74, "누적배당금": 10_512.44},
            "MSTY": {"수량": 407, "매수평단": 113.78, "매수금액": 46_306.91, "누적배당금": 26_222.97},
            "YBIT": {"수량": 40, "매수평단": 66.70, "매수금액": 2_668.07, "누적배당금": 1_014.87},
        },
    },
    "엄마": {
        "투자금액_원화": 30_000_000,
        "ETF": {
            "CONY": {"수량": 70, "매수평단": 134.27, "매수금액": 9_398.97, "누적배당금": 6_552.39},
            "MSTY": {"수량": 69, "매수평단": 172.51, "매수금액": 11_903.43, "누적배당금": 6_609.39},
            "YBIT": {"수량": 27, "매수평단": 70.92, "매수금액": 1_914.83, "누적배당금": 854.70},
        },
    },
    "시윤": {
        "투자금액_원화": 10_000_000,
        "ETF": {
            "CONY": {"수량": 40, "매수평단": 125.28, "매수금액": 5_011.34, "누적배당금": 2_610.91},
            "MSTY": {"수량": 52, "매수평단": 132.07, "매수금액": 6_867.54, "누적배당금": 3_630.91},
            "YBIT": {"수량": 20, "매수평단": 62.25, "매수금액": 1_245.00, "누적배당금": 572.76},
        },
    },
}

# 현재 주가 (스크립트 실행 시 업데이트됨, 기본값은 최근 데이터)
CURRENT_PRICES = {
    "CONY": 25.07,
    "MSTY": 21.29,
    "YBIT": 24.44,
}

EXCHANGE_RATE = 1483  # 원/달러 환율

TAX_RATE = 0.15  # 세금 15%

# 파일 경로
LOG_DIR = os.path.expanduser("~/scripts/logs")
LOG_FILE = os.path.join(LOG_DIR, "yieldmax_dividends.json")
HTML_FILE = os.path.expanduser("~/scripts/yieldmax_dashboard.html")


def fetch_prices_from_yahoo():
    """Yahoo Finance에서 최근 목요일 종가와 환율을 가져옵니다."""
    global CURRENT_PRICES, EXCHANGE_RATE

    if not HAS_YFINANCE:
        print("  ⚠️  yfinance 미설치 - 기본 주가 사용 (pip3 install yfinance)")
        return

    try:
        # 가장 최근 목요일 찾기
        today = datetime.now()
        # 요일: 0=월, 1=화, 2=수, 3=목, 4=금, 5=토, 6=일
        days_since_thursday = (today.weekday() - 3) % 7
        if days_since_thursday == 0 and today.hour < 16:
            # 오늘이 목요일이고 장 마감 전이면 지난주 목요일
            days_since_thursday = 7
        last_thursday = today - timedelta(days=days_since_thursday)

        # 목요일부터 1일 뒤까지 데이터 요청 (종가 확보)
        start_date = (last_thursday - timedelta(days=1)).strftime("%Y-%m-%d")
        end_date = (last_thursday + timedelta(days=2)).strftime("%Y-%m-%d")

        print(f"  📈 Yahoo Finance에서 주가 조회 중 (기준: {last_thursday.strftime('%Y-%m-%d')} 목요일)...")

        # ETF 주가 가져오기
        tickers = ["CONY", "MSTY", "YBIT"]
        data = yf.download(tickers, start=start_date, end=end_date, progress=False)

        if data.empty:
            print("  ⚠️  Yahoo Finance 데이터 없음 - 기본 주가 사용")
            return

        # 가장 최근 종가 (목요일 또는 그 직전 거래일)
        close_data = data["Close"]
        for ticker in tickers:
            if ticker in close_data.columns:
                last_price = close_data[ticker].dropna().iloc[-1]
                CURRENT_PRICES[ticker] = round(float(last_price), 2)
                print(f"     {ticker}: ${CURRENT_PRICES[ticker]:.2f}")

        # USD/KRW 환율 가져오기
        fx = yf.download("KRW=X", start=start_date, end=end_date, progress=False)
        if not fx.empty:
            last_fx = fx["Close"].dropna().iloc[-1]
            EXCHANGE_RATE = round(float(last_fx.iloc[0]) if hasattr(last_fx, 'iloc') else float(last_fx), 0)
            print(f"     환율: ₩{EXCHANGE_RATE:,.0f}")

        print(f"  ✅ 주가 업데이트 완료!")

    except Exception as e:
        print(f"  ⚠️  Yahoo Finance 조회 실패: {e} - 기본 주가 사용")


# ── 누적배당금 자동 갱신 ──
DIVIDEND_ADDITIONS_FILE = os.path.join(LOG_DIR, "dividend_additions.json")


def update_cumulative_dividends(all_distributions):
    """
    웹사이트에서 가져온 배당 데이터 중 PORTFOLIO_BASE_DATE 이후의 배당금을
    계좌별로 계산하여 PORTFOLIO의 누적배당금에 더합니다.
    결과는 JSON 파일에 저장되어 이력 관리됩니다.
    """
    base_date = datetime.strptime(PORTFOLIO_BASE_DATE, "%m/%d/%Y")

    # 기준일 이후의 배당 필터링 (지급일 기준)
    new_distributions = []
    for d in all_distributions:
        try:
            payable = datetime.strptime(d["payable_date"], "%m/%d/%Y")
            if payable > base_date:
                new_distributions.append(d)
        except ValueError:
            continue

    if not new_distributions:
        print("  ℹ️  기준일 이후 새로운 배당 없음")
        return

    # 계좌별 추가 배당금 계산 (세후)
    additions = {}
    for account, holdings in HOLDINGS.items():
        additions[account] = {}
        for ticker, shares in holdings.items():
            ticker_dists = [d for d in new_distributions if d["ticker"] == ticker]
            total_post_tax = sum(d["amount"] * shares * (1 - TAX_RATE) for d in ticker_dists)
            additions[account][ticker] = round(total_post_tax, 2)

    # PORTFOLIO에 추가 배당금 반영
    for account, pdata in PORTFOLIO.items():
        for ticker, info in pdata["ETF"].items():
            added = additions.get(account, {}).get(ticker, 0)
            info["누적배당금_추가"] = added
            info["누적배당금_합계"] = round(info["누적배당금"] + added, 2)

    # 이력 저장
    os.makedirs(LOG_DIR, exist_ok=True)
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "base_date": PORTFOLIO_BASE_DATE,
        "new_distributions_count": len(new_distributions),
        "additions": additions,
        "distributions_detail": [
            {"ticker": d["ticker"], "amount": d["amount"], "payable_date": d["payable_date"]}
            for d in sorted(new_distributions, key=lambda x: x["payable_date"])
        ],
    }

    with open(DIVIDEND_ADDITIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(log_entry, f, indent=2, ensure_ascii=False)

    # 요약 출력
    print(f"  💰 기준일({PORTFOLIO_BASE_DATE}) 이후 배당금 {len(new_distributions)}건 반영:")
    for account in HOLDINGS:
        total_added = sum(additions[account].values())
        if total_added > 0:
            details = " + ".join(
                f"{t}:${v:.2f}" for t, v in additions[account].items() if v > 0
            )
            print(f"     {account}: +${total_added:.2f} ({details})")


def fetch_distributions(ticker, url):
    """YieldMax 웹사이트에서 배당금 정보를 가져옵니다."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"[ERROR] {ticker} 데이터 가져오기 실패: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    text = soup.get_text()

    distributions = []
    pattern = r'\$(\d+\.\d+)(\d{2}/\d{2}/\d{4})(\d{2}/\d{2}/\d{4})(\d{2}/\d{2}/\d{4})(\d{2}/\d{2}/\d{4})(\d+\.?\d*%)'
    matches = re.findall(pattern, text)

    for match in matches:
        distributions.append({
            "ticker": ticker,
            "amount": float(match[0]),
            "declared_date": match[1],
            "ex_date": match[2],
            "record_date": match[3],
            "payable_date": match[4],
            "roc": match[5],
        })

    return distributions


def get_recent_distributions(distributions, weeks=2):
    """최근 N주간의 배당금만 필터링합니다."""
    if not distributions:
        return []

    cutoff = datetime.now() - timedelta(weeks=weeks)
    recent = []

    for d in distributions:
        try:
            payable = datetime.strptime(d["payable_date"], "%m/%d/%Y")
            if payable >= cutoff:
                recent.append(d)
        except ValueError:
            continue

    return sorted(recent, key=lambda x: x["payable_date"], reverse=True)


def calculate_dividends(distributions):
    """계좌별 예상 배당금을 계산합니다."""
    results = {}

    for account, holdings in HOLDINGS.items():
        account_total_pre = 0
        account_total_post = 0
        details = []

        for d in distributions:
            ticker = d["ticker"]
            if ticker in holdings:
                shares = holdings[ticker]
                pre_tax = d["amount"] * shares
                post_tax = pre_tax * (1 - TAX_RATE)
                account_total_pre += pre_tax
                account_total_post += post_tax
                details.append({
                    "ticker": ticker,
                    "amount_per_share": d["amount"],
                    "shares": shares,
                    "pre_tax": round(pre_tax, 2),
                    "post_tax": round(post_tax, 2),
                    "payable_date": d["payable_date"],
                })

        results[account] = {
            "total_pre_tax": round(account_total_pre, 2),
            "total_post_tax": round(account_total_post, 2),
            "details": details,
        }

    return results


def _generate_portfolio_section():
    """포트폴리오 요약 HTML 섹션을 생성합니다 (누적배당금, 매수평단, 투자금, 평가금액)."""
    rows_by_account = ""
    grand_total_invested = 0
    grand_total_eval = 0
    grand_total_dividend = 0

    for account, pdata in PORTFOLIO.items():
        invested_krw = pdata["투자금액_원화"]
        account_invested_usd = 0
        account_eval_usd = 0
        account_dividend_usd = 0
        etf_rows = ""

        for ticker, info in pdata["ETF"].items():
            qty = info["수량"]
            avg_price = info["매수평단"]
            buy_amount = info["매수금액"]
            # 합계가 있으면 (기준일 이후 배당 포함) 사용, 없으면 기존값
            cum_dividend = info.get("누적배당금_합계", info["누적배당금"])
            current_price = CURRENT_PRICES.get(ticker, 0)
            eval_amount = current_price * qty
            recovery_rate = (cum_dividend / buy_amount * 100) if buy_amount > 0 else 0
            pnl_rate = ((eval_amount + cum_dividend) / buy_amount - 1) * 100 if buy_amount > 0 else 0

            account_invested_usd += buy_amount
            account_eval_usd += eval_amount
            account_dividend_usd += cum_dividend

            # 수익률 색상
            pnl_color = "#4caf50" if pnl_rate >= 0 else "#ef5350"
            recovery_color = "#64b5f6"

            etf_rows += f"""
                <tr>
                    <td><span class="badge badge-{ticker.lower()}">{ticker}</span></td>
                    <td>{qty}</td>
                    <td>${avg_price:.2f}</td>
                    <td>${buy_amount:,.2f}</td>
                    <td>${current_price:.2f}</td>
                    <td>${eval_amount:,.2f}</td>
                    <td class="amount">${cum_dividend:,.2f}</td>
                    <td style="color:{recovery_color}">{recovery_rate:.0f}%</td>
                    <td style="color:{pnl_color};font-weight:600">{pnl_rate:+.1f}%</td>
                </tr>"""

        # 계좌 합계
        account_recovery = (account_dividend_usd / account_invested_usd * 100) if account_invested_usd > 0 else 0
        account_pnl = ((account_eval_usd + account_dividend_usd) / account_invested_usd - 1) * 100 if account_invested_usd > 0 else 0
        pnl_color = "#4caf50" if account_pnl >= 0 else "#ef5350"

        grand_total_invested += account_invested_usd
        grand_total_eval += account_eval_usd
        grand_total_dividend += account_dividend_usd

        rows_by_account += f"""
        <div class="card">
            <div class="card-header">
                <h3>{account} <small style="color:#888;font-size:0.8rem">투자: ₩{invested_krw:,.0f}</small></h3>
                <div>
                    <span style="color:{pnl_color};font-size:1.2rem;font-weight:700">{account_pnl:+.1f}%</span>
                    <small style="color:#888;margin-left:0.5rem">회수율 {account_recovery:.0f}%</small>
                </div>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>ETF</th><th>수량</th><th>매수평단</th><th>매수금액</th>
                        <th>현재가</th><th>평가금액</th><th>누적배당</th><th>회수율</th><th>수익률</th>
                    </tr>
                </thead>
                <tbody>
                    {etf_rows}
                    <tr style="border-top:2px solid rgba(255,255,255,0.2);font-weight:600">
                        <td colspan="3">합계</td>
                        <td>${account_invested_usd:,.2f}</td>
                        <td></td>
                        <td>${account_eval_usd:,.2f}</td>
                        <td class="amount">${account_dividend_usd:,.2f}</td>
                        <td style="color:#64b5f6">{account_recovery:.0f}%</td>
                        <td style="color:{pnl_color}">{account_pnl:+.1f}%</td>
                    </tr>
                </tbody>
            </table>
        </div>"""

    # 전체 합계 카드
    grand_recovery = (grand_total_dividend / grand_total_invested * 100) if grand_total_invested > 0 else 0
    grand_pnl = ((grand_total_eval + grand_total_dividend) / grand_total_invested - 1) * 100 if grand_total_invested > 0 else 0
    grand_pnl_color = "#4caf50" if grand_pnl >= 0 else "#ef5350"
    grand_eval_krw = grand_total_eval * EXCHANGE_RATE
    grand_dividend_krw = grand_total_dividend * EXCHANGE_RATE

    portfolio_summary = f"""
    <div class="portfolio-section">
        <h2>투자 포트폴리오 현황</h2>
        <div class="summary-grid" style="margin-bottom:1.5rem">
            <div class="summary-card">
                <div class="label">총 투자금액</div>
                <div class="value" style="color:#fff;font-size:1.4rem">${grand_total_invested:,.0f}</div>
            </div>
            <div class="summary-card">
                <div class="label">현재 평가금액</div>
                <div class="value" style="color:#64b5f6;font-size:1.4rem">${grand_total_eval:,.0f}</div>
            </div>
            <div class="summary-card">
                <div class="label">누적 배당금</div>
                <div class="value" style="color:#4caf50;font-size:1.4rem">${grand_total_dividend:,.0f}</div>
            </div>
            <div class="summary-card">
                <div class="label">회수율 / 수익률</div>
                <div class="value" style="font-size:1.2rem">
                    <span style="color:#64b5f6">{grand_recovery:.0f}%</span>
                    <span style="color:#666"> / </span>
                    <span style="color:{grand_pnl_color}">{grand_pnl:+.1f}%</span>
                </div>
            </div>
        </div>
        <div class="summary-grid" style="grid-template-columns: repeat(2, 1fr); margin-bottom:1.5rem">
            <div class="summary-card">
                <div class="label">평가금액 (원화)</div>
                <div class="value" style="color:#64b5f6;font-size:1.2rem">₩{grand_eval_krw:,.0f}</div>
            </div>
            <div class="summary-card">
                <div class="label">누적배당 (원화)</div>
                <div class="value" style="color:#4caf50;font-size:1.2rem">₩{grand_dividend_krw:,.0f}</div>
            </div>
        </div>
        {rows_by_account}
        <p style="text-align:right;color:#555;font-size:0.75rem;margin-top:0.5rem">
            환율: ₩{EXCHANGE_RATE:,} | 현재가: CONY ${CURRENT_PRICES['CONY']}, MSTY ${CURRENT_PRICES['MSTY']}, YBIT ${CURRENT_PRICES['YBIT']}
        </p>
    </div>"""

    # ── 회수 예상일 계산 ──
    recovery_section = _generate_recovery_estimate(grand_total_invested, grand_total_dividend)
    portfolio_summary += recovery_section

    return portfolio_summary


def _generate_recovery_estimate(grand_invested, grand_dividend):
    """현재 배당 추세 기반 투자금 회수 예상일을 계산합니다."""
    recovery_rows = ""

    for account, pdata in PORTFOLIO.items():
        account_rows = ""
        for ticker, info in pdata["ETF"].items():
            buy_amount = info["매수금액"]
            cum_dividend = info.get("누적배당금_합계", info["누적배당금"])
            remaining = buy_amount - cum_dividend

            # 최근 4주 평균 배당금으로 주간 수령액 추정
            # PORTFOLIO에 저장된 추가 배당금 정보 활용
            qty = info["수량"]
            added = info.get("누적배당금_추가", 0)

            # 기준일(4/10)부터 오늘까지의 주 수로 주당 평균 계산
            base_date = datetime.strptime(PORTFOLIO_BASE_DATE, "%m/%d/%Y")
            weeks_elapsed = max(1, (datetime.now() - base_date).days / 7)
            weekly_dividend = added / weeks_elapsed if added > 0 else 0

            if weekly_dividend > 0 and remaining > 0:
                weeks_to_recover = remaining / weekly_dividend
                months_to_recover = weeks_to_recover / 4.33
                recover_date = datetime.now() + timedelta(weeks=weeks_to_recover)
                recover_str = recover_date.strftime("%Y년 %m월")
                progress = min(100, cum_dividend / buy_amount * 100)

                account_rows += f"""
                <tr>
                    <td><span class="badge badge-{ticker.lower()}">{ticker}</span></td>
                    <td>${buy_amount:,.0f}</td>
                    <td>${cum_dividend:,.0f}</td>
                    <td>${remaining:,.0f}</td>
                    <td>${weekly_dividend:.2f}/주</td>
                    <td style="color:#ffd54f;font-weight:600">{recover_str}</td>
                    <td style="color:#ffd54f">({months_to_recover:.0f}개월)</td>
                    <td>
                        <div style="background:rgba(255,255,255,0.1);border-radius:4px;height:8px;width:100px;display:inline-block">
                            <div style="background:#4caf50;border-radius:4px;height:8px;width:{progress}px"></div>
                        </div>
                        <span style="font-size:0.7rem;margin-left:4px">{progress:.0f}%</span>
                    </td>
                </tr>"""
            elif remaining <= 0:
                account_rows += f"""
                <tr>
                    <td><span class="badge badge-{ticker.lower()}">{ticker}</span></td>
                    <td>${buy_amount:,.0f}</td>
                    <td>${cum_dividend:,.0f}</td>
                    <td style="color:#4caf50;font-weight:600">회수완료!</td>
                    <td>-</td>
                    <td style="color:#4caf50;font-weight:600">완료</td>
                    <td></td>
                    <td>
                        <div style="background:rgba(255,255,255,0.1);border-radius:4px;height:8px;width:100px;display:inline-block">
                            <div style="background:#4caf50;border-radius:4px;height:8px;width:100px"></div>
                        </div>
                        <span style="font-size:0.7rem;margin-left:4px">100%</span>
                    </td>
                </tr>"""

        if account_rows:
            recovery_rows += f"""
            <tr style="border-top:1px solid rgba(255,255,255,0.1)">
                <td colspan="8" style="color:#fff;font-weight:600;padding-top:0.8rem">{account}</td>
            </tr>
            {account_rows}"""

    # 전체 회수 예상
    total_remaining = grand_invested - grand_dividend
    base_date = datetime.strptime(PORTFOLIO_BASE_DATE, "%m/%d/%Y")
    weeks_elapsed = max(1, (datetime.now() - base_date).days / 7)

    # 전체 주당 배당 합계
    total_weekly = 0
    for account, pdata in PORTFOLIO.items():
        for ticker, info in pdata["ETF"].items():
            added = info.get("누적배당금_추가", 0)
            total_weekly += added / weeks_elapsed if added > 0 else 0

    if total_weekly > 0 and total_remaining > 0:
        total_weeks = total_remaining / total_weekly
        total_months = total_weeks / 4.33
        total_recover_date = (datetime.now() + timedelta(weeks=total_weeks)).strftime("%Y년 %m월")
        total_summary = f'<span style="color:#ffd54f;font-size:1.3rem;font-weight:700">{total_recover_date}</span> <span style="color:#888">({total_months:.0f}개월 후, 주당 ${total_weekly:.2f} 기준)</span>'
    elif total_remaining <= 0:
        total_summary = '<span style="color:#4caf50;font-size:1.3rem;font-weight:700">이미 회수 완료!</span>'
    else:
        total_summary = '<span style="color:#888">계산 불가 (배당 데이터 부족)</span>'

    return f"""
    <div class="card" style="margin-top:1.5rem;border:1px solid rgba(255,213,79,0.3)">
        <div class="card-header">
            <h3 style="color:#ffd54f">📅 투자금 회수 예상</h3>
            <div>{total_summary}</div>
        </div>
        <table>
            <thead>
                <tr><th>ETF</th><th>투자금</th><th>누적배당</th><th>잔여</th><th>주간배당</th><th>회수예상</th><th></th><th>진행률</th></tr>
            </thead>
            <tbody>{recovery_rows}</tbody>
        </table>
        <p style="color:#555;font-size:0.7rem;margin-top:0.5rem">
            * 최근 {weeks_elapsed:.0f}주간 평균 배당금 기준 추정. 배당금 변동에 따라 달라질 수 있음.
        </p>
    </div>"""


def _generate_news_section():
    """YieldMax 커버드콜 관련 뉴스 + 비트코인/코인 뉴스를 가져옵니다."""
    NEWS_FILE = os.path.join(LOG_DIR, "weekly_news.json")

    def _fetch_news():
        """Google News RSS를 통해 관련 뉴스를 가져옵니다."""
        news_items = []
        search_queries = [
            ("YieldMax ETF", "https://news.google.com/rss/search?q=YieldMax+ETF+covered+call&hl=en&gl=US&ceid=US:en"),
            ("Bitcoin Crypto", "https://news.google.com/rss/search?q=bitcoin+crypto+market&hl=en&gl=US&ceid=US:en"),
            ("Coinbase COIN", "https://news.google.com/rss/search?q=Coinbase+COIN+stock&hl=en&gl=US&ceid=US:en"),
        ]

        for category, rss_url in search_queries:
            try:
                resp = requests.get(rss_url, timeout=10)
                if resp.status_code == 200:
                    # 간단한 RSS XML 파싱
                    soup = BeautifulSoup(resp.text, "html.parser")
                    items = soup.find_all("item")[:3]
                    for item in items:
                        title = item.find("title")
                        link = item.find("link")
                        pub_date = item.find("pubdate")
                        if title and link:
                            news_items.append({
                                "category": category,
                                "title": title.get_text(),
                                "url": link.next_sibling.strip() if link.next_sibling else "",
                                "date": pub_date.get_text()[:16] if pub_date else "",
                            })
            except Exception:
                continue

        return news_items

    # 뉴스 가져오기 시도, 실패 시 캐시된 뉴스 사용
    news_items = _fetch_news()

    if not news_items:
        # 캐시 파일에서 로드
        if os.path.exists(NEWS_FILE):
            try:
                with open(NEWS_FILE, "r") as f:
                    cached = json.load(f)
                    news_items = cached.get("items", [])
            except (json.JSONDecodeError, IOError):
                pass

    # 뉴스가 없으면 하드코딩된 최근 뉴스 사용
    if not news_items:
        news_items = [
            {"category": "YieldMax ETF", "title": "MSTY shareholders face uncapped losses despite weekly distributions", "url": "https://247wallst.com/investing/etf/2026/07/05/why-msty-shareholders-are-facing-uncapped-losses-despite-weekly-distributions/", "date": "2026-07-05"},
            {"category": "YieldMax ETF", "title": "MSTY's 66% Yield Is the Bait. Uncapped Downside Is the Trap.", "url": "https://www.ainvest.com/news/msty-66-yield-bait-uncapped-downside-trap-2607/", "date": "2026-07-05"},
            {"category": "YieldMax ETF", "title": "CONY's Dreamy Yield Hides a Track Record That Should Concern Long Term Holders", "url": "https://247wallst.com/investing/2026/05/21/conys-dreamy-yield-hides-a-track-record-that-should-concern-long-term-holders/", "date": "2026-05-21"},
            {"category": "YieldMax ETF", "title": "YieldMax MSTY Returned More Than Half Your Capital — Most Holders Think It Was Income", "url": "https://247wallst.com/investing/2026/06/08/yieldmax-msty-returned-more-than-half-your-capital-in-a-single-quarter-and-most-holders-think-it-was-income/", "date": "2026-06-08"},
            {"category": "YieldMax ETF", "title": "YieldMax Yield + Capital Gain Analysis: Reverse-split ETFs excluded (CONY, MSTY, YBIT)", "url": "https://dividendfarmer.substack.com/p/yieldmax-yield-capital-gain-analysis-26e", "date": "2026-06-20"},
            {"category": "Bitcoin Crypto", "title": "Crypto Slides on Renewed Inflation Fears — BTC falls 3.3% to $62,049", "url": "https://www.fool.com/coverage/stock-market-today/2026/07/13/crypto-market-today-july-13-crypto-slides-on-renewed-inflation-fears/", "date": "2026-07-13"},
            {"category": "Bitcoin Crypto", "title": "Bitcoin Weathered 4 CPI Shocks in 2026 — Including 27.6% Crash", "url": "https://beincrypto.com/us-cpi-report-bitcoin-pump-or-dump-july-2026/", "date": "2026-07-12"},
            {"category": "Bitcoin Crypto", "title": "First Signs of Crypto Bottoming — Market Shrugs Off Major Sale (Wintermute)", "url": "https://www.cryptotimes.io/2026/07/14/first-signs-of-crypto-bottoming-as-market-shrugs-off-major-sale-wintermute/", "date": "2026-07-14"},
            {"category": "Bitcoin Crypto", "title": "Bitcoin Pushes Above $64K — $96M in Bearish Bets Collapse", "url": "https://news.bitcoin.com/bitcoin-pushes-above-64k-as-96m-in-bearish-bets-collapse-and-momentum-rebuilds/", "date": "2026-07-10"},
            {"category": "Coinbase COIN", "title": "Prediction Market Pricing Collapse of Bull Cycle — BTC $65K strike at 88% implied probability", "url": "https://www.ainvest.com/news/bitcoin-july-2026-prediction-market-pricing-collapse-bull-cycle-2607/", "date": "2026-07-11"},
        ]

    # 캐시 저장
    os.makedirs(LOG_DIR, exist_ok=True)
    try:
        with open(NEWS_FILE, "w", encoding="utf-8") as f:
            json.dump({"timestamp": datetime.now().isoformat(), "items": news_items}, f, ensure_ascii=False, indent=2)
    except IOError:
        pass

    # HTML 생성
    # 카테고리별 분류
    yieldmax_news = [n for n in news_items if "YieldMax" in n.get("category", "")]
    crypto_news = [n for n in news_items if "Bitcoin" in n.get("category", "") or "Coinbase" in n.get("category", "")]

    def _render_news_list(items, max_items=5):
        html = ""
        for item in items[:max_items]:
            title = item.get("title", "")
            url = item.get("url", "#")
            date = item.get("date", "")
            html += f"""
                <li style="margin-bottom:0.8rem">
                    <a href="{url}" target="_blank" style="color:#64b5f6;text-decoration:none;font-size:0.9rem">{title}</a>
                    <span style="color:#555;font-size:0.75rem;margin-left:0.5rem">{date}</span>
                </li>"""
        return html

    yieldmax_html = _render_news_list(yieldmax_news)
    crypto_html = _render_news_list(crypto_news)

    return f"""
    <div class="card" style="margin-top:2rem">
        <div class="card-header">
            <h3>📰 주간 뉴스 & 분석</h3>
            <small style="color:#888">{datetime.now().strftime('%Y-%m-%d')} 기준</small>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:2rem">
            <div>
                <h4 style="color:#ff9800;margin-bottom:0.8rem;font-size:0.95rem">🏦 YieldMax 커버드콜 ETF</h4>
                <ul style="list-style:none;padding:0">{yieldmax_html}</ul>
            </div>
            <div>
                <h4 style="color:#f7931a;margin-bottom:0.8rem;font-size:0.95rem">₿ 비트코인 & 크립토</h4>
                <ul style="list-style:none;padding:0">{crypto_html}</ul>
            </div>
        </div>
        <p style="color:#555;font-size:0.7rem;margin-top:1rem;border-top:1px solid rgba(255,255,255,0.05);padding-top:0.5rem">
            * 뉴스는 매주 금요일 자동 업데이트됩니다. 링크를 클릭하면 원문을 볼 수 있습니다.
        </p>
    </div>"""


def _generate_chart_section(all_fetched):
    """ETF별 주가 추이 + 배당금 추이 차트를 각각 생성합니다."""
    if not HAS_YFINANCE:
        return '<div class="card"><p style="color:#888">차트 표시를 위해 yfinance가 필요합니다.</p></div>'

    import json as _json

    # 각 ETF의 상장일
    inception_dates = {
        "CONY": "2023-08-14",
        "MSTY": "2024-02-21",
        "YBIT": "2024-04-22",
    }
    colors = {"CONY": "#ff9800", "MSTY": "#2196f3", "YBIT": "#9c27b0"}
    descriptions = {
        "CONY": "Coinbase(COIN) 옵션 인컴 전략",
        "MSTY": "Strategy Inc(MSTR) 옵션 인컴 전략",
        "YBIT": "iShares Bitcoin Trust(IBIT) 옵션 인컴 전략",
    }

    chart_data = {}
    for ticker, start_date in inception_dates.items():
        try:
            hist = yf.download(ticker, start=start_date, progress=False, interval="1wk")
            if not hist.empty:
                prices = []
                for date, row in hist.iterrows():
                    close_val = row["Close"]
                    if hasattr(close_val, 'iloc'):
                        close_val = close_val.iloc[0]
                    prices.append({
                        "date": date.strftime("%Y-%m-%d"),
                        "price": round(float(close_val), 2)
                    })
                chart_data[ticker] = prices
        except Exception as e:
            print(f"  ⚠️  {ticker} 차트 데이터 실패: {e}")

    # 배당금 데이터
    dividend_data = {}
    for ticker in ["CONY", "MSTY", "YBIT"]:
        ticker_dists = [d for d in all_fetched if d["ticker"] == ticker]
        dividends = []
        for d in sorted(ticker_dists, key=lambda x: x["payable_date"]):
            try:
                dt = datetime.strptime(d["payable_date"], "%m/%d/%Y")
                dividends.append({"date": dt.strftime("%Y-%m-%d"), "amount": d["amount"]})
            except ValueError:
                continue
        dividend_data[ticker] = dividends

    # ETF별 개별 차트 HTML 생성
    charts_html = ""
    chart_scripts = ""

    for idx, ticker in enumerate(["CONY", "MSTY", "YBIT"]):
        color = colors[ticker]
        desc = descriptions[ticker]
        canvas_id = f"chart_{ticker.lower()}"

        # 주가 데이터
        price_data = chart_data.get(ticker, [])
        price_dataset = {
            "label": f"{ticker} 주가 ($)",
            "data": [{"x": p["date"], "y": p["price"]} for p in price_data],
            "borderColor": color,
            "backgroundColor": color + "15",
            "borderWidth": 2,
            "pointRadius": 0,
            "tension": 0.3,
            "fill": True,
            "yAxisID": "y",
        }

        # 배당금 데이터 (라인 차트로)
        div_data = dividend_data.get(ticker, [])
        div_dataset = {
            "label": f"{ticker} 배당금 ($)",
            "data": [{"x": d["date"], "y": d["amount"]} for d in div_data],
            "borderColor": "#4caf50",
            "backgroundColor": "#4caf5033",
            "borderWidth": 1.5,
            "pointRadius": 2,
            "pointBackgroundColor": "#4caf50",
            "tension": 0.3,
            "fill": True,
            "yAxisID": "y1",
        }

        datasets = [price_dataset, div_dataset]
        datasets_json = _json.dumps(datasets, ensure_ascii=False)

        # 현재가, 최고가 계산
        current_price = CURRENT_PRICES.get(ticker, 0)
        max_price = max([p["price"] for p in price_data]) if price_data else 0
        latest_div = div_data[-1]["amount"] if div_data else 0

        charts_html += f"""
        <div class="card" style="margin-bottom:1.5rem">
            <div class="card-header">
                <h3><span class="badge badge-{ticker.lower()}" style="font-size:0.9rem;padding:4px 10px">{ticker}</span>
                    <small style="color:#888;margin-left:0.5rem">{desc}</small>
                </h3>
                <div style="text-align:right">
                    <span style="color:{color};font-weight:700">${current_price:.2f}</span>
                    <span style="color:#555;font-size:0.75rem;margin-left:0.5rem">최고 ${max_price:.2f}</span>
                    <span style="color:#4caf50;font-size:0.75rem;margin-left:0.5rem">배당 ${latest_div:.4f}</span>
                </div>
            </div>
            <div style="position:relative;height:280px;width:100%">
                <canvas id="{canvas_id}"></canvas>
            </div>
        </div>"""

        chart_scripts += f"""
        new Chart(document.getElementById('{canvas_id}').getContext('2d'), {{
            type: 'line',
            data: {{ datasets: {datasets_json} }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                interaction: {{ mode: 'index', intersect: false }},
                plugins: {{
                    legend: {{ labels: {{ color: '#ccc', font: {{ size: 10 }} }} }},
                    tooltip: {{
                        backgroundColor: 'rgba(0,0,0,0.85)',
                        titleColor: '#fff',
                        bodyColor: '#ccc',
                        callbacks: {{
                            label: function(ctx) {{
                                return ctx.dataset.yAxisID === 'y'
                                    ? ctx.dataset.label + ': $' + ctx.parsed.y.toFixed(2)
                                    : ctx.dataset.label + ': $' + ctx.parsed.y.toFixed(4);
                            }}
                        }}
                    }}
                }},
                scales: {{
                    x: {{
                        type: 'time',
                        time: {{ unit: 'month', displayFormats: {{ month: 'yy-MM' }} }},
                        ticks: {{ color: '#666', maxTicksLimit: 12 }},
                        grid: {{ color: 'rgba(255,255,255,0.03)' }}
                    }},
                    y: {{
                        position: 'left',
                        title: {{ display: true, text: '주가 ($)', color: '{color}' }},
                        ticks: {{ color: '{color}' }},
                        grid: {{ color: 'rgba(255,255,255,0.05)' }}
                    }},
                    y1: {{
                        position: 'right',
                        title: {{ display: true, text: '배당금 ($)', color: '#4caf50' }},
                        ticks: {{ color: '#4caf50' }},
                        grid: {{ drawOnChartArea: false }},
                        min: 0,
                    }}
                }}
            }}
        }});
        """

    return f"""
    <div style="margin-top:2rem">
        <h2 style="color:#fff;margin-bottom:1rem;font-size:1.3rem">📈 ETF별 주가 & 배당 추이</h2>
        {charts_html}
    </div>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns"></script>
    <script>{chart_scripts}</script>"""


def generate_html_dashboard(all_distributions, all_fetched, account_dividends):
    """보기 좋은 HTML 대시보드를 생성합니다."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total_post_tax = sum(d["total_post_tax"] for d in account_dividends.values())
    total_pre_tax = sum(d["total_pre_tax"] for d in account_dividends.values())

    # 최신 배당금 (ETF별)
    latest_by_ticker = {}
    for ticker in ["CONY", "MSTY", "YBIT"]:
        ticker_dists = [d for d in all_distributions if d["ticker"] == ticker]
        if ticker_dists:
            latest_by_ticker[ticker] = ticker_dists[0]

    # ── 포트폴리오 요약 섹션 생성 ──
    portfolio_section = _generate_portfolio_section()

    # ── 차트 섹션 생성 ──
    chart_section = _generate_chart_section(all_fetched)

    # ── 뉴스 섹션 생성 ──
    news_section = _generate_news_section()

    # 최근 배당 히스토리 (날짜순 정렬 후 최근 12건)
    sorted_history = sorted(
        all_fetched,
        key=lambda x: datetime.strptime(x["payable_date"], "%m/%d/%Y"),
        reverse=True
    )
    history_rows = ""
    for d in sorted_history[:12]:  # 최근 12건 (ETF 혼합, 날짜 내림차순)
        history_rows += f"""
            <tr>
                <td><span class="badge badge-{d['ticker'].lower()}">{d['ticker']}</span></td>
                <td class="amount">${d['amount']:.4f}</td>
                <td>{d['declared_date']}</td>
                <td>{d['payable_date']}</td>
                <td>{d['roc']}</td>
            </tr>"""

    # 계좌별 상세
    account_cards = ""
    for account, data in account_dividends.items():
        detail_rows = ""
        for det in data["details"]:
            detail_rows += f"""
                <tr>
                    <td><span class="badge badge-{det['ticker'].lower()}">{det['ticker']}</span></td>
                    <td>${det['amount_per_share']:.4f}</td>
                    <td>{det['shares']}</td>
                    <td>${det['pre_tax']:.2f}</td>
                    <td class="amount">${det['post_tax']:.2f}</td>
                    <td>{det['payable_date']}</td>
                </tr>"""

        account_cards += f"""
        <div class="card">
            <div class="card-header">
                <h3>{account}</h3>
                <div class="card-total">${data['total_post_tax']:.2f} <small>(세후)</small></div>
            </div>
            <table class="detail-table">
                <thead>
                    <tr><th>ETF</th><th>주당배당</th><th>수량</th><th>세전</th><th>세후</th><th>지급일</th></tr>
                </thead>
                <tbody>{detail_rows}</tbody>
            </table>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YieldMax 배당금 대시보드</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            color: #e0e0e0;
            min-height: 100vh;
            padding: 2rem;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        
        /* Header */
        .header {{
            text-align: center;
            margin-bottom: 2rem;
            padding: 2rem;
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .header h1 {{ font-size: 2rem; color: #fff; margin-bottom: 0.5rem; }}
        .header .subtitle {{ color: #888; font-size: 0.9rem; }}
        .header .update-time {{ color: #64b5f6; margin-top: 0.5rem; }}

        /* Summary Cards */
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        .summary-card {{
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 1.5rem;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.1);
            transition: transform 0.2s;
        }}
        .summary-card:hover {{ transform: translateY(-2px); }}
        .summary-card .label {{ font-size: 0.8rem; color: #888; text-transform: uppercase; letter-spacing: 1px; }}
        .summary-card .value {{ font-size: 1.8rem; font-weight: 700; margin-top: 0.5rem; }}
        .summary-card.total .value {{ color: #4caf50; }}
        .summary-card.cony .value {{ color: #ff9800; }}
        .summary-card.msty .value {{ color: #2196f3; }}
        .summary-card.ybit .value {{ color: #9c27b0; }}

        /* Badges */
        .badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
        }}
        .badge-cony {{ background: rgba(255,152,0,0.2); color: #ff9800; }}
        .badge-msty {{ background: rgba(33,150,243,0.2); color: #2196f3; }}
        .badge-ybit {{ background: rgba(156,39,176,0.2); color: #9c27b0; }}

        /* Cards */
        .card {{
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
            padding-bottom: 0.75rem;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        .card-header h3 {{ color: #fff; font-size: 1.2rem; }}
        .card-total {{ font-size: 1.4rem; font-weight: 700; color: #4caf50; }}
        .card-total small {{ font-size: 0.7rem; color: #888; }}

        /* Tables */
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ text-align: left; padding: 0.6rem 0.8rem; color: #888; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; }}
        td {{ padding: 0.6rem 0.8rem; border-top: 1px solid rgba(255,255,255,0.05); font-size: 0.9rem; }}
        .amount {{ font-weight: 600; color: #4caf50; }}

        /* History Section */
        .history-section {{ margin-top: 2rem; }}
        .history-section h2 {{ color: #fff; margin-bottom: 1rem; font-size: 1.3rem; }}

        /* Portfolio Section */
        .portfolio-section {{ margin-bottom: 2.5rem; }}
        .portfolio-section h2 {{ color: #fff; margin-bottom: 1rem; font-size: 1.3rem; }}

        /* Footer */
        .footer {{
            text-align: center;
            margin-top: 2rem;
            padding: 1rem;
            color: #555;
            font-size: 0.8rem;
        }}
        .footer a {{ color: #64b5f6; text-decoration: none; }}

        /* 반응형 */
        @media (max-width: 768px) {{
            body {{ padding: 1rem; }}
            .summary-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .card-header {{ flex-direction: column; gap: 0.5rem; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>YieldMax 배당금 대시보드</h1>
            <div class="subtitle">CONY &middot; MSTY &middot; YBIT 주간 배당 리포트</div>
            <div class="update-time">마지막 업데이트: {now}</div>
        </div>

        <!-- 포트폴리오 현황 -->
        {portfolio_section}

        <!-- 이번 주 배당금 -->
        <h2 style="color:#fff;margin-bottom:1rem;font-size:1.3rem">이번 주 배당금</h2>

        <!-- 요약 카드 -->
        <div class="summary-grid">
            <div class="summary-card total">
                <div class="label">이번 주 세후 합계</div>
                <div class="value">${total_post_tax:.2f}</div>
            </div>
            <div class="summary-card cony">
                <div class="label">CONY 주당배당</div>
                <div class="value">${latest_by_ticker.get('CONY', {}).get('amount', 0):.4f}</div>
            </div>
            <div class="summary-card msty">
                <div class="label">MSTY 주당배당</div>
                <div class="value">${latest_by_ticker.get('MSTY', {}).get('amount', 0):.4f}</div>
            </div>
            <div class="summary-card ybit">
                <div class="label">YBIT 주당배당</div>
                <div class="value">${latest_by_ticker.get('YBIT', {}).get('amount', 0):.4f}</div>
            </div>
        </div>

        <!-- 계좌별 상세 -->
        {account_cards}

        <!-- 최근 배당 히스토리 -->
        <div class="history-section">
            <h2>최근 배당 히스토리</h2>
            <div class="card">
                <table>
                    <thead>
                        <tr><th>ETF</th><th>주당배당</th><th>선언일</th><th>지급일</th><th>ROC</th></tr>
                    </thead>
                    <tbody>{history_rows}</tbody>
                </table>
            </div>
        </div>

        <!-- 주가 & 배당 추이 차트 -->
        {chart_section}

        <!-- 주간 뉴스 -->
        {news_section}

        <div class="footer">
            데이터 출처: <a href="https://yieldmaxetfs.com/" target="_blank">yieldmaxetfs.com</a> |
            세율: {TAX_RATE*100:.0f}% |
            보유: 아빠(CONY:{HOLDINGS['아빠']['CONY']}, MSTY:{HOLDINGS['아빠']['MSTY']}, YBIT:{HOLDINGS['아빠']['YBIT']})
            엄마(CONY:{HOLDINGS['엄마']['CONY']}, MSTY:{HOLDINGS['엄마']['MSTY']}, YBIT:{HOLDINGS['엄마']['YBIT']})
            시윤(CONY:{HOLDINGS['시윤']['CONY']}, MSTY:{HOLDINGS['시윤']['MSTY']}, YBIT:{HOLDINGS['시윤']['YBIT']})
        </div>
    </div>
</body>
</html>"""

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    return HTML_FILE


def send_macos_notification(title, message, subtitle=""):
    """macOS 알림을 보냅니다."""
    script = f'''
    display notification "{message}" with title "{title}" subtitle "{subtitle}"
    '''
    subprocess.run(["osascript", "-e", script], capture_output=True)


def save_log(all_distributions, account_dividends):
    """결과를 JSON으로 저장합니다."""
    os.makedirs(LOG_DIR, exist_ok=True)

    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "distributions": all_distributions,
        "account_dividends": account_dividends,
    }

    logs = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                logs = json.load(f)
        except (json.JSONDecodeError, IOError):
            logs = []

    logs.append(log_entry)
    logs = logs[-52:]

    with open(LOG_FILE, "w") as f:
        json.dump(logs, f, indent=2, ensure_ascii=False)


def main():
    print(f"\n🚀 YieldMax 배당금 확인 시작... ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n")

    # 1. Yahoo Finance에서 목요일 종가 + 환율 업데이트
    fetch_prices_from_yahoo()
    print()

    all_fetched = []  # 전체 히스토리용
    all_recent = []   # 최근 배당금
    all_distributions_full = []  # 전체 배당 데이터 (누적 계산용)

    for ticker, url in ETFS.items():
        print(f"  📥 {ticker} 배당금 정보 가져오는 중...")
        distributions = fetch_distributions(ticker, url)
        print(f"     → 총 {len(distributions)}건 발견")

        # 전체 배당 데이터 (누적배당금 계산용)
        all_distributions_full.extend(distributions)

        # 전체 데이터 (히스토리 + 차트 표시용)
        all_fetched.extend(distributions)

        # 최근 1주 배당금
        recent = get_recent_distributions(distributions, weeks=1)
        if recent:
            print(f"     → 최근 1주: {len(recent)}건")
            all_recent.extend(recent)
        else:
            # 최근 2주로 확대
            recent = get_recent_distributions(distributions, weeks=2)
            if recent:
                latest = recent[0]
                all_recent.append(latest)
                print(f"     → 최근 배당: ${latest['amount']:.4f} ({latest['payable_date']})")

    if not all_recent:
        msg = "최근 배당금 정보를 찾을 수 없습니다."
        print(f"\n⚠️  {msg}")
        send_macos_notification("YieldMax 배당 알림", msg, "데이터 없음")
        return

    # 계좌별 배당금 계산
    account_dividends = calculate_dividends(all_recent)

    # 누적배당금 자동 갱신 (기준일 이후 배당금 합산)
    print()
    update_cumulative_dividends(all_distributions_full)

    # HTML 대시보드 생성 및 브라우저 열기
    html_path = generate_html_dashboard(all_recent, all_fetched, account_dividends)
    print(f"\n📊 HTML 대시보드 생성: {html_path}")
    webbrowser.open(f"file://{html_path}")

    # 로그 저장
    save_log(all_recent, account_dividends)
    print(f"💾 로그 저장: {LOG_FILE}")

    # macOS 알림
    total_post_tax = sum(d["total_post_tax"] for d in account_dividends.values())
    etf_summary = []
    for ticker in ["CONY", "MSTY", "YBIT"]:
        ticker_dists = [d for d in all_recent if d["ticker"] == ticker]
        if ticker_dists:
            etf_summary.append(f"{ticker}: ${ticker_dists[0]['amount']:.4f}")

    notification_msg = (
        f"{' | '.join(etf_summary)}\n"
        f"세후 합계: ${total_post_tax:.2f}"
    )

    send_macos_notification(
        "YieldMax 주간 배당 알림",
        notification_msg,
        f"아빠: ${account_dividends['아빠']['total_post_tax']:.2f} | "
        f"엄마: ${account_dividends['엄마']['total_post_tax']:.2f} | "
        f"시윤: ${account_dividends['시윤']['total_post_tax']:.2f}"
    )

    print("✅ 완료! 브라우저에서 대시보드를 확인하세요.")


if __name__ == "__main__":
    main()
