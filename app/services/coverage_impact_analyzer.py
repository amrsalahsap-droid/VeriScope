"""Coverage Gap Analyzer for Phase 8

Analyzes coverage data in the context of semantic changes to identify
gaps where new or modified code is not covered by tests.
"""

from typing import List, Dict, Any, Optional
from app.schemas.regression_scope_v2 import ChangeSummary, CoverageGap


class CoverageImpactAnalyzer:
    """Analyzes coverage gaps in the context of code changes."""
    
    # Coverage thresholds
    HIGH_COVERAGE_THRESHOLD = 0.8  # 80%
    MEDIUM_COVERAGE_THRESHOLD = 0.6  # 60%
    
    @staticmethod
    def analyze_file_coverage_gap(
        change_summary: ChangeSummary,
        coverage_data: Optional[Dict[str, Any]],
        file_to_requirement_map: Optional[Dict[str, List[str]]] = None
    ) -> Optional[CoverageGap]:
        """Analyze coverage gaps for a single changed file."""
        
        if not coverage_data:
            # No coverage data available, assume gap if changes exist
            if change_summary.new_conditionals > 0 or change_summary.changed_functions:
                return CoverageGap(
                    file_path=change_summary.file_path,
                    uncovered_branches=[
                        f"No coverage data available for {len(change_summary.changed_functions)} changed functions"
                    ],
                    related_requirement_ids=file_to_requirement_map.get(change_summary.file_path, []) if file_to_requirement_map else [],
                    risk="HIGH",
                    gap_type="NEW_BRANCH"
                )
            return None
        
        # Get coverage for this specific file
        file_coverage = coverage_data.get(change_summary.file_path, {})
        
        gaps = []
        risk_level = "LOW"
        
        # Check for uncovered new conditionals
        if change_summary.new_conditionals > 0:
            branch_coverage = file_coverage.get('branch_coverage', 1.0)
            if branch_coverage < CoverageImpactAnalyzer.HIGH_COVERAGE_THRESHOLD:
                gaps.append(f"{change_summary.new_conditionals} new conditionals with {branch_coverage:.0%} branch coverage")
                risk_level = "HIGH"
        
        # Check for uncovered changed functions
        for func in change_summary.changed_functions:
            func_coverage = file_coverage.get('functions', {}).get(func, {})
            if not func_coverage or func_coverage.get('coverage', 1.0) < CoverageImpactAnalyzer.HIGH_COVERAGE_THRESHOLD:
                gaps.append(f"Function '{func}' has low or no coverage")
                risk_level = "HIGH"
        
        # Check for changed rules (validation logic)
        for rule in change_summary.changed_rules:
            if rule.rule_type == 'security':
                gaps.append(f"Security rule '{rule.rule_name}' was modified")
                risk_level = "HIGH"
            elif rule.rule_type == 'validation':
                gaps.append(f"Validation rule '{rule.rule_name}' was modified")
                risk_level = "MEDIUM"
        
        # Determine gap type based on what was found
        gap_type = "SHALLOW_COVERAGE"
        if change_summary.new_conditionals > 0 and any('conditional' in gap for gap in gaps):
            gap_type = "NEW_BRANCH"
        elif any('function' in gap for gap in gaps):
            gap_type = "UNCOVERED_FUNCTION"
        
        # Only return if we found actual gaps
        if gaps:
            return CoverageGap(
                file_path=change_summary.file_path,
                uncovered_branches=gaps,
                related_requirement_ids=file_to_requirement_map.get(change_summary.file_path, []) if file_to_requirement_map else [],
                risk=risk_level,
                gap_type=gap_type
            )
        
        return None
    
    @staticmethod
    def analyze_coverage_gaps(
        change_summaries: List[ChangeSummary],
        coverage_data: Optional[Dict[str, Any]] = None,
        file_to_requirement_map: Optional[Dict[str, List[str]]] = None
    ) -> List[CoverageGap]:
        """Analyze coverage gaps across all changed files."""
        gaps = []
        
        for summary in change_summaries:
            gap = CoverageImpactAnalyzer.analyze_file_coverage_gap(
                summary,
                coverage_data,
                file_to_requirement_map
            )
            if gap:
                gaps.append(gap)
        
        return gaps
    
    @staticmethod
    def extract_coverage_from_snapshot(snapshot_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract coverage data from the evidence graph snapshot."""
        # Coverage data might be stored in different locations
        # Try common paths
        if 'coverage' in snapshot_data:
            return snapshot_data['coverage']
        
        if 'testCoverage' in snapshot_data:
            return snapshot_data['testCoverage']
        
        # If not found, return None
        return None
    
    @staticmethod
    def build_file_to_requirement_map(
        snapshot_data: Dict[str, Any],
        changed_files: List[str]
    ) -> Dict[str, List[str]]:
        """Build a mapping from file paths to related requirement IDs."""
        file_to_req = {f: [] for f in changed_files}
        
        # Extract from acTraceability if available
        ac_traceability = snapshot_data.get('acTraceability', [])
        
        for trace in ac_traceability:
            req_id = trace.get('requirementId')
            linked_tests = trace.get('linkedExistingTests', [])
            
            # Extract file paths from test names
            for test in linked_tests:
                test_name = test if isinstance(test, str) else str(test)
                # Try to extract file path from test name
                # Common patterns: "file.spec.ts", "file.test.ts", "file.ts"
                for changed_file in changed_files:
                    file_name = changed_file.split('/')[-1].replace('.ts', '').replace('.js', '')
                    if file_name in test_name:
                        if req_id and req_id not in file_to_req[changed_file]:
                            file_to_req[changed_file].append(req_id)
        
        return file_to_req
