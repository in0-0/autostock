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
    telegram_delivery_status: str | None = "disabled",
    candidate_exclusion_counts: dict[str, int] | None = None,
) -> str:
    market_data_warnings = market_data_warnings or []
    candidate_exclusion_counts = candidate_exclusion_counts or {}
    lines: list[str] = []
    lines.append("📌 포트폴리오 점검 요약")
    lines.append("--------------------------------")
    lines.append(f"평가금액: {portfolio.total_krw_evaluation:,}원 | 현금: {portfolio.total_krw_deposit:,}원 | 보유 종목: {len(portfolio.positions)}개")
    lines.append("")
    lines.append("📊 이번 주 거시 시장 상태")
    lines.append("--------------------------------")
    lines.append(f"{macro_status.value} | KOSPI 10MA: {macro_indicators['kospi_above_10ma']} | KOSDAQ 10MA: {macro_indicators['kosdaq_above_10ma']}")
    lines.append(f"미국 기준금리: {macro_indicators.get('us_rate')} | 장단기 금리차: {macro_indicators.get('yield_curve_10y2y')}")
    lines.append("")
    lines.append("🏆 금주 우량 성장주 후보 TOP")
    lines.append("--------------------------------")
    if ranked_candidates:
        for candidate in ranked_candidates:
            score_text = f" | 점수: {candidate.review_score:.2f}" if candidate.review_score is not None else ""
            lines.append(f"{candidate.final_rank}. {candidate.name} ({candidate.ticker}) | PEG: {candidate.peg:.2f}{score_text} | TAG: {candidate.strategy_type}")
            if candidate.rationale:
                lines.append(f"   - 근거: {', '.join(candidate.rationale)}")
            if candidate.risks:
                lines.append(f"   - 리스크: {', '.join(candidate.risks)}")
            if candidate.provider:
                lines.append(f"   - 데이터: {candidate.provider}")
    else:
        lines.append("- 조건 만족 종목이 최소 기준 미만이거나 후보 검토 보류 상태입니다.")
        if candidate_exclusion_counts:
            lines.append("- 주요 제외 사유:")
            for reason, count in list(candidate_exclusion_counts.items())[:5]:
                lines.append(f"   - {reason}: {count}개")
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
    if telegram_delivery_status is not None:
        lines.append(f"- Telegram 전송 상태: {telegram_delivery_status}")
    if portfolio.ip_changed_flag:
        lines.append("- 공인 IP 변경 감지: 증권사 화이트리스트 확인 필요")
    if not failed_sources and not portfolio.source_warnings and not market_data_warnings and not portfolio.ip_changed_flag:
        lines.append("- 포트폴리오 입력 및 데이터 소스 상태 정상")
    lines.append("")
    lines.append("💰 후보 검토 메모")
    lines.append("--------------------------------")
    if ranked_candidates:
        for candidate in ranked_candidates:
            note = candidate.review_note
            lines.append(f"- {candidate.name} ({candidate.ticker}): 후보 검토 [{candidate.strategy_type}]")
            if note is None:
                lines.append("  - 검토 이유: 구조화된 검토 메모가 아직 생성되지 않았습니다.")
                continue
            lines.append(f"  - 검토 이유: {note.review_reason}")
            lines.append(f"  - 보류/확인 사유: {note.defer_or_reject_reason}")
            lines.append(f"  - 다음 확인: {note.next_check}")
            lines.append(f"  - 데이터 신뢰도: {note.data_confidence}")
    else:
        lines.append("- 검토 가능한 신규 후보가 없습니다.")
        if candidate_exclusion_counts:
            lines.append("- 다음 확인: 주요 제외 사유 상위 항목을 확인해 이번 주 검토 보류 원인을 점검하세요.")
    lines.append("")
    lines.append(f"생성 시각: {generated_at.isoformat()}")
    return "\n".join(lines)


def render_telegram_markdown_v2(report: str) -> str:
    return escape_markdown(report)
