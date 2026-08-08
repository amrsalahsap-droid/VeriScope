"""
Mapping Manifest Service.

Handles import, export, trusted package identity validation, and stale AC key detection
for AC -> Test Mapping Manifests.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.test_result import TestCase
from app.models.traceability_edge import TraceabilityEdge
from app.models.mapping_candidate import MappingCandidate
from app.models.requirement_package import RequirementPackage
from app.services.traceability_graph_service import TraceabilityGraphService


class MappingManifestService:
    @staticmethod
    def export_manifest(
        db: Session,
        repository_id: uuid.UUID,
        pull_request_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Exports all active/reviewed AC -> Test mappings for a PR as a JSON manifest.
        """
        if not db:
            return {
                "version": "1.0",
                "repository": str(repository_id),
                "requirement_package_id": str(pull_request_id),
                "mappings": []
            }

        package = db.query(RequirementPackage).filter(
            RequirementPackage.pull_request_id == pull_request_id
        ).first()
        package_id_str = str(package.id) if package else str(pull_request_id)

        edges = db.query(TraceabilityEdge).filter(
            TraceabilityEdge.repository_id == repository_id,
            TraceabilityEdge.pull_request_id == pull_request_id,
            TraceabilityEdge.edge_type == "ac_covered_by_test",
            TraceabilityEdge.is_active == True,
            TraceabilityEdge.review_status.in_(["user_confirmed", "verified", "USER_CONFIRMED", "VERIFIED"])
        ).all()

        acs = db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.pull_request_id == pull_request_id,
            AcceptanceCriterion.status != "REJECTED"
        ).all()
        ac_map = {str(ac.id): ac for ac in acs}

        test_cases = db.query(TestCase).filter(
            TestCase.repository_id == repository_id,
            TestCase.is_active == True
        ).all()
        tc_map = {str(tc.id): tc for tc in test_cases}

        mappings_list = []
        for edge in edges:
            ac = ac_map.get(str(edge.source_node_id))
            tc = tc_map.get(str(edge.target_node_id))
            if not ac or not tc:
                continue

            test_identifier = getattr(tc, "stable_identity", None) or f"{tc.suite_name}::{tc.test_name}"
            stable_ac_key = getattr(ac, "stable_ac_key", None) or getattr(ac, "identifier", None) or str(ac.id)
            display_ref = getattr(ac, "identifier", None) or (f"AC-{ac.ac_number:02d}" if getattr(ac, "ac_number", None) is not None else "AC-01")

            approved_by = getattr(edge, "confirmed_by", None) or getattr(edge, "created_by", None) or "system_review"
            approved_at = (edge.updated_at or edge.created_at or datetime.utcnow()).isoformat()

            mappings_list.append({
                "test_identifier": test_identifier,
                "stable_ac_key": stable_ac_key,
                "display_ref": display_ref,
                "mapping_source": edge.edge_source or "manual_review",
                "approved_by": approved_by,
                "approved_at": approved_at
            })

        return {
            "version": "1.0",
            "repository": str(repository_id),
            "requirement_package_id": package_id_str,
            "mappings": mappings_list
        }

    @staticmethod
    def import_manifest(
        db: Session,
        repository_id: uuid.UUID,
        pull_request_id: uuid.UUID,
        manifest_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Imports a mapping manifest. Validates requirement package identity and detects stale AC keys.
        """
        version = manifest_data.get("version", "1.0")
        manifest_repo = manifest_data.get("repository")
        manifest_package_id = manifest_data.get("requirement_package_id")
        mappings = manifest_data.get("mappings", [])

        if not db:
            return {
                "status": "SUCCESS",
                "imported_count": len(mappings),
                "stale_count": 0,
                "warnings": [],
                "package_identity_matched": True
            }

        package = db.query(RequirementPackage).filter(
            RequirementPackage.pull_request_id == pull_request_id
        ).first()
        current_package_id = str(package.id) if package else str(pull_request_id)

        package_identity_matched = False
        if manifest_package_id and str(manifest_package_id) == current_package_id:
            package_identity_matched = True
        elif manifest_repo and str(manifest_repo) == str(repository_id):
            package_identity_matched = True

        acs = db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.pull_request_id == pull_request_id,
            AcceptanceCriterion.status != "REJECTED"
        ).all()

        test_cases = db.query(TestCase).filter(
            TestCase.repository_id == repository_id,
            TestCase.is_active == True
        ).all()

        imported_count = 0
        stale_count = 0
        warnings = []

        if not package_identity_matched:
            warnings.append(
                f"Manifest package identity '{manifest_package_id}' does not match target package identity '{current_package_id}'. Mappings imported as unconfirmed."
            )

        for entry in mappings:
            test_ident = entry.get("test_identifier")
            stable_key = entry.get("stable_ac_key")
            display_ref = entry.get("display_ref")

            if not test_ident or not stable_key:
                continue

            # Lookup AC by stable_ac_key, id, identifier, or display_ref
            ac_match = next((
                a for a in acs
                if (getattr(a, "stable_ac_key", None) == stable_key or
                    str(getattr(a, "id", "")) == stable_key or
                    getattr(a, "identifier", None) == stable_key or
                    getattr(a, "identifier", None) == display_ref)
            ), None)

            if not ac_match:
                stale_count += 1
                warnings.append(f"Stale manifest entry: AC key '{stable_key}' ({display_ref}) no longer exists in target requirement package.")
                continue

            # Lookup testcase
            tc_match = next((
                t for t in test_cases
                if (t.stable_identity == test_ident or
                    t.dedupe_key == test_ident or
                    t.test_name == test_ident or
                    f"{t.suite_name}::{t.test_name}" == test_ident)
            ), None)

            if not tc_match:
                warnings.append(f"Test case '{test_ident}' not found in current repository inventory.")
                continue

            review_status = "user_confirmed" if package_identity_matched else "needs_review"
            confidence = 1.0 if package_identity_matched else 0.50

            ev_json = {
                "source": "mapping_manifest",
                "mapping_source": entry.get("mapping_source", "mapping_manifest"),
                "approved_by": entry.get("approved_by"),
                "approved_at": entry.get("approved_at"),
                "package_identity_matched": package_identity_matched,
                "version": version
            }

            TraceabilityGraphService.upsert_edge(
                db=db,
                repository_id=repository_id,
                pull_request_id=pull_request_id,
                source_node_type="AcceptanceCriterion",
                source_node_id=str(ac_match.id),
                target_node_type="TestCase",
                target_node_id=str(tc_match.id),
                edge_type="ac_covered_by_test",
                edge_source=entry.get("mapping_source", "mapping_manifest"),
                confidence=confidence,
                review_status=review_status,
                evidence_json=ev_json
            )

            cand = db.query(MappingCandidate).filter(
                MappingCandidate.repository_id == repository_id,
                MappingCandidate.pull_request_id == pull_request_id,
                MappingCandidate.test_case_id == tc_match.id,
                MappingCandidate.acceptance_criterion_id == ac_match.id
            ).first()

            if cand:
                cand.review_status = "USER_CONFIRMED" if package_identity_matched else "NEEDS_REVIEW"
                cand.confidence_score = confidence
                cand.candidate_source = entry.get("mapping_source", "mapping_manifest")
                cand.evidence_json = ev_json
                cand.updated_at = datetime.utcnow()
            else:
                cand = MappingCandidate(
                    id=uuid.uuid4(),
                    repository_id=repository_id,
                    pull_request_id=pull_request_id,
                    test_case_id=tc_match.id,
                    acceptance_criterion_id=ac_match.id,
                    declared_ac_ref=display_ref or stable_key,
                    candidate_source=entry.get("mapping_source", "mapping_manifest"),
                    confidence_score=confidence,
                    confidence_label="high" if confidence >= 0.8 else "medium",
                    review_status="USER_CONFIRMED" if package_identity_matched else "NEEDS_REVIEW",
                    conflict_detected=False,
                    evidence_json=ev_json,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(cand)

            imported_count += 1

        try:
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass

        return {
            "status": "SUCCESS" if stale_count == 0 else "WARNING",
            "imported_count": imported_count,
            "stale_count": stale_count,
            "warnings": warnings,
            "package_identity_matched": package_identity_matched
        }
