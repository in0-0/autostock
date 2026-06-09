from __future__ import annotations

from datetime import datetime
from typing import Any

from src.models import Candidate, CandidateReviewNote, MacroStatus


_REVIEW_REASON_LABELS = {
    "financial_cutoff_passed": "재무 기준을 통과했습니다",
    "WEEKLY_20MA_PULLBACK": "주봉 20주선 눌림목 조건을 만족했습니다",
    "WEEKLY_60MA_PULLBACK": "주봉 60주선 눌림목 조건을 만족했습니다",
}

_RISK_LABELS = {
    "macro_caution_penalty": "거시 환경이 CAUTION 상태라 점수에 보수적 감점이 반영되었습니다",
    "macro_data_unavailable": "거시 데이터가 부족해 보수적 확인이 필요합니다",
    "stale_price_data": "가격 데이터가 오래되어 최신성 확인이 필요합니다",
    "stale_technical_data": "기술적 지표 데이터가 오래되어 최신성 확인이 필요합니다",
    "stale_fundamental_data": "재무 데이터가 오래되어 최신성 확인이 필요합니다",
    "source_risk_not_allowed": "허용되지 않은 데이터 출처 위험이 감지되었습니다",
    "missing_current_price": "현재가 데이터가 부족합니다",
}


def build_candidate_review_note(
    candidate: Candidate,
    *,
    macro_status: MacroStatus,
    macro_provider: str | None,
    generated_at: datetime,
    market_data_warnings: list[str] | None = None,
) -> CandidateReviewNote:
    """Build a human-review note from existing candidate evidence.

    The first pass intentionally uses only current Candidate/filter/provenance/risk
    data. Excluded or near-miss tickers are summarized separately by top exclusion
    categories rather than silently mixing per-ticker near-miss notes into ranked
    candidate notes.
    """

    warnings = list(dict.fromkeys(market_data_warnings or []))
    risks = list(dict.fromkeys([*candidate.risks, *warnings]))
    review_reason = _review_reason(candidate)
    defer_or_reject_reason = _defer_or_reject_reason(risks)
    next_check = _next_check(candidate, macro_status, risks)
    data_confidence = _data_confidence(candidate, macro_status, risks)
    source_context = {
        "note_scope": "ranked_candidate_only",
        "excluded_or_near_miss_policy": "top_exclusion_categories_only",
        "ticker": candidate.ticker,
        "provider": candidate.provider,
        "rationale": list(candidate.rationale),
        "risks": risks,
        "review_score": candidate.review_score,
        "score_inputs": dict(candidate.score_inputs),
        "filters": dict(candidate.filters),
        "data_provenance": dict(candidate.data_provenance),
        "strategy_type": candidate.strategy_type,
        "peg": candidate.peg,
        "macro_status": macro_status.value,
        "macro_provider": macro_provider,
    }
    generated_context = {
        "generated_at": generated_at.isoformat(),
        "note_policy_version": "candidate_review_note_v1",
        "language": "ko",
    }
    return CandidateReviewNote(
        review_reason=review_reason,
        defer_or_reject_reason=defer_or_reject_reason,
        next_check=next_check,
        data_confidence=data_confidence,
        source_context=source_context,
        generated_context=generated_context,
        excluded_or_near_miss_context="first_pass_uses_top_exclusion_categories_only",
    )


def _review_reason(candidate: Candidate) -> str:
    reasons = [_REVIEW_REASON_LABELS.get(item, item) for item in candidate.rationale]
    if candidate.review_score is not None:
        reasons.append(f"검토 점수 {candidate.review_score:.2f}로 후보군 내 우선순위가 산정되었습니다")
    reasons.append(f"PEG {candidate.peg:.2f}와 {candidate.strategy_type} 조건을 함께 확인했습니다")
    return "; ".join(dict.fromkeys(reasons))


def _defer_or_reject_reason(risks: list[str]) -> str:
    if not risks:
        return "현재 후보 메모 기준의 즉시 보류 사유는 감지되지 않았습니다."
    return "보류 또는 추가 확인 사유: " + "; ".join(_risk_label(risk) for risk in risks)


def _next_check(candidate: Candidate, macro_status: MacroStatus, risks: list[str]) -> str:
    if macro_status == MacroStatus.CAUTION or "macro_caution_penalty" in risks:
        return "거시 환경 CAUTION 감점이 유지되는지와 후보의 주봉 눌림목 조건이 유지되는지 확인하세요."
    if any("stale" in risk or "unavailable" in risk for risk in risks):
        return "데이터 최신성 또는 provider 경고가 해소된 뒤 같은 후보가 유지되는지 확인하세요."
    if any("opendart" in risk.lower() or "dart_status" in risk for risk in risks):
        return "OpenDART 재무제표 제공 공백이 후보 판단에 영향을 주는지 확인하세요."
    return f"다음 거래일 전 {candidate.strategy_type} 조건과 최근 거래량 흐름이 유지되는지 확인하세요."


def _data_confidence(candidate: Candidate, macro_status: MacroStatus, risks: list[str]) -> str:
    source_risks = _collect_source_risks(candidate.data_provenance)
    if risks or macro_status != MacroStatus.NORMAL:
        return "주의: 리스크 또는 거시/데이터 경고가 있어 추가 확인이 필요합니다."
    if any(risk not in {"official_api", "package_public_source", "manual_config", None, ""} for risk in source_risks):
        return "주의: 일부 데이터 출처의 신뢰도 확인이 필요합니다."
    return "기본 확인: 현재 provider/provenance 기준에서 주요 데이터 경고는 감지되지 않았습니다."


def _risk_label(risk: str) -> str:
    if risk.startswith("provider_failed:opendart:dart_status:013"):
        return "OpenDART가 해당 종목/기간 재무제표 데이터를 제공하지 않았습니다"
    if risk.startswith("missing_"):
        return f"필수 입력 데이터가 부족합니다({risk})"
    return _RISK_LABELS.get(risk, risk)


def _collect_source_risks(value: Any) -> list[str | None]:
    if isinstance(value, dict):
        risks: list[str | None] = []
        if "source_risk" in value:
            risks.append(value.get("source_risk"))
        for item in value.values():
            risks.extend(_collect_source_risks(item))
        return risks
    if isinstance(value, list):
        risks = []
        for item in value:
            risks.extend(_collect_source_risks(item))
        return risks
    return []
