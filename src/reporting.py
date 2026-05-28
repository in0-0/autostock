from __future__ import annotations

from datetime import datetime

from src.models import Candidate, MacroStatus, PortfolioState, TradeGuide
from src.utils.telegram import escape_markdown


def render_markdown_report(
    *,
    generated_at: datetime,
    macro_status: MacroStatus,
    macro_indicators: dict,
    ranked_candidates: list[Candidate],
    trade_guides: list[TradeGuide],
    portfolio: PortfolioState,
    market_data_warnings: list[str] | None = None,
) -> str:
    market_data_warnings = market_data_warnings or []
    lines: list[str] = []
    lines.append("📊 이번 주 거시 시장 상태")
    lines.append("--------------------------------")
    lines.append(f"{macro_status.value} | KOSPI 10MA: {macro_indicators['kospi_above_10ma']} | KOSDAQ 10MA: {macro_indicators['kosdaq_above_10ma']}")
    lines.append(f"미국 기준금리: {macro_indicators.get('us_rate')} | 장단기 금리차: {macro_indicators.get('yield_curve_10y2y')}")
    lines.append("")
    lines.append("🏆 금주 우량 성장주 추천 TOP")
    lines.append("--------------------------------")
    if ranked_candidates:
        for candidate in ranked_candidates:
            lines.append(f"{candidate.final_rank}. {candidate.name} ({candidate.ticker}) | PEG: {candidate.peg:.2f} | TAG: {candidate.strategy_type}")
            if candidate.rationale:
                lines.append(f"   - 근거: {', '.join(candidate.rationale)}")
            if candidate.risks:
                lines.append(f"   - 리스크: {', '.join(candidate.risks)}")
            if candidate.provider:
                lines.append(f"   - 데이터: {candidate.provider}")
    else:
        lines.append("- 조건 만족 종목이 최소 기준 미만이거나 매수 차단 상태입니다.")
    lines.append("")
    lines.append("🚨 시스템 리스크 경고 현황")
    lines.append("--------------------------------")
    failed_sources = portfolio.failed_sources or portfolio.failed_brokers
    if failed_sources:
        lines.append(f"- 일부 데이터 소스 응답 실패: {', '.join(failed_sources)}")
    for warning in portfolio.source_warnings:
        lines.append(f"- 포트폴리오 입력 경고: {warning}")
    for warning in market_data_warnings:
        lines.append(f"- 시장데이터 경고: {warning}")
    if portfolio.ip_changed_flag:
        lines.append("- 공인 IP 변경 감지: 증권사 화이트리스트 확인 필요")
    if not failed_sources and not portfolio.source_warnings and not market_data_warnings and not portfolio.ip_changed_flag:
        lines.append("- 포트폴리오 입력 및 데이터 소스 상태 정상")
    lines.append("")
    lines.append("💰 후보 검토 메모")
    lines.append("--------------------------------")
    if ranked_candidates:
        for candidate in ranked_candidates:
            lines.append(f"- {candidate.name} ({candidate.ticker}): 후보 검토 대상 [{candidate.strategy_type}]")
    else:
        lines.append("- 검토 가능한 신규 매수 후보가 없습니다.")
    lines.append("")
    lines.append(f"생성 시각: {generated_at.isoformat()}")
    return "\n".join(lines)


def render_telegram_markdown_v2(report: str) -> str:
    return escape_markdown(report)
