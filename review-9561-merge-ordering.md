# #9561 / muldiv_u16_scaled merge-ordering investigation (2026-09-08 to 2026-09-15; cleaned 2026-11-17)

Status: CLOSED / HISTORICAL. #9561 is fixed by upstream Ghidra code (user, 2026-11-12; the upstream commit hash is not recorded, see `todo.md` B1). The original 1,300-line file (findings out of order, four overturned hypotheses, temporary-diagnostic notes for a private core build) is in `..\H8-review-archive\review-9561-merge-ordering.md`. Surviving conclusions are also in `review-summary-2026-11-12.md`. The earlier history this file replaced is `review-calling-convention-regression.md`.

## What was real

1. **SIGSEGV in `Merge::trimOpOutput` (`merge.cc`): fixed.** `PcodeOp::getOpFromConst(op->getIn(1)->getAddr())` on a `CPUI_INDIRECT` could decode a stale IOP pointer to a deleted PcodeOp, which `Funcdata::opInsertAfter` then dereferenced. The fix used `indirectSource->isDead() ? op : indirectSource` as the insert position (11 lines added, 2 removed). Its fallback position was the direct cause of a use-before-define ordering defect for `muldiv_u16_scaled` (Finding 3: `isDead()` true there; this confirmed the mechanism for that function).
2. **For `muldiv_u16` the `isDead()` branch is not the cause** (Finding 1: `isDead()` is false for both of its INDIRECTs).
3. **The INDIRECT on `register:2` at 0x141c2 is correct, conservative decompiler behaviour** (Findings 12-13). It comes from `Heritage::guardStores` (`heritage.cc` 1539-1560): a STORE with a not-yet-resolved pointer into the same space gets an INDIRECT on every heritaged range. The "free" STORE pointer seen in the trace was only an early heritage pass (`heritage()` ran 12 times for this function). It is not a bug in `heritage.cc`.
4. **Hardware facts (datasheets, still true):** `PJSR` pushes PC then CP (two words); `PRTS` pops CP then PC; `LINK FP,#0` pushes the old FP. `muldiv_u16_scaled` (0x141dc, 13 call sites) is genuinely reached by a static `pjsr @0x141dc:24`; the `[COMPUTED_CALL]` flag in Ghidra's xref list is only its classification of `pjsr @absolute:24`.

## What was wrong (do not reuse)

- **Finding 4 (killedbycall for `muldiv_u16`): falsified by experiment.** The scratch prototype `__stdcall_far_allstack_noR1kill` was a leftover of it (removed in local commit 0b5c0b0).
- **Findings 6, 7, 8 (offset 4 vs 6, "one stack word too early", the six-function table): all overturned** by later findings. Finding 8's "working" counterexample `FUN_0001400f` has zero callers and was never a counterexample.
- **Findings 9-11 conclusion `extrapop=6` / pentry `offset=6`: superseded.** The datasheet part is right, but it mixed FP-relative and entry-SP-relative offsets. `link FP,#0` leaves FP = entry SP - 2, so the first argument at FP+6 is `Stack[4]` (confirmed from p-code later), so `offset="4"` is the right pentry offset; the stack-model fix that was verified is `stackshift="0"` with purge 4 (see `review32.md`). The prototype `__stdcall_far_allstack_32ret_farcall` built on it was removed in commit 0b5c0b0 (local, not pushed). (Inference, not re-tested: `in_stack_00000004` in the Finding 11 decompile was then the first real argument, not "the CP word".)
- **The statement that `muldiv_u16`/`muldiv_u16_scaled` return the wrong value** (the "output is confirmed wrong" status of 2026-09-14) is no longer open: #9561 is fixed upstream. Per `todo.md`, the origin of these wrong displays was the language p-code shape and stale project data, not the core. Checked 2026-11-17 on `.hex.2` against the disassembly: `muldiv_u16` is correct; `muldiv_u16_scaled` still decompiles with a `ushort` return although it returns a 32-bit R0:R1 value (the low word is lost), so the old "wrong value" concern is only partly gone (see `review-core-investigations-closed.md`).
- **The closing "next step" (pursue `cover.cc` / `merge.cc` for the final register:2 selection) is not open.**

## Still unverified

- What actually removed the wrong displays is not established: candidates are the upstream #9561 fix, the five purge corrections in `review32.md` (including the two `muldiv_*` functions that had purge 2), the cspec stackshift 0 change, and the `bra:16` fix.




