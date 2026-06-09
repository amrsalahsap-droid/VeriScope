# Consistency Verification Tests

## Test Cases

### 1. HIGH Readiness Snapshot Renders High-Confidence Recommendation
**Given:** A recommendation with `readiness_snapshot.expected_confidence = "HIGH"` and `readiness_score >= 80`
**When:** The recommendation detail page renders
**Then:**
- Health state should be "Ready"
- No "Limited Evidence" or "Needs More Evidence" warnings
- Evidence gaps should be minimal or non-critical
- AC, coverage, and test history should show as available

### 2. LOW Readiness Snapshot Renders Limited Evidence
**Given:** A recommendation with `readiness_snapshot.expected_confidence = "LOW"` or `readiness_score < 50`
**When:** The recommendation detail page renders
**Then:**
- Health state should be "Limited Evidence" or "Needs Review"
- "Limited Evidence" or similar warning should be visible
- Evidence gaps should be present
- Missing evidence signals should be displayed

### 3. Stale Input Shows Stale Banner
**Given:** A recommendation with `input_stale = true`
**When:** The recommendation detail page renders
**Then:**
- Health state should be "Stale Inputs"
- Stale banner should be visible at the top
- Banner should explain inputs changed after generation
- CTA should be "Regenerate Recommendation"

### 4. Duplicate Tests Are Deduped
**Given:** A recommendation with duplicate tests in `recommended_tests`
**When:** The recommendation detail page renders
**Then:**
- No duplicate test IDs or titles should appear in the UI
- Test counts should match unique tests displayed
- Console should log duplicate detection

### 5. Gaps/Scenarios Are Merged
**Given:** A recommendation with multiple gap sources (AC coverage, behavior coverage, missing scenarios)
**When:** The recommendation detail page renders
**Then:**
- Only one "Coverage Gaps & Suggested Scenarios" section exists
- Gaps are grouped by type (Requirement, Behavior, Scenario, Automation)
- No repeated AC text fragments as separate cards
- Section shows top 10 gaps by default with expand option

### 6. Raw Labels Are Mapped
**Given:** A recommendation with raw enum values in backend data
**When:** The recommendation detail page renders
**Then:**
- No snake_case labels visible in user-facing text
- No raw enum names like `FULL_SUITE`, `MISSING_AUTOMATED_COVERAGE` visible
- All badges use human-readable labels
- Dev console should warn if raw keys detected

## Manual Verification Steps

### TrustDesk Scenario
1. Open TrustDesk repository readiness page
2. Confirm: High Confidence Ready (score >= 80, confidence HIGH)
3. Generate recommendation for TrustDesk
4. Open recommendation detail page
5. Verify:
   - Health state shows "Ready"
   - No "Limited Evidence" warnings
   - Evidence shows as sufficient
   - All labels are human-readable
6. Add new acceptance criteria after generation
7. Refresh recommendation page
8. Verify:
   - Stale banner appears
   - Health state shows "Stale Inputs"
   - CTA is "Regenerate Recommendation"
9. Regenerate recommendation
10. Verify:
    - Snapshot updates to include new AC
    - Health state returns to "Ready" (if still high confidence)

## Consistency Checker Output

The `checkConsistency()` function logs warnings and errors in development mode:

**Warnings:**
- AC available but requirements show as missing
- Coverage available but gaps show missing automated coverage
- Raw enum keys detected in rendered data
- Legacy recommendation (no snapshot)

**Errors:**
- Confidence mismatch (HIGH confidence but critical gaps exist)
- Score/confidence mismatch (low score but HIGH confidence)
- Duplicate tests detected

## Implementation Status

- ✅ Consistency checker function created
- ✅ Dev warnings implemented (visible in development mode)
- ✅ Confidence/score mismatch checks
- ✅ Available/missing contradiction checks
- ✅ Raw key detection
- ✅ Duplicate test detection
- ⏳ Automated tests (requires test framework setup)
- ⏳ Manual verification of TrustDesk scenario
