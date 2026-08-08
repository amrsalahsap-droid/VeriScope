"""Recommendation Detail Builder - Generates specific detailed scenarios."""

from typing import List, Dict, Any, Optional, Set
from app.schemas.regression_scope_v2 import DetailedScenario
from app.services.evidence_graph.edge_case_knowledge import EDGE_CASE_KNOWLEDGE

FLOW_PRECONDITIONS = {
    "sign_up": "User navigates to sign-up form",
    "sign-up": "User navigates to sign-up form",
    "update_password": "User is logged in and navigates to change password page",
    "update-password": "User is logged in and navigates to change password page",
    "reset_password": "User clicks password reset link with valid token",
    "reset-password": "User clicks password reset link with valid token",
    "login": "User navigates to login page",
    "login_after_password_change": "User logs in with the new password after a successful update",
    "api_validation": "Direct API request sent to endpoint without frontend",
    "ui_validation": "User interacts with the UI form",
    "account_security": "User performs account security-sensitive operation",
}

def _derive_precondition(flow_name: str) -> str:
    """Derive precondition from flow name."""
    normalized = flow_name.lower().replace(" ", "_").replace("-", "_") if flow_name else ""
    return FLOW_PRECONDITIONS.get(normalized, f"User is on the {flow_name} page" if flow_name else "the application")

def _generate_input_for_rule(rule_title: str, linked_test_data: List[str]) -> str:
    """Generate or extract a password that violates the child rule but meets other rules."""
    rule_lower = rule_title.lower()
    rule_type = None
    
    if "uppercase" in rule_lower or "upper case" in rule_lower or "capital" in rule_lower:
        rule_type = "uppercase"
    elif "lowercase" in rule_lower or "lower case" in rule_lower:
        rule_type = "lowercase"
    elif "number" in rule_lower or "digit" in rule_lower:
        rule_type = "number"
    elif "special" in rule_lower or "symbol" in rule_lower:
        rule_type = "special"
    elif "length" in rule_lower:
        rule_type = "length"

    # Search linked_test_data for a matching input
    if linked_test_data:
        for item in linked_test_data:
            item_str = str(item)
            clean_item = item_str.replace("invalid examples:", "").strip()
            parts = [p.strip() for p in clean_item.split(",") if p.strip()]
            for part in parts:
                part_clean = part.strip("'\"")
                if rule_type == "uppercase" and not any(c.isupper() for c in part_clean):
                    return part_clean
                elif rule_type == "lowercase" and not any(c.islower() for c in part_clean):
                    return part_clean
                elif rule_type == "number" and not any(c.isdigit() for c in part_clean):
                    return part_clean
                elif rule_type == "special" and part_clean.isalnum():
                    return part_clean
                elif rule_type == "length" and len(part_clean) < 8:
                    return part_clean

    # Fallback to base transformations on "StrongPass#2026"
    base = "StrongPass#2026"
    if rule_type == "uppercase":
        return base.lower()  # e.g., strongpass#2026
    elif rule_type == "lowercase":
        return base.upper()  # e.g., STRONGPASS#2026
    elif rule_type == "number":
        return "".join(c for c in base if not c.isdigit())  # e.g., StrongPass#
    elif rule_type == "special":
        return "".join(c for c in base if c.isalnum())  # e.g., StrongPass2026
    elif rule_type == "length":
        return "Str#202"  # short length (7 chars)
    
    return base

def _is_child_rule_tested(rule_title: str, existing_tests: Set[str]) -> bool:
    """Determine if a child rule has an existing test by keyword checking."""
    if not existing_tests:
        return False
    
    rule_lower = rule_title.lower()
    keywords = []
    
    if "uppercase" in rule_lower or "upper case" in rule_lower or "capital" in rule_lower:
        keywords = ["uppercase", "upper_case", "capital"]
    elif "lowercase" in rule_lower or "lower case" in rule_lower:
        keywords = ["lowercase", "lower_case"]
    elif "number" in rule_lower or "digit" in rule_lower:
        keywords = ["number", "digit", "numeric"]
    elif "special character" in rule_lower or "special char" in rule_lower or "symbol" in rule_lower:
        keywords = ["special_char", "specialchar", "symbol", "non_alphanumeric"]
    elif "length" in rule_lower or "character" in rule_lower or "char" in rule_lower:
        keywords = ["length", "short", "min_char", "minchar"]
        
    if not keywords:
        words = [w for w in rule_lower.split() if len(w) > 3]
        keywords = words
        
    for test in existing_tests:
        test_lower = test.lower()
        if any(kw in test_lower for kw in keywords):
            return True
            
    return False

