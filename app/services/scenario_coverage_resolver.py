"""
ScenarioCoverageResolver
=========================
Determines coverage status for each ScenarioIntent by combining existing test coverage,
code coverage, and execution evidence.
"""

from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from enum import Enum
from sqlalchemy.orm import Session


class ExistingTestStatus(Enum):
    """Status of existing test coverage for a scenario intent."""
    AVAILABLE = "AVAILABLE"
    NOT_FOUND = "NOT_FOUND"


class CodeCoverageStatus(Enum):
    """Status of code coverage for a scenario intent."""
    DIRECT = "DIRECT"
    INDIRECT = "INDIRECT"
    NONE = "NONE"


class ExecutionStatus(Enum):
    """Execution status of tests for a scenario intent."""
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    NOT_RUN = "NOT_RUN"
    UNKNOWN = "UNKNOWN"
    FLAKY = "FLAKY"


class FinalCoverageStatus(Enum):
    """Final consolidated coverage status for a scenario intent."""
    COVERED_AND_VERIFIED = "COVERED_AND_VERIFIED"
    COVERED_NOT_RUN = "COVERED_NOT_RUN"
    PARTIALLY_COVERED = "PARTIALLY_COVERED"
    MISSING_AUTOMATED_COVERAGE = "MISSING_AUTOMATED_COVERAGE"
    SUGGEST_MANUAL_VALIDATION = "SUGGEST_MANUAL_VALIDATION"


@dataclass
class ScenarioCoverageStatus:
    """Coverage status for a scenario intent."""
    scenario_intent_key: str
    existing_test_status: ExistingTestStatus
    code_coverage_status: CodeCoverageStatus
    current_pr_execution_status: ExecutionStatus
    historical_execution_status: ExecutionStatus
    final_status: FinalCoverageStatus
    related_test_identifiers: List[str] = None
    related_file_paths: List[str] = None
    confidence: str = "MEDIUM"
    
    def __post_init__(self):
        if self.related_test_identifiers is None:
            self.related_test_identifiers = []
        if self.related_file_paths is None:
            self.related_file_paths = []


