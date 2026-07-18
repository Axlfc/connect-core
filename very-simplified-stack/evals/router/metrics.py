from typing import List, Dict, Any
from evals.router.schemas import LabeledTestCase
from app.models.domain import RouteDecision

TIER_SEVERITY = {
    "local": 1,
    "luna": 2,
    "terra": 3,
    "sol": 4
}

def calculate_evaluation_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(results)
    if total == 0:
        return {}

    exact_tier_agreements = 0
    executor_agreements = 0
    safe_route_agreements = 0

    under_routed_count = 0
    under_routed_cost = 0.0
    over_routed_count = 0

    high_risk_total = 0
    high_risk_correct_sol = 0

    for r in results:
        case: LabeledTestCase = r["case"]
        decision: RouteDecision = r["decision"]

        exp_tier = case.expected_logical_tier
        act_tier = decision.logical_tier

        exp_sev = TIER_SEVERITY.get(exp_tier, 1)
        act_sev = TIER_SEVERITY.get(act_tier, 1)

        # Exact agreement
        if exp_tier == act_tier:
            exact_tier_agreements += 1

        # Executor agreement
        if case.expected_executor == decision.executor:
            executor_agreements += 1

        # Safe route agreement (actual >= expected severity)
        if act_sev >= exp_sev:
            safe_route_agreements += 1
        else:
            under_routed_count += 1
            # Weighted penalty based on severity gap
            under_routed_cost += (exp_sev - act_sev) * 2.0

        # Over routing
        if act_sev > exp_sev:
            over_routed_count += 1

        # High risk recall
        if case.is_high_risk:
            high_risk_total += 1
            if act_tier == "sol":
                high_risk_correct_sol += 1

    return {
        "total_cases": total,
        "exact_tier_agreement_rate": exact_tier_agreements / total,
        "executor_agreement_rate": executor_agreements / total,
        "safe_route_agreement_rate": safe_route_agreements / total,
        "under_routing_rate": under_routed_count / total,
        "under_routing_weighted_cost": under_routed_cost,
        "over_routing_rate": over_routed_count / total,
        "high_risk_recall": high_risk_correct_sol / high_risk_total if high_risk_total > 0 else 1.0,
        "high_risk_total": high_risk_total
    }
