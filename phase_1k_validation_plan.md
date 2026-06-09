# Phase 1K — Real User Flow Validation

## Test Environment
- Repository: TrustDesk
- PR: "Implement modern password validation rules and fix test suites"
- Frontend: http://localhost:3000
- Backend: http://127.0.0.1:8000

## Test Scenarios

### Step 1: Navigate to TrustDesk Repository
1. Open http://localhost:3000
2. Login if required
3. Navigate to the TrustDesk repository
4. Verify the PR "Implement modern password validation rules and fix test suites" is visible

**Expected Result:** Repository page loads with PR list visible

---

### Step 2: Verify JUnit + Coverage are Uploaded
1. Check if test history shows recent JUnit uploads
2. Check if coverage data is available
3. Verify behavior/journey/architecture signals are present

**Expected Result:** 
- Test history shows uploaded JUnit files
- Coverage data is available
- Behavior/journey/architecture signals are detected

---

### Step 3: Click View/Generate Recommendation
1. Click on the PR "Implement modern password validation rules and fix test suites"
2. Click "Generate Recommendation" or "View Recommendation" button

**Expected Result:** Recommendation generation starts or readiness gate appears

---

### Step 4: Confirm Readiness Gate Appears Before Recommendation
1. Verify that a readiness gate modal/panel appears BEFORE the recommendation page
2. The gate should show available and missing signals

**Expected Result:** Readiness gate is displayed, not the recommendation page directly

---

### Step 5: Verify Available Signals
Check that the following signals are marked as AVAILABLE:
- [ ] PR diff
- [ ] Source code
- [ ] JUnit
- [ ] Coverage
- [ ] Behavior/Journey/Architecture

**Expected Result:** All 5 signals are shown as available with green checkmarks

---

### Step 6: Verify Missing Signals
Check that the following signals are marked as MISSING:
- [ ] Acceptance Criteria (AC)
- [ ] Current PR execution (if JUnit not linked to PR head SHA)
- [ ] Manual tests (optional)

**Expected Result:** AC is marked as required/missing, current PR execution may be missing, manual tests optional

---

### Step 7: Click Paste Acceptance Criteria
1. Click the "Paste Acceptance Criteria" button in the readiness gate
2. A modal should appear with a text area

**Expected Result:** AC paste modal opens with text input field

---

### Step 8: Paste Sample AC Text
Paste the following acceptance criteria:
```
- Weak passwords are rejected.
- Strong passwords are accepted.
- Signup form shows password validation error.
- Reset password flow enforces same policy.
```

**Expected Result:** Text is pasted into the modal

---

### Step 9: Confirm Readiness Improves
1. Click "Save" or "Continue" in the AC modal
2. Observe the readiness gate update
3. Check that "Acceptance Criteria" is now marked as available
4. Check that the confidence level increases (e.g., from LOW to MEDIUM)

**Expected Result:** 
- AC is now available
- Readiness score improves
- Confidence level increases

---

### Step 10: Continue to Recommendation
1. Click "Generate Recommendation" or "Continue" button
2. Wait for recommendation to generate

**Expected Result:** Recommendation page loads

---

### Step 11: Confirm Recommendation Page Layout
1. Check the top of the recommendation page
2. Verify that it does NOT begin with:
   - Outcome Status
   - "Was this recommendation useful?" feedback
   - Post-Merge Outcome
3. Verify that it DOES begin with:
   - Executive Summary
   - Must-Run Tests
   - Other value-first sections

**Expected Result:** Value sections appear first, feedback sections appear at the bottom

---

### Step 12: Confirm Missing-Input Warnings are Compact
1. Look for warnings about missing inputs
2. Verify they are in a compact format (not large alert boxes)
3. Verify there are no duplicate warnings

**Expected Result:** 
- Warnings are compact (single line or small box)
- No duplicate warnings for the same missing signal
- Warnings show "Improve inputs" link

---

### Step 13: Confirm Attach Current PR Test Results Upload Path
1. Look for "Attach Current PR Test Results" button/section
2. Click it
3. Verify upload options appear:
   - Upload JUnit XML for this PR
   - Select historical test run
   - Continue without current execution

**Expected Result:** Upload modal appears with all three options

---

### Step 14: Test Upload JUnit XML Option
1. Click "Upload JUnit XML for this PR"
2. Select a JUnit XML file (or verify the file picker opens)
3. Verify upload progress or success message

**Expected Result:** File picker opens, upload succeeds with success message

---

### Step 15: Confirm Improve Accuracy Actions
1. Look for "Improve Accuracy" panel or actions
2. Verify actions are either:
   - Working (clickable and functional)
   - Hidden if all signals are available

**Expected Result:** Actions are either functional or appropriately hidden

---

## Defect Documentation

### UX Defects Found
*(Document any UX issues discovered during testing)*

| ID | Description | Severity | Steps to Reproduce |
|----|-------------|----------|-------------------|
|    |             |          |                   |

### Backend Defects Found
*(Document any backend issues discovered during testing)*

| ID | Description | Severity | Steps to Reproduce |
|----|-------------|----------|-------------------|
|    |             |          |                   |

---

## Final Assessment

### PASS/FAIL Criteria
- [ ] Readiness gate appears before recommendation
- [ ] Available signals are correctly identified
- [ ] Missing signals are correctly identified
- [ ] Pasting AC improves readiness
- [ ] Recommendation page layout is correct (value first)
- [ ] Warnings are compact and not duplicated
- [ ] Attach Test Results upload path works
- [ ] Improve Accuracy actions work or are hidden
- [ ] No critical UX defects
- [ ] No critical backend defects

### Overall Result: _____ (PASS/FAIL)

### Notes
*(Any additional observations or comments)*
