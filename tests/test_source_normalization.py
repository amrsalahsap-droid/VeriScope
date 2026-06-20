"""Tests for source normalization (PHASE 0.8)."""
import pytest
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.services.source_normalization_service import SourceNormalizationService
from app.models.source_segment import SourceSegment, SegmentDisposition
from app.models.acceptance_criterion import AcceptanceCriterion
import uuid


def _get_golden_run(db):
    """Retrieve the golden password validation demo run to prevent postgres UUID validation errors with dirty/mocked PR IDs."""
    from app.models.recommendation import RecommendationRun
    run = db.query(RecommendationRun).filter(RecommendationRun.id == "ac42bec0-59b5-47f3-85be-956d771f0480").first()
    if not run:
        run = db.query(RecommendationRun).order_by(RecommendationRun.created_at.desc()).first()
    return run


def test_source_normalization_with_25_acs_and_3_security_notes():
    """Test 1: Given uploaded source with 25 numbered ACs and 3 security notes."""
    db = SessionLocal()
    
    try:
        # Get actual repository ID from database
        run = _get_golden_run(db)
        
        if not run:
            pytest.skip("No recommendation run found")
        
        repository_id = run.repository_id
        pr_id = run.pr_id
        
        # Clean up
        db.query(SourceSegment).filter(
            SourceSegment.repository_id == repository_id
        ).delete()
        db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.repository_id == repository_id
        ).delete()
        db.commit()
        
        # Test data with 25 ACs and 3 security notes
        raw_text = """Acceptance Criteria
1. Weak passwords are rejected during sign-up.
2. Strong passwords are accepted during sign-up.
3. Weak passwords are rejected during update-password.
4. Strong passwords are accepted during update-password.
5. After successful password update, the user can log in using the new password.
6. After successful password update, the old password is rejected.
7. Minimum password length is enforced: at least 12 characters.
8. Password complexity is enforced: uppercase, lowercase, number, and special character are required.
9. Empty password input is rejected.
10. Whitespace-only password input is rejected.
11. Leading and trailing spaces are handled consistently according to the defined policy.
12. Backend/API validation is mandatory and cannot rely only on frontend validation.
13. Direct API requests with weak passwords are rejected.
14. UI and API validation rules are consistent.
15. Validation error messages are safe, clear, and user-friendly.
16. Validation error messages do not expose internal system details.
17. Password is not updated when validation fails.
18. Weak passwords are rejected during reset-password.
19. Strong passwords are accepted during reset-password.
20. Reset-password with a valid unexpired token succeeds when the new password is strong.
21. Reset-password with an expired token is rejected.
22. Reset-password with a reused token is rejected.
23. Existing valid login behavior is not broken.
24. Password confirmation must match the password field.
25. Password update/reset operation is atomic: either the full update succeeds or nothing changes.

Security Notes
- Password policy must be shared or aligned across sign-up, update-password, and reset-password flows.
- Backend validation is the source of truth.
- Frontend UX only provides user-friendly validation messages.
"""
        
        # Normalize
        service = SourceNormalizationService(db)
        segments, diagnostics = service.normalize_source_text(
            raw_text,
            str(repository_id),
            str(pr_id)
        )
        
        # Verify segments
        ac_segments = [s for s in segments if s.disposition == SegmentDisposition.ACCEPTANCE_CRITERION]
        security_note_segments = [s for s in segments if s.disposition == SegmentDisposition.SECURITY_NOTE]
        
        assert len(ac_segments) == 25, f"Expected 25 AC segments, got {len(ac_segments)}"
        assert len(security_note_segments) == 3, f"Expected 3 security note segments, got {len(security_note_segments)}"
        
        # Verify AC-03
        ac_03 = next((s for s in ac_segments if s.source_number == 3), None)
        assert ac_03 is not None, "AC-03 not found"
        assert ac_03.normalized_text == "Weak passwords are rejected during update-password.", f"AC-03 text incorrect: {ac_03.normalized_text}"
        
        # Verify AC-25
        ac_25 = next((s for s in ac_segments if s.source_number == 25), None)
        assert ac_25 is not None, "AC-25 not found"
        assert ac_25.normalized_text == "Password update/reset operation is atomic: either the full update succeeds or nothing changes.", f"AC-25 text incorrect: {ac_25.normalized_text}"
        
        # Clean up
        db.query(SourceSegment).filter(
            SourceSegment.repository_id == repository_id
        ).delete()
        db.commit()
        
    finally:
        db.close()


