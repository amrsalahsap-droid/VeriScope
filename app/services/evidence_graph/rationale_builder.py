"""Rationale Builder - Builds change-aware rationales for recommended tests."""

from typing import Any, Optional

def _get_attr(obj: Any, key: str, default: Any = None) -> Any:
    """Helper to get attribute from object or dictionary."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

def build_rationale(
    source: str,
    requirement_node: Optional[Any] = None,
    change_summary: Optional[Any] = None,
    existing_test_info: Optional[Any] = None,
    gap_description: Optional[str] = None,
    file_path: Optional[str] = None,
    flow_name: Optional[str] = None
) -> str:
    """Build natural language justifications/rationales for missing tests."""
    gap_description = gap_description or "this specific case"
    flow_name = flow_name or _get_attr(requirement_node, "flow", "this flow") if requirement_node else "this flow"

    if source == "REQUIREMENT_GAP":
        if change_summary:
            # Extract specific rule from change_summary
            rules = _get_attr(change_summary, "changed_rules", [])
            changed_rule = "password validation rules"
            if rules:
                first_rule = rules[0]
                rule_name = _get_attr(first_rule, "rule_name") or str(first_rule)
                changed_rule = rule_name
            
            file = _get_attr(change_summary, "file_path", "the code")
            test_name = _get_attr(existing_test_info, "name", "the existing test")
            what_it_covers = _get_attr(existing_test_info, "covers", "the basic case")
            
            consequence = "weak passwords could be accepted" if "weak" in gap_description.lower() else "a defect could go undetected"
            
            return (
                f"The PR modified {changed_rule} in {file}. "
                f"The existing test '{test_name}' covers {what_it_covers} but does not verify {gap_description}. "
                f"If {gap_description} has a defect, {consequence}."
            )
        else:
            return (
                f"The existing test covers the basic case but does not verify {gap_description}. "
                f"This edge case is commonly a source of defects in {flow_name} implementations."
            )

    elif source == "COVERAGE_GAP":
        if change_summary and _get_attr(change_summary, "new_conditionals", 0) > 0:
            new_cond_count = _get_attr(change_summary, "new_conditionals", 0)
            file = _get_attr(change_summary, "file_path", "the changed file")
            return f"The PR added {new_cond_count} new conditional branch(es) in {file}. This branch has 0% coverage. A bug in this logic would not be caught by any existing test."
        else:
            file = file_path or "the changed file"
            return f"The uncovered branches in {file} are not exercised by any existing test. A bug here would go undetected."

    elif source == "RISK_HEURISTIC":
        count = _get_attr(existing_test_info, "count", 0)
        if change_summary:
            file = _get_attr(change_summary, "file_path", "the code")
            return f"{flow_name} is security-sensitive and was modified in {file}. The edge case '{gap_description}' remains untested, which could allow a security vulnerability if the change introduced a regression."
        else:
            return f"{flow_name} is security-sensitive with only {count} test(s). The edge case '{gap_description}' is untested and could allow a vulnerability."

    # Fallback
    return (
        f"The existing test covers the basic case but does not verify {gap_description}. "
        f"This edge case is commonly a source of defects in {flow_name} implementations."
    )
