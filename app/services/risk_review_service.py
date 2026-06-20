import uuid
import hashlib
import json
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.recommendation import RecommendationRun
from app.models.risk_review import RiskReview
from app.models.user import User
from app.models.pull_request import PullRequest
from app.models.acceptance_criterion import AcceptanceCriterion
from app.services.evidence_graph.requirement_evidence_graph_service import RequirementEvidenceGraphService
from app.services.regression_evidence_classifier import EvidenceClassification
from app.services.business_understanding.business_context_service import BusinessContextService

class RiskReviewService:
    @staticmethod
    def get_snapshot_hash(run: RecommendationRun) -> str:
        """Get or compute the canonical snapshot hash of the recommendation evidence graph."""
        if run.requirement_evidence_snapshot_json:
            snapshot_json = run.requirement_evidence_snapshot_json
            if isinstance(snapshot_json, str):
                snapshot_data = json.loads(snapshot_json)
            else:
                snapshot_data = snapshot_json
            canonical_snapshot = json.dumps(snapshot_data, sort_keys=True)
            return hashlib.md5(canonical_snapshot.encode()).hexdigest()
        else:
            return hashlib.md5(str(run.id).encode()).hexdigest()

    @staticmethod
    def get_active_reviews(db: Session, run_id: uuid.UUID) -> List[RiskReview]:
        return db.query(RiskReview).filter(
            RiskReview.recommendation_run_id == run_id,
            RiskReview.is_active == True
        ).all()

    @staticmethod
    def build_reviewable_gap_index(db: Session, run: RecommendationRun) -> Dict[str, Any]:
        """
        Build a snapshot-backed index of reviewable gaps.
        
        Returns a dictionary with:
        - 'gaps': list of reviewable gap items with full context
        - 'by_source_ac_number': dict mapping source_ac_number to gap
        - 'by_source_requirement_id': dict mapping source_requirement_id to gap
        - 'by_readable_id': dict mapping readable_id to gap
        - 'snapshot_hash': the computed snapshot hash
        
        This method uses the stored evidence graph snapshot and does not
        require browser request context or recomputed changed files.
        """
        snapshot_hash = RiskReviewService.get_snapshot_hash(run)
        
        # Load PR and changed files from stored snapshot
        pr = db.query(PullRequest).filter(PullRequest.id == run.pull_request_id).first()
        if not pr:
            raise HTTPException(status_code=404, detail="Pull request not found for recommendation run.")
            
        changed_files = []
        if run.input_snapshot and run.input_snapshot.changed_files:
            raw = run.input_snapshot.changed_files
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, str):
                        changed_files.append(item)
                    elif isinstance(item, dict):
                        fp = item.get("file_path") or item.get("filename")
                        if fp:
                            changed_files.append(fp)

        from app.routers.recommendation import _resolve_acceptance_criteria_text
        ac_source = _resolve_acceptance_criteria_text(run, pr, db)

        # Query canonical AcceptanceCriterion rows if they exist
        ac_rows = db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.pull_request_id == pr.id
        ).all()

        graph_service = RequirementEvidenceGraphService(db)
        if ac_rows:
            view_model = graph_service.build_evidence_graph(
                repository_id=str(run.repository_id),
                pull_request_id=str(pr.id),
                head_sha=pr.head_commit_sha,
                changed_files=changed_files,
                pr_description=None,
                recommendation_run_id=str(run.id),
                canonical_ac_rows=ac_rows
            )
        else:
            view_model = graph_service.build_evidence_graph(
                repository_id=str(run.repository_id),
                pull_request_id=str(pr.id),
                head_sha=pr.head_commit_sha,
                changed_files=changed_files,
                pr_description=ac_source["text"],
                recommendation_run_id=str(run.id)
            )

        parent_reqs = [
            req for req in getattr(view_model, "requirements", [])
            if req.node_type == "PARENT_REQUIREMENT" and req.classification != EvidenceClassification.EXCLUDED_FRAGMENT_OR_TEST_DATA
        ]

        reviewable_classifications = {
            EvidenceClassification.MISSING_AUTOMATED_COVERAGE,
            EvidenceClassification.PARTIALLY_COVERED
        }

        reviewable_nodes = [
            r for r in parent_reqs if r.classification in reviewable_classifications
        ]

        bc_service = BusinessContextService()
        gaps = []

        for r in reviewable_nodes:
            # Generate original generated risk level & priority
            bc = bc_service.generate_business_context(
                requirement_text=r.title,
                requirement_title=r.readable_id,
                requirement_id=r.requirement_id,
                matched_tests=[t.title for t in getattr(r, "linked_existing_tests", [])],
                pr_title=pr.title if pr else "",
                pr_description=getattr(pr, "description", ""),
                changed_files=changed_files
            )
            
            orig_risk = (bc.risk_level or "UNKNOWN").upper()
            orig_priority = (bc.priority or "UNKNOWN").upper()

            ac = db.query(AcceptanceCriterion).filter(AcceptanceCriterion.id == r.requirement_id).first()
            source_ac_number = ac.source_number if ac else None

            gap_item = {
                "sourceRequirementId": str(r.requirement_id) if r.requirement_id else None,
                "sourceAcNumber": source_ac_number,
                "readableId": r.readable_id,
                "title": r.title,
                "evidenceClassification": r.classification.value if hasattr(r.classification, "value") else str(r.classification),
                "originalRiskLevel": orig_risk,
                "originalPriority": orig_priority,
                "businessContext": bc.to_dict()
            }
            gaps.append(gap_item)

        # Build indexes
        by_source_ac_number = {}
        by_source_requirement_id = {}
        by_readable_id = {}
        
        for gap in gaps:
            if gap["sourceAcNumber"] is not None:
                by_source_ac_number[str(gap["sourceAcNumber"])] = gap
            if gap["sourceRequirementId"]:
                by_source_requirement_id[str(gap["sourceRequirementId"])] = gap
            if gap["readableId"]:
                by_readable_id[gap["readableId"]] = gap

        return {
            "gaps": gaps,
            "by_source_ac_number": by_source_ac_number,
            "by_source_requirement_id": by_source_requirement_id,
            "by_readable_id": by_readable_id,
            "snapshot_hash": snapshot_hash
        }

    @staticmethod
    def get_review_state(db: Session, run: RecommendationRun) -> Dict[str, Any]:
        """Get review state using the shared reviewable gap index."""
        gap_index = RiskReviewService.build_reviewable_gap_index(db, run)
        gaps = gap_index["gaps"]
        snapshot_hash = gap_index["snapshot_hash"]
        
        active_reviews = RiskReviewService.get_active_reviews(db, run.id)
        reviews_by_req_id = {r.source_requirement_id: r for r in active_reviews if r.source_requirement_id}
        reviews_by_ac_num = {r.source_ac_number: r for r in active_reviews if r.source_ac_number is not None}

        items_payload = []
        reviewed_count = 0
        unreviewed_count = 0

        for gap in gaps:
            orig_risk = gap["originalRiskLevel"]
            orig_priority = gap["originalPriority"]
            bc_dict = gap["businessContext"].copy()  # Copy to avoid mutating the index

            # Find active review matching this item
            review_rec = reviews_by_req_id.get(gap["sourceRequirementId"])
            if not review_rec and gap["sourceAcNumber"] is not None:
                review_rec = reviews_by_ac_num.get(gap["sourceAcNumber"])

            if review_rec and review_rec.review_status != "UNREVIEWED":
                reviewed_count += 1
                status_val = review_rec.review_status
                rev_risk = review_rec.reviewed_risk_level
                rev_priority = review_rec.reviewed_priority
                reviewer_name = review_rec.reviewer_name
                review_note = review_rec.review_note
                updated_at_val = review_rec.updated_at.isoformat()
            else:
                unreviewed_count += 1
                status_val = "UNREVIEWED"
                rev_risk = orig_risk
                rev_priority = orig_priority
                reviewer_name = None
                review_note = None
                updated_at_val = None

            # Effective risk calculation rules
            if status_val == "OVERRIDDEN":
                eff_risk = rev_risk
                eff_priority = rev_priority
            elif status_val == "ACCEPTED":
                eff_risk = orig_risk
                eff_priority = orig_priority
            elif status_val == "UNREVIEWED":
                eff_risk = orig_risk
                eff_priority = orig_priority
            elif status_val == "NEEDS_DISCUSSION":
                eff_risk = rev_risk if rev_risk else orig_risk
                eff_priority = rev_priority if rev_priority else orig_priority
            else:
                eff_risk = orig_risk
                eff_priority = orig_priority

            # Inject effective values into business context
            bc_dict["effectiveRiskLevel"] = eff_risk
            bc_dict["effectivePriority"] = eff_priority
            bc_dict["reviewStatus"] = status_val

            items_payload.append({
                "sourceRequirementId": gap["sourceRequirementId"],
                "sourceAcNumber": gap["sourceAcNumber"],
                "readableId": gap["readableId"],
                "title": gap["title"],
                "evidenceClassification": gap["evidenceClassification"],
                "originalRiskLevel": orig_risk,
                "originalPriority": orig_priority,
                "reviewedRiskLevel": rev_risk,
                "reviewedPriority": rev_priority,
                "effectiveRiskLevel": eff_risk,
                "effectivePriority": eff_priority,
                "reviewStatus": status_val,
                "reviewerName": reviewer_name,
                "reviewNote": review_note,
                "updatedAt": updated_at_val,
                "businessContext": bc_dict
            })

        return {
            "recommendationRunId": str(run.id),
            "snapshotHash": snapshot_hash,
            "totalReviewableGaps": len(gaps),
            "reviewedCount": reviewed_count,
            "unreviewedCount": unreviewed_count,
            "items": items_payload
        }

    @staticmethod
    def check_active_review_integrity(db: Session, run_id: uuid.UUID, requirement_id: Optional[str], ac_number: Optional[int]) -> None:
        """
        Check if there are multiple active reviews for the target requirement.
        If count > 1, raises HTTP 500 with MULTIPLE_ACTIVE_REVIEWS_DETECTED and REVIEW_HISTORY_INCONSISTENT.
        """
        query = db.query(RiskReview).filter(
            RiskReview.recommendation_run_id == run_id,
            RiskReview.is_active == True
        )
        if requirement_id:
            query = query.filter(RiskReview.source_requirement_id == requirement_id)
        elif ac_number is not None:
            query = query.filter(RiskReview.source_ac_number == ac_number)
        else:
            return

        active_count = query.count()
        if active_count > 1:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="REVIEW_HISTORY_INCONSISTENT: MULTIPLE_ACTIVE_REVIEWS_DETECTED"
            )

    @staticmethod
    def submit_review(db: Session, run: RecommendationRun, data: Dict[str, Any], reviewer: User) -> RiskReview:
        # 1. Snapshot check
        current_hash = RiskReviewService.get_snapshot_hash(run)
        if data.get("snapshotHash") != current_hash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="REVIEW_SNAPSHOT_MISMATCH: REQUIRES_REGENERATION"
            )

        # 2. Enforce note requirements
        review_status_val = data.get("reviewStatus")
        if review_status_val not in ("ACCEPTED", "OVERRIDDEN", "NEEDS_DISCUSSION"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Active review states must be ACCEPTED, OVERRIDDEN, or NEEDS_DISCUSSION."
            )

        review_note = data.get("reviewNote")
        if review_status_val in ("OVERRIDDEN", "NEEDS_DISCUSSION") and not review_note:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Review note is required for {review_status_val} status."
            )

        source_requirement_id = data.get("sourceRequirementId")
        source_ac_number = data.get("sourceAcNumber")
        readable_id = data.get("readableId")

        if not source_requirement_id and source_ac_number is None and not readable_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either sourceRequirementId, sourceAcNumber, or readableId must be provided."
            )

        # 3. Resolve requirement from shared reviewable gap index
        gap_index = RiskReviewService.build_reviewable_gap_index(db, run)
        
        # Validate snapshot hash matches index
        if gap_index["snapshot_hash"] != current_hash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="REVIEW_SNAPSHOT_MISMATCH: REQUIRES_REGENERATION"
            )

        # Find the target gap - use readableId as primary stable identifier
        target_gap = None
        
        if readable_id:
            target_gap = gap_index["by_readable_id"].get(readable_id)
        
        # Fallback to sourceRequirementId if readableId not provided
        if not target_gap and source_requirement_id:
            target_gap = gap_index["by_source_requirement_id"].get(str(source_requirement_id))
        
        # Fallback to sourceAcNumber if still not found
        if not target_gap and source_ac_number is not None:
            target_gap = gap_index["by_source_ac_number"].get(str(source_ac_number))
        
        # If still not found, target is not reviewable
        if not target_gap:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="REVIEW_TARGET_NOT_REVIEWABLE"
            )

        # Extract original generated risk level & priority from gap
        orig_risk = target_gap["originalRiskLevel"]
        orig_priority = target_gap["originalPriority"]
        target_req_id = target_gap["sourceRequirementId"]
        target_ac_num = target_gap["sourceAcNumber"]
        readable_id = target_gap["readableId"]

        # 4. Check active reviews integrity
        RiskReviewService.check_active_review_integrity(db, run.id, target_req_id, target_ac_num)

        # 5. Deactivate existing reviews for this item
        existing_reviews = db.query(RiskReview).filter(
            RiskReview.recommendation_run_id == run.id,
            RiskReview.is_active == True
        ).all()

        for er in existing_reviews:
            matches = False
            if er.source_requirement_id == target_req_id:
                matches = True
            elif target_ac_num is not None and er.source_ac_number == target_ac_num:
                matches = True
            
            if matches:
                er.is_active = False

        # 6. Create and persist new review decision
        new_review = RiskReview(
            id=uuid.uuid4(),
            recommendation_run_id=run.id,
            source_requirement_id=target_req_id,
            source_ac_number=target_ac_num,
            readable_id=readable_id,
            original_risk_level=orig_risk,
            original_priority=orig_priority,
            reviewed_risk_level=data.get("reviewedRiskLevel") or orig_risk,
            reviewed_priority=data.get("reviewedPriority") or orig_priority,
            review_status=review_status_val,
            reviewer_id=str(reviewer.id),
            reviewer_name=reviewer.name or reviewer.email,
            review_note=review_note,
            source_snapshot_hash=current_hash,
            is_active=True
        )

        db.add(new_review)
        db.commit()
        db.refresh(new_review)

        return new_review

    @staticmethod
    def bulk_accept(db: Session, run: RecommendationRun, data: Dict[str, Any], reviewer: User) -> List[RiskReview]:
        # 1. Snapshot check
        current_hash = RiskReviewService.get_snapshot_hash(run)
        if data.get("snapshotHash") != current_hash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="REVIEW_SNAPSHOT_MISMATCH: REQUIRES_REGENERATION"
            )

        # 2. Get all gaps from shared index
        gap_index = RiskReviewService.build_reviewable_gap_index(db, run)
        gaps = gap_index["gaps"]
        
        # Validate snapshot hash matches index
        if gap_index["snapshot_hash"] != current_hash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="REVIEW_SNAPSHOT_MISMATCH: REQUIRES_REGENERATION"
            )

        # 3. Check integrity for all target gaps
        for g in gaps:
            RiskReviewService.check_active_review_integrity(
                db, run.id, g["sourceRequirementId"], g["sourceAcNumber"]
            )

        # Deactivate all active reviews for these gaps first
        gap_req_ids = [g["sourceRequirementId"] for g in gaps]
        existing_reviews = db.query(RiskReview).filter(
            RiskReview.recommendation_run_id == run.id,
            RiskReview.is_active == True,
            RiskReview.source_requirement_id.in_(gap_req_ids)
        ).all()
        for er in existing_reviews:
            er.is_active = False

        created_reviews = []
        for g in gaps:
            new_review = RiskReview(
                id=uuid.uuid4(),
                recommendation_run_id=run.id,
                source_requirement_id=g["sourceRequirementId"],
                source_ac_number=g["sourceAcNumber"],
                readable_id=g["readableId"],
                original_risk_level=g["originalRiskLevel"],
                original_priority=g["originalPriority"],
                reviewed_risk_level=g["originalRiskLevel"],
                reviewed_priority=g["originalPriority"],
                review_status="ACCEPTED",
                reviewer_id=str(reviewer.id),
                reviewer_name=reviewer.name or reviewer.email,
                review_note=None,
                source_snapshot_hash=current_hash,
                is_active=True
            )
            db.add(new_review)
            created_reviews.append(new_review)

        db.commit()
        return {
            "acceptedCount": len(created_reviews),
            "totalReviewableGaps": len(gaps),
            "reviews": created_reviews
        }

    @staticmethod
    def reset_review(db: Session, run: RecommendationRun, review_id: uuid.UUID, data: Dict[str, Any], reviewer: User) -> None:
        # 1. Snapshot check
        current_hash = RiskReviewService.get_snapshot_hash(run)
        if data.get("snapshotHash") and data.get("snapshotHash") != current_hash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="REVIEW_SNAPSHOT_MISMATCH: REQUIRES_REGENERATION"
            )

        review = db.query(RiskReview).filter(
            RiskReview.id == review_id,
            RiskReview.recommendation_run_id == run.id
        ).first()
        if not review:
            raise HTTPException(status_code=404, detail="Risk review not found.")

        # 2. Check active reviews integrity
        RiskReviewService.check_active_review_integrity(
            db, run.id, review.source_requirement_id, review.source_ac_number
        )

        # 3. Deactivate active reviews for this requirement
        active_query = db.query(RiskReview).filter(
            RiskReview.recommendation_run_id == run.id,
            RiskReview.is_active == True
        )
        if review.source_requirement_id:
            active_query = active_query.filter(RiskReview.source_requirement_id == review.source_requirement_id)
        elif review.source_ac_number is not None:
            active_query = active_query.filter(RiskReview.source_ac_number == review.source_ac_number)
        
        for ar in active_query.all():
            ar.is_active = False

        # 4. Insert RESET row (is_active = False)
        reset_event = RiskReview(
            id=uuid.uuid4(),
            recommendation_run_id=run.id,
            source_requirement_id=review.source_requirement_id,
            source_ac_number=review.source_ac_number,
            readable_id=review.readable_id,
            original_risk_level=review.original_risk_level,
            original_priority=review.original_priority,
            reviewed_risk_level=review.original_risk_level,
            reviewed_priority=review.original_priority,
            review_status="RESET",
            reviewer_id=str(reviewer.id),
            reviewer_name=reviewer.name or reviewer.email,
            review_note=data.get("reviewNote") or "Reset via DELETE endpoint",
            source_snapshot_hash=current_hash,
            is_active=False
        )
        db.add(reset_event)
        db.commit()

    @staticmethod
    def reset_review_by_item(db: Session, run: RecommendationRun, data: Dict[str, Any], reviewer: User) -> None:
        # 1. Snapshot check
        current_hash = RiskReviewService.get_snapshot_hash(run)
        if data.get("snapshotHash") and data.get("snapshotHash") != current_hash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="REVIEW_SNAPSHOT_MISMATCH: REQUIRES_REGENERATION"
            )

        source_requirement_id = data.get("sourceRequirementId")
        source_ac_number = data.get("sourceAcNumber")

        if not source_requirement_id and source_ac_number is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either sourceRequirementId or sourceAcNumber must be provided."
            )

        # 2. Resolve from shared reviewable gap index
        gap_index = RiskReviewService.build_reviewable_gap_index(db, run)
        
        # Validate snapshot hash matches index
        if gap_index["snapshot_hash"] != current_hash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="REVIEW_SNAPSHOT_MISMATCH: REQUIRES_REGENERATION"
            )

        # Find the target gap to validate it exists
        target_gap = None
        if source_requirement_id:
            target_gap = gap_index["by_source_requirement_id"].get(str(source_requirement_id))
        elif source_ac_number is not None:
            target_gap = gap_index["by_source_ac_number"].get(str(source_ac_number))

        if not target_gap:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="REVIEW_TARGET_NOT_REVIEWABLE"
            )

        target_req_id = target_gap["sourceRequirementId"]
        target_ac_num = target_gap["sourceAcNumber"]

        # 3. Check active reviews integrity
        RiskReviewService.check_active_review_integrity(db, run.id, target_req_id, target_ac_num)

        # 4. Deactivate reviews for this item
        query = db.query(RiskReview).filter(
            RiskReview.recommendation_run_id == run.id,
            RiskReview.is_active == True
        )

        if target_req_id:
            query = query.filter(RiskReview.source_requirement_id == target_req_id)
        elif target_ac_num is not None:
            query = query.filter(RiskReview.source_ac_number == int(target_ac_num))

        reviews = query.all()
        for r in reviews:
            r.is_active = False

        # 5. Insert RESET row (is_active = False)
        reset_event = RiskReview(
            id=uuid.uuid4(),
            recommendation_run_id=run.id,
            source_requirement_id=target_req_id,
            source_ac_number=target_ac_num,
            readable_id=target_gap["readableId"],
            original_risk_level=target_gap["originalRiskLevel"],
            original_priority=target_gap["originalPriority"],
            reviewed_risk_level=target_gap["originalRiskLevel"],
            reviewed_priority=target_gap["originalPriority"],
            review_status="RESET",
            reviewer_id=str(reviewer.id),
            reviewer_name=reviewer.name or reviewer.email,
            review_note=data.get("reviewNote") or "Reset via POST endpoint",
            source_snapshot_hash=current_hash,
            is_active=False
        )
        db.add(reset_event)
        db.commit()

    @staticmethod
    def get_review_history(
        db: Session,
        run: RecommendationRun,
        source_ac_number: Optional[int] = None,
        readable_id: Optional[str] = None,
        source_requirement_id: Optional[str] = None,
        include_inactive: bool = True,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        audit: bool = False
    ) -> Dict[str, Any]:
        """
        Retrieve risk review history for all reviewable gaps, grouping and sorting chronologically.
        Computes transition summaries and respects normal vs. audit mode.
        """
        current_hash = RiskReviewService.get_snapshot_hash(run)
        gap_index = RiskReviewService.build_reviewable_gap_index(db, run)
        gaps = gap_index["gaps"]

        # Filter gaps based on parameters
        filtered_gaps = []
        for g in gaps:
            if source_ac_number is not None and g["sourceAcNumber"] != source_ac_number:
                continue
            if readable_id is not None and g["readableId"] != readable_id:
                continue
            if source_requirement_id is not None and g["sourceRequirementId"] != source_requirement_id:
                continue
            filtered_gaps.append(g)

        # Retrieve all reviews for this recommendation run
        all_reviews = db.query(RiskReview).filter(
            RiskReview.recommendation_run_id == run.id
        ).all()

        items = []
        total_history_events = 0

        for gap in filtered_gaps:
            gap_req_id = gap["sourceRequirementId"]
            gap_ac_num = gap["sourceAcNumber"]
            gap_readable_id = gap["readableId"]

            # Match reviews to this gap
            gap_reviews = []
            for r in all_reviews:
                match = False
                if gap_req_id and r.source_requirement_id == gap_req_id:
                    match = True
                elif gap_ac_num is not None and r.source_ac_number == gap_ac_num:
                    match = True
                elif gap_readable_id and r.readable_id == gap_readable_id:
                    match = True
                
                if match:
                    gap_reviews.append(r)

            # Sort chronologically ascending
            gap_reviews.sort(key=lambda r: r.created_at)

            # Compute transition summary fields over all historical events for the gap
            first_reviewed_at = gap_reviews[0].created_at.isoformat() + "Z" if gap_reviews else None
            last_reviewed_at = gap_reviews[-1].created_at.isoformat() + "Z" if gap_reviews else None
            last_reviewer_name = gap_reviews[-1].reviewer_name if gap_reviews else None
            
            active_rev = next((r for r in gap_reviews if r.is_active), None)
            active_status = active_rev.review_status if active_rev else "UNREVIEWED"

            total_events = len(gap_reviews)
            reset_count = sum(1 for r in gap_reviews if r.review_status == "RESET")
            override_count = sum(1 for r in gap_reviews if r.review_status == "OVERRIDDEN")
            needs_discussion_count = sum(1 for r in gap_reviews if r.review_status == "NEEDS_DISCUSSION")
            accepted_count = sum(1 for r in gap_reviews if r.review_status == "ACCEPTED")

            # Determine current effective risk and status
            if active_rev:
                curr_eff_risk = active_rev.reviewed_risk_level if active_rev.review_status == "OVERRIDDEN" else active_rev.original_risk_level
                curr_status = active_rev.review_status
            else:
                curr_eff_risk = gap["originalRiskLevel"]
                curr_status = "UNREVIEWED"

            # Filter events to return based on include_inactive
            events_to_serialize = gap_reviews
            if not include_inactive:
                events_to_serialize = [r for r in gap_reviews if r.is_active]

            total_history_events += len(events_to_serialize)

            serialized_events = []
            for rev in events_to_serialize:
                serialized_events.append({
                    "reviewId": str(rev.id) if audit else None,
                    "eventType": rev.review_status,
                    "reviewStatus": rev.review_status,
                    "originalRiskLevel": rev.original_risk_level,
                    "originalPriority": rev.original_priority,
                    "reviewedRiskLevel": rev.reviewed_risk_level,
                    "reviewedPriority": rev.reviewed_priority,
                    "reviewerName": rev.reviewer_name,
                    "reviewerId": rev.reviewer_id if audit else None,
                    "reviewNote": rev.review_note,
                    "sourceSnapshotHash": rev.source_snapshot_hash if audit else None,
                    "createdAt": rev.created_at.isoformat() + "Z" if rev.created_at else None,
                    "isActive": rev.is_active
                })

            items.append({
                "sourceAcNumber": gap["sourceAcNumber"],
                "readableId": gap["readableId"],
                "sourceRequirementId": gap["sourceRequirementId"] if audit else None,
                "title": gap["title"],
                "currentEffectiveRiskLevel": curr_eff_risk,
                "currentReviewStatus": curr_status,
                "firstReviewedAt": first_reviewed_at,
                "lastReviewedAt": last_reviewed_at,
                "lastReviewerName": last_reviewer_name,
                "activeStatus": active_status,
                "totalEvents": total_events,
                "resetCount": reset_count,
                "overrideCount": override_count,
                "needsDiscussionCount": needs_discussion_count,
                "acceptedCount": accepted_count,
                "history": serialized_events
            })

        # Apply limit & offset to the outer items list
        if offset is not None:
            items = items[offset:]
        if limit is not None:
            items = items[:limit]

        return {
            "recommendationRunId": str(run.id) if audit else None,
            "snapshotHash": current_hash if audit else None,
            "totalHistoryEvents": total_history_events,
            "items": items
        }

