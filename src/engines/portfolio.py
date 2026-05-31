from __future__ import annotations

from src.models import Candidate, MacroStatus, PortfolioState, RecommendationAction, TradeGuide


class PortfolioEngine:
    def __init__(self, min_candidates: int, max_candidates: int, target_position_ratio: float) -> None:
        self.min_candidates = min_candidates
        self.max_candidates = max_candidates
        self.target_position_ratio = target_position_ratio

    def rank_candidates(
        self,
        candidates: list[Candidate],
        macro_status: MacroStatus = MacroStatus.NORMAL,
    ) -> list[Candidate]:
        if len(candidates) < self.min_candidates:
            return []
        scored = [self._score_candidate(candidate, macro_status) for candidate in candidates]
        ranked = sorted(scored, key=lambda candidate: (-(candidate.review_score or 0.0), candidate.peg))[: self.max_candidates]
        return [candidate.model_copy(update={"final_rank": index + 1}) for index, candidate in enumerate(ranked)]

    def _score_candidate(self, candidate: Candidate, macro_status: MacroStatus) -> Candidate:
        base_score = 0.0 if candidate.peg <= 0 else 100.0 / candidate.peg
        macro_penalty = 0.85 if macro_status == MacroStatus.CAUTION else 1.0
        review_score = round(base_score * macro_penalty, 4)
        risks = list(candidate.risks)
        if macro_status == MacroStatus.CAUTION and "macro_caution_penalty" not in risks:
            risks.append("macro_caution_penalty")
        score_inputs = {
            "score_policy_version": "peg_macro_v1",
            "peg": candidate.peg,
            "base_score": round(base_score, 4),
            "macro_status": macro_status.value,
            "macro_penalty": macro_penalty,
        }
        return candidate.model_copy(
            update={
                "review_score": review_score,
                "score_inputs": score_inputs,
                "risks": risks,
            }
        )

    def build_trade_guides(
        self,
        ranked_candidates: list[Candidate],
        portfolio: PortfolioState,
        macro_status: MacroStatus,
    ) -> list[TradeGuide]:
        guides: list[TradeGuide] = []
        buy_blocked = portfolio.partial_success or macro_status == MacroStatus.RISK_OFF
        available_cash = portfolio.total_krw_deposit

        for candidate in ranked_candidates:
            held = portfolio.positions.get(candidate.ticker)
            current_ratio = held.current_ratio if held else 0.0

            if candidate.exit_signal.value == "REDUCE":
                guides.append(self._guide(candidate, RecommendationAction.REDUCE, "valuation_or_20ma_reduce", current_ratio))
                continue
            if candidate.exit_signal.value == "EXIT":
                guides.append(self._guide(candidate, RecommendationAction.EXIT, "hard_exit_signal", current_ratio))
                continue
            if candidate.exit_signal.value == "WARNING":
                guides.append(self._guide(candidate, RecommendationAction.HOLD_WARNING, "warning_blocks_top_up", current_ratio))
                continue
            if buy_blocked:
                guides.append(self._guide(candidate, RecommendationAction.SKIP, "buy_blocked_by_partial_success_or_macro", current_ratio))
                continue
            if current_ratio >= self.target_position_ratio:
                guides.append(self._guide(candidate, RecommendationAction.HOLD_STRONG, "target_ratio_already_met", current_ratio))
                continue

            required_value = int(portfolio.total_krw_evaluation * (self.target_position_ratio - current_ratio))
            quantity_delta = required_value // candidate.current_price
            required_cash = quantity_delta * candidate.current_price
            if quantity_delta <= 0 or required_cash > available_cash:
                guides.append(self._guide(candidate, RecommendationAction.SKIP, "insufficient_cash_or_too_small", current_ratio))
                continue

            available_cash -= required_cash
            guides.append(
                TradeGuide(
                    ticker=candidate.ticker,
                    name=candidate.name,
                    action=RecommendationAction.BUY,
                    reason="top_up_to_target_ratio",
                    target_ratio=self.target_position_ratio,
                    current_ratio=current_ratio,
                    quantity_delta=quantity_delta,
                    required_cash=required_cash,
                )
            )

        return guides

    def _guide(
        self,
        candidate: Candidate,
        action: RecommendationAction,
        reason: str,
        current_ratio: float,
    ) -> TradeGuide:
        return TradeGuide(
            ticker=candidate.ticker,
            name=candidate.name,
            action=action,
            reason=reason,
            target_ratio=self.target_position_ratio,
            current_ratio=current_ratio,
        )
