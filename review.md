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
   mode field (via o2_sensor_control_dispatch). bit13 (P6DR.2): CHECKED
   2026-07-23 via xref trace (corroborates a prior 2026-07-22 byte-pattern
   sweep) -- no directly-encoded writer exists anywhere in this ROM
   (mirror_status_f0e6_to_ports reads/forwards it to P6DR.2 faithfully, but
   nothing else touches bit 0x2000). Consistent with this ROM's known
   static-analysis blind spot for bank-prefixed/indirect RAM writes -- not
   proof no writer exists at all, just that none is reachable via a literal-
   address instruction. Low priority to pursue further absent a new lead.
   Separately, SCI1 cmd 0xCD sets f510 bit13 (a different bit13, different
   RAM word, read by o2_upstream_enable_check) -- a fourth SCI1-reachable
   actuator chain, but it doesn't terminate in a physical pin the way the
   other three do.

2. Address table / table-of-tables cleanup -- CLOSED (2026-07-21), one
   thread still open. 0x13898 was a false-positive 2-genuine-pointer +
   3-junk-word cluster, not a real dispatch table (no xref to it or its two
   real function pointers anywhere). Other bookmarks resolved: 0x2d8ec is a
   genuine ISCV/idle-RPM dispatch structure; 0x2d9ac/0x2d9ec/0x2da6c/0x2db2c
   are a real calibration-table catalog (see in-place Ghidra bookmarks,
   category "H8539F-Analysis"). RESOLVED 2026-07-23: 0x10140 is not a
   separate mystery address at all -- it's just an ordinary row inside the
   H8 interrupt vector table, which actually runs from ~0x10100 through past
   0x10152 (item 11's sweep had only confirmed the back portion,
   0x10152-0x12170, as the repeating f9c4/f9ba pointer run; the front
   portion, 0x10100-0x10151, is the same 4-byte-pointer-per-vector table
   with varied real targets). Read raw bytes directly: entries at this
   address and its neighbors are 24-bit pointers (00 01 xx xx format) to
   confirmed real code -- 0x15197 is the ROM's own entry()/reset handler,
   0x1682b is isr_tpu5_tgi5a_sci1_rx_poll (one of item 10's 18
   spacebase-warning functions), 0x18865/0x18871/0x18872 are further real
   targets. Repeated entries pointing back to entry() are simply unused
   vectors falling back to the reset handler, standard practice. No further
   action needed -- purpose was always "interrupt vector," Ghidra's
   `pointer`/no-xref classification at this one address was just an
   analysis gap in an otherwise-already-identified table region, not
   evidence of anything unusual.

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

