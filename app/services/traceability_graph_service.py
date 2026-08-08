import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.models.traceability_edge import TraceabilityEdge
from app.models.test_result import TestCase, TestResult, TestRun
from app.models.pull_request import PullRequestChangedFile, PullRequest

class TraceabilityGraphService:
    @staticmethod
    def _to_uuid(val: Any) -> Optional[uuid.UUID]:
        if not val:
            return None
        if isinstance(val, uuid.UUID):
            return val
        try:
            return uuid.UUID(str(val))
        except ValueError:
            return None

    @classmethod
    def upsert_edge(
        cls,
        db: Session,
        repository_id: Any,
        pull_request_id: Any,
        source_node_type: str,
        source_node_id: str,
        target_node_type: str,
        target_node_id: str,
        edge_type: str,
        edge_source: str,
        confidence: Optional[float] = None,
        review_status: str = "system_suggested",
        is_active: bool = True,
        evidence_json: Optional[Dict[str, Any]] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
        created_by: Optional[str] = None,
    ) -> TraceabilityEdge:
        repo_uuid = cls._to_uuid(repository_id)
        pr_uuid = cls._to_uuid(pull_request_id)
        
        # Check if an edge already exists matching the uniqueness constraints
        existing_edge = db.query(TraceabilityEdge).filter(
            TraceabilityEdge.repository_id == repo_uuid,
            TraceabilityEdge.pull_request_id == pr_uuid,
            TraceabilityEdge.source_node_type == source_node_type,
            TraceabilityEdge.source_node_id == str(source_node_id),
            TraceabilityEdge.target_node_type == target_node_type,
            TraceabilityEdge.target_node_id == str(target_node_id),
            TraceabilityEdge.edge_type == edge_type,
            TraceabilityEdge.edge_source == edge_source
        ).first()

        if existing_edge:
            # Do not overwrite explicit user review decisions during re-import.
            if existing_edge.review_status in ("user_confirmed", "rejected"):
                return existing_edge
            
            existing_edge.pull_request_id = pr_uuid
            existing_edge.confidence = confidence
            existing_edge.evidence_json = evidence_json
            existing_edge.metadata_json = metadata_json
            existing_edge.review_status = review_status
            existing_edge.is_active = is_active
            existing_edge.updated_at = datetime.utcnow()
            if created_by:
                existing_edge.created_by = created_by
            db.flush()
            return existing_edge
        
        # Create a new edge
        new_edge = TraceabilityEdge(
            id=uuid.uuid4(),
            repository_id=repo_uuid,
            pull_request_id=pr_uuid,
            source_node_type=source_node_type,
            source_node_id=str(source_node_id),
            target_node_type=target_node_type,
            target_node_id=str(target_node_id),
            edge_type=edge_type,
            edge_source=edge_source,
            confidence=confidence,
            evidence_json=evidence_json,
            metadata_json=metadata_json,
            review_status=review_status,
            is_active=is_active,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            created_by=created_by
        )
        db.add(new_edge)
        db.flush()
        return new_edge

    @classmethod
    def find_edges(
        cls,
        db: Session,
        repository_id: Any,
        pull_request_id: Optional[Any] = None,
        source_node_type: Optional[str] = None,
        source_node_id: Optional[str] = None,
        target_node_type: Optional[str] = None,
        target_node_id: Optional[str] = None,
        edge_type: Optional[str] = None,
        is_active: Optional[bool] = True
    ) -> List[TraceabilityEdge]:
        repo_uuid = cls._to_uuid(repository_id)
        query = db.query(TraceabilityEdge).filter(TraceabilityEdge.repository_id == repo_uuid)
        
        if pull_request_id:
            pr_uuid = cls._to_uuid(pull_request_id)
            query = query.filter(TraceabilityEdge.pull_request_id == pr_uuid)
        if source_node_type:
            query = query.filter(TraceabilityEdge.source_node_type == source_node_type)
        if source_node_id:
            query = query.filter(TraceabilityEdge.source_node_id == str(source_node_id))
        if target_node_type:
            query = query.filter(TraceabilityEdge.target_node_type == target_node_type)
        if target_node_id:
            query = query.filter(TraceabilityEdge.target_node_id == str(target_node_id))
        if edge_type:
            query = query.filter(TraceabilityEdge.edge_type == edge_type)
        if is_active is not None:
            query = query.filter(TraceabilityEdge.is_active == is_active)
            
        return query.all()

    @classmethod
    def get_ac_to_test_mappings(cls, db: Session, repository_id: Any, pull_request_id: Optional[Any] = None) -> List[TraceabilityEdge]:
        repo_uuid = cls._to_uuid(repository_id)
        query = db.query(TraceabilityEdge).filter(
            TraceabilityEdge.repository_id == repo_uuid,
            TraceabilityEdge.source_node_type == "AcceptanceCriterion",
            TraceabilityEdge.target_node_type == "TestCase",
            TraceabilityEdge.is_active == True
        )
        if pull_request_id:
            pr_uuid = cls._to_uuid(pull_request_id)
            query = query.filter(TraceabilityEdge.pull_request_id == pr_uuid)
        return query.all()

    @classmethod
    def get_behavior_to_test_mappings(cls, db: Session, repository_id: Any, pull_request_id: Optional[Any] = None) -> List[TraceabilityEdge]:
        repo_uuid = cls._to_uuid(repository_id)
        query = db.query(TraceabilityEdge).filter(
            TraceabilityEdge.repository_id == repo_uuid,
            TraceabilityEdge.source_node_type == "ProductBehavior",
            TraceabilityEdge.target_node_type == "TestCase",
            TraceabilityEdge.is_active == True
        )
        if pull_request_id:
            pr_uuid = cls._to_uuid(pull_request_id)
            query = query.filter(TraceabilityEdge.pull_request_id == pr_uuid)
        return query.all()

    @classmethod
    def get_evidence_path_for_recommendation(
        cls,
        db: Session,
        repository_id: Any,
        pull_request_id: Any,
        test_id: str
    ) -> List[Dict[str, Any]]:
        repo_uuid = cls._to_uuid(repository_id)
        pr_uuid = cls._to_uuid(pull_request_id)
        
        # Convert test_id to string representation for comparison
        test_id_str = str(test_id)
        
        # Load PR changed files
        changed_files = db.query(PullRequestChangedFile).filter(
            PullRequestChangedFile.pull_request_id == pr_uuid
        ).all()
        changed_paths = [cf.file_path for cf in changed_files]
        
        if not changed_paths:
            return []
            
        # Get all active traceability edges for this PR/repo
        edges = db.query(TraceabilityEdge).filter(
            TraceabilityEdge.repository_id == repo_uuid,
            TraceabilityEdge.is_active == True
        ).all()
        
        # Search for path: ChangedFile -> ProductBehavior -> (Optional AC) -> TestCase
        # Let's organize edges by source_node_id and target_node_id
        edges_from_source = {}
        for edge in edges:
            edges_from_source.setdefault(edge.source_node_id, []).append(edge)
            
        # Find paths starting at changed files and ending at test_id_str
        best_path = []
        best_confidence = -1.0
        
        for file_path in changed_paths:
            # Traversal Stage 1: ChangedFile -> ProductBehavior
            file_edges = [
                e for e in edges_from_source.get(file_path, [])
                if e.source_node_type == "ChangedFile" and e.target_node_type == "ProductBehavior"
            ]
            
            for file_to_beh in file_edges:
                beh_id = file_to_beh.target_node_id
                
                # Traversal Option A: ProductBehavior -> TestCase (direct behavior coverage)
                beh_to_test_edges = [
                    e for e in edges_from_source.get(beh_id, [])
                    if e.source_node_type == "ProductBehavior" and e.target_node_type == "TestCase" and e.target_node_id == test_id_str
                ]
                for beh_to_test in beh_to_test_edges:
                    path_conf = (file_to_beh.confidence or 1.0) * (beh_to_test.confidence or 1.0)
                    if path_conf > best_confidence:
                        best_confidence = path_conf
                        best_path = [
                            {
                                "type": "changed_file_impacts_behavior",
                                "from": file_path,
                                "to": beh_id,
                                "source": file_to_beh.edge_source,
                                "confidence": file_to_beh.confidence
                            },
                            {
                                "type": "behavior_covered_by_test",
                                "from": beh_id,
                                "to": test_id_str,
                                "source": beh_to_test.edge_source,
                                "confidence": beh_to_test.confidence,
                                "review_status": beh_to_test.review_status
                            }
                        ]
                
                # Traversal Option B: ProductBehavior -> AcceptanceCriterion -> TestCase
                beh_to_ac_edges = [
                    e for e in edges_from_source.get(beh_id, [])
                    if e.source_node_type == "ProductBehavior" and e.target_node_type == "AcceptanceCriterion"
                ]
                for beh_to_ac in beh_to_ac_edges:
                    ac_id = beh_to_ac.target_node_id
                    
                    ac_to_test_edges = [
                        e for e in edges_from_source.get(ac_id, [])
                        if e.source_node_type == "AcceptanceCriterion" and e.target_node_type == "TestCase" and e.target_node_id == test_id_str
                    ]
                    for ac_to_test in ac_to_test_edges:
                        path_conf = (file_to_beh.confidence or 1.0) * (beh_to_ac.confidence or 1.0) * (ac_to_test.confidence or 1.0)
                        if path_conf > best_confidence:
                            best_confidence = path_conf
                            best_path = [
                                {
                                    "type": "changed_file_impacts_behavior",
                                    "from": file_path,
                                    "to": beh_id,
                                    "source": file_to_beh.edge_source,
                                    "confidence": file_to_beh.confidence
                                },
                                {
                                    "type": "behavior_covers_ac",
                                    "from": beh_id,
                                    "to": ac_id,
                                    "source": beh_to_ac.edge_source,
                                    "confidence": beh_to_ac.confidence
                                },
                                {
                                    "type": "ac_covered_by_test",
                                    "from": ac_id,
                                    "to": test_id_str,
                                    "source": ac_to_test.edge_source,
                                    "confidence": ac_to_test.confidence,
                                    "review_status": ac_to_test.review_status
                                }
                            ]
        
        # If no path found via ChangedFile, check direct AC-to-Test or Behavior-to-Test mappings
        if not best_path:
            direct_ac_edges = [
                e for e in edges
                if e.source_node_type == "AcceptanceCriterion" and e.target_node_type == "TestCase" and e.target_node_id == test_id_str
            ]
            if direct_ac_edges:
                best_edge = max(direct_ac_edges, key=lambda e: e.confidence or 0.0)
                best_path = [
                    {
                        "type": "ac_covered_by_test",
                        "from": best_edge.source_node_id,
                        "to": test_id_str,
                        "source": best_edge.edge_source,
                        "confidence": best_edge.confidence,
                        "review_status": best_edge.review_status
                    }
                ]
            else:
                direct_beh_edges = [
                    e for e in edges
                    if e.source_node_type == "ProductBehavior" and e.target_node_type == "TestCase" and e.target_node_id == test_id_str
                ]
                if direct_beh_edges:
                    best_edge = max(direct_beh_edges, key=lambda e: e.confidence or 0.0)
                    best_path = [
                        {
                            "type": "behavior_covered_by_test",
                            "from": best_edge.source_node_id,
                            "to": test_id_str,
                            "source": best_edge.edge_source,
                            "confidence": best_edge.confidence,
                            "review_status": best_edge.review_status
                        }
                    ]
        
        # Add execution result step if available
        # Find the latest test run/result for this testcase in the current PR
        # Get TestCase stable identity first
        tc_obj = db.query(TestCase).filter(TestCase.id == repo_uuid if test_id_str == str(repo_uuid) else TestCase.id == cls._to_uuid(test_id_str)).first()
        if not tc_obj:
            # Fallback lookup by stable_identity
            tc_obj = db.query(TestCase).filter(
                TestCase.repository_id == repo_uuid,
                TestCase.stable_identity == test_id_str
            ).first()
            
        if tc_obj:
            latest_result = db.query(TestResult).join(TestRun).filter(
                TestRun.pull_request_id == pr_uuid,
                TestResult.test_case_id == tc_obj.id
            ).order_by(TestResult.created_at.desc()).first()
            
            if latest_result:
                best_path.append({
                    "type": "test_has_execution_result",
                    "from": tc_obj.stable_identity,
                    "to": f"test_run:{str(latest_result.test_run_id)[:8]}",
                    "source": "junit_result",
                    "status": latest_result.status,
                    "commit_sha": latest_result.test_run.commit_sha
                })
                
        return best_path

    @classmethod
    def summarize_mapping_coverage(cls, db: Session, repository_id: Any, pull_request_id: Optional[Any] = None) -> Dict[str, Any]:
        mappings = cls.get_ac_to_test_mappings(db, repository_id, pull_request_id)
        
        total_mappings = len(mappings)
        confirmed = sum(1 for m in mappings if m.review_status == "user_confirmed")
        suggested = sum(1 for m in mappings if m.review_status == "system_suggested")
        pending_review = sum(1 for m in mappings if m.review_status == "pending_review")
        needs_review = sum(1 for m in mappings if m.review_status == "needs_review")
        rejected = sum(1 for m in mappings if m.review_status == "rejected")
        
        return {
            "total_mappings": total_mappings,
            "confirmed_count": confirmed,
            "suggested_count": suggested,
            "pending_review_count": pending_review,
            "needs_review_count": needs_review,
            "rejected_count": rejected
        }
