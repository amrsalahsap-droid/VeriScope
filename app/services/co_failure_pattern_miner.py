"""
CoFailurePatternMiner Service

Detects tests/modules/behaviors that fail together for meaningful reasons.
Creates FragilityMemory and FragilityEvidenceEvent records for:
- CO_FAILURE_PATTERN (test clusters)
- BEHAVIOR_FRAGILITY (behavior clusters)
- RISKY_CHANGE_COMBINATION (module combinations)
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Tuple
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.repository import Repository
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.test_result import TestRun, TestResult, TestCase
from app.models.dependency import FileDependency
from app.models.behavior import Behavior
from app.models.journey import Journey
from app.models.behavior_scenario import BehaviorScenario
from app.models.fragility_memory_v2 import FragilityMemoryV2
from app.models.fragility_evidence_event import FragilityEvidenceEvent

logger = logging.getLogger(__name__)


class CoFailurePatternMiner:
    """Detects co-failure patterns with shared context validation."""
    
    DEFAULT_TIME_WINDOW_DAYS = 90
    MIN_CO_FAILURE_COUNT = 3
    MIN_DISTINCT_PRS = 2
    MIN_SHARED_CONTEXT_COUNT = 2
    
    def __init__(self, db: Session):
        self.db = db
    
    def mine_co_failure_patterns(
        self,
        repository_id: uuid.UUID,
        time_window_days: int = DEFAULT_TIME_WINDOW_DAYS,
    ) -> Dict[str, int]:
        """
        Mine co-failure patterns and create fragility memory records.
        
        Args:
            repository_id: Repository to mine
            time_window_days: Time window for historical data (default 90 days)
            
        Returns:
            Dict with mining results:
            - co_failure_patterns_detected: count of CO_FAILURE_PATTERN patterns
            - behavior_cluster_patterns_detected: count of behavior cluster patterns
            - module_combination_patterns_detected: count of module combination patterns
            - evidence_events_created: count of evidence events created
        """
        logger.info(f"Mining co-failure patterns for repository {repository_id} with {time_window_days} day window")
        
        # Calculate time window
        now = datetime.utcnow()
        window_start = now - timedelta(days=time_window_days)
        
        # Validate repository
        repo = self.db.query(Repository).filter(Repository.id == repository_id).first()
        if not repo:
            raise ValueError(f"Repository {repository_id} not found")
        
        results = {
            "co_failure_patterns_detected": 0,
            "behavior_cluster_patterns_detected": 0,
            "module_combination_patterns_detected": 0,
            "evidence_events_created": 0,
        }
        
        # 1. Detect test cluster co-failures
        test_clusters = self._detect_test_cluster_co_failures(repository_id, window_start, now)
        results["co_failure_patterns_detected"] = len(test_clusters)
        
        # 2. Detect behavior cluster co-failures
        behavior_clusters = self._detect_behavior_cluster_co_failures(repository_id, window_start, now)
        results["behavior_cluster_patterns_detected"] = len(behavior_clusters)
        
        # 3. Detect module combination co-failures
        module_combinations = self._detect_module_combination_co_failures(repository_id, window_start, now)
        results["module_combination_patterns_detected"] = len(module_combinations)
        
        # 4. Create fragility memory records
        for cluster_data in test_clusters:
            memory_id, evidence_count = self._create_co_failure_memory(
                repository_id, cluster_data, window_start, now
            )
            results["evidence_events_created"] += evidence_count
        
        for behavior_cluster in behavior_clusters:
            memory_id, evidence_count = self._create_behavior_cluster_memory(
                repository_id, behavior_cluster, window_start, now
            )
            results["evidence_events_created"] += evidence_count
        
        for module_combination in module_combinations:
            memory_id, evidence_count = self._create_module_combination_memory(
                repository_id, module_combination, window_start, now
            )
            results["evidence_events_created"] += evidence_count
        
        self.db.commit()
        
        logger.info(
            f"Co-failure pattern mining complete: "
            f"test_clusters={results['co_failure_patterns_detected']}, "
            f"behavior_clusters={results['behavior_cluster_patterns_detected']}, "
            f"module_combinations={results['module_combination_patterns_detected']}, "
            f"evidence_events={results['evidence_events_created']}"
        )
        
        return results
    
    def _detect_test_cluster_co_failures(
        self,
        repository_id: uuid.UUID,
        window_start: datetime,
        window_end: datetime,
    ) -> List[Dict]:
        """
        Detect test clusters failing together with shared context.
        """
        # Query failed test runs within window
        failed_runs = self.db.query(TestRun).filter(
            TestRun.repository_id == repository_id,
            TestRun.created_at >= window_start,
            TestRun.created_at <= window_end,
            TestRun.status == "failed",
            TestRun.parser_support_status != "UNSUPPORTED",
        ).all()
        
        # Build test pair -> context mapping
        test_pair_contexts = defaultdict(list)
        
        for run in failed_runs:
            # Get failed test results for this run
            failed_results = self.db.query(TestResult, TestCase).join(
                TestCase, TestResult.test_case_id == TestCase.id
            ).filter(
                TestResult.test_run_id == run.id,
                TestResult.status == "failed",
            ).all()
            
            if len(failed_results) < 2:
                continue  # Need at least 2 failures to form a cluster
            
            # Get PR for this run
            pr = self.db.query(PullRequest).filter(
                PullRequest.id == run.pull_request_id
            ).first() if run.pull_request_id else None
            
            # Get changed files
            changed_files = []
            if pr:
                changed_files_objs = self.db.query(PullRequestChangedFile).filter(
                    PullRequestChangedFile.pull_request_id == pr.id
                ).all()
                changed_files = [cf.file_path for cf in changed_files_objs]
            
            # Get test identities
            test_identities = [test_case.stable_identity for result, test_case in failed_results]
            
            # Count all pairs with context
            for i in range(len(test_identities)):
                for j in range(i + 1, len(test_identities)):
                    pair = tuple(sorted([test_identities[i], test_identities[j]]))
                    
                    # Validate shared context
                    shared_context = self._validate_shared_context(
                        test_identities[i], test_identities[j], changed_files, run.id
                    )
                    
                    if shared_context:
                        test_pair_contexts[pair].append({
                            "run_id": run.id,
                            "pr_id": pr.id if pr else None,
                            "changed_files": changed_files,
                            "shared_context": shared_context,
                            "occurred_at": run.created_at,
                        })
        
        # Filter for significant co-failure patterns
        co_failures = []
        for pair, contexts in test_pair_contexts.items():
            if len(contexts) < self.MIN_CO_FAILURE_COUNT:
                continue
            
            # Check for distinct PRs
            pr_ids = {c["pr_id"] for c in contexts if c["pr_id"]}
            if len(pr_ids) < self.MIN_DISTINCT_PRS:
                continue
            
            # Calculate score
            score = self._calculate_co_failure_score(len(contexts), len(pr_ids), window_end)
            
            # Get most recent context
            most_recent = max(contexts, key=lambda x: x["occurred_at"])
            
            co_failures.append({
                "test_pair": pair,
                "co_failure_count": len(contexts),
                "distinct_pr_count": len(pr_ids),
                "shared_context_type": most_recent["shared_context"]["type"],
                "shared_context_details": most_recent["shared_context"],
                "most_recent_at": most_recent["occurred_at"],
                "first_seen_at": min(c["occurred_at"] for c in contexts),
                "score": score,
                "contexts": contexts,
            })
        
        return co_failures
    
    def _detect_behavior_cluster_co_failures(
        self,
        repository_id: uuid.UUID,
        window_start: datetime,
        window_end: datetime,
    ) -> List[Dict]:
        """
        Detect behavior clusters failing together with shared context.
        """
        # Query failed test runs within window
        failed_runs = self.db.query(TestRun).filter(
            TestRun.repository_id == repository_id,
            TestRun.created_at >= window_start,
            TestRun.created_at <= window_end,
            TestRun.status == "failed",
            TestRun.parser_support_status != "UNSUPPORTED",
        ).all()
        
        # Build behavior pair -> context mapping
        behavior_pair_contexts = defaultdict(list)
        
        for run in failed_runs:
            # Get failed test results for this run
            failed_results = self.db.query(TestResult, TestCase).join(
                TestCase, TestResult.test_case_id == TestCase.id
            ).filter(
                TestResult.test_run_id == run.id,
                TestResult.status == "failed",
            ).all()
            
            # Map tests to behaviors
            test_identities = [test_case.stable_identity for result, test_case in failed_results]
            behavior_ids = []
            
            for test_identity in test_identities:
                behavior_scenarios = self.db.query(BehaviorScenario).filter(
                    BehaviorScenario.test_identifier == test_identity
                ).all()
                for bs in behavior_scenarios:
                    if bs.behavior_id not in behavior_ids:
                        behavior_ids.append(bs.behavior_id)
            
            if len(behavior_ids) < 2:
                continue  # Need at least 2 behaviors to form a cluster
            
            # Get PR for this run
            pr = self.db.query(PullRequest).filter(
                PullRequest.id == run.pull_request_id
            ).first() if run.pull_request_id else None
            
            # Get changed files
            changed_files = []
            if pr:
                changed_files_objs = self.db.query(PullRequestChangedFile).filter(
                    PullRequestChangedFile.pull_request_id == pr.id
                ).all()
                changed_files = [cf.file_path for cf in changed_files_objs]
            
            # Count all behavior pairs with context
            for i in range(len(behavior_ids)):
                for j in range(i + 1, len(behavior_ids)):
                    pair = tuple(sorted([str(behavior_ids[i]), str(behavior_ids[j])]))
                    
                    # Validate shared context
                    shared_context = self._validate_behavior_shared_context(
                        behavior_ids[i], behavior_ids[j], changed_files, run.id
                    )
                    
                    if shared_context:
                        behavior_pair_contexts[pair].append({
                            "run_id": run.id,
                            "pr_id": pr.id if pr else None,
                            "changed_files": changed_files,
                            "shared_context": shared_context,
                            "occurred_at": run.created_at,
                        })
        
        # Filter for significant behavior co-failure patterns
        behavior_clusters = []
        for pair, contexts in behavior_pair_contexts.items():
            if len(contexts) < self.MIN_CO_FAILURE_COUNT:
                continue
            
            pr_ids = {c["pr_id"] for c in contexts if c["pr_id"]}
            if len(pr_ids) < self.MIN_DISTINCT_PRS:
                continue
            
            score = self._calculate_co_failure_score(len(contexts), len(pr_ids), window_end)
            
            most_recent = max(contexts, key=lambda x: x["occurred_at"])
            
            behavior_clusters.append({
                "behavior_pair": pair,
                "co_failure_count": len(contexts),
                "distinct_pr_count": len(pr_ids),
                "shared_context_type": most_recent["shared_context"]["type"],
                "shared_context_details": most_recent["shared_context"],
                "most_recent_at": most_recent["occurred_at"],
                "first_seen_at": min(c["occurred_at"] for c in contexts),
                "score": score,
                "contexts": contexts,
            })
        
        return behavior_clusters
    
    def _detect_module_combination_co_failures(
        self,
        repository_id: uuid.UUID,
        window_start: datetime,
        window_end: datetime,
    ) -> List[Dict]:
        """
        Detect module combinations that precede failures.
        """
        # Query failed test runs within window
        failed_runs = self.db.query(TestRun).filter(
            TestRun.repository_id == repository_id,
            TestRun.created_at >= window_start,
            TestRun.created_at <= window_end,
            TestRun.status == "failed",
            TestRun.parser_support_status != "UNSUPPORTED",
        ).all()
        
        # Build module combination -> context mapping
        module_combination_contexts = defaultdict(list)
        
        for run in failed_runs:
            # Get PR for this run
            pr = self.db.query(PullRequest).filter(
                PullRequest.id == run.pull_request_id
            ).first() if run.pull_request_id else None
            
            if not pr:
                continue
            
            # Get changed files
            changed_files_objs = self.db.query(PullRequestChangedFile).filter(
                PullRequestChangedFile.pull_request_id == pr.id
            ).all()
            
            if len(changed_files_objs) < 2:
                continue  # Need at least 2 changed files
            
            # Extract modules from file paths
            modules = self._extract_modules_from_files([cf.file_path for cf in changed_files_objs])
            
            if len(modules) < 2:
                continue
            
            # Count all module pairs
            for i in range(len(modules)):
                for j in range(i + 1, len(modules)):
                    pair = tuple(sorted([modules[i], modules[j]]))
                    
                    module_combination_contexts[pair].append({
                        "run_id": run.id,
                        "pr_id": pr.id,
                        "changed_files": [cf.file_path for cf in changed_files_objs],
                        "occurred_at": run.created_at,
                    })
        
        # Filter for significant module combinations
        module_combinations = []
        for combination, contexts in module_combination_contexts.items():
            if len(contexts) < self.MIN_CO_FAILURE_COUNT:
                continue
            
            pr_ids = {c["pr_id"] for c in contexts if c["pr_id"]}
            if len(pr_ids) < self.MIN_DISTINCT_PRS:
                continue
            
            score = self._calculate_co_failure_score(len(contexts), len(pr_ids), window_end)
            
            most_recent = max(contexts, key=lambda x: x["occurred_at"])
            
            module_combinations.append({
                "module_pair": combination,
                "combination_count": len(contexts),
                "distinct_pr_count": len(pr_ids),
                "most_recent_at": most_recent["occurred_at"],
                "first_seen_at": min(c["occurred_at"] for c in contexts),
                "score": score,
                "contexts": contexts,
            })
        
        return module_combinations
    
    def _validate_shared_context(
        self,
        test1: str,
        test2: str,
        changed_files: List[str],
        run_id: uuid.UUID,
    ) -> Optional[Dict]:
        """
        Validate shared context between two tests.
        
        Returns:
            Dict with shared context type and details, or None if no shared context
        """
        # Check for shared changed files (via test coverage)
        # This would require test coverage data
        # For now, check if tests are in same suite
        test1_suite = test1.split("::")[0] if "::" in test1 else test1
        test2_suite = test2.split("::")[0] if "::" in test2 else test2
        
        if test1_suite == test2_suite:
            return {
                "type": "SAME_SUITE",
                "details": f"Tests in same suite: {test1_suite}",
            }
        
        # Check for shared changed files
        if changed_files:
            return {
                "type": "SHARED_CHANGED_FILES",
                "details": f"Shared changed files: {len(changed_files)}",
                "files": changed_files,
            }
        
        # Check for shared behavior via BehaviorScenario
        behavior_scenarios1 = self.db.query(BehaviorScenario).filter(
            BehaviorScenario.test_identifier == test1
        ).all()
        behavior_scenarios2 = self.db.query(BehaviorScenario).filter(
            BehaviorScenario.test_identifier == test2
        ).all()
        
        behavior_ids1 = {bs.behavior_id for bs in behavior_scenarios1}
        behavior_ids2 = {bs.behavior_id for bs in behavior_scenarios2}
        
        shared_behaviors = behavior_ids1 & behavior_ids2
        if shared_behaviors:
            return {
                "type": "SHARED_BEHAVIOR",
                "details": f"Shared behaviors: {len(shared_behaviors)}",
                "behavior_ids": list(shared_behaviors),
            }
        
        # Check for shared dependency
        # This would require dependency data
        # For now, return None
        return None
    
    def _validate_behavior_shared_context(
        self,
        behavior1_id: uuid.UUID,
        behavior2_id: uuid.UUID,
        changed_files: List[str],
        run_id: uuid.UUID,
    ) -> Optional[Dict]:
        """
        Validate shared context between two behaviors.
        """
        # Check for shared journey
        behavior1 = self.db.query(Behavior).filter(Behavior.id == behavior1_id).first()
        behavior2 = self.db.query(Behavior).filter(Behavior.id == behavior2_id).first()
        
        if not behavior1 or not behavior2:
            return None
        
        if behavior1.journey_id and behavior1.journey_id == behavior2.journey_id:
            return {
                "type": "SHARED_JOURNEY",
                "details": f"Shared journey: {behavior1.journey_id}",
            }
        
        # Check for shared changed files
        if changed_files:
            return {
                "type": "SHARED_CHANGED_FILES",
                "details": f"Shared changed files: {len(changed_files)}",
                "files": changed_files,
            }
        
        return None
    
    def _extract_modules_from_files(self, file_paths: List[str]) -> List[str]:
        """
        Extract module names from file paths.
        
        Simple heuristic: take the first 2-3 path components as module
        """
        modules = []
        for file_path in file_paths:
            parts = file_path.replace("\\", "/").split("/")
            if len(parts) >= 2:
                module = "/".join(parts[:2])
                if module not in modules:
                    modules.append(module)
        return modules
    
    def _calculate_co_failure_score(
        self,
        co_failure_count: int,
        distinct_pr_count: int,
        window_end: datetime,
    ) -> float:
        """
        Calculate fragility score for co-failure pattern.
        """
        # Frequency score
        frequency_score = min(100.0, (co_failure_count / 5.0) * 100.0)
        
        # PR diversity score
        diversity_score = min(100.0, (distinct_pr_count / 3.0) * 100.0)
        
        # Weighted score
        score = (frequency_score * 0.6) + (diversity_score * 0.4)
        
        return round(score, 2)
    
    def _create_co_failure_memory(
        self,
        repository_id: uuid.UUID,
        cluster_data: Dict,
        window_start: datetime,
        window_end: datetime,
    ) -> Tuple[uuid.UUID, int]:
        """
        Create FragilityMemory record for test cluster co-failure.
        """
        # Generate deterministic memory key
        pair_key = ":".join(cluster_data["test_pair"])
        memory_key = f"CO_FAILURE_PATTERN:{pair_key}"
        
        # Determine risk level
        risk_level = self._determine_risk_level(cluster_data["score"])
        
        # Calculate confidence
        confidence = min(1.0, cluster_data["co_failure_count"] / 5.0)
        
        # Check for existing memory
        existing = self.db.query(FragilityMemoryV2).filter(
            FragilityMemoryV2.repository_id == repository_id,
            FragilityMemoryV2.memory_key == memory_key,
            FragilityMemoryV2.subject_type == "TEST",
        ).first()
        
        if existing:
            # Update existing memory
            existing.fragility_score = cluster_data["score"]
            existing.risk_level = risk_level
            existing.confidence = confidence
            existing.last_seen_at = window_end
            existing.status = "ACTIVE"
            memory_id = existing.id
        else:
            # Create new memory
            memory = FragilityMemoryV2(
                repository_id=repository_id,
                memory_key=memory_key,
                memory_type="CO_FAILURE_PATTERN",
                subject_type="TEST",
                subject_id=None,
                subject_name=pair_key,
                risk_level=risk_level,
                fragility_score=cluster_data["score"],
                confidence=confidence,
                status="ACTIVE",
                first_seen_at=cluster_data["first_seen_at"],
                last_seen_at=window_end,
            )
            self.db.add(memory)
            self.db.flush()
            memory_id = memory.id
        
        # Create evidence events for each context
        evidence_count = 0
        for context in cluster_data["contexts"]:
            self._create_evidence_event(
                memory_id=memory_id,
                repository_id=repository_id,
                evidence_type="CO_FAILURE",
                source_entity_type="TEST_RUN",
                source_entity_id=context["run_id"],
                pull_request_id=context["pr_id"],
                test_run_id=context["run_id"],
                changed_files=context["changed_files"],
                evidence_summary=f"Co-failure pattern: {pair_key} failed together with shared context {context['shared_context']['type']}",
                evidence_weight=1.0 / len(cluster_data["contexts"]),
                occurred_at=context["occurred_at"],
            )
            evidence_count += 1
        
        return memory_id, evidence_count
    
    def _create_behavior_cluster_memory(
        self,
        repository_id: uuid.UUID,
        cluster_data: Dict,
        window_start: datetime,
        window_end: datetime,
    ) -> Tuple[uuid.UUID, int]:
        """
        Create FragilityMemory record for behavior cluster co-failure.
        """
        # Generate deterministic memory key
        pair_key = ":".join(cluster_data["behavior_pair"])
        memory_key = f"BEHAVIOR_FRAGILITY:{pair_key}"
        
        # Determine risk level
        risk_level = self._determine_risk_level(cluster_data["score"])
        
        # Calculate confidence
        confidence = min(1.0, cluster_data["co_failure_count"] / 5.0)
        
        # Check for existing memory
        existing = self.db.query(FragilityMemoryV2).filter(
            FragilityMemoryV2.repository_id == repository_id,
            FragilityMemoryV2.memory_key == memory_key,
            FragilityMemoryV2.subject_type == "BEHAVIOR",
        ).first()
        
        if existing:
            # Update existing memory
            existing.fragility_score = cluster_data["score"]
            existing.risk_level = risk_level
            existing.confidence = confidence
            existing.last_seen_at = window_end
            existing.status = "ACTIVE"
            memory_id = existing.id
        else:
            # Create new memory
            memory = FragilityMemoryV2(
                repository_id=repository_id,
                memory_key=memory_key,
                memory_type="BEHAVIOR_FRAGILITY",
                subject_type="BEHAVIOR",
                subject_id=None,
                subject_name=pair_key,
                risk_level=risk_level,
                fragility_score=cluster_data["score"],
                confidence=confidence,
                status="ACTIVE",
                first_seen_at=cluster_data["first_seen_at"],
                last_seen_at=window_end,
            )
            self.db.add(memory)
            self.db.flush()
            memory_id = memory.id
        
        # Create evidence events for each context
        evidence_count = 0
        for context in cluster_data["contexts"]:
            self._create_evidence_event(
                memory_id=memory_id,
                repository_id=repository_id,
                evidence_type="CO_FAILURE",
                source_entity_type="TEST_RUN",
                source_entity_id=context["run_id"],
                pull_request_id=context["pr_id"],
                test_run_id=context["run_id"],
                changed_files=context["changed_files"],
                affected_behaviors=list(cluster_data["behavior_pair"]),
                evidence_summary=f"Behavior cluster co-failure: {pair_key} failed together with shared context {context['shared_context']['type']}",
                evidence_weight=1.0 / len(cluster_data["contexts"]),
                occurred_at=context["occurred_at"],
            )
            evidence_count += 1
        
        return memory_id, evidence_count
    
    def _create_module_combination_memory(
        self,
        repository_id: uuid.UUID,
        combination_data: Dict,
        window_start: datetime,
        window_end: datetime,
    ) -> Tuple[uuid.UUID, int]:
        """
        Create FragilityMemory record for module combination co-failure.
        """
        # Generate deterministic memory key
        combination_key = ":".join(combination_data["module_pair"])
        memory_key = f"RISKY_CHANGE_COMBINATION:{combination_key}"
        
        # Determine risk level
        risk_level = self._determine_risk_level(combination_data["score"])
        
        # Calculate confidence
        confidence = min(1.0, combination_data["combination_count"] / 5.0)
        
        # Check for existing memory
        existing = self.db.query(FragilityMemoryV2).filter(
            FragilityMemoryV2.repository_id == repository_id,
            FragilityMemoryV2.memory_key == memory_key,
            FragilityMemoryV2.subject_type == "MODULE",
        ).first()
        
        if existing:
            # Update existing memory
            existing.fragility_score = combination_data["score"]
            existing.risk_level = risk_level
            existing.confidence = confidence
            existing.last_seen_at = window_end
            existing.status = "ACTIVE"
            memory_id = existing.id
        else:
            # Create new memory
            memory = FragilityMemoryV2(
                repository_id=repository_id,
                memory_key=memory_key,
                memory_type="RISKY_CHANGE_COMBINATION",
                subject_type="MODULE",
                subject_id=None,
                subject_name=combination_key,
                risk_level=risk_level,
                fragility_score=combination_data["score"],
                confidence=confidence,
                status="ACTIVE",
                first_seen_at=combination_data["first_seen_at"],
                last_seen_at=window_end,
            )
            self.db.add(memory)
            self.db.flush()
            memory_id = memory.id
        
        # Create evidence events for each context
        evidence_count = 0
        for context in combination_data["contexts"]:
            self._create_evidence_event(
                memory_id=memory_id,
                repository_id=repository_id,
                evidence_type="CO_FAILURE",
                source_entity_type="TEST_RUN",
                source_entity_id=context["run_id"],
                pull_request_id=context["pr_id"],
                test_run_id=context["run_id"],
                changed_files=context["changed_files"],
                evidence_summary=f"Module combination co-failure: {combination_key} preceded failures in {len(context['changed_files'])} changed files",
                evidence_weight=1.0 / len(combination_data["contexts"]),
                occurred_at=context["occurred_at"],
            )
            evidence_count += 1
        
        return memory_id, evidence_count
    
    def _create_evidence_event(
        self,
        memory_id: uuid.UUID,
        repository_id: uuid.UUID,
        evidence_type: str,
        source_entity_type: str,
        source_entity_id: Optional[uuid.UUID],
        pull_request_id: Optional[uuid.UUID] = None,
        recommendation_run_id: Optional[uuid.UUID] = None,
        test_run_id: Optional[uuid.UUID] = None,
        test_result_id: Optional[uuid.UUID] = None,
        incident_url: Optional[str] = None,
        rollback_url: Optional[str] = None,
        changed_files: Optional[List[str]] = None,
        affected_behaviors: Optional[List[str]] = None,
        affected_journeys: Optional[List[str]] = None,
        evidence_summary: str = "",
        evidence_weight: float = 1.0,
        occurred_at: Optional[datetime] = None,
    ):
        """Create FragilityEvidenceEvent record."""
        event = FragilityEvidenceEvent(
            fragility_memory_id=memory_id,
            repository_id=repository_id,
            evidence_type=evidence_type,
            source_entity_type=source_entity_type,
            source_entity_id=source_entity_id,
            pull_request_id=pull_request_id,
            recommendation_run_id=recommendation_run_id,
            test_run_id=test_run_id,
            test_result_id=test_result_id,
            incident_url=incident_url,
            rollback_url=rollback_url,
            changed_files=changed_files or [],
            affected_behaviors=affected_behaviors or [],
            affected_journeys=affected_journeys or [],
            evidence_summary=evidence_summary,
            evidence_weight=evidence_weight,
            occurred_at=occurred_at or datetime.utcnow(),
        )
        self.db.add(event)
    
    def _determine_risk_level(self, score: float) -> str:
        """Determine risk level from fragility score."""
        if score >= 75.0:
            return "CRITICAL"
        elif score >= 50.0:
            return "HIGH"
        elif score >= 25.0:
            return "MODERATE"
        else:
            return "LOW"