def test_security_note_not_stored_as_acceptance_criterion():
    """Test 2: Security note 'Password policy must be shared...' is not stored as AcceptanceCriterion."""
    db = SessionLocal()
    
    try:
        # Get actual repository ID from database
        run = _get_golden_run(db)
        
        if not run:
            pytest.skip("No recommendation run found")
        
        repository_id = run.repository_id
        pr_id = run.pr_id
        
        # Clean up
        db.query(SourceSegment).filter(
            SourceSegment.repository_id == repository_id
        ).delete()
        db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.repository_id == repository_id
        ).delete()
        db.commit()
        
        raw_text = """Acceptance Criteria
1. Weak passwords are rejected during sign-up.

Security Notes
- Password policy must be shared or aligned across sign-up, update-password, and reset-password flows.
"""
        
        # Normalize and persist
        service = SourceNormalizationService(db)
        segments, diagnostics = service.normalize_source_text(
            raw_text,
            str(repository_id),
            str(pr_id)
        )
        service.persist_segments(segments)
        
        # Check AcceptanceCriterion table
        acs = db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.repository_id == repository_id
        ).all()
        
        security_note_in_ac = any("shared or aligned" in ac.text for ac in acs)
        assert not security_note_in_ac, "Security note found in AcceptanceCriterion table"
        
        # Check SourceSegment table
        security_note_segments = db.query(SourceSegment).filter(
            SourceSegment.repository_id == repository_id,
            SourceSegment.disposition == SegmentDisposition.SECURITY_NOTE
        ).all()
        
        assert len(security_note_segments) == 1, f"Expected 1 security note segment, got {len(security_note_segments)}"
        assert "shared or aligned" in security_note_segments[0].raw_text, "Security note text not found in segment"
        
        # Clean up
        db.query(SourceSegment).filter(
            SourceSegment.repository_id == repository_id
        ).delete()
        db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.repository_id == repository_id
        ).delete()
        db.commit()
        
    finally:
        db.close()


def test_security_notes_have_no_source_ac_number():
    """Test 3: Security notes have no source_ac_number."""
    db = SessionLocal()
    
    try:
        # Get actual repository ID from database
        run = _get_golden_run(db)
        
        if not run:
            pytest.skip("No recommendation run found")
        
        repository_id = run.repository_id
        pr_id = run.pr_id
        
        # Clean up
        db.query(SourceSegment).filter(
            SourceSegment.repository_id == repository_id
        ).delete()
        db.commit()
        
        raw_text = """Security Notes
- Password policy must be shared or aligned across sign-up, update-password, and reset-password flows.
- Backend validation is the source of truth.
- Frontend UX only provides user-friendly validation messages.
"""
        
        # Normalize
        service = SourceNormalizationService(db)
        segments, diagnostics = service.normalize_source_text(
            raw_text,
            str(repository_id),
            str(pr_id)
        )
        
        # Check security notes
        security_note_segments = [s for s in segments if s.disposition == SegmentDisposition.SECURITY_NOTE]
        
        for seg in security_note_segments:
            assert seg.source_number is None, f"Security note has source_number: {seg.source_number}"
        
        # Clean up
        db.query(SourceSegment).filter(
            SourceSegment.repository_id == repository_id
        ).delete()
        db.commit()
        
    finally:
        db.close()


