from typing import List, Dict, Any, Optional, Set
import os


class CoverageFileBehaviorSupportMapper:
    """Maps code coverage inputs as auxiliary backing evidence to support behavior-level confidence."""

    def __init__(self, db: Optional[Any] = None):
        """Initialize mapper with optional database session."""
        self.db = db

    def map_coverage_support(
        self,
        coverage_file_entries: List[Dict[str, Any]], # [{ "file_path": "auth/reset-password/api.py", "line_coverage_ratio": 0.85 }]
        behavior_evidences: List[Dict[str, Any]],    # [{ "behavior_id": "...", "source_path": "auth/reset-password/api.py" }]
        behavior_impact_items: List[Dict[str, Any]], # [{ "behavior_id": "...", "behavior_name": "Password Reset" }]
        test_coverage_links: Optional[List[Dict[str, Any]]] = None,
        commit_mismatch: bool = False,               # If commit/branch mismatch is detected
    ) -> List[Dict[str, Any]]:
        """Map coverage report file entries as supporting evidence to behavior-level items."""
        support_records = []
        coverage_links = test_coverage_links or []

        # Create quick lookups
        behavior_evidences_map = {}
        for ev in behavior_evidences:
            b_id = str(ev["behavior_id"])
            if b_id not in behavior_evidences_map:
                behavior_evidences_map[b_id] = []
            behavior_evidences_map[b_id].append(ev)

        # Map each coverage file entry
        for entry in coverage_file_entries:
            file_path = entry["file_path"]
            file_lower = file_path.lower()
            file_cov_p = entry.get("line_coverage_ratio", 0.0)

            # Skip mapping files with zero coverage (no supportive evidence)
            if file_cov_p <= 0:
                continue

            for item in behavior_impact_items:
                b_id = str(item["behavior_id"])
                b_evidences = behavior_evidences_map.get(b_id, [])

                # Match stages:
                support_type = None
                confidence = "LOW"
                reason_parts = []

                # Stage 1: Direct file coverage
                is_direct = False
                for ev in b_evidences:
                    if ev.get("source_path") and ev["source_path"].lower() == file_lower:
                        is_direct = True
                        break

                if is_direct:
                    support_type = "DIRECT_FILE"
                    confidence = "HIGH" if file_cov_p >= 0.8 else "MODERATE"
                    reason_parts.append(f"Direct code coverage on behavior evidence source file ({file_cov_p * 100:.1f}%)")

                # Stage 2: Related module coverage
                elif any(term in file_lower for term in item["behavior_name"].lower().split() if len(term) > 3):
                    support_type = "RELATED_MODULE"
                    confidence = "MODERATE" if file_cov_p >= 0.5 else "LOW"
                    reason_parts.append(f"Indirect coverage on related module path matching behavior tokens ({file_cov_p * 100:.1f}%)")

                # Stage 3: Indirect tracing via TestCoverageLink
                else:
                    has_indirect_trace = False
                    for link in coverage_links:
                        if link["file_path"].lower() == file_lower:
                            has_indirect_trace = True
                            break
                    if has_indirect_trace:
                        support_type = "INDIRECT"
                        confidence = "LOW"
                        reason_parts.append(f"Indirect coverage matched via test execution traces ({file_cov_p * 100:.1f}%)")

                # Apply decay / penalty rules
                if support_type:
                    # Mismatch penalty rule: commit or branch mismatch significantly reduces confidence
                    if commit_mismatch:
                        confidence = "LOW"
                        reason_parts.append("Branch/commit mismatch detected - coverage mapped with degraded confidence")

                    # Scenario coverage rule: code coverage does NOT prove validation of a scenario alone
                    reason_parts.append("Coverage acts as supporting evidence; does not independently verify business scenario")

                    support_records.append({
                        "behavior_id": b_id,
                        "behavior_scenario_id": item.get("behavior_scenario_id"),
                        "coverage_file_path": file_path,
                        "support_type": support_type,
                        "confidence": confidence,
                        "reason": " / ".join(reason_parts),
                    })

        return support_records