class ScenarioCoverageResolver:
    """
    Resolves coverage status for scenario intents by combining multiple evidence sources.
    
    Rules:
    - Historical JUnit does not equal current PR verification
    - File coverage does not equal scenario coverage
    - Current PR execution outranks historical evidence
    - Missing scenario only if no related existing test and no sufficient coverage
    """
    
    @classmethod
    def determine_existing_test_status(
        cls,
        scenario_intent_key: str,
        existing_test_coverages: List[Any],
        min_confidence: str = "MODERATE"
    ) -> ExistingTestStatus:
        """
        Determine if an existing test covers this scenario intent.
        
        Args:
            scenario_intent_key: The canonical key of the scenario intent
            existing_test_coverages: List of ExistingTestScenarioCoverage objects
            min_confidence: Minimum confidence level to consider (HIGH, MODERATE, LOW)
        
        Returns:
            ExistingTestStatus indicating if a test is available
        """
        confidence_order = {
            "HIGH": 3,
            "MODERATE": 2,
            "LOW": 1
        }
        min_score = confidence_order.get(min_confidence, 2)
        
        for coverage in existing_test_coverages:
            if coverage.scenario_intent_key == scenario_intent_key:
                conf_score = confidence_order.get(coverage.confidence.value, 0)
                if conf_score >= min_score:
                    return ExistingTestStatus.AVAILABLE
        
        return ExistingTestStatus.NOT_FOUND
    
    @classmethod
    def determine_code_coverage_status(
        cls,
        scenario_intent_key: str,
        related_changed_files: List[str],
        coverage_file_entries: List[Any],
        test_coverage_links: List[Any]
    ) -> CodeCoverageStatus:
        """
        Determine code coverage status for the scenario intent.
        
        Args:
            scenario_intent_key: The canonical key of the scenario intent
            related_changed_files: Files related to this scenario
            coverage_file_entries: CoverageFileEntry records
            test_coverage_links: TestCoverageLink records
        
        Returns:
            CodeCoverageStatus indicating coverage level
        """
        if not related_changed_files:
            return CodeCoverageStatus.NONE
        
        # Extract domain/feature from intent key for file matching
        intent_parts = scenario_intent_key.split(".")
        domain = intent_parts[0] if len(intent_parts) > 0 else ""
        feature = intent_parts[1] if len(intent_parts) > 1 else ""
        
        # Check for direct file coverage
        direct_coverage_count = 0
        indirect_coverage_count = 0
        
        for file_path in related_changed_files:
            file_lower = file_path.lower()
            
            # Check coverage file entries
            for entry in coverage_file_entries:
                if hasattr(entry, 'file_path') and entry.file_path.lower() in file_lower:
                    line_cov = getattr(entry, 'line_coverage_percent', None) or getattr(entry, 'line_coverage_ratio', None)
                    if line_cov and line_cov > 0:
                        direct_coverage_count += 1
                        break
            
            # Check test coverage links
            for link in test_coverage_links:
                if hasattr(link, 'file_path') and link.file_path.lower() in file_lower:
                    mapping_type = getattr(link, 'mapping_type', 'HEURISTIC')
                    if mapping_type == 'DIRECT':
                        direct_coverage_count += 1
                    else:
                        indirect_coverage_count += 1
        
        if direct_coverage_count > 0:
            return CodeCoverageStatus.DIRECT
        elif indirect_coverage_count > 0:
            return CodeCoverageStatus.INDIRECT
        else:
            return CodeCoverageStatus.NONE
    
    @classmethod
    def determine_current_pr_execution_status(
        cls,
        scenario_intent_key: str,
        related_test_identifiers: List[str],
        current_pr_test_run: Optional[Any]
    ) -> ExecutionStatus:
        """
        Determine execution status for current PR test run.
        
        Args:
            scenario_intent_key: The canonical key of the scenario intent
            related_test_identifiers: Test identifiers related to this scenario
            current_pr_test_run: TestRun for the current PR (if available)
        
        Returns:
            ExecutionStatus for current PR execution
        """
        if not current_pr_test_run or not related_test_identifiers:
            return ExecutionStatus.NOT_RUN
        
        # Check if any related test ran in the current PR
        if not hasattr(current_pr_test_run, 'test_results'):
            return ExecutionStatus.UNKNOWN
        
        test_results = current_pr_test_run.test_results
        if not test_results:
            return ExecutionStatus.NOT_RUN
        
        # Find matching test results
        passed_count = 0
        failed_count = 0
        skipped_count = 0
        
        for result in test_results:
            test_id = getattr(result, 'stable_identity', None) or getattr(result, 'test_case_id', None)
            if test_id in related_test_identifiers:
                status = getattr(result, 'status', 'UNKNOWN').upper()
                if status == 'PASSED':
                    passed_count += 1
                elif status == 'FAILED':
                    failed_count += 1
                elif status == 'SKIPPED':
                    skipped_count += 1
        
        if failed_count > 0:
            return ExecutionStatus.FAILED
        elif passed_count > 0:
            return ExecutionStatus.PASSED
        elif skipped_count > 0:
            return ExecutionStatus.SKIPPED
        else:
            return ExecutionStatus.NOT_RUN
    
    @classmethod
    def determine_historical_execution_status(
        cls,
        scenario_intent_key: str,
        related_test_identifiers: List[str],
        historical_test_runs: List[Any]
    ) -> ExecutionStatus:
        """
        Determine historical execution status for the scenario intent.
        
        Args:
            scenario_intent_key: The canonical key of the scenario intent
            related_test_identifiers: Test identifiers related to this scenario
            historical_test_runs: List of historical TestRun records
        
        Returns:
            ExecutionStatus for historical execution
        """
        if not historical_test_runs or not related_test_identifiers:
            return ExecutionStatus.UNKNOWN
        
        # Aggregate results from historical runs
        total_passed = 0
        total_failed = 0
        total_runs = 0
        
        for run in historical_test_runs:
            if not hasattr(run, 'test_results'):
                continue
            
            test_results = run.test_results
            if not test_results:
                continue
            
            total_runs += 1
            
            for result in test_results:
                test_id = getattr(result, 'stable_identity', None) or getattr(result, 'test_case_id', None)
                if test_id in related_test_identifiers:
                    status = getattr(result, 'status', 'UNKNOWN').upper()
                    if status == 'PASSED':
                        total_passed += 1
                    elif status == 'FAILED':
                        total_failed += 1
        
        if total_runs == 0:
            return ExecutionStatus.UNKNOWN
        
        # Determine flakiness (mixed pass/fail in history)
        if total_passed > 0 and total_failed > 0:
            return ExecutionStatus.FLAKY
        elif total_failed > 0:
            return ExecutionStatus.FAILED
        elif total_passed > 0:
            return ExecutionStatus.PASSED
        else:
            return ExecutionStatus.UNKNOWN
    
    @classmethod
    def consolidate_final_status(
        cls,
        existing_test_status: ExistingTestStatus,
        code_coverage_status: CodeCoverageStatus,
        current_pr_execution_status: ExecutionStatus,
        historical_execution_status: ExecutionStatus
    ) -> FinalCoverageStatus:
        """
        Consolidate all evidence into a final coverage status.
        
        Evidence Semantics:
        - JUnit TestRun = execution evidence (historical)
        - CoverageReport = code coverage evidence (file-level)
        - TestCoverageLink = test-to-code relationship evidence
        - Current PR TestRun = verification evidence for this PR
        - ScenarioCoverageStatus = behavior coverage inference
        
        Rules:
        - COVERED_AND_VERIFIED: ONLY when existing test exists AND current PR execution is PASSED
        - COVERED_NOT_RUN: When existing test exists but no current PR execution (regardless of historical)
        - PARTIALLY_COVERED: When there's some evidence but not enough to be confident
        - MISSING_AUTOMATED_COVERAGE: When no existing test and weak/no coverage
        - SUGGEST_MANUAL_VALIDATION: When evidence is weak or ambiguous
        - File coverage alone can NEVER result in COVERED_AND_VERIFIED or COVERED_NOT_RUN
        - Coverage can increase confidence but cannot prove business scenario alone
        
        Args:
            existing_test_status: Status of existing test coverage
            code_coverage_status: Status of code coverage
            current_pr_execution_status: Current PR execution status
            historical_execution_status: Historical execution status
        
        Returns:
            FinalCoverageStatus
        """
        # Priority 1: Existing test with current PR execution
        if existing_test_status == ExistingTestStatus.AVAILABLE:
            if current_pr_execution_status == ExecutionStatus.PASSED:
                # Only mark as verified when test actually passed on current PR
                return FinalCoverageStatus.COVERED_AND_VERIFIED
            elif current_pr_execution_status == ExecutionStatus.FAILED:
                # Test exists but failed on current PR - still covered but not verified
                return FinalCoverageStatus.COVERED_NOT_RUN
            elif current_pr_execution_status == ExecutionStatus.SKIPPED:
                # Test exists but was skipped on current PR
                return FinalCoverageStatus.COVERED_NOT_RUN
            elif current_pr_execution_status == ExecutionStatus.NOT_RUN:
                # Test exists but not run on current PR - recommend running it
                return FinalCoverageStatus.COVERED_NOT_RUN
        
        # Priority 2: Existing test exists but no current PR execution
        if existing_test_status == ExistingTestStatus.AVAILABLE:
            # Test exists in repository but not run on this PR
            # Historical execution doesn't count as verification for this PR
            return FinalCoverageStatus.COVERED_NOT_RUN
        
        # Priority 3: No existing test, check code coverage
        # File coverage alone cannot prove business scenario coverage
        if existing_test_status == ExistingTestStatus.NOT_FOUND:
            if code_coverage_status == CodeCoverageStatus.DIRECT:
                # Direct file coverage suggests some coverage but no test exists
                # This is partial coverage at best - need actual test
                return FinalCoverageStatus.PARTIALLY_COVERED
            elif code_coverage_status == CodeCoverageStatus.INDIRECT:
                # Indirect coverage is weak evidence
                return FinalCoverageStatus.SUGGEST_MANUAL_VALIDATION
            else:
                # No code coverage evidence
                return FinalCoverageStatus.MISSING_AUTOMATED_COVERAGE
        
        # Priority 4: Weak evidence or unknown
        return FinalCoverageStatus.SUGGEST_MANUAL_VALIDATION
    
    @classmethod
    def resolve_coverage_status(
        cls,
        scenario_intent_key: str,
        related_changed_files: List[str],
        related_test_identifiers: List[str],
        existing_test_coverages: List[Any],
        coverage_file_entries: List[Any],
        test_coverage_links: List[Any],
        current_pr_test_run: Optional[Any] = None,
        historical_test_runs: Optional[List[Any]] = None,
        min_confidence: str = "MODERATE"
    ) -> ScenarioCoverageStatus:
        """
        Resolve coverage status for a single scenario intent.
        
        Args:
            scenario_intent_key: The canonical key of the scenario intent
            related_changed_files: Files related to this scenario
            related_test_identifiers: Test identifiers related to this scenario
            existing_test_coverages: List of ExistingTestScenarioCoverage objects
            coverage_file_entries: CoverageFileEntry records
            test_coverage_links: TestCoverageLink records
            current_pr_test_run: TestRun for current PR (optional)
            historical_test_runs: List of historical TestRun records (optional)
            min_confidence: Minimum confidence for existing test matching
        
        Returns:
            ScenarioCoverageStatus with all status information
        """
        # Determine individual status components
        existing_test_status = cls.determine_existing_test_status(
            scenario_intent_key=scenario_intent_key,
            existing_test_coverages=existing_test_coverages,
            min_confidence=min_confidence
        )
        
        code_coverage_status = cls.determine_code_coverage_status(
            scenario_intent_key=scenario_intent_key,
            related_changed_files=related_changed_files,
            coverage_file_entries=coverage_file_entries,
            test_coverage_links=test_coverage_links
        )
        
        current_pr_execution_status = cls.determine_current_pr_execution_status(
            scenario_intent_key=scenario_intent_key,
            related_test_identifiers=related_test_identifiers,
            current_pr_test_run=current_pr_test_run
        )
        
        historical_execution_status = cls.determine_historical_execution_status(
            scenario_intent_key=scenario_intent_key,
            related_test_identifiers=related_test_identifiers,
            historical_test_runs=historical_test_runs or []
        )
        
        # Consolidate final status
        final_status = cls.consolidate_final_status(
            existing_test_status=existing_test_status,
            code_coverage_status=code_coverage_status,
            current_pr_execution_status=current_pr_execution_status,
            historical_execution_status=historical_execution_status
        )
        
        # Determine confidence based on evidence strength
        confidence = cls._calculate_confidence(
            existing_test_status=existing_test_status,
            code_coverage_status=code_coverage_status,
            current_pr_execution_status=current_pr_execution_status
        )
        
        return ScenarioCoverageStatus(
            scenario_intent_key=scenario_intent_key,
            existing_test_status=existing_test_status,
            code_coverage_status=code_coverage_status,
            current_pr_execution_status=current_pr_execution_status,
            historical_execution_status=historical_execution_status,
            final_status=final_status,
            related_test_identifiers=related_test_identifiers,
            related_file_paths=related_changed_files,
            confidence=confidence
        )
    
    @classmethod
    def _calculate_confidence(
        cls,
        existing_test_status: ExistingTestStatus,
        code_coverage_status: CodeCoverageStatus,
        current_pr_execution_status: ExecutionStatus
    ) -> str:
        """
        Calculate overall confidence in the coverage status.
        
        Args:
            existing_test_status: Status of existing test coverage
            code_coverage_status: Status of code coverage
            current_pr_execution_status: Current PR execution status
        
        Returns:
            Confidence level: HIGH, MEDIUM, or LOW
        """
        # HIGH confidence: existing test with current PR execution
        if existing_test_status == ExistingTestStatus.AVAILABLE:
            if current_pr_execution_status in (ExecutionStatus.PASSED, ExecutionStatus.FAILED, ExecutionStatus.SKIPPED):
                return "HIGH"
            elif code_coverage_status == CodeCoverageStatus.DIRECT:
                return "HIGH"
        
        # MEDIUM confidence: existing test or direct coverage
        if existing_test_status == ExistingTestStatus.AVAILABLE:
            return "MEDIUM"
        if code_coverage_status == CodeCoverageStatus.DIRECT:
            return "MEDIUM"
        
        # LOW confidence: indirect or no coverage
        return "LOW"
    
    @classmethod
    def resolve_batch_coverage_status(
        cls,
        scenario_intents: List[Any],
        existing_test_coverages: List[Any],
        coverage_file_entries: List[Any],
        test_coverage_links: List[Any],
        current_pr_test_run: Optional[Any] = None,
        historical_test_runs: Optional[List[Any]] = None,
        min_confidence: str = "MODERATE"
    ) -> List[ScenarioCoverageStatus]:
        """
        Resolve coverage status for multiple scenario intents.
        
        Args:
            scenario_intents: List of ScenarioIntent objects
            existing_test_coverages: List of ExistingTestScenarioCoverage objects
            coverage_file_entries: CoverageFileEntry records
            test_coverage_links: TestCoverageLink records
            current_pr_test_run: TestRun for current PR (optional)
            historical_test_runs: List of historical TestRun records (optional)
            min_confidence: Minimum confidence for existing test matching
        
        Returns:
            List of ScenarioCoverageStatus objects
        """
        statuses = []
        
        for intent in scenario_intents:
            # Extract related information from intent
            related_changed_files = getattr(intent, 'related_changed_files', [])
            canonical_key = getattr(intent, 'canonical_key', '')
            
            # Find related test identifiers from existing test coverages
            related_test_identifiers = []
            for coverage in existing_test_coverages:
                if coverage.scenario_intent_key == canonical_key:
                    related_test_identifiers.append(coverage.test_identifier)
            
            status = cls.resolve_coverage_status(
                scenario_intent_key=canonical_key,
                related_changed_files=related_changed_files,
                related_test_identifiers=related_test_identifiers,
                existing_test_coverages=existing_test_coverages,
                coverage_file_entries=coverage_file_entries,
                test_coverage_links=test_coverage_links,
                current_pr_test_run=current_pr_test_run,
                historical_test_runs=historical_test_runs,
                min_confidence=min_confidence
            )
            statuses.append(status)
        
        return statuses