def test_extraction_produces_25_parent_requirements():
    """Test 4: Extraction produces 25 parent requirements unless grouping policy explicitly reduces count."""
    db = SessionLocal()
    
    try:
        # Get actual repository ID from database
        run = _get_golden_run(db)
        
        if not run:
            pytest.skip("No recommendation run found")
        
        repository_id = run.repository_id
        pr_id = run.pr_id
        
        # Clean up
        db.query(SourceSegment).filter(
            SourceSegment.repository_id == repository_id
        ).delete()
        db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.repository_id == repository_id
        ).delete()
        db.commit()
        
        raw_text = """Acceptance Criteria
1. Weak passwords are rejected during sign-up.
2. Strong passwords are accepted during sign-up.
3. Weak passwords are rejected during update-password.
4. Strong passwords are accepted during update-password.
5. After successful password update, the user can log in using the new password.
6. After successful password update, the old password is rejected.
7. Minimum password length is enforced: at least 12 characters.
8. Password complexity is enforced: uppercase, lowercase, number, and special character are required.
9. Empty password input is rejected.
10. Whitespace-only password input is rejected.
11. Leading and trailing spaces are handled consistently according to the defined policy.
12. Backend/API validation is mandatory and cannot rely only on frontend validation.
13. Direct API requests with weak passwords are rejected.
14. UI and API validation rules are consistent.
15. Validation error messages are safe, clear, and user-friendly.
16. Validation error messages do not expose internal system details.
17. Password is not updated when validation fails.
18. Weak passwords are rejected during reset-password.
19. Strong passwords are accepted during reset-password.
20. Reset-password with a valid unexpired token succeeds when the new password is strong.
21. Reset-password with an expired token is rejected.
22. Reset-password with a reused token is rejected.
23. Existing valid login behavior is not broken.
24. Password confirmation must match the password field.
25. Password update/reset operation is atomic: either the full update succeeds or nothing changes.
"""
        
        # Normalize and extract
        service = SourceNormalizationService(db)
        segments, diagnostics = service.normalize_source_text(
            raw_text,
            str(repository_id),
            str(pr_id)
        )
        
        ac_segments = [s for s in segments if s.disposition == SegmentDisposition.ACCEPTANCE_CRITERION]
        
        # Convert to criteria and persist
        from app.services.acceptance_criteria_extractor import AcceptanceCriteriaExtractor
        extractor = AcceptanceCriteriaExtractor(db)
        
        criteria = []
        for segment in ac_segments:
            criteria.append({
                "text": segment.normalized_text,
                "source": "TEST",
                "confidence": 0.8,
                "evidence_excerpt": segment.raw_text,
                "source_section": segment.source_section,
                "source_number": segment.source_number,
                "source_hash": segment.source_hash,
            })
        
        criteria = extractor._normalize_and_deduplicate(criteria)
        persisted, excluded = extractor.persist_criteria(
            criteria,
            repository_id,
            pr_id,
            db
        )
        
        assert len(persisted) == 25, f"Expected 25 parent requirements, got {len(persisted)}"
        
        # Clean up
        db.query(SourceSegment).filter(
            SourceSegment.repository_id == repository_id
        ).delete()
        db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.repository_id == repository_id
        ).delete()
        db.commit()
        
    finally:
        db.close()


def test_source_section_mismatch_detection():
    """Test 5: Polluted DB row detection - SOURCE_SECTION_MISMATCH."""
    db = SessionLocal()
    
    try:
        # Get actual repository ID from database
        run = _get_golden_run(db)
        
        if not run:
            pytest.skip("No recommendation run found")
        
        repository_id = run.repository_id
        pr_id = run.pr_id
        
        # Clean up
        db.query(SourceSegment).filter(
            SourceSegment.repository_id == repository_id
        ).delete()
        db.commit()
        
        # Create a segment with ACCEPTANCE_CRITERION disposition but wrong section
        segment = SourceSegment(
            id=uuid.uuid4(),
            repository_id=repository_id,
            pull_request_id=pr_id,
            source_section="Security Notes",
            source_number=1,
            raw_text="Weak passwords are rejected during sign-up.",
            normalized_text="Weak passwords are rejected during sign-up.",
            disposition=SegmentDisposition.ACCEPTANCE_CRITERION,
            source_hash="test",
            line_number=1
        )
        db.add(segment)
        db.commit()
        
        # Validate
        service = SourceNormalizationService(db)
        diagnostics = service.validate_source_integrity([segment])
        
        source_section_mismatch = any(d['code'] == 'SOURCE_SECTION_MISMATCH' for d in diagnostics)
        assert source_section_mismatch, "SOURCE_SECTION_MISMATCH not detected"
        
        # Clean up
        db.query(SourceSegment).filter(
            SourceSegment.repository_id == repository_id
        ).delete()
        db.commit()
        
    finally:
        db.close()


def test_source_ac_number_gap_detection():
    """Test 6: Source number gap detection - SOURCE_AC_NUMBER_GAP."""
    db = SessionLocal()
    
    try:
        # Get actual repository ID from database
        run = _get_golden_run(db)
        
        if not run:
            pytest.skip("No recommendation run found")
        
        repository_id = run.repository_id
        pr_id = run.pr_id
        
        # Clean up
        db.query(SourceSegment).filter(
            SourceSegment.repository_id == repository_id
        ).delete()
        db.commit()
        
        # Create segments with missing AC-03
        segments = []
        for i in [1, 2, 4, 5]:
            segment = SourceSegment(
                id=uuid.uuid4(),
                repository_id=repository_id,
                pull_request_id=pr_id,
                source_section="Acceptance Criteria",
                source_number=i,
                raw_text=f"Test AC {i}",
                normalized_text=f"Test AC {i}",
                disposition=SegmentDisposition.ACCEPTANCE_CRITERION,
                source_hash=f"test{i}",
                line_number=i
            )
            segments.append(segment)
            db.add(segment)
        db.commit()
        
        # Validate
        service = SourceNormalizationService(db)
        diagnostics = service.validate_source_integrity(segments)
        
        source_ac_number_gap = any(d['code'] == 'SOURCE_AC_NUMBER_GAP' for d in diagnostics)
        assert source_ac_number_gap, "SOURCE_AC_NUMBER_GAP not detected"
        
        # Check that missing number 3 is reported
        gap_diagnostic = next(d for d in diagnostics if d['code'] == 'SOURCE_AC_NUMBER_GAP')
        assert 3 in gap_diagnostic['missing_numbers'], f"Missing number 3 not in gap report: {gap_diagnostic['missing_numbers']}"
        
        # Clean up
        db.query(SourceSegment).filter(
            SourceSegment.repository_id == repository_id
        ).delete()
        db.commit()
        
    finally:
        db.close()


