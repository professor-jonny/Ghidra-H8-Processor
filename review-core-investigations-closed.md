# Closed decompiler-core investigations (register0x0e, auStack_, sat_add_u16, muldiv, #9561)

Condensed 2026-11-17 from review15, review16, review17, review18, review19, review20, review21, review22 and review-calling-convention-regression (about 13,000 lines). Originals: `..\H8-review-archive\`. Everything here is CLOSED. #9561 is fixed by upstream Ghidra code (user, 2026-11-12; hash not recorded, `todo.md` B1). This file is built from each original's status lines, headings and corrections, so details inside their bodies are not repeated. Related: `review-9561-merge-ordering.md` (Findings 1-13), `review-summary-2026-11-12.md`, `review32.md`.

## Timeline and verdicts

| Original | Topic | Verdict |
|---|---|---|
| review15, review16 | `register0x0e` investigation and print-layer fix | FIXED. Landed 2026-08-26 as NationalSecurityAgency/ghidra #9540/#9541, plus the RdN and displacement-order language fixes. Commit id is inconsistent in the old notes (920fcd6 vs aadd7ee); not reconciled. |
| review17 | `auStack_` grouping regression after #9541 | CLOSED. Two hypotheses stayed FALSIFIED: the `RangeHint::merge` "confuse" branch, and a SEGMENTOP-exclusion gate on `gatherAdditiveBase` (the gate had a measurable effect but did not fix the grouping). The grouping was traced to `gatherOpen`/`minItems` seeding. |
| review18 | `auStack_`/`sat_add_u16`, continued | CLOSED. `RuleAddMultCollapse` hypothesis FALSIFIED. Found that `RuleLoadVarnode`'s SEGMENTOP unwrap is not recursive (the chain is three levels deep), which became commit 9561 (`RuleLoadVarnode::vnSpacebase`). A first recursive fix crashed the #9541 regression test and was reverted; unconditional `getIn(2)` on any SEGMENTOP was the likely culprit. Several of its crash diagnoses were partly wrong, including one that blamed `register0x0e_crossregister_fix.xml`. |
| review19 | `sat_add_u16` `auStack_102[128]` bug | FIXED (2026-08-31). Crash cause was unwrapped offset arithmetic overflowing a 16-bit address space. The old index gave a different attribution (displacement order, RdN pointer store, param_fpN offsets); the two were never reconciled and may both be true. |
| review-calling-convention-regression | Commit 9561 causes a new wrong-return/crash regression on functions with one SEGMENTOP-resolved stack param plus register params (`__stdcall_far_allstack`, `_32ret`) | CLOSED. Its SIGSEGV in `Merge::trimOpOutput` was fixed (see `review-9561-merge-ordering.md`). Its "root cause located, fix not working" header was stale. |
| review20 | `muldiv_*` wrong return value from 9561 | CLOSED. The "correctness regression" headline was walked back inside the file itself: the displayed name is not wrong in terms of raw computed values. |
| review21 | `muldiv_u16` handoff | CLOSED. Conclusion: a display/HighVariable naming problem; the computation was always correct. Two real fixes were made in `merge.cc` (`mergeTestBoundary`). |
| review22 | `muldiv_u16`, rewritten summary | CLOSED. Superseded the "INDIRECT merge" framing as the wrong layer. |

## Former open conflict: PARTLY RESOLVED, with a remaining defect (corrected 2026-11-17)

review21/22 said the `muldiv_u16` problem was display-only; `review-9561-merge-ordering.md` Findings 5 and 12 said the returned value was a wrong pre-division intermediate. Checked on `.hex.2` (Ghidra session of 2026-11-17) against both the decompile and the disassembly:
- `muldiv_u16` @000141ba (`__stdcall_far_allstack_pR2`): CORRECT. `mulxu.w R1,R0` gives a*b in R0:R1; if `c == 0` or the high half R0 >= c, result is 0xffff; else `divxu.w R2,R0` and the quotient in R1 is returned in R0. Decompile `(a*b) / c` with saturation matches. No `in_R1` / stack artifacts.
- `muldiv_u16_scaled` @000141dc (`__stdcall_far_allstack_32ret_pR2`): decompile is INCOMPLETE. Disassembly: N = a*c + ((b*c) >> 16) in R0:R2; saturate to R0:R1 = 0xffff:0xffff if `d == 0` or R0 >= d; else `divxu.w d,R0` (high-word quotient, remainder to R2), then `divxu.w d,R2` with R3 = low word of b*c (low-word quotient), and the result is returned in R0 (high) : R1 (low). So it returns a 32-bit value, effectively (a:b as 32-bit) * c / d. The decompiled `ushort` return keeps only the high word and drops the second divide. Evidence in the callers: in `f2ea_f2ee_composite_correction_calc` the second argument `b` of the chained `muldiv_u16_scaled` calls is a variable that is never assigned, i.e. R1 of the previous result, which the `ushort` return type hides.
- Proposed fix (NOT applied, needs your approval; changes the program): change the return type of `muldiv_u16_scaled` to a 32-bit type in R0:R1, and check whether its first two stack args (a, b) are one 32-bit value. The same check is needed for `muldiv_s16_rounded_3op` (the other `_32ret` function) and for the remaining `_32ret` helpers (`todo.md` P3).
## `_32ret` helpers checked against the disassembly (2026-11-17, read-only)

All of these take 32-bit operands as two stack words (high word first) and return a 32-bit value in R0 (high) : R1 (low). Ghidra currently types them with 16-bit parameters and a 16-bit return, so the low word and some arguments show up as `in_stack_*` variables. Stack slots are `FP+6` / `FP+8` / `FP+0xa` / `FP+0xc` (= Stack[4]..[0xa]).
- `sat_add_s16` @0001401f: really an UNSIGNED 32-bit saturating add. X = (hi@FP+6, lo@FP+8), Y = (hi@FP+0xa, lo@FP+0xc); `R1 = Xlo + Ylo; R0 = Xhi + Yhi + carry`; on carry out the result is 0xffff:0xffff. The name `_s16` is wrong on both counts (not signed, not 16-bit). Decompile shows 2 params and a `short` return.
- `sat_sub_u16_clamp0` @00014045: UNSIGNED 32-bit subtract X - Y clamped to 0 (`sub.w`/`subx.w`; on borrow R0:R1 = 0). Same operand layout. The name `_u16` is wrong (32-bit).
- `muldiv_s16_rounded_3op` @00014247: same two-stage divide as `muldiv_u16_scaled` ((a:b as 32-bit) * c / d, 32-bit result in R0:R1) plus rounding: after the second divide the remainder is doubled and, if >= d (or the doubling carries), the result is incremented; overflow saturates to 0xffff:0xffff. Decompile has 3 named params plus `in_stack_0000000a` (this is `d`, so it really has 4 stack args) and a `short` return.
- `muldiv_u16_scaled` @000141dc: see above (4 args, 32-bit return).
- Not yet checked: `select_min_xy_triple` @00014471, `div_u32_u16_rounded`, `div_s32_s16_rounded`, `div_u32_u16_sat`, `div_u16_sat`, `div_u16_rounded`. Their names suggest more of the same (32-bit operands and results).
- Proposed fix (NOT applied, needs your approval, changes the program): custom signatures with `uint` params/returns for the four above (or a 32-bit return plus the correct stack arg list), and corrected names for `sat_add_s16` -> e.g. `sat_add_u32`, `sat_sub_u16_clamp0` -> `sat_sub_u32_clamp0`. Callers then show real 32-bit chains instead of an unassigned `b`.
## Lessons worth keeping (from the originals' own notes)

- Check the project's own cspec/slaspec comments before assuming a core bug; most of the "decompiler bugs" in this chain came from the language p-code shape or project data, not the core (`todo.md`).
- Falsified, do not retry: `RangeHint::merge` confuse branch, `gatherAdditiveBase` SEGMENTOP gate, `RuleAddMultCollapse`, killedbycall for `muldiv_u16`.
- Edit review files with `run-command`/direct writes, not `str_replace` (it failed on long lines).
- Use `set disable-randomization on` in gdb; traces without it vary run to run.



