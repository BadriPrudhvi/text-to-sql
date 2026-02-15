# /fix-bug

You are about to debug and fix a bug. Follow this systematic approach:

## Phase 1: Reproduce & Understand
1. Ask me:
   - "Paste the exact error message/stack trace"
   - "What were you doing when this happened?"
   - "What's the expected behavior vs actual behavior?"
2. Read the error carefully and identify:
   - Error type (syntax, type, runtime, logic)
   - File and line number
   - Stack trace (which function called which)

## Phase 2: Investigate Root Cause
1. Read the relevant file(s)
2. Use "think ultra hard" reasoning:
   - What does this code do?
   - What are the inputs? Expected vs actual?
   - Where could it fail?
   - Are there edge cases not handled?
3. Form a hypothesis: "I think the bug is caused by [X] because [Y]"
4. Ask me: "Does this hypothesis sound correct, or should I investigate other possibilities?"

## Phase 3: Write Reproduction Test
1. Create a minimal test that reproduces the bug:
```python
   # backend/tests/test_bug_[issue_number].py
   def test_bug_reproduction():
       # This test should FAIL before the fix
       result = buggy_function(edge_case_input)
       assert result == expected_output  # Currently fails
```
2. Run the test and confirm it fails
3. Ask me: "Test reproduces the bug. Ready to fix?"

## Phase 4: Implement Fix
1. Fix the bug with the smallest possible change
2. Add defensive checks/validations if needed
3. Update docstrings if behavior changed
4. Run the reproduction test → Should now PASS
5. Run full test suite → All tests should pass

## Phase 5: Prevent Regression
1. Keep the reproduction test (don't delete it)
2. Add additional edge case tests if bug was subtle
3. Commit with message: `fix(scope): [brief description of bug] (closes #[issue])`

## Phase 6: Document
If the bug was subtle or could recur:
1. Add a comment in the code explaining why the fix was needed
2. Update relevant documentation if behavior changed

## Rules
- NEVER fix without understanding root cause
- ALWAYS write a reproduction test first
- NEVER make unrelated changes in bug fix commits
- ALWAYS verify full test suite passes after fix