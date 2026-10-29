"""Combine policy decisions; not connected to the guard or executor yet."""


def combine_decisions(decisions: object) -> str:
    """Combine applicable layers into allow, deny, or review.

    Only allow permits execution. Review means wait for a human decision.
    Any denial wins over review; only all-allow input permits the action.
    """
    if not isinstance(decisions, list):
        return "deny"
    if any(
        not isinstance(decision, str)
        or decision not in ("allow", "deny", "review")
        for decision in decisions
    ):
        return "deny"

    # A denial takes priority regardless of which layer produced it.
    if "deny" in decisions:
        return "deny"
    elif "review" in decisions or decisions == []:
        return "review"
    else:
        return "allow"
