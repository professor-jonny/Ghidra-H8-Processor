# TODO / session handoff: H8539F decompiler cleanup

Written 2026-10-26 to start a fresh conversation. "Verified" means observed in the live
Ghidra project or in the exports; "unverified" means inference. Companion note:
`todo-r0-r5-displacement-order.md` (details for item 2 below).

## State in one paragraph

Running on an UNPATCHED upstream core (master 73a102ba27, 2026-10-09, includes 920fcd6) with
the language fixes below. A patched core (branch `base_`, commit 53929579f8, = cherry-pick of
83ec213f from PR #9564) exists but is not in use. Almost all earlier "decompiler bugs"
(#9540/#9541 register0x0e, #9561 sat_add_u16 arrays, muldiv_u16_scaled crash) turned out to
come from the language's p-code shape or from project data, not from the core.

## Done (do not redo)

1. **RdN fix** (committed; hash not recorded): `mulxu.w`/`divxu.w` (18 constructors in
   h8539f-arith.sinc) used `rdNext = &Rd + 2; *[register]:2 rdNext = ...`, a pointer store into
   register space. The decompiler then lost SP tracking after the first mul/div. Now `RdN`
   (alias field over the Rd bits, `attach variables [ RdN ] [ R1 R2 R3 R4 R5 FP SP _ ]`) is
   written directly. Side effect: mulxu.w/divxu.w no longer decode with SP as destination.
2. **FP/SP displacement order**: commit fc00e4f (shared eab/eaw_disp8/16 operands) and commit
   9e0f902 (46 inline single-operand forms: tst/clr/neg/not/shifts/rotates, each with FP and SP
   variants; generic forms limited to `Rn < 6`). Address is now
   `SEGMENTOP(TP, FP + disp)` instead of `SEGMENTOP(TP, FP) + disp`.
3. **`param_fpN` parameters moved down by 2** (`Stack[6]` -> `Stack[4]`, `Stack[8]` -> `Stack[6]`, ...).
   - Cause: a `pjsr` return address is 4 bytes and `link FP` leaves FP 2 below entry SP, so the
     first pushed argument is `Stack[4]` in the callee, but 37 functions declared it at `Stack[6]`.
     Callers then read 2 bytes too high (the `+6` in `auStack_100 + 0x7d) + 6`), and callees showed
     `in_stack_00000004`. (Cause of the "param_fp" naming: unverified, likely FP-relative numbering.)
   - Applied with inline Ghidra scripts: 36 functions changed, 1 skipped (f3f0_target_state_reset_and_reload,
     fixed earlier as a test), 0 failed. All 37 start with `link FP`, use `__stdcall`, custom storage.
   - **This is project data in Ghidra project `new`, NOT in git.** A project backup was made before.
   - Scripts left in your ghidra_scripts folder: `ShiftOneParam.java`, `ListParamFp.java`,
     `ShiftParamFpAll.java`.

## Measured results (exports in test/rvr/, same regex counts on each)

| Metric | old 1 Sep | _newghidra | final | final2 (after param shift) |
|---|---|---|---|---|
| `register0x...` | 210 | 0 | 0 | 0 |
| stack arrays (`a?Stack_`) | 237 | 110 | 34 | 46 (6 functions) |
| `in_stack_...` | 251 | 330 | 340 | 163 |
| `in_stack_00000004` | - | - | 256 | 79 |
| "Restarted to delay" | 42 | 2 | 2 | 2 |
| decompile failures | 1 | 0 | 0 | 0 |
| `&stack0x...` | - | - | 14 | 21 |

Not a regression check by itself: counts only. Spot checks found no regression (see item 4).

## TODO (priority order)

1. [ ] **Save the Ghidra program** (File -> Save). Param changes were made by script. Keep the backup.
2. [ ] **R0-R5 displacement order**: convert the generic `Rn < 6` constructors (slaspec ~635-638 and
   the generic forms in h8539f-arith.sinc) to `local off:2 = Rn + disp; local a:4 = spSegment(PAGE, off);`
   (PAGE = DP for R0-R3, EP for R4/R5). Hardware-faithful per the programming manual, expected NOT
   to change stack symptoms. UNTESTED. Full plan: `todo-r0-r5-displacement-order.md`.
   Lessons: assign `spSegment(...)` to a sized local first (`local easeg:4`), then to tmp/ea;
   assigning it straight into the global gives "Could not resolve at least 1 variable size".
   Compile-check in a temp COPY of the languages folder with sleigh.exe before touching the live file.
3. [ ] **34 functions have `in_stack_` reads but no declared parameters** (final export): add parameters
   from the slots they use. Plan: script lists proposed params per function (dry list, no changes),
   you approve, then apply.
4. [ ] **Finish the disassembly-vs-decompile checks** (2 of 6 done):
   - DONE tcu_torque_converter_slip_calc: `(ushort)&V` argument is correct (assembly passes FP-0x10).
   - DONE isc_f408_correction_calc: flag==0 branch right (`sat_sub_u16(f40c, b)`); flag!=0 branch WRONG:
     assembly pushes `f40c + b`, decompile passes the 0/1 flag. Earlier exports passed `unaff_FP` in both
     branches, so not a regression. Cause unknown; decompiler p-code at the call site not yet inspected.
   - TODO isc_stepper_position_calc (stack flag replaced by global g_isc_stepper_integrator_f462),
     o2_closed_loop_fuel_trim_compute (lost a `(*mul_u16_x2_sat)()` line), the `in_ram_0000389d`/`389e`
     indirect call in the eeprom_backup_table_write_dispatch family (new, odd), function 0x30 (flag/goto
     restructure).
5. [ ] **Remaining unresolved call arguments**: 3 functions still show arrays (engine_mode_dispatch_and_f240_edge_counter,
   knock_octane_secondary_dispatch, knock_octane_trim_master_dispatch) and 21 `&stack0x...` call args.
   Two others now show small `auStack_N [2]` arrays for pushes feeding function-pointer calls
   (channel_dispatch_and_snapshot_update, status_word_table_subdispatch_group_a), probably a drawing change,
   not a new error. Optional experiment: run the patched `decompile.exe` (branch `base_`) against the project
   to see whether the vnSpacebase recursion resolves them. Only worth it if ~24 call sites matter.
6. [ ] **Check for any script that creates `param_fpN` at Stack[6]**; fix its offset or it will undo item 3 of "Done".
7. [ ] **Close #9561** ("not planned") once item 4 finds nothing worse. Comment: language built the address
   as `SEGMENTOP(TP,FP)+disp` and used pointer stores into register space; both fixed in the language; no core
   change needed. Fill in commit hashes. Re-check PR #9522 (cspec far-pointer fusing) in case it is now unneeded.
8. [ ] **Housekeeping**: tag/check branch `9561` and its stashes before deleting; condense or archive the
   review*.md notes (many superseded by the RdN/segment findings); decide which of the two new .cspec
   prototypes to keep (one is marked scratch); keep `test/rvr/*.hex.c` exports out of commits.

## Paths and tooling notes

- Repo: `C:\Users\j.brophy.CORKILLSYSTEMS\github\Ghidra-H8-Processor` (branch main).
- Live install (launched with pyghidra): `...\Downloads\ghidra_12.2_DEV_20260818\ghidra_stock`
  (languages in `Ghidra\Processors\h8\data\languages`). Keep its slaspec/sinc in sync with the repo.
- Ghidra source tree: `...\github\ghidra`, branch `base_` (patched) / clean = parent 73a102ba27.
- sleigh compile check: `...\ghidra_stock\Ghidra\Features\Decompiler\os\win_x86_64\sleigh.exe h8539f.slaspec out.sla`
  run inside the languages folder (do NOT use `-a`).
- git is not on PATH; use GitHub Desktop's bundled git.exe under `%LOCALAPPDATA%\GitHubDesktop\app-*\resources\app\git\cmd\`.
- Ghidra MCP: `list_instances`, `connect_instance` (project `new`); analysis tools must be loaded with `tool_search`;
  `set_variable_storage` cannot change storage (use a script); `run_script_inline` takes a full Java class and
  its `dry_run` actually compiles the script (it also saves it in ghidra_scripts).
- Pulsar `run-command` blocked commands until `confirm:true` was passed; the approval prompt did not appear in the
  chat panel. Worth fixing before relying on it again.
- Backups of edited language files sit beside them as `*.bak_rdnext`, `*.bak_segdisp`, `*.bak_inline`.
## From review.md (added 2026-10-26)

Source: `review.md` (last modified 2026-08-19). Its index lists the other review files and whether
each is open; several statuses predate this work.

9. [ ] **Close review15.md** (register0x0e / SP display bug, listed OPEN, root cause unknown).
   Evidence: `register0x...` 210 -> 0 in the exports, and the four bookmarked functions (0x21df5,
   0x23523, 0x26124, 0x27b9d) decompiled clean when checked this session. Cause: the #9540/#9541
   print-layer fix (920fcd6) plus the RdN and displacement-order language fixes. Update review15.md
   and mark the four `register0x0e-BADSPACEBASE` bookmarks resolved.
10. [ ] **Re-check review.md item 10** ("Unable to track spacebase fully for stack"). It lists 18 functions
   (isr_sci1_eri, isr_tpu5_*, axis_interp_lerp_u8frac, axis_lookup_interp, the div_*/muldiv_* family,
   sci1_boot_build_data_frame, weighted_blend_u8frac, ...). It ruled out the R0:R1 cspec work and EP/DP banking
   but did not consider the mulxu/divxu pointer store (RdN). Warning count went 27 -> 15 in the exports.
   Re-run that list against final2 and record what is left (likely ISRs without mul/div). The item's own untried
   idea: a `callotherfixup` that expands spSegment(TP, SP). Not implemented or tested.
11. [ ] **PR #9522 (issue #9450): `<farpointerjoin hislot joinsize>` + ActionFarPointerJoin.** Independent of the
   stack-offset fixes (it fuses a page byte + offset word pushed as two arguments into one far pointer), so it is
   NOT made redundant by this work. Status from the PR text: opt-in per prototype; only a unit round-trip test
   (testfuncproto.cc); no in-tree datatest; exercised only against the out-of-tree H8/539F module; the PR offers
   to add a datatest. Current setup: the live h8539f.cspec has 0 `<farpointerjoin>` entries, the clean core cannot
   use it, and ghidra_scripts/CheckFarPointerJoins.java does not compile on the clean core (needs the PR's
   FarPointerJoinSpec API). Decide: add an in-tree datatest as offered, or keep it patched-core-only. Compare how
   far-pointer call arguments render with and without it (plan in review3.md; table_lookup_interp family).
   Check the PR's current review state on GitHub (not visible in the fetched text).
12. [ ] **h8520.slaspec still has the pointer-store pattern**: 18 `rdNext` lines (the mulxu.w/divxu.w equivalents),
   untouched. Apply the RdN-style fix if H8/520 is used. Consider doing it once via review.md item 8
   (unify H8/520, H8/538, H8/539F onto one shared decode core).
13. [ ] **review7.md** (call-site CONCAT/extraout_ artifact audit): OPEN, checklist assembled, no function verified.
   Re-run against final2 and use it for the leftover call-argument noise (`*(ushort *)((int)&stack0x... + N)` forms).
14. [ ] **Follow the documented workflow** (review.md "Build/test workflow", ~lines 641-688): edit in the repo,
   compile, copy ALL changed language files (.sla .pspec .cspec .slaspec .sinc) to the install, run
   ReloadSleighLanguage.java; .cspec changes need a full Ghidra restart. This session edited the live install
   first and copied to the repo afterwards. As of 2026-10-26 every h8539f* source file is byte-identical between
   repo and install. The workflow's paths still name ghidra_12.0.4_PUBLIC; update them to
   `ghidra_12.2_DEV_20260818\ghidra_stock`.
15. [ ] **h8539f.sla differs**: repo copy is 2026-08-21, install copy was regenerated 2026-10-25. If the repo
   ships the .sla it predates every fix; regenerate and commit it, or note that Ghidra rebuilds it on load.