4. 0x20843 reachability -- REVISED (2026-07-23): this is the `bpl` branch
   target from sci1_boot_switch_case4_frag_20640 (0x20640). Confirmed real
   instruction, not dead/blank space or a missing grammar family (see below
   for the two now-superseded theories tried first).

   Full byte decode against ana.cpp, confirmed correct: FF 12 3C B7 9C 1D ->
   `divxu.w @(0x123C:16,SP), SP` (or similar register pairing) -- byte 1
   (0xFF) is a MAP4 escape (A2tail[9]=MAP4) with ds16 16-bit-displacement
   addressing (register = code&7 = 7 = SP); bytes 2-3 (12 3C) are the
   0x123C displacement; byte 4 (0xB7) resolves via A4tail[(0xB7>>3)-4] =
   A4tail[18] = H8500_divxu.

   SUPERSEDED THEORY 1 (grammar gap): initially looked like the Sleigh
   grammar only implements MAP4 for opcode47=14 (0xE0-0xEF, 8-bit
   displacement) and is missing an opcode47=15 (0xF0-0xFF, 16-bit
   displacement) mirror. WRONG -- the EA-addressing infrastructure
   (eab_disp16/eaw_disp16, mode=15) is already generic across all of
   mode=10-15 and does not need a MAP4-specific opcode47=15 family; see
   h8539f.slaspec's "BUG 4b" comment (~line 813-824), which already found
   and removed a MAP4-only 0x80-0x9F duplicate block for the same reason.

   SUPERSEDED THEORY 2 (missing divxu.w EA form): checked h8539f-arith.sinc
   directly -- `:divxu.w eaw_disp16,Rd is eaw_disp16; opcode=23 & Rd { ... }`
   (line 716) ALREADY EXISTS in source and should cover this exact
   instruction. Also wrong as a diagnosis of "nothing is written" -- the
   constructor is present.

   ACTUAL OPEN BUG: despite that constructor existing in h8539f-arith.sinc,
   Ghidra still fails to disassemble real bytes at 0x20843 (re-disassembling
   both 6 and 8 bytes at this address only ever produces a 1-byte undefined
   function body -- confirmed twice, same result). This means the compiled
   .sla does not actually match this byte pattern at runtime, even though
   the source text looks correct -- the same "compiles fine, doesn't match
   live ROM bytes" failure class as BUG 5 (h8539f.slaspec ~line 693-695:
   "Chaining ... compiles (no error) but does not match at runtime"). BUG 5's
   root cause there was byte-1-scoped tokens (eab_direct/eaw_direct) not
   shifting to byte 2 despite an intervening subtable -- the MAP4 path here
   is a similar or deeper multi-byte layering (byte1 MAP4 escape -> ds16
   payload -> byte4 A4tail dispatch), so eaw_disp16 (built on the plain
   byte-1-scoped `addrMode` token) may be colliding with, or never actually
   reached along, the real MAP4 control-flow path the compiler generates.

   TO FIX: trace the compiled .sla's actual decision tree for this byte
   pattern (not just the .sinc source text) to find where the real
   MAP4-then-divxu path diverges from what eaw_disp16/opcode=23 expects to
   match against. Likely needs the same fix pattern as BUG 5 (a
   byte-position-scoped duplicate token/subtable, e.g. an "eaw_disp16_map4"
   analogous to the existing _2-suffixed byte-2-scoped forms) rather than
   reusing the plain eaw_disp16 subtable as-is inside the MAP4 dispatch
   path. After fixing, re-run the build/test workflow below and
   re-disassemble 0x20843 (currently a stuck 1-byte FUN_00020843 stub) to
   confirm a real multi-byte divxu.w instruction is produced instead.

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
       page-banking work in item 9.
   FIXED (2026-07-23): sci1_periodic_phase_dispatch_f526's body was wrongly
   absorbing 0x2800c-0x28b51 (2.9KB before its own entry at 0x28b2f) due to
   a stale computed-jump xref from the switch at 0x28b50 -- same root cause
   as the earlier sci1_boot_switch_case4_frag_20640/0x20640 fix (see git
   history). Verified via the actual jump-table bytes at 0x28b52 (8 entries,
   all in 0x28xxx, matching the plate comment) that 0x2800c was never a real
   target. Deleted and recreated the function at 0x28b2f; body is now
   correctly 0x28b2f-0x28b51 (79 bytes), matching the 8-entry switch. The
   freed-up region 0x2800a-0x28081 turned out to contain two real,
   previously-absorbed functions (FUN_0002800a, FUN_00028038/now
   FUN_00028082 after further splitting) -- see new item 11 below.
   FUN_0002f490 CHECKED 2026-07-23: NOT an orphaned duplicate function --
   it's unprogrammed 0xFF flash filler (64 bytes read, all 0xFF), same
   category as the other confirmed-blank regions in item 11. The stale
   xref from the switch at 0x28b50 pointing to it is a leftover of the
   exact same stale-computed-jump-xref bug already fixed for this switch
   (0x2800c) -- the real jump table at 0x28b52 (read directly, 8 words) only
   targets 0x28b62/8b89/8ba8/8c5a/8c78/8c83/8cba/8cc8, all in 0x28xxx, none
   at 0x2f490. Closed -- no action needed beyond noting the stale xref if a
   future cleanup pass touches this switch's xref table.
   Open: any reader for f510/f512, physical meaning of any bit, the <0xC0
   pointer table, and SCI1-vs-SCI3 reachability. Full detail
   in mut_verification_status.md.

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