def test_current_recommendation_fixture():
    """Test 7: Current recommendation fixture - no AcceptanceCriterion row contains security note."""
    db = SessionLocal()
    
    try:
        # Get the actual recommendation run
        run = _get_golden_run(db)
        
        if not run:
            pytest.skip("No recommendation run found")
        
        repository_id = run.repository_id
        pr_id = run.pr_id
        
        # First, set up the test data (25 ACs with proper section headers)
        raw_text = """Acceptance Criteria
1. Weak passwords are rejected during sign-up.
2. Strong passwords are accepted during sign-up.
3. Weak passwords are rejected during update-password.
4. Strong passwords are accepted during update-password.
5. After successful password update, the user can log in using the new password.
6. After successful password update, the old password is rejected.
7. Minimum password length is enforced: at least 12 characters.
8. Password complexity is enforced: uppercase, lowercase, number, and special character are required.
9. Empty password input is rejected.
10. Whitespace-only password input is rejected.
11. Leading and trailing spaces are handled consistently according to the defined policy.
12. Backend/API validation is mandatory and cannot rely only on frontend validation.
13. Direct API requests with weak passwords are rejected.
14. UI and API validation rules are consistent.
15. Validation error messages are safe, clear, and user-friendly.
16. Validation error messages do not expose internal system details.
17. Password is not updated when validation fails.
18. Weak passwords are rejected during reset-password.
19. Strong passwords are accepted during reset-password.
20. Reset-password with a valid unexpired token succeeds when the new password is strong.
21. Reset-password with an expired token is rejected.
22. Reset-password with a reused token is rejected.
23. Existing valid login behavior is not broken.
24. Password confirmation must match the password field.
25. Password update/reset operation is atomic: either the full update succeeds or nothing changes.

Security Notes
- Password policy must be shared or aligned across sign-up, update-password, and reset-password flows.
- Backend validation is the source of truth.
- Frontend UX only provides user-friendly validation messages.
"""
        
        # Clean up first
        db.query(SourceSegment).filter(
            SourceSegment.repository_id == repository_id
        ).delete()
        db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.repository_id == repository_id
        ).delete()
        db.commit()
        
        # Normalize and persist
        service = SourceNormalizationService(db)
        segments, diagnostics = service.normalize_source_text(
            raw_text,
            str(repository_id),
            str(pr_id)
        )
        service.persist_segments(segments)
        
        # Extract and persist ACs
        from app.services.acceptance_criteria_extractor import AcceptanceCriteriaExtractor
        extractor = AcceptanceCriteriaExtractor(db)
        
        ac_segments = [s for s in segments if s.disposition == SegmentDisposition.ACCEPTANCE_CRITERION]
        
        criteria = []
        for segment in ac_segments:
            criteria.append({
                "text": segment.normalized_text,
                "source": "TEST",
                "confidence": 0.8,
                "evidence_excerpt": segment.raw_text,
                "source_section": segment.source_section,
                "source_number": segment.source_number,
                "source_hash": segment.source_hash,
            })
        
        criteria = extractor._normalize_and_deduplicate(criteria)
        persisted, excluded = extractor.persist_criteria(
            criteria,
            repository_id,
            pr_id,
            db
        )
        
        # Check for security note in AcceptanceCriterion
        security_note_in_ac = db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.repository_id == repository_id,
            AcceptanceCriterion.text.like("%shared or aligned%")
        ).first()
        
        assert security_note_in_ac is None, "Security note found in AcceptanceCriterion table"
        
        # Check total real AC rows
        acs = db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.repository_id == repository_id
        ).all()
        
        # Should have 25 ACs
        assert len(acs) == 25, f"Expected 25 AC rows, got {len(acs)}"
        
    finally:
        db.close()