def build_detailed_scenario(
    source: str,
    requirement_node: Optional[Any] = None,
    coverage_gap_info: Optional[Any] = None,
    flow_name: Optional[str] = None,
    existing_tests: Optional[Set[str]] = None,
    change_summary: Optional[Any] = None
) -> List[DetailedScenario]:
    """Build a list of detailed test scenarios based on the gap source."""
    scenarios = []
    existing_tests = existing_tests or set()

    if source == "REQUIREMENT_GAP" and requirement_node:
        child_rules = getattr(requirement_node, "child_rules", []) or []
        linked_test_data = getattr(requirement_node, "linked_test_data", []) or []
        flow = getattr(requirement_node, "flow", flow_name or "sign-up")
        validation_layer = getattr(requirement_node, "validation_layer", "API")
        title = getattr(requirement_node, "title", "")
        polarity = getattr(requirement_node, "polarity", "negative")
        
        # Determine test layer mapping
        layer_lower = str(validation_layer).lower()
        if "backend" in layer_lower:
            test_layer = "API"
        elif "ui" in layer_lower:
            test_layer = "UI"
        elif "cross" in layer_lower:
            test_layer = "API + UI"
        else:
            test_layer = "API"

        precondition = _derive_precondition(flow)

        if child_rules:
            # Loop through child rules
            for rule in child_rules:
                rule_title = getattr(rule, "title", "") if not isinstance(rule, dict) else rule.get("title", "")
                if not rule_title:
                    continue

                if not _is_child_rule_tested(rule_title, existing_tests):
                    rule_name = rule_title.replace("System must require ", "").replace("System must require at least one ", "").strip()
                    test_input = _generate_input_for_rule(rule_title, linked_test_data)
                    
                    scenarios.append(DetailedScenario(
                        precondition=precondition,
                        test_input=f"Password: '{test_input}' (meets all rules except {rule_name})",
                        expected_result=f"Password rejected with message indicating {rule_name} is required",
                        test_layer=test_layer
                    ))
        else:
            # Scenario for main requirement
            title_lower = title.lower()
            is_negative = "reject" in title_lower or "weak" in title_lower or "invalid" in title_lower or polarity == "negative"
            
            if is_negative:
                weak_input = None
                if linked_test_data:
                    for item in linked_test_data:
                        item_str = str(item)
                        for cand in ["short1!", "password123!", "", " ", "   "]:
                            if cand == item_str.strip().strip("'\""):
                                weak_input = cand
                                break
                        if weak_input is not None:
                            break
                    if weak_input is None and len(linked_test_data) > 0:
                        weak_input = str(linked_test_data[0]).strip().strip("'\"")
                
                if weak_input is None:
                    if "weak" in title_lower:
                        weak_input = "short1!"
                    elif "empty" in title_lower:
                        weak_input = '""'
                    elif "whitespace" in title_lower:
                        weak_input = '"   "'
                    else:
                        weak_input = "short1!"
                
                test_input = f"Password: '{weak_input}'"
                expected_result = "Password validation fails and request is rejected"
            else:
                test_input = "Password: 'StrongPass#2026'"
                expected_result = "Password validation succeeds and request is accepted"

            scenarios.append(DetailedScenario(
                precondition=precondition,
                test_input=test_input,
                expected_result=expected_result,
                test_layer=test_layer
            ))

    elif source == "COVERAGE_GAP" and coverage_gap_info:
        file_path = getattr(coverage_gap_info, "file_path", "") if not isinstance(coverage_gap_info, dict) else coverage_gap_info.get("file_path", "")
        
        precondition = f"Derive context for {flow_name or 'validation'} in {file_path.split('/')[-1]}" if file_path else "Setup test environment"
        
        # Check if we have change summary data and a new conditional branch
        new_conds = getattr(change_summary, "new_conditionals", []) if change_summary else []
        if isinstance(new_conds, list) and len(new_conds) > 0:
            cond = new_conds[0]
            test_input = f"Exercise the branch: {cond}"
        else:
            test_input = f"Exercise uncovered branches in {file_path}"

        scenarios.append(DetailedScenario(
            precondition=precondition,
            test_input=test_input,
            expected_result="Verify correct behavior per the requirement specification",
            test_layer="API"
        ))

    elif source == "RISK_HEURISTIC" and flow_name:
        flow_key = flow_name.lower()
        matching_flow = None
        for k in EDGE_CASE_KNOWLEDGE.keys():
            if k in flow_key or flow_key in k:
                matching_flow = k
                break
        
        if matching_flow:
            edge_cases = EDGE_CASE_KNOWLEDGE[matching_flow]
            precondition = _derive_precondition(matching_flow)
            
            uncovered_cases = []
            for ec_desc, ec_expected in edge_cases:
                is_tested = False
                flow_words = {matching_flow, matching_flow.replace("-", ""), "login", "signup", "password", "reset", "update"}
                ec_words = [w.lower() for w in ec_desc.split() if len(w) > 3 and w.lower() not in flow_words]
                
                ec_normalized = ec_desc.lower().replace(" ", "_")
                ec_normalized_dash = ec_desc.lower().replace(" ", "-")
                
                for test in existing_tests:
                    test_lower = test.lower()
                    if ec_desc.lower() in test_lower or ec_normalized in test_lower or ec_normalized_dash in test_lower:
                        is_tested = True
                        break
                    if ec_words and any(w in test_lower for w in ec_words):
                        is_tested = True
                        break
                if not is_tested:
                    uncovered_cases.append((ec_desc, ec_expected))
            
            for ec_desc, ec_expected in uncovered_cases[:3]:
                if any(kw in ec_desc.lower() for kw in ["security", "concurrent", "race"]):
                    layer = "E2E"
                elif any(kw in ec_desc.lower() for kw in ["token", "boundary", "api"]):
                    layer = "API"
                else:
                    layer = "UI"

                test_input = f"Edge case: {ec_desc}"
                if "weak" in ec_desc.lower():
                    test_input = "short1!"
                elif "empty" in ec_desc.lower():
                    test_input = '""'
                elif "whitespace" in ec_desc.lower():
                    test_input = '"   "'

                scenarios.append(DetailedScenario(
                    precondition=precondition,
                    test_input=test_input,
                    expected_result=ec_expected,
                    test_layer=layer
                ))

    return scenarios