11. Function-boundary / undefined-code-gap sweep (2026-07-23) -- prompted by
    the item 6 fix above. Used find_code_gaps (84 gaps ROM-wide initially) and
    manually inspected raw bytes at each gap before acting -- size/heuristic
    flags alone were not reliable (many "orphaned instruction" gaps were
    genuine 0xFF erased-flash filler or repeating-constant data tables, not
    missed code; conversely many "no orphaned instructions" gaps were real
    unbound code). Also checked for mid-function prts/rte occurrences
    ROM-wide (search_byte_patterns on 1119 and 0a0a) as a possible signal of
    wrongly-absorbed function boundaries elsewhere -- none found; every real
    rte/prts hit landed exactly at a correct function's tail. The apparent
    extra 0a0a hits were inside a data table (0x12995, an arithmetic
    progression 00/0a/14/1e...), a reminder that raw byte-pattern search
    needs manual byte inspection before acting, same lesson as item 3.

    22 new functions created and verified this session (each: dry-run,
    create, get_function_by_address to confirm sane non-overlapping bounds):
      FUN_0002800a (0x2800a, 46b), FUN_00028082 (0x28082, 60b, formerly
        FUN_00028038's absorbed tail), FUN_00027fb1 (0x27fb1, 52b),
      FUN_00024cd2 (0x24cd2, 36b) -- also caused Ghidra to auto-discover
        FUN_00024d36 immediately after it,
      FUN_00014079 (71b), FUN_000140fc (47b), FUN_0001431f (77b),
      FUN_000143e8 (69b), FUN_00014502 (9b), FUN_0001460d (72b),
      FUN_00014838 (28b), FUN_0001497b (44b, gap RESOLVED 2026-07-23 --
        see below),
      FUN_000164f8 (13b), FUN_00016505 (13b, second small function found
        immediately after FUN_000164f8), FUN_00016786 (63b),
      FUN_0001a146 (22b), FUN_0001a2d0 (22b), FUN_00022898 (85b),
      FUN_000254dd (103b), FUN_0002561d (14b), FUN_00026982 (135b),
      FUN_00027644 (143b, gap RESOLVED 2026-07-23 -- see below),
        FUN_000278ef (68b), FUN_00027bc6 (37b).
    Gap count dropped 84 -> 68 after this pass, all as expected shrinkage
    (no new gaps appeared elsewhere -- ROM-wide total is stable).

    Confirmed genuine 0xFF filler / real data tables, NOT missed code (left
    untouched): the isr/flag-check cluster's small 1-15 byte gaps
    (0x1519d, 0x175ef, 0x193ec, 0x185f3, 0x19191, 0x1a2fc, etc.), the boot
    region's 0x20d42/0x20de3/0x21edf/0x22f92/0x24e5d/0x260e5/0x28e90/
    0x28f23/0x2a930/0x2b832, and the three huge regions 0x10152-0x12170
    (repeating f9c4/f9ba-style pointer table), 0x1a49a-0x1ffff, and
    0x2cee4-0x2ffff (both confirmed 0xFF filler/reserved flash space).

    NOT YET RESOLVED, flagged as higher-risk (real, varied, non-filler
    bytes present but deliberately not touched given this region's
    documented fragility -- see item 4's BUG 5 class of issue):
      0x20208-0x202b1 (170b), 0x2031e-0x2036c (79b, borders the
        scratch_pjmp_demo experimental stub), 0x20747-0x20771 (43b),
      0x2077d-0x2077e (2b) -- all inside/adjacent to
        sci1_boot_ihex_colon_record_decode_dispatch's boot-record parsing;
      0x20134-0x2014b (24b) and 0x20a14-0x20a7f (108b) -- ambiguous,
        short/irregular byte patterns that could be small data tables
        (flash constants) rather than code, not confidently classified
        either way.
    RESOLVED 2026-07-23: 0x149a7-0x149c7 (33b) and 0x276d3-0x276fa (40b),
    the two residual slivers left by the two partial fixes above -- same
    dry-run-create-verify method as the rest of this pass. Both raw byte
    reads showed varied, non-repeating bytes (not filler); both dry-run
    creates produced clean, exact-size bodies with no overlap warnings;
    both decompile cleanly with no decompiler garbage/warnings:
      gear_indexed_table_lookup_f1fc (0x149a7, 33b) -- gear-indexed table
        lookup (uses f1fc, the same gear-index register as the SCI1
        dispatcher's EC-EF case), reads *(stack_param + (f1fc & 7)*4).
      f0f8_gated_constant_select_f3f4_neighbor (0x276d3, 40b) -- small
        mode-selected constant picker gated on f0f8 bits 4/0, structurally
        similar to the neighboring f3f4_bit2_3_4_hysteresis_gate_check
        (0x27644).
    Neither has any incoming xref yet (get_xrefs_to: none found for either)
    -- same situation as several of the other 22 functions from this pass,
    likely reached via computed/indirect calls given FUN_000149a7's own
    gear-index-table-lookup shape. Not itself concerning; call-site tracing
    not yet done for either, low priority given the physical meaning of
    f1fc/f0f8 in this context is already established elsewhere.

    TO CONTINUE: same method (read real bytes first, dry-run create,
    verify bounds against neighbors) -- do NOT run Ghidra's built-in
    "Function Start Search" analyzers over this region; per manual
    inspection during this session they add nothing for already-defined
    code and risk re-triggering the same heuristic mis-splits that caused
    the original absorption bugs (item 6, and originally
    sci1_boot_switch_case4_frag_20640/0x20640).

----------------------------------------------------------------------------------
12. Cross-binary function matching (4g63t md352553 -> w4a51 md352554, plus
    4g63t -> Evo5 stock 22580006_EVO5_Stock.hex) -- IN PROGRESS (2026-07-23).

    Evo5 UPDATE (2026-07-23, see test/functions_evo5.md for the full
    checklist): a third ROM added to this effort, and it matched
    substantially better than w4a51 -- of 721 named 4g63t functions,
    almost the entire set came back at 0.9+, with 267 landing at a perfect
    1.0 (byte-identical). Most of the 1.0 list has already been
    renamed/prototyped as a direct carry-over from the verified 4g63t
    prototypes in functions.md; remaining unchecked items cluster in the O2
    sensor mode-select family (~30 functions, 0x19b2a-0x1a37f) and the
    ISC/EGR/status-flag update cluster (~60 functions, 0x21f-0x28f range),
    plus boot/flash/SCI1 routines (0x20024-0x20e00). 18 near-1.0 matches
    (0.92-0.99) are flagged for decompile-and-verify before renaming.
    Collision pattern is the same structural one seen on w4a51 (stub/noop
    cluster, a few real function pairs landing on the same target address)
    -- confirms these are inherent ambiguities in the source ROM's own
    code shape, not ROM-pair-specific artifacts. One collision differs:
    update_max, which collided on w4a51, does NOT collide on Evo5 --
    worth cross-referencing when the w4a51 collision is eventually
    resolved. One new collision not seen on w4a51: sci_fifo_f58a_advance_
    and_load_fed3 makes the sci1_rx_frame_accumulator/fedd5_fifo_rx_store_
    byte pair into a three-way collision on Evo5. Having three independent
    ROMs now agree on function identity strengthens the case for building
    the FID database (next step c below) sooner rather than later.

    SCRIPT IDEA, NOT YET WRITTEN: a rename-only script to clear the
    remaining `[ ]` rows across functions.md/functions_evo5.md. Scope:
    Score-1.0 matches ONLY (near-1.0 and flagged collisions stay manual --
    only a 1.0 guarantees identical internal RAM/DAT addresses, see
    discussion above). Per row: rename_function_by_address(target_addr,
    source_name), optionally set_function_prototype() carried over from
    functions.md. Must NOT touch data -- no apply_data_type/create_struct/
    rename_data calls, since address/type work is only safe on addresses
    individually verified, not implied by a function rename. Flip the
    checklist `[ ]` -> `[x]` as each row is applied for an audit trail.

    Two RVR_1998_x3 H8/539F ROMs are open in the same
    Ghidra instance: the well-analyzed 4g63t ROM (md352553.hex, 719 functions,
    source of nearly every name/finding in this file and mut_verification_status.md)
    and the largely-unanalyzed w4a51 ROM (md352554.hex, 787 functions, mentioned
    in mut_verification_status.md as a candidate for cross-checking the DP=2
    pointer table on a different calibration).

    Used ghidra:bulk_fuzzy_match (source=4g63t, target=w4a51, threshold=0.9) across
    all 718 named source functions, paginated in full. Of 718, only 43 produced a
    confident, unambiguous cross-binary match -- expected, since the two ROMs are
    different calibrations/revisions, not identical images. All 43 renamed on the
    w4a51 program via rename_function_by_address:
      - 26 shared math/utility helpers (sat_add_u16, sat_sub_u16,
        sat_sub_u16_clamp0, sat_mul_u16, mul_u16_hi, div_u16_sat,
        div_u32_u16_sat, div_u16_rounded, div_s32_s16_rounded, muldiv_u16,
        muldiv_s16_rounded, mul_u16_x2_sat_alt, mul_u16_x2_sat,
        mul_u16_shr8_sat, mul_fixedpoint_8, clamp_u8, passthrough_or_sat,
        clamp_u16, get_high_byte, round_high_byte_signed, inc_if_signed_flag,
        zero_ram_range, axis_interp_lerp_u8frac_256, weighted_blend_4term_u8frac,
        axis_lookup_interp, axis_interp_lerp_u8frac) -- all score 1.0.
      - 17 named engine functions: channel_validity_gated_handler_dispatch
        (0.9567), toggle_flag_fe8b_bit4, trap_hang, isr_nmi,
        sci_fifo_f58a_advance_and_load_fed3 (0.915), isr_tpu5_tgi5b_sci1_tie_clear,
        ff0d_clear_bits5_6, adc_sensor_convert_multi, byte_sum_banked,
        sum_byte_array, memcpy_banked, boot_ram_block_copy,
        control_state_latch_prev, rpm_sync_ready_check (0.915),
        mirror_f18a_to_f18e, mirror_f406_f408_to_f40a_f40c,
        f510_f512_f00e_f514_reset.

    FLAGGED, NOT AUTO-RENAMED -- four collision/false-positive groups need a
    human decision before touching them:
      - w4a51 0x15fb2: 15 different 4g63t stub_empty_*/noop_return* names all
        fuzzy-match this one target (expected -- they're trivially identical
        empty/one-instruction stubs in the source ROM too). Suggest a single
        generic name (e.g. noop_return) rather than picking one of the 15
        arbitrarily.
      - w4a51 0x16b18: latch_request_f588 AND sci_request_latch_f58a_conditional
        both match -- not yet decompiled/compared to determine which name fits,
        or whether this is one merged function on w4a51 where 4g63t had two.
      - w4a51 0x16b61: sci1_rx_frame_accumulator AND fedd5_fifo_rx_store_byte
        both match -- same situation as above, needs decompile comparison.
      - update_max (4g63t 0x268b3, score 0.9) -> w4a51 0x14aac -- collides with
        sat_sub_u16's own 1.0-confidence match at the same address. Almost
        certainly a false positive (shape-alike code, not the same function);
        recommend discarding rather than renaming.

    NEXT STEPS AGREED, NOT YET STARTED:
      a. Set proper function prototypes (param/return types, calling convention)
         on the 43 matched functions in both ROMs -- these are shared
         library-style routines with identical signatures everywhere, so this
         is cheap and immediately cleans up decompiler output at every call site
         in both programs.
      b. Resolve the four flagged collisions above (decompile-and-compare,
         then rename or merge as appropriate).
      c. Build a Ghidra Function ID (FID) database from the source (4g63t) ROM's
         now-named function set. Function ID analysis is already enabled in this
         project's analyzer list (see item on auto-analysis re-corrupting fixed
         regions, above) but currently has no populated database to match
         against. A FID database turns this from a manual per-ROM-pair
         bulk_fuzzy_match exercise into something that runs automatically during
         normal auto-analysis on any newly-opened ROM.
      d. Validate the FID database by re-opening w4a51 fresh and confirming
         Function ID reproduces today's 43 matches (and ideally more, once
         prototypes/signatures are cleaner) without a manual fuzzy-match pass.
      e. STATED GOAL: once validated on a second known ROM, use the same FID
         database (or an expanded one covering both 4g63t and w4a51) to assist
         disassembly/naming on a genuinely UNKNOWN ROM -- this is the actual
         motivation for building it now rather than repeating the manual
         bulk_fuzzy_match step per ROM pair indefinitely.

    Also worth doing once the above is further along: identify which of the 43
    matched functions/data patterns are good candidates for struct definitions
    (e.g. the mode-shadow triplets EECA/EECC/EECE, the F5C0-C8 snapshot cluster,
    the 0x20a14 range-classification table from this session) -- these recur
    across ROMs and would give an unknown ROM's disassembly the same structural
    hints, not just function names.

----------------------------------------------------------------------------------
13. DAT_ global address renaming (2026-07-24) -- NOT YET STARTED. Distinct from
    the per-function prototype/rename work in item 12/functions_evo5.md: a single
    DAT_ address (e.g. DAT_0001f0f8) is read/written across dozens of functions,
    so renaming it improves every decompile that touches it at once, rather than
    one function at a time. Tracked separately here rather than folded into
    functions_evo5.md's checklist, since the unit of work (a global address) does
    not map 1:1 to that file's per-function rows.

    SCOPE (deliberately narrow to start): only the DAT_ addresses referenced by
    the ~85 functions typed/prototyped on the 4g63t ROM during the 2026-07-24
    functions_evo5.md session (item 12 above), not a ROM-wide sweep. Expand scope
    later once a naming convention is proven out on this set.

    Candidate clusters observed during that session (grouped by apparent role,
    inferred from the surrounding bit-check/threshold functions already named --
    NOT yet verified against ana.cpp or cross-referenced independently, treat as
    a starting hypothesis only):
      - Status/flag words with many named bit-check functions already pointing
        at them: DAT_0001f0f8, DAT_0001f0fa, DAT_0001f20e, DAT_0001f216,
        DAT_0001f224, DAT_0001f226, DAT_0001f21c, DAT_0001f33e, DAT_0001f3a4,
        DAT_0001f3f0, DAT_0001f3f2, DAT_0001f3f4, DAT_0001f490, DAT_0001f510,
        DAT_0001f512, DAT_0001f516, DAT_0001f520, DAT_0001f524.
      - Timer/counter RAM cells paired with named functions: DAT_0001ef6a,
        DAT_0001ef70, DAT_0001ef78, DAT_0001efa0-DAT_0001efd8 range (several
        distinct efXX timers/latches, each already has a dedicated
        _check/_update function name to anchor from).
      - Calibration/constant-table pointers, one per named _select/_constant_
        function (e.g. DAT_00010c22-DAT_00010d92 range) -- lower priority,
        since these are ROM-immutable lookup constants rather than live state,
        and a generic TABLE_xxx name style may fit better than a semantic one.
      - SCI1/SCI2/SCI3 channel registers confirmed genuinely parallel in item
        12's collision resolution: f588/f522/fecb (SCI1) vs f58a/f524/fed3
        (SCI2/3) -- naming these with a channel-number prefix (sci1_/sci2_)
        would make the parallel structure visible at the DAT_ level too, not
        just in the function names that already reflect it.

    METHOD, once started: use ghidra:rename_global_variable (or rename_data
    where the symbol is data-typed) one address at a time, dry_run first.
    Do NOT batch-rename by pattern-matching address ranges -- as item 3 and
    item 11 both found on this ROM, apparent groupings from one investigation
    angle can hide false positives; confirm each address's role via its actual
    xrefs/callers before committing a name, the same discipline used for the
    function-level work above.

----------------------------------------------------------------------------------
14. DP-banked CONCAT decompiler noise -- PARTIALLY FIXED (2026-07-24). Follow-on from the
    earlier bankify-macro pilot (Rn_banked R0-R3 direct-register form, disp8_banked/
    disp16_banked's live jmp @(disp,Rs) use). That pilot converted ~31 call sites (disp8_banked/
    disp16_banked/Rn_banked/Rs_banked/Rn_banked2/eab_predec/eab_postinc/eaw_predec/eaw_postinc,
    R0-R3) to call a shared `bankifyDP` macro, but the macro itself still inlined
    `(zext(DP) << 16) | zext(reg)` as raw pcode -- textbook "concatenate a 1-byte value with a
    2-byte value," so Ghidra's decompiler correctly rendered every one of those sites as
    `CONCAT12(DP, reg)`. Not a regression from the pilot, just an unfinished half of it.

    FIXED: `bankifyDP` now calls the existing `spSegment` pcodeop (`result = spSegment(DP,
    reg);`) instead of inlining the zext/shift/OR, reusing the same `<segmentop space="ram"
    userop="spSegment">` already declared in h8539f.pspec for EP/TP/FP/SP (item 9, steps 1-3b).
    DP is deliberately NOT added to `<constresolve>` -- Ghidra only allows one fully-resolved
    register per address space and TP already holds that slot -- so this doesn't constant-fold
    DP=0/1 the way the old inline pattern did, but it's a real segmented pointer, not an opaque
    CALLOTHER, and it stops emitting CONCAT12 at every DP-banked callsite. Identical tradeoff
    already proven safe for EP in step 3b.

    Verified via full ROM-wide before/after decompile diff (md352553.hex.c vs
    md352553_fix2.hex.c, RVR_1998_x3 4g63t 21000011): CONCAT total 315 -> 77 (-238); WARNING:
    count unchanged 644 -> 644 (no new decompiler warnings anywhere -- the key regression
    check); extraout_ unchanged 509 -> 509 (expected, different bug class, item 10); unaff_
    89 -> 83 (-6, bonus cleanup). Compiled clean (sleigh.bat, exit 0, only pre-existing WARN
    lines), full file set copied to the Ghidra install with matching timestamps, reload done.

    NOT YET FIXED: 77 CONCATs remain (18 CONCAT12 + 44 CONCAT11 + 15 CONCAT22), suspected but
    NOT YET CONFIRMED to trace to the separate `addr16_dp` construct (h8539f.slaspec ~line 506),
    which has its own independent inline `(zext(DP) << 16) | (addr16)` that never went through
    `bankifyDP` and was out of scope for this pass. TO CONTINUE: pull a sample of the remaining
    CONCAT12 sites in md352553_fix2.hex.c and confirm they're addr16_dp call sites (not some
    third source) before deciding whether addr16_dp needs the same spSegment treatment, and
    separately investigate what's generating the 44 CONCAT11 / 15 CONCAT22 occurrences, which
    are a different byte-width shape than anything bankifyDP or addr16_dp produces.

    PRIORITIZATION (decided 2026-07-24): finish this CONCAT cleanup (addr16_dp + the
    CONCAT11/CONCAT22 source) BEFORE starting item 13's DAT_ renaming or any struct work.
    Reasoning: renaming/typing a DAT_ address or building a struct requires trusting the
    decompile at that address; if the access still shows CONCAT/unaff_/extraout_ noise, the
    inferred type/shape may be an artifact of the addressing bug rather than the real field
    layout, risking rework once addressing is clean. The CONCAT fix is narrow, well-understood
    (spSegment pattern already proven twice, on EP and now DP-via-bankifyDP), and has a fast,
    already-working verification loop (before/after CONCAT/WARNING/extraout_/unaff_ diff), so
    it's worth closing out first rather than building item 12/13 work on top of unverified
    decompile output. Order: (1) confirm/fix addr16_dp, (2) identify the CONCAT11/CONCAT22
    source, (3) re-run the ROM-wide diff to confirm clean, (4) then resume item 13 DAT_
    renaming and struct work on trustworthy decompile output.

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
