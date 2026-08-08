                                                                                                                  # Frontend PR Package Readiness Validation

This document describes the validation logic for the 5 required UI states for Input 1 PR Package Readiness.

## State 1: Ready

**Input:**
- head SHA exists
- changed files count > 0
- snapshot current

**Expected UI:**
- PR Package: Ready (green badge)
- Head SHA visible (e.g., "abc123d")
- Changed files visible (e.g., "6 files")
- No blocker warning
- Generate Confident Regression Plan enabled (green button)
- Readiness badge: "High Confidence Ready" or "Ready"

**Validation Points:**
- `pr_package.readiness.status === "READY"`
- `pr_package.head_commit_sha` is present and non-empty
- `pr_package.changed_files_count > 0`
- `pr_package.snapshot.is_stale === false`
- CTA button shows "Generate Confident Regression Plan" with positive tone
- No warning banners displayed

## State 2: Missing changed files

**Input:**
- head SHA exists
- changed files count = 0

**Expected UI:**
- PR Package: Blocked (red badge)
- Changed files missing warning ("CHANGED_FILES_MISSING")
- Targeted/risk-based confidence blocked
- Sync PR Changes First shown (warning button)
- Helper text: "Changed files/head SHA are required for confident targeted regression."

**Validation Points:**
- `pr_package.readiness.status === "BLOCKED"`
- `pr_package.readiness.blockers.includes("CHANGED_FILES_MISSING")`
- CTA button shows "Sync PR Changes First" with warning tone
- Warning banner displays "Changed files are missing"
- Generate button is disabled or shows resolve action

## State 3: Missing head SHA

**Input:**
- head SHA missing
- changed files exist

**Expected UI:**
- PR Package: Blocked (red badge)
- Head SHA missing warning ("HEAD_SHA_MISSING")
- Freshness cannot be calculated warning
- Sync PR Changes First shown (warning button)
- Helper text: "PR head commit SHA is missing. Test freshness cannot be calculated."

**Validation Points:**
- `pr_package.readiness.status === "BLOCKED"`
- `pr_package.readiness.blockers.includes("HEAD_SHA_MISSING")`
- CTA button shows "Sync PR Changes First" with warning tone
- Warning banner displays "PR head commit SHA is missing"
- Head SHA display shows "N/A"

## State 4: Outdated recommendation

**Input:**
- current PR SHA != recommendation snapshot SHA

**Expected UI:**
- Recommendation Outdated (orange banner)
- Old SHA and new SHA visible
- Regenerate Recommendation CTA visible (caution button)
- Helper text: "PR has changed since this recommendation was generated."

**Validation Points:**
- `pr_package.snapshot.is_stale === true`
- `pr_package.snapshot.stale_reason === "PR_UPDATED_AFTER_RECOMMENDATION"`
- StaleRecommendationBanner component is displayed
- CTA button shows "Regenerate Recommendation" with caution tone
- Both old SHA (snapshot_head_sha) and new SHA (current_head_sha) are visible

## State 5: Patch warning

**Input:**
- changed files exist
- patch missing/truncated

**Expected UI:**
- PR Package: Ready with warning (yellow badge)
- Patch details unavailable warning ("PATCH_MISSING" or "LARGE_DIFF_TRUNCATED")
- Generate Draft Recommendation or Generate with Limited Confidence
- Helper text: "Changed files were found, but patch details are unavailable. Impact analysis may be less precise."

**Validation Points:**
- `pr_package.readiness.status === "PARTIAL"` or `"READY"` with warnings
- `pr_package.readiness.warnings.includes("PATCH_MISSING")` or `"LARGE_DIFF_TRUNCATED"`
- CTA button shows "Generate Draft Recommendation" with caution tone
- Warning banner displays patch warning
- Changed files are still visible and expandable

## Component Integration Validation

### PRPackageSummaryCard
- Renders correctly with compact and full modes
- Shows status badge with correct color (green/yellow/red/orange)
- Displays head SHA when available
- Shows changed files count
- Expandable changed files list works
- Blockers and warnings are displayed

### InputReadinessBanner
- Shows correct status icon (CheckCircle/AlertTriangle/XCircle/RefreshCw)
- Displays appropriate message based on status
- Color coding matches status

### StaleRecommendationBanner
- Only displays when `snapshot.is_stale === true`
- Shows both old and new SHAs
- Regenerate button is clickable

### MissingInputWarning
- Displays correct message for each warning type
- Color coding matches severity (red for blockers, yellow for warnings)

### Button Behavior (CTA Resolver)
- `resolveRecommendationAction` returns correct action type
- Button label matches expected state
- Button tone (positive/caution/warning/neutral) matches state
- Helper text is appropriate for the state

## Test Coverage

To validate these states, the following test scenarios should be implemented:

1. **Ready State Test**
   - Mock API response with complete PR package
   - Verify all UI elements are present and correct
   - Verify CTA button is "Generate Confident Regression Plan"

2. **Missing Changed Files Test**
   - Mock API response with `changed_files_count = 0`
   - Verify blocked status and warning banner
   - Verify CTA button is "Sync PR Changes First"

3. **Missing Head SHA Test**
   - Mock API response with `head_commit_sha = null`
   - Verify blocked status and warning banner
   - Verify CTA button is "Sync PR Changes First"

4. **Outdated Recommendation Test**
   - Mock API response with `snapshot.is_stale = true`
   - Verify stale banner is displayed
   - Verify CTA button is "Regenerate Recommendation"

5. **Patch Warning Test**
   - Mock API response with `warnings.includes("PATCH_MISSING")`
   - Verify warning banner is displayed
   - Verify CTA button is "Generate Draft Recommendation"

## Manual Validation Checklist

- [ ] Ready state displays correctly with all elements
- [ ] Missing changed files shows blocked state
- [ ] Missing head SHA shows blocked state
- [ ] Outdated recommendation shows stale banner
- [ ] Patch warning shows warning banner
- [ ] Button labels change correctly for each state
- [ ] Button colors change correctly for each state
- [ ] Helper text is appropriate for each state
- [ ] No contradictory "High Confidence Ready" when blocked
- [ ] PR package card expands/collapses correctly
- [ ] Changed files list displays correctly
- [ ] TypeScript types match API contract
