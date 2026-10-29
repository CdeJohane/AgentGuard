"""Combine and explain policy decisions for policy demos and project execution."""


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


def explain_decisions(layer_decisions: object) -> tuple[str, str]:
    """Combine policy-authored layer records and explain the winning decision.

    Records have nonblank string layer/reason fields and a recognized decision.
    Supply policy reasons, never file contents or credentials. This helper does
    not sanitize secrets in otherwise valid strings or execute any action.
    """
    malformed = ("deny", "Malformed policy decisions.")
    if not isinstance(layer_decisions, list):
        return malformed
    for item in layer_decisions:
        if not isinstance(item, dict):
            return malformed
        if not all(
            isinstance(item.get(field), str) and item[field].strip()
            for field in ("layer", "decision", "reason")
        ):
            return malformed
        if item["decision"] not in ("allow", "deny", "review"):
            return malformed
    if not layer_decisions:
        return ("review", "No policy decisions were provided.")

    decision = combine_decisions([item["decision"] for item in layer_decisions])

    # Keep all reasons matching the final decision, in input order.
    my_str = ""
    for dec in layer_decisions:
        if dec["decision"] == decision:
            if my_str == "":
                my_str = dec["layer"] + ": " + dec["reason"]
            else:
                my_str += "; " + dec["layer"] + ": " + dec["reason"]
    return (decision, my_str)
