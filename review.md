Review: h8539f Sleigh implementation vs ana.cpp (IDA H8/500 module)
====================================================================

Scope: h8539f.slaspec + h8539f-branch.sinc, h8539f-arith.sinc,
h8539f-logic.sinc, h8539f-bit.sinc, h8539f-mem.sinc, cross-checked against
source/ida-sdk-main/src/module/h8500/ana.cpp.

Completed items (fixed bugs, resolved bookmarks, retracted false leads) have
been moved to CHANGELOG.md. This file tracks only open/in-progress work.
Compressed 2026-07-23 to current state only -- superseded theories, reverted
trial fixes, and session-by-session narration have been dropped in favor of
final conclusions. Git history has the full story if it's ever needed.

Verified correct
----------------
- Branch/control instructions (JMP/JSR/PJMP/PJSR/BSR/RTS/PRTS/PRTD/RTE/RTD/
  LINK/UNLK/TRAPA/TRAP:VS/SLEEP/BPT/SCB) in h8539f-branch.sinc.
- DADD/DSUB nested MAP3->MAP6 dispatch (traced byte-by-byte against ana.cpp's
  tables[] resolution loop) -- correct.
- arith.sinc: add:g/sub/subx/adds/addx (opcode 4/5/6/20/22), add:q
  (+1/+2/-1/-2), swap, btst (Rs and #imm4), clr/neg/tst/not
  (opcode_special 0x11-0x16), cmp:e/cmp:i, shal/shll/shar/shlr/rotl/rotr/
  rotxl/rotxr, mulxu/divxu, tas -- all match A3/A4/A3tail/A4tail rows.
- logic.sinc: or/and/xor EA forms (opcode 8/10/12), andc/orc/xorc CR8/CR16
  forms (opcode 9/11/13) for the MAP3/MAP4 tail groups that ARE implemented.
- mem.sinc: mov:l/mov:s/mov:e/mov:i/mov:f, ldm.w/stm (with reglist!=0 guard
  matching ana.cpp's Op2.reg rejection), xch.b/xch.w (correctly coexisting
  with mov:g store at the same opcode=18 via mode=10 vs mode=11-15 split),
  mov:g load/store/immediate forms, ldc/stc EA-sourced forms for all six
  control registers (CR8 in {1,3,4,5,7}, CR16=0).
- 0x05/0x0D/0x15/0x1D MAP4-literal-prefix family (aa8/aa16-then-dispatch):
  IS implemented (tst.b/tst.w/clr.b/clr.w via opcode_special gates, plus the
  mov:g.w literal-prefix escape) and confirmed working against the live ROM
  at multiple addresses. See CHANGELOG for the fixed cmp:"g.w"/BNOT bugs that
  came out of this investigation.

Open items
----------

1. MUT Mode5 actuator-test RequestID mapping + physical output pin ID --
   IN PROGRESS, full detail in mut_verification_status.md.
   Confirmed: output_relay_flags_f0e6 (RAM 0xf0e6) is a real 8-bit
   relay/output flag word mirrored to ports by mirror_status_f0e6_to_ports
   (0x156ce). Bits identified: bit0 (isc_f0e6_bit0_update, knock-gated, not
   SCI1-reachable), bit3 (EGR solenoid, P2DR.7 -- has two writers, one
   unconditional, their interaction not yet understood), bit4 (EGR valve
   position, P4DR.4/PCDR.6), bit6 (PCDR.7, via dispatcher cmd 0xD2), bit7
   (canister purge, P4DR.7 -- CONFIRMED forceable via SCI1 cmd 0xD1, the
   strongest real actuator-test candidate found on this ROM). Separately,
   f0e6 bits 8-11 are an unrelated O2 sensor upstream/downstream control
   mode field (via o2_sensor_control_dispatch). Open: bit13 (P6DR.2)
   untraced; SCI1 cmd 0xCD sets f510 bit13 (read by
   o2_upstream_enable_check) -- a fourth SCI1-reachable actuator chain, but
   it doesn't terminate in a physical pin the way the other three do.

2. Address table / table-of-tables cleanup -- CLOSED (2026-07-21), one
   thread still open. 0x13898 was a false-positive 2-genuine-pointer +
   3-junk-word cluster, not a real dispatch table (no xref to it or its two
   real function pointers anywhere). Other bookmarks resolved: 0x2d8ec is a
   genuine ISCV/idle-RPM dispatch structure; 0x2d9ac/0x2d9ec/0x2da6c/0x2db2c
   are a real calibration-table catalog (see in-place Ghidra bookmarks,
   category "H8539F-Analysis"). Still open: 0x10140 confirmed not a jump
   table, but its actual purpose is unresolved (low priority, doesn't block
   anything).

3. XML table verification design -- NOT YET IMPLEMENTED. Community EcuFlash
   XML table defs and the ROM byte-pattern scraper are both individually
   fallible (same failure mode as the 0x13898 false positive above), so a
   new Step 5d ("XML Cross-Verification") is designed to sit between XML
   labeling and auto-analysis in h8539_ecu_master_setup_new.py: for each XML
   <table>, recompute the expected header address, run the byte-signature
   check against it, cross-check the XML's declared axis RAM pointer against
   the one actually in the header, run a length-bounded data-body sanity
   check using the XML's own element count, and check for a real Ghidra code
   xref to the header -- plus item 2's table-of-tables catalog pattern as an
   extra corroborating signal. Classify VERIFIED/SUSPECT/REJECTED (agreement
   is corroboration, not automatic truth); only VERIFIED tables get typed
   and protected from auto-analysis. 1D-scalar tables (no header signature
   to check) default to SUSPECT unless otherwise corroborated. Not yet
   wired into the script -- `verify_xml_table()` and the Step 5d call site
   are the next concrete step.

4. 0x20640/0x20843 reachability -- low priority, does not block anything.
   Zero xrefs found from anywhere presently mapped in the binary (including
   the switch at 0x28b2f, whose real 8 case targets all land elsewhere).
   Bytes decode as real, deliberate-looking instructions (bpl/nop/ldm.w),
   not 0xFF filler, so not simple padding either. Left as a placeholder
   function (sci1_boot_switch_case4_frag_20640). Open: find what, if
   anything, actually reaches this address.

5. RPM identity -- FINAL STATE (2026-07-15). Best candidate: P54/T2IOC1,
   polled by isr_ipu_ch2ch4_input_capture (0x168e3, renamed from an earlier
   isr_sci3_eri mislabel -- it touches zero SCI/serial registers). Structural
   evidence (simple single-edge period-delta, no missing-tooth sync logic,
   unlike the confirmed crank ISR isr_tpu3_tgi3a which does implement
   missing-tooth sync) favors this being the 2-tooth camshaft position
   signal rather than crank-angle, giving 1 pulse per crank revolution (a
   real if coarse RPM-equivalent). Two independent downstream consumers
   confirmed, corroborating a genuine engine-speed signal: F5DE -> ... ->
   engine_torque_pct_scale_calc (0x2184b), and F5D6/F5D8 ->
   tcu_shift_ratio_buffer_update (0x2c16e, via tcu_periodic_dispatch
   0x2c12b). This is inference from ISR structure, not a proven pin-level
   trace -- no connector-pin-to-H8-chip-pin schematic exists for this ECU,
   so board-level wiring confirmation is closed at this confidence level;
   do not resume searching for one. Open: absolute RPM scale/units (timer
   tick rate + the 0x10 divisor's real-world meaning) not yet derived.

6. SCI1 command dispatcher (sci1_meta_cmd_dispatch_c0_ff, 0x28869) -- its
   0xC0-0xD8 actuator bit-table (ROM 0x13740) is decoded. Confirmed:
     - f516 bits 2/5/6/8 (cmds C3/C4/FA) -> f516_request_latch_f09a_calib_
       select (0x27e1a), a calibration selector for output f09a.
     - f516 bit7 (cmd FC) -> eee0_eeee_diag_flags_reset_dispatch (0x282c1)
       -> startup_phase_reset_eed6_eefa_bulk (0x28413) -- a live, on-demand
       trigger, not just a startup path. Independently corroborated by the
       user-supplied XML's own "FC = Clear EFI Diagnostic Codes" label.
     - f516 bit11 -> f588_duty_gate_f516_bit11_set (0x28b62), inside
       sci1_periodic_phase_dispatch_f526 (0x28b2f). That parent function has
       a genuine decompiler jump-table reconstruction failure
       (halt_baddata()/"Could not recover jumptable" on switch cases
       0/2/4/6) -- a real open item on its own merits, unrelated to the
       page-banking work in item 9. FUN_0002f490 looks like an orphaned
       duplicate fragment split off from the same bad region.
   Open: writer for f516 bits 1/12/13/15, any reader for f510/f512,
   physical meaning of any bit, the <0xC0 pointer table, SCI1-vs-SCI3
   reachability, and the 0x28b2f jump-table re-split. Full detail in
   mut_verification_status.md.

7. MUT BLANK/actuator sweep -- mostly resolved, full detail in
   mut_verification_status.md. Confirmed: EECA/EECC (mode-shadow copies,
   isc_eeca_eecc_eece_correction_calc), F3FB/F3FD (real low bytes of
   F3FA/F3FC, not scraper artifacts), F971/F972 (real low/high bytes of
   F970/F973, closing that cluster). Reusable technique for whoever
   continues this: per-address xref search on BLANK cells is a dead end
   (known indirect/bank-prefixed blind spot) -- search from the PRODUCER
   side instead (search_functions on "calc"/"duty"/"target"/"stepper",
   cross-check write addresses against the table), prioritizing BLANK rows
   adjacent to already-CONFIRMED cells.
   Separately (EFI/TCU XML cross-check): ReqID 0x1C/F187 = ECULoad (was
   BLANK, now fixed); ReqID 0x00 has a third conflicting claim (gmas/Airflow
   vs LoadMUT2Byte) on top of an existing GalantLegnum conflict, likely
   genuinely ROM-revision-dependent, not a single stable value. NEW SCOPE,
   NOT YET WORKED: the TCU-side XML has its own 13-entry MUT RequestID
   scheme (AT_ID1-3, AT_Temp, gear states, shaft-speed pulses, AT_Brake,
   AT_ClearDTC), entirely separate from every tcu_* function traced so far --
   no TCU-side equivalent of adc_sensor_convert_single/the 0x2fad0 table has
   been located yet.

8. Unify H8/520, H8/538, H8/539F onto one shared instruction-decode core --
   confirmed via IDA's ana.cpp (a single generic H8/500-family decoder that
   never branches on chip model) that the full 63-instruction ISA and
   control-register set are identical across all three; only the memory map
   and peripheral set differ, and that's already isolated per-chip in each
   .pspec. Current state: h8539f.slaspec is the mature, actively-verified
   implementation; h8520.slaspec is a fully independent 1827-line grammar
   with the same CR8/CR16 unguarded-fallback bug h8539f already fixed, and
   no `sleep` instruction at all; h8538f.slaspec is an empty stub, not
   usable as-is. DECISION: hold off on porting until h8539f's own open items
   are resolved, then factor the branch/arith/logic/bit/mem .sinc files out
   as a shared core with each chip keeping only a thin wrapper .slaspec plus
   its own .pspec -- this retroactively fixes h8520's divergence rather than
   hand-porting each fix individually. Intentionally out of scope for the
   port itself: which operating mode (minimum/maximum) the real H8/538 and
   H8/520 target ROMs actually run in (doesn't affect the shared decode
   grammar, only each chip's .pspec context-register defaults); a full
   instruction-by-instruction completeness audit of h8520.slaspec against
   h8539f's .sinc files (not yet done -- the datasheet says the ISA is
   identical, but that's not been mechanically verified).

9. SP24/FP24/DP/EP page-register banking vs Ghidra's stack-frame analyzer --
   STATUS (2026-07-22): Steps 1 (SP) and 2 (FP) are DONE/PASSED, verified
   live with no regressions -- both now route through a shared spSegment()
   segmentop userop instead of manual zext/shift/OR, and Ghidra's
   stack-frame analyzer correctly recognizes SP/FP again (no more
   unaff_SP/unaff_FP anywhere in the decompiled output). Step 3 (EP) is
   installed and stable but delivers no decompiler benefit for genuinely
   dynamic (non-zero, runtime-loaded) EP values: Ghidra's <constresolve>
   only accepts one register per address space, and TP already holds that
   slot for SP/FP. Verified this matches real, actively-exercised Ghidra
   x86-16 behavior, not a design gap on our side: ia.sinc calls segment()
   with SS/ES/CS throughout without any of them being in constresolve
   either. Accepted, documented limitation. DP banking: deferred, not
   converted -- a ROM-wide search found no genuinely dynamic `ldc.b Rn,DP`
   site anywhere (every DP load is either a compile-time constant or the
   already-tracked default), so there's no live repro to justify the much
   larger blast radius (every general register-indirect/displacement
   addressing mode in the ISA, not just EP's narrow R4/R5 slice). Re-run
   that search first if a future ROM or function is ever suspected of
   loading DP dynamically. h8520 port: intentionally not hand-patched
   separately -- item 8's unification plan carries the SP/FP fix over once
   it happens.

   Related, closed: an attempt to give 6 math helpers (muldiv_u16_scaled,
   sat_add_s16, sat_sub_u16_clamp0, muldiv_s16_rounded_3op,
   div_u32_u16_rounded, select_min_xy_triple) a real joined R0:R1 32-bit
   return type was tried and reverted -- confirmed unrelated to the
   spacebase-warning cluster in item 10 (three different cspec shapes for
   the prototype all produced byte-identical warnings on the same 18
   functions). These 6 helpers intentionally return plain ushort/short (the
   R1 half of the true 32-bit result is silently dropped) as a final,
   accepted limitation, not a regression to revisit. A backup of the
   R0:R1-in-place file state is kept at
   h8/data/languages/backup_20260722_pre_r0r1_revert/ if ever needed again.

   Ghidra allows only ONE<segmentop> per address space -- reuse one userop
   for multiple banked registers that share the same base/shape rather than
   declaring a second one; (3) adding a genuinely new *register*
   (not just a constructor/grammar change) needs a full Ghidra restart to
   take effect reliably.
   the live ReloadSleighLanguage.java script can silently leave stale
   Language/CompilerSpec state for compiler-spec-level changes specifically.

10. "Unable to track spacebase fully for stack" warning -- STATUS: real
    mechanism identified via live pcode inspection; no fix implemented yet;
    not upstream-filing material (same general class as Ghidra's own x86-16
    issues #817/#5199).

    Affects at least 18 structurally-unrelated functions: isr_sci1_eri,
    isr_tpu5_tci5u, isr_tpu5_tgi5a_sci1_rx_poll,
    isr_tpu5_tgi5b_sci1_tie_clear, axis_interp_lerp_u8frac,
    axis_lookup_interp, div_s32_s16_rounded, div_u16_rounded, div_u16_sat,
    div_u32_u16_rounded, div_u32_u16_sat, muldiv_s16_rounded,
    muldiv_s16_rounded_3op, muldiv_u16, muldiv_u16_scaled,
    f26e_cluster_accumulator_unrelated_to_ihex, sci1_boot_build_data_frame,
    weighted_blend_u8frac. Ruled out as causes: the R0:R1 cspec work (item 9
    above); EP/DP dynamic banking (only 3 of the 18 touch DP/EP dynamically
    at all -- the other 15, including isr_sci1_eri, don't); which return
    instruction is used (rts/prts/rte all appear on both warned and clean
    functions); default_proto vs an explicit calling convention (three
    default_proto, rte-ending sibling ISRs -- isr_sci2_eri, isr_nmi,
    isr_adi_adc -- decompile perfectly clean).

    MECHANISM, confirmed against Ghidra's actual decompiler source
    (coreaction.cc, ActionStackPtrFlow::analyzeExtraPop / StackSolver): the
    analysis only runs when a function's prototype has extrapop="unknown"
    (true for anything on default_proto in this cspec). It builds a system
    of linear equations from every stack-pointer-derived varnode, including
    CPUI_INDIRECT ops at call sites to callees whose own extrapop is
    unresolved (which get a guessed equation, not a derived one). The
    warning fires per-unsolved-variable when that system can't be solved.

    RE-DIAGNOSED VIA LIVE PCODE (2026-07-23), isr_sci1_eri specifically:
    Instruction.getPcode() on the raw SLEIGH output (before any decompiler
    analysis runs) for "stc.b EP,@-SP" shows:
      SP = SP - 1                                     (INT_SUB)
      ptr24_tmp = CALLOTHER(spSegment, TP, SP)         (unique, 4 bytes)
      tmp = COPY(EP)
      STORE(ram, ptr24_tmp, tmp)
    and the identical shape recurs for every push/pop in the function --
    both pjsr-embedded pushes and all four rte-embedded pops -- eight
    occurrences, zero exceptions. SP's own storage is clean (plain
    INT_SUB/INT_ADD, one of the solver's recognized shapes), but the
    STORE/LOAD *address* -- what the solver actually needs to resolve, to
    alias each access back to a stack slot -- is CALLOTHER(spSegment, TP,
    SP) in every case, and CALLOTHER isn't one of the solver's 5 recognized
    op shapes (INT_ADD/COPY/INDIRECT/MULTIEQUAL/INT_AND). This is the
    concrete, per-address confirmation of the general mechanism above, for
    this specific function.

    UNTRIED FIX CANDIDATE: TP is a tracked_set context register with a
    compile-time-constant default of 0. spSegment is declared only as a
    bare `define pcodeop spSegment;` (h8539f.slaspec line 323) with no
    <callotherfixup>/pcode injection defined anywhere in the .pspec or
    .cspec -- nothing currently tells the decompiler how to expand it.
    Adding a callotherfixup that expands spSegment(TP, SP) to concrete
    arithmetic (e.g. zext(SP) when TP==0, falling back to the full segmented
    form otherwise) would make the address transparent to constant folding
    and the spacebase solver in the common case, without any upstream
    Ghidra change. NOT YET IMPLEMENTED OR TESTED -- this is the next
    concrete step if pursued.

    Treated as cosmetic/expected in the meantime: decompiled output is
    still numerically correct on every function checked so far (e.g.
    isr_sci1_eri's own body decompiles to a correct, if warning-flagged,
    call+return). Revisit filing upstream only if the callotherfixup
    experiment surfaces something not already covered by #817/#5199, or if
    a function's decompiled output is ever found to be actually wrong (not
    just warned).

----------------------------------------------------------------------------------
Build/test workflow
----------------------------------------------------------------------------------
Use this every time a .sinc/.slaspec grammar change needs compiling and
testing against the live ROM. No need to re-ask for these paths again.

- Compiler:  C:\Users\j.brophy.CORKILLSYSTEMS\Downloads\ghidra_12.0.4_PUBLIC\support\sleigh.bat
- Source (edit here):    C:\Users\j.brophy.CORKILLSYSTEMS\github\Ghidra-H8-Processor\h8\data\languages
- Ghidra install target: C:\Users\j.brophy.CORKILLSYSTEMS\Downloads\ghidra_12.0.4_PUBLIC\Ghidra\Processors\h8\data\languages

Steps:
1. Edit the .sinc/.slaspec files in the github source folder (never edit the Ghidra
   install copy directly -- it gets overwritten/regenerated).
2. Compile via run-command:
   & "C:\Users\j.brophy.CORKILLSYSTEMS\Downloads\ghidra_12.0.4_PUBLIC\support\sleigh.bat" "C:\Users\j.brophy.CORKILLSYSTEMS\github\Ghidra-H8-Processor\h8\data\languages\h8539f.slaspec"
   Exit code 0 = success (WARN lines about unreferenced tables/NOP constructors are
   pre-existing and expected -- only ERROR lines or a nonzero exit code mean the
   grammar actually broke). This produces h8539f.sla next to the .slaspec source.
3. Copy ALL changed language files into the Ghidra install, not just h8539f.sla --
   BUG FOUND 2026-07-21: copying only the .sla left a stale .pspec installed (the
   .pspec/.cspec/.sinc files are read separately at runtime, not compiled into the
   .sla), which silently made a source-level fix (a new <segmentop> block) invisible
   in the already-open Ghidra project even after reanalyze/close/reopen -- wasted a
   full test cycle before the mismatch was caught by comparing file timestamps.
   Always copy the full set together:
   $src = "...\github\Ghidra-H8-Processor\h8\data\languages"
   $dst = "...\ghidra_12.0.4_PUBLIC\Ghidra\Processors\h8\data\languages"
   Copy-Item "$src\h8539f.sla"    "$dst\h8539f.sla"    -Force
   Copy-Item "$src\h8539f.pspec"    "$dst\h8539f.pspec"    -Force
   Copy-Item "$src\h8539f.cspec"    "$dst\h8539f.cspec"    -Force
   Copy-Item "$src\h8539f.slaspec"  "$dst\h8539f.slaspec"  -Force
   Copy-Item "$src\h8539f-arith.sinc"  "$dst\h8539f-arith.sinc"  -Force
   Copy-Item "$src\h8539f-bit.sinc"    "$dst\h8539f-bit.sinc"    -Force
   Copy-Item "$src\h8539f-branch.sinc" "$dst\h8539f-branch.sinc" -Force
   Copy-Item "$src\h8539f-logic.sinc"  "$dst\h8539f-logic.sinc"  -Force
   Copy-Item "$src\h8539f-mem.sinc"    "$dst\h8539f-mem.sinc"    -Force
   Sanity check after copying (both listings should show matching timestamps for
   every h8539f* file): Get-ChildItem "$src" | Select Name,LastWriteTime
   and the same command against $dst.
4. run the script  ReloadSleighLanguage.java in Ghidra to refresh the open project with the new sleigh files.
5. Test in the Ghidra project as normal
