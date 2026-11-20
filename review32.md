# Stackshift 0 and stack purge (session 32, 2026-11-06 to 2026-11-09; cleaned 2026-11-17)

Status: DONE, deployed and verified. This file keeps only the conclusions that were verified. Interim states (cspec not deployed, restart pending, an invalid-XML deploy that was replaced within a minute, unsaved purge edits lost in crashes) were removed as superseded. The original is in `..\H8-review-archive\review32.md`.

"Verified" = observed on `/RVR_1998_x3 4g63t 21000011 md352553.hex.1`/`.hex.2` (language H8:BE:32:H8539F, 741 functions, 355 with calls, 1614 call sites) with read-only scripts, or with temporary changes that were rolled back and checked.

## Conclusions

1. For a callee with a known stack purge the decompiler uses extrapop = purge + model.stackshift (Ghidra `FunctionPrototype.grabFromFunction`). The H8 analyzers store the whole pop of the return instruction as the purge (`prts` 4, `rts` 2, `rte` 6), which already includes the return address. With stackshift 2 or 4 on the prototype the return address was counted twice, so the decompiler's SP drifted by +2 or +4 per call. That drift produced the `uStackNNNN = <return address>` stores.
2. The fix is `stackshift="0"` on every prototype used with an analyzer-set purge. Result on the copy: call sites with a surviving return-address store 353 -> 0 (of 1614), 0 decompile failures. No analyzer change is needed for the stores. The earlier "stackshift is not the lever" experiment was misleading because the drift accumulates down a function.
3. The cspec was later cleaned up: the eight `_ns0*`/`_ns2*` experiment prototypes were removed (26 prototypes, all stackshift 0, commit 078ee5f, deployed). A later local commit 0b5c0b0 removes `noR1kill` and `32ret_farcall` (24 prototypes); it is NOT pushed or deployed (see `todo.md`, P4).
4. Five functions had a wrong stored purge: `sat_add_s16` (12), `sat_sub_u16_clamp0` (12), `select_min_xy_triple` (16), `muldiv_u16_scaled` (2), `muldiv_s16_rounded_3op` (2). All five end with `unlk FP; prts` and pop exactly 4 bytes; callers clean up the arguments with `adds.b 8/0xc,SP`. They were corrected to purge 4 and saved (copy `.hex.1` v4; `.hex.2` is the reference copy from 2026-11-09). The earlier idea that purge 12/16 means callee cleanup was wrong. Ghidra's own `FunctionResultStateStackAnalysisCmd` and `ApplyFunctionSignatureCmd` store purges first, and the H8 analyzers never overwrite a non-zero value, so a wrong value stays unless corrected. (Whether the two `__stdcall_far_allstack_32ret_pR2` functions with purge 2 and `prts` need more than this was not separately examined.)
5. `H8PurgeEnforcementAnalyzer` ("H8 Stack Purge Enforcer", last priority) was written, tested, deployed in `h8539f-analyzers.jar` (16 entries) and ran in a real analysis: 719 functions checked, 719 correct. It corrects a mismatch only for leaf functions with depth 0 at every return; for a function with calls it only warns. `scripts\measure\CheckStackPurge.java` is the read-only audit to run on every new ROM.
6. After the cspec change, 147 of 741 functions decompiled differently (hash comparison). Seven parameter counts changed, all register inputs (R0/R1/R2); none was judged an improvement or regression except `tcu_rx_main_scheduler` 13 -> 2 (very likely an improvement). Four callers of the repaired functions (`isc_integrator_update`, `f2e0_f2ec_composite_correction_calc`, `f2ea_f2ee_composite_correction_calc`, `tcu_gear_ratio_calc`) were switched by the analysis to `__stdcall_ns_pR2` with identical decompiled bodies (inference: the wrong purges had mis-tracked SP).
7. Clean state with this cspec: all 741 functions decompile, 0 failures, 0 return-address stores. The `pcode error` at 0xf290 and 0x20849 existed before the cspec change and is not caused by it.

## table_lookup_interp @00014656 (addenda of 2026-11-10 and 2026-11-12, corrected)

The missing stack arguments of the final `axis_interp_lerp_u8frac` call were NOT a cspec or stackshift issue. The `bra:16` at 0x1469a had p-code `CBRANCH (ram,0x14729),(const,1)`, so all 117 `bra:16` sites in the RVR ROM had flow type `CONDITIONAL_JUMP` with a phantom fall-through. FIXED 2026-11-13: one `cond=0` special case in `h8539f-branch.sinc` (commit e556677, pushed); all 117 sites are now `UNCONDITIONAL_JUMP` and the ghost stack params are gone. The planned `FlowOverride.BRANCH` test was invalid (a flow override does not rewrite a CBRANCH). The 2026-11-10 addendum also noted that the decompiler ignores the stackshift attribute in one place (fspec.cc line 2563); that was not followed up. PR #9522 (far pointer join) is unrelated.

## Open (all tracked in `todo.md`)

- Other `stackshift` users in the module (argument offsets; the base `__stdcall` stack input starts at offset 4) were not checked.
- Phantom/missing stack arguments are a separate problem: the stack-origin argument count did not change with this fix (233 -> 246). See `todo.md` E6 (19 functions genuinely lack declared params) and the analyzer bugs.
- Only one ROM copy was measured; the other four ROM projects need a database upgrade to open.
- Enforcer limit: a wrong purge on a function WITH calls is reported, not fixed.

