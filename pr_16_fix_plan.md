# PR #16 Fix Plan: Add Playwright Coverage for Session Lifecycle Flows

## Overview
**PR Number**: 16
**Branch**: `codex/expand-browser-tests-for-session-lifecycle`
**Status**: `CHANGES_REQUESTED`
**Author**: mruderman
**URL**: https://github.com/mruderman/subjective-priority-driven-swarm/pull/16

This PR adds comprehensive Playwright end-to-end tests for session management lifecycle, including mocking API endpoints and testing various scenarios.

## Action Items Summary
- **Total Items**: 5
- **High Priority**: 1
- **Medium Priority**: 2
- **Low Priority**: 2

## Detailed Action Items

### 1. JSON Parsing Improvement (HIGH PRIORITY)
**Source**: Review by coderabbitai
**File**: `swarms-web/tests/e2e/sessions.spec.ts`
**Confidence**: High

**Issue**: The `parseJson` function should use Playwright's `postDataJSON()` method with robust fallback to avoid silently swallowing malformed JSON.

**Suggested Change**: Implement safer JSON parsing using Playwright's built-in parser with fallback to manual parsing.

**Code Change**:
```diff
<<<<<<< SEARCH
const parseJson = (request: Request) => {
  try {
    const fn = (request as unknown as { postDataJSON?: () => unknown }).postDataJSON;
    if (typeof fn === 'function') {
      const parsed = fn.call(request);
      return parsed ?? {};
    }
  } catch {
    /* ignore and fall through */
  }

  const data = request.postData();
  if (!data) {
    return {};
  }

  try {
    return JSON.parse(data);
  } catch {
    return {};
  }
};
=======
const parseJson = (request: Request) => {
  try {
    const fn = (request as any).postDataJSON;
    if (typeof fn === 'function') {
      const parsed = fn.call(request);
      return parsed ?? {};
    }
  } catch {
    /* fall through to manual parsing */
  }

  const data = request.postData();
  if (!data) return {};
  try {
    return JSON.parse(data);
  } catch {
    return {};
  }
};
>>>>>>> REPLACE
```

**Testing**:
```bash
npx playwright test tests/e2e/sessions.spec.ts --grep 'parseJson'
```

**Risk**: Low

---

### 2. Test Coverage Verification (MEDIUM PRIORITY)
**Source**: Review by coderabbitai
**File**: `swarms-web/tests/e2e/sessions.spec.ts`
**Confidence**: High

**Issue**: Verify test coverage is comprehensive and add any missing edge cases.

**Suggested Change**: Ensure all test scenarios are properly covered and add any missing validation.

**Testing**:
```bash
npx playwright test tests/e2e/sessions.spec.ts
```

**Risk**: Low

---

### 3. Minor Improvements Check (LOW PRIORITY)
**Source**: Comment by chatgpt-codex-connector
**File**: `swarms-web/tests/e2e/sessions.spec.ts`
**Confidence**: High

**Issue**: Address any remaining minor improvements or edge cases identified in review.

**Suggested Change**: Review and implement any remaining minor improvements suggested by reviewers.

**Testing**:
```bash
npx playwright test tests/e2e/sessions.spec.ts --reporter=line
```

**Risk**: Low

---

### 4. Implementation Verification (LOW PRIORITY)
**Source**: Comment by chatgpt-codex-connector
**File**: `swarms-web/tests/e2e/sessions.spec.ts`
**Confidence**: High

**Issue**: Verify all requested improvements have been properly implemented.

**Suggested Change**: Confirm that all feedback from CodeRabbit has been addressed.

**Testing**:
```bash
npx playwright test tests/e2e/sessions.spec.ts
```

**Risk**: Low

---

### 5. Test Scenario Validation (MEDIUM PRIORITY)
**Source**: Review by coderabbitai
**File**: `swarms-web/tests/e2e/sessions.spec.ts`
**Confidence**: High

**Issue**: Ensure all test scenarios are properly covered and add any missing validation.

**Suggested Change**: Verify comprehensive coverage of limit parameters, chat navigation, and other edge cases.

**Testing**:
```bash
npx playwright test tests/e2e/sessions.spec.ts --grep 'limit|chat|navigation'
```

**Risk**: Low

---

## Next Steps
1. **Run all tests** to ensure current implementation works:
   ```bash
   npx playwright test tests/e2e/sessions.spec.ts
   ```

2. **Apply the JSON parsing improvement** (Priority 1) if not already implemented correctly

3. **Review and run additional tests** to ensure comprehensive coverage

4. **Address any remaining feedback** from reviewers

## Files to Review
- `swarms-web/tests/e2e/sessions.spec.ts` - Main test file requiring attention

## Risk Assessment
Overall risk is **LOW**. The changes are primarily focused on improving test reliability and coverage without affecting core application functionality.

## Testing Strategy
- Run the full Playwright test suite for sessions
- Focus on edge cases and error scenarios
- Verify proper mocking behavior
- Ensure test stability and reliability