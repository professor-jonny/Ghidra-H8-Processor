Review: h8539f Sleigh implementation vs ana.cpp (IDA H8/500 module)
====================================================================

Scope: h8539f.slaspec + h8539f-branch.sinc, h8539f-arith.sinc,
h8539f-logic.sinc, h8539f-bit.sinc, h8539f-mem.sinc, cross-checked against
source/ida-sdk-main/src/module/h8500/ana.cpp.

Completed items (fixed bugs, resolved bookmarks, retracted false leads) have
been moved to CHANGELOG.md. This file tracks only open/in-progress work.

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

1. Reference: ana.cpp addressing-mode table (byte top-nibble -> EA mode),
   carried over from the README for future decode work:
   0x60-0x6F: @aa:8, Rn            0xA0-0xAF: Rn, Rn (direct)
   0x70-0x7F: Rn, @aa:8            0xB0-0xBF: @-Rn, Rn (predecrement)
   0x80-0x8F: mov:f @(d:8,R6),Rn   0xC0-0xCF: @Rn+, Rn (postincrement)
   0x90-0x9F: mov:f Rn,@(d:8,R6)   0xD0-0xDF: @Rn, Rn (indirect)
                                   0xE0-0xEF: @(d:8,Rn), Rn (disp8)
                                   0xF0-0xFF: @(d:16,Rn), Rn (disp16)
   This matches the slaspec's own `mode` field values (10=direct, 11=predec,
   12=postinc, 13=indirect, 14=disp8, 15=disp16) nibble-for-nibble --
   reassuring, but confirm which itype/switch actually owns a given byte
   range before using this table alone to diagnose.

2. Other open items (carried over from the README, longstanding):
   - The ROM header scraper in `h8539_ecu_master_setup_new.py` only scans
     `0x0 .. MUT_OFFSET` (page 1). Embedded calibration/lookup tables that
     appear inline in page 2 code (`0x20000+`) aren't reached by the current
     scan range. Scraper needs a second range covering page 2.
   - `prtd` (far return with immediate stack pop) decodes correctly, but
     stack purge accounting isn't modelled -- functions using `prtd #n` to
     clean caller-pushed arguments will show slightly wrong stack depth in
     decompiler output. Would need a plugin equivalent to Ghidra's
     `X86FunctionPurgeAnalyzer`.
   - The decompiler may report "unable to track spacebase fully for stack"
     on some functions despite `SP24` being declared unaffected in the
     cspec, which can cause local variables to be missed or misassigned.
   - Some preserved registers (R3-R5, FP) may still appear as explicit
     push/pop in decompiler output for functions using them as
     general-purpose callee-saved registers.

3. New jump tables surfaced by auto-analysis, not yet correlated to the
   functions/switches that dispatch through them:
   Address Table bookmarks at 0x10140 (48 entries), 0x13898 (5), 0x2d8ec (40),
   0x2d9ac (8), 0x2d9ec (16), 0x2da6c (16), 0x2db2c (48).
   0x13898 and 0x2d8ec were investigated this session (see chat log/
   companion review doc) -- 0x2d8ec correlates to a genuine, XML-confirmed
   ISCV/idle-RPM dispatch structure (Desired_Idle_RPM_Neutral etc., cross-
   checked against 21000011_1997-2001_RVR_X3_Mt__4g63t_.xml); 0x13898's
   validity is still unresolved (no code xref, no clean repeating structure,
   sits in a messy byte region alongside other coincidental-looking pointer
   values -- treat with suspicion pending the Step 5d verification tool,
   item 4 below). The remaining 5 tables (0x10140, 0x2d9ac, 0x2d9ec, 0x2da6c,
   0x2db2c) have not yet been checked at all.

4. XML table verification design -- Step 5d, not yet implemented
   Community EcuFlash XML table definitions cannot be trusted blindly, and
   neither can the ROM byte-pattern scraper on its own -- both are
   independent, individually fallible signals (the scraper's "adjacent word
   delta" sanity gate is heuristic, not proof, same failure mode as
   Ghidra's built-in Address Table analyzer producing the 0x13898
   false-positive vs. the genuine SCALING_TABLE_0002D8D6 cluster at
   0x2d8ec, see item 3 above).

   Design: a new Step 5d ("XML Cross-Verification"), inserted between
   Step 5c (XML labeling) and Step 6 (auto-analysis) in
   h8539_ecu_master_setup_new.py. For each XML <table> entry: recompute
   the expected header address, run Step 8's exact byte-signature checks
   against it, cross-check the XML's declared axis RAM pointer against the
   RAM pointer actually encoded in the header bytes, run a length-bounded
   data-body sanity check using the XML's own elements x cell-size (rather
   than Step 8's open-ended scan), and check for an actual Ghidra code
   xref to the header as a third, independent corroborating signal.
   Classify each table VERIFIED / SUSPECT / REJECTED -- agreement between
   XML and scraper is corroboration, not automatic truth; disagreement
   is logged for manual review, not silently resolved either way. Only
   VERIFIED tables get their header + full data body typed as data and
   protected from Step 6 auto-analysis. SUSPECT tables get labeled but
   left unprotected and flagged in a report; REJECTED tables get no label,
   logged with reason + raw header bytes for manual adjudication.

   Full design writeup: review.md companion doc drafted this session
   (see /mnt/user-data/outputs/review.md from the same conversation) --
   covers the classification table, 1D-scalar special case (no header
   signature exists to check, defaults to SUSPECT unless corroborated),
   and open questions (axis-pointer tolerance, whether REJECTED tables
   still get a comment-only plate, manual-override list for promoting a
   SUSPECT to VERIFIED without re-running the full check). Not yet
   implemented in the script -- `verify_xml_table()` function and Step 5d
   wiring are the next concrete step.

5. 0x20640/0x20843 reachability -- low priority, does not block anything
6. Imported plate comments from old (pre-Sleigh-fix) XML export - need re-verification
   Source: RVR_1998_x3 4g63t 21000011 md352553.hex.xml (old Ghidra Program XML export,
   produced under the old/buggy Sleigh grammar before this project's fixes). All 475
   function names in that file were already confirmed present in the live program
   (imported previously via import_old_function_names.py). Additionally, 9 hand-written
   analytical plate comments (session 10, 2026-07-03) were address-verified against the
   live program this session -- all 9 target addresses still resolve to functions with
   matching names and sane (non-truncated) boundaries -- and have now been copied onto
   the live functions:
     0x18fe0  wgdc_correction_integrator_update
     0x19110  wgdc_output_clamp_f44c
     0x24680  injpw_airvol_reset_on_fuelcut
     0x2629b  idle_target_rpm_compute_f400
     0x26f82  isc_stepper_output_state_machine_eed4
     0x27cb7  startup_phase_reset_eed6_cluster
     0x28413  startup_phase_reset_eed6_eefa_bulk
     0x28fff  tcu_shift_torque_and_knock_mgmt
     0x29fba  fuel_pw_and_airvol_compute
   IMPORTANT: address-matching and boundary sanity checks confirm these comments are
   PLAUSIBLY still valid, not that their content has been RE-VERIFIED under the current
   Sleigh grammar. The analysis inside them (register/table reads, xref chains, gating
   conditions) was derived by decompiling under the OLD grammar, which is known to have
   had bugs (see CHANGELOG.md and this file's history) including at least one confirmed
   function mis-split (0x28fff, the tcu_shift_torque_and_knock_mgmt case, which is
   itself one of the 9 -- its own boundary fix should be spot-checked against the
   current live disassembly before relying on it, ironic as that is). Each imported
   comment is tagged in-place with "[IMPORTED FROM OLD XML ... NOT YET RE-VERIFIED]" so
   this is visible directly in Ghidra, not just here. Two of the nine explicitly
   document their own open items (Load1B's real steady-state writer, at 0x27cb7 and
   0x28413) which remain unresolved regardless of re-verification status.
   Action: spot-check at least the 0x28fff boundary (0x28fff-0x29c32 expected) and the
   isr_sci3_eri computed-call xref it depends on against the current live listing before
   treating any of these 9 as settled. Low priority relative to items 3/4 (address
   tables, Step 5d) but should happen before further work builds on these functions'
   documented behavior. All useful content has now been extracted from the source XML
   (test/rvr/RVR_1998_x3 4g63t 21000011 md352553.hex.xml) -- safe for the user to
   delete that file.

7. logging.txt (test/rvr/) - MUT verification log - RE-VERIFICATION IN PROGRESS,
   CONFIRMED + REFUTED(partial) sections now done
   Separate from the XML in item 6: a hand-curated, already-deduplicated summary
   (805 lines) of MUT RequestID address/semantic verification, produced session 10
   (2026-07-03) under the OLD/buggy Sleigh grammar - i.e. before the MAP3-6 dispatch
   fixes that later changed how surrounding bytes decode. Since the decoder has
   materially changed since this file was written (691 functions now analyzed with
   zero outstanding decode bugs), its claims cannot be trusted at face value and are
   being re-verified live against current disassembly + xrefs, not just imported.
   Approach taken (2026-07-12 session): rather than a blanket caveat-tag import into a
   new file, each CONFIRMED-section claim is being re-derived from live disassembly
   (never decompile_function output alone - see note below) and RequestID-table
   cross-checks, then recorded as a dated plate comment directly on the relevant
   Ghidra function(s), so the finding lives next to the code it describes.
     - CONFIRMED MUT ITEMS: ALL ~15 RequestIDs RE-VERIFIED this session (2026-07-12)
       against live disassembly + the MUT RequestID table @ROM 0x2fad0 (150 entries,
       indexed via adc_sensor_convert_single @0x171c3). All hold up under the current
       decoder: TPS, Battery, AirTemp, MAP/Boost, O2 Sensor, O2 Sensor 2, Octane Level
       (full chain), TargetIdleRPM, AirVol, InjPulseWidth, ISCSteps, WGDC (full chain),
       TCU Shift Torque Cmd, and the full Knock cluster (Sum/ADC/Var/Base/Change/
       Dynamics) - 14 of 15 confirmed. EXCEPTION: Knock Voltage (0x30 -> 0xF15C/F15D) -
       read location confirmed inside tcu_shift_torque_and_knock_mgmt, but NO WRITER
       found under any bank prefix (0x0-0x3) checked. logging.txt's claim that this is
       "written by knock/TCU handler" is NOT CONFIRMED on the write side - flagged
       in-place in Ghidra, needs further investigation (possibly a bank prefix >3, a
       computed/indirect write, or the value may not be runtime-written at all).
       Coolant Temp (0xF109/F10F) also re-checked: no writer found under bank prefixes
       0x0-0x1 either - consistent with logging.txt's own admission this one was never
       independently traced (still 4-way unreconciled, see OPEN ITEMS below).
       NOTE ON DECOMPILER RELIABILITY: several MUT-related functions
       (adc_read_sequence_b @0x15689, o2_closed_loop_fuel_trim_compute @0x237a0)
       produce decompile_function output with stack-var-as-address artifacts
       (CONCAT12/ZEXT24 garbage, spurious function names like noop_return_void/
       trap_hang) that do NOT reflect real code - this is a decompiler presentation
       issue, not a grammar bug (raw disassemble_function output for the same
       addresses is clean and correct). Use disassembly, not decompile, when
       verifying MUT-adjacent functions until this is understood/fixed.
     - REFUTED / MISLABELED: address arithmetic correct but semantic label wrong.
       BOTH items RE-VERIFIED this session (2026-07-12):
       - knock_flag (EFC2/EFC3): CONFIRMED mislabel. Both writers
         (efc2_threshold_update @0x252f9, and a second writer inside
         tcu_rx_main_scheduler @0x2b676) are throttle-position-delta detectors
         (TPS-now vs TPS-previous, @0xF13C/0xF142) - genuinely nothing to do with
         knock. Matches logging.txt exactly.
       - F17A/F17B "RPM": CONFIRMED refuted. engine_torque_pct_scale_calc (@0x2184b,
         write to F17A at ROM 0x218b8 - exact address match to logging.txt's citation)
         reads only 0xF5CA/F5CC (confirmed torque values) via div_s32_s16_rounded-style
         calls, zero RPM input anywhere in the function. Matches logging.txt exactly.
       - EFEA and F0C0 candidates: NOT YET RE-CHECKED this session - still pending.
     - CURRENTLY OPEN ITEMS (8 items): most significant is RPM's real location is
       UNKNOWN -- all three prior candidates refuted/unsupported, with a concrete
       proposed next step (re-check callers of div_u16_sat/div_u32_u16_sat/
       div_u32_u16_rounded now that more functions are named). Also: Load1B producer
       not found (only reset paths located), WGDC vs WGDCCorr relationship untraced,
       a four-way coolant-temp address conflict with none reconciled, two undecoded
       gear-config table addresses, ~140 remaining "Bad Instruction" bookmarks
       clustered at 0x10000-0x10090/0x14000-0x14e10.
     - RETRACTED DEAD ENDS: explicitly do-not-re-investigate list, including a claim
       that "0x3898[chan] dispatch table" was decoded as a generic ADC/DMA transfer
       descriptor state machine (init/start/poll/ready/done), NOT RPM-specific.
       CHECKED THIS SESSION against the live program: no function and no xrefs
       currently exist at 0x13898 (the address this file's item 3 flags as an
       unresolved/suspect address table) -- it is NOT CONFIRMED that logging.txt's
       "0x3898" is the same address as this file's 0x13898; could be shorthand for a
       different address, a typo, or a stale reference from before a boundary/label
       change. Do not treat item 3's 0x13898 as resolved by this logging.txt entry
       without independently re-deriving the dispatch-table structure against the
       current live listing.
   Also contains a documented independent verification pass (table-overlap collision
   check: 3408 -> 913 after removing a ~60-table speculative block from the MT XML)
   which is a real piece of cross-checking work, not just assertion -- but was still
   performed under the old grammar and against XML/table data that may itself need
   re-verification per items 3/4 above.
   ACTION NEEDED: this content is NOT yet imported into any tracked doc or Ghidra
   plate comment. Before importing, each claim needs the same treatment as item 6's
   plate comments -- re-verify against the CURRENT live disassembly/decompile, not
   just checked for address plausibility, since these are semantic/behavioral
   conclusions (not just names) and are more expensive to get wrong. Recommended
   approach: extract the four sections into a new tracked file (e.g.
   mut_verification_status.md) with the same "[NOT YET RE-VERIFIED under current
   Sleigh grammar]" caveat used in item 6's plate comments, rather than scattering
   into individual function comments -- this is cross-cutting MUT/RAM-address content,
   not one-function-at-a-time content. The REFUTED and RETRACTED sections are lower-
   risk to import as-is (negative results -- "don't waste time here again" -- are
   still useful even if the exact old-grammar reasoning has minor inaccuracies), but
   the CONFIRMED section's specific claims (e.g. "F17A is computed purely from F5CA/
   F5CC via div_s32_s16_rounded + clamp") should be spot-checked against a fresh
   decompile before being trusted or acted on. Source file test/rvr/logging.txt is
   safe to delete once its content is captured, same as item 6's XML.

   Final state (after two rounds of investigation and one retraction): the
   `switchD_00028b50::caseD_4` label that earlier sessions relied on to
   claim 0x20843 was a genuine live jump-table entry point is stale/orphaned
   Ghidra metadata, not a real relationship. The switch at 0x28b2f's real
   8 case targets (read directly from ROM) all land next to the switch
   itself; none near 0x20640. Zero xrefs to 0x20640. A binary-wide search
   for the address's low word inside any of the 7 known jump/address tables
   found no matches. Current best evidence: 0x20640/0x20843 are not reached
   by anything presently mapped in this binary -- but the bytes decode as
   real, deliberate-looking instructions (bpl/nop/ldm.w), not a 0xFF filler
   pattern, so this isn't simply padding either. Left the placeholder
   function (sci1_boot_switch_case4_frag_20640) in place. Open item: find
   what, if anything, actually reaches 0x20640 -- possibilities include a
   computed/indirect call not caught by current scans, a genuinely
   dead/legacy code path, or disassembler noise that happens to decode
   plausibly.

7b. continued from 7


  "new_str": "   crank-period buffer at F9A0-F9A8 (written by the confirmed-real
   isr_tpu3_tgi3a capture ISR) must be converted to RPM somewhere via a
   division operation; re-check all callers of div_u16_sat/div_u32_u16_sat/
   div_u32_u16_rounded a second time now that ~10 more functions have been
   named and decompiled since that check was last run (session 2), in case
   one of the newly-resolved functions is the missing link.

   NEW LEAD (2026-07-13 session, reopens this item): `isr_sci3_eri` (0x16956)
   is mislabeled -- it touches zero SCI/serial registers. It actually reads
   H8 timer input-capture registers (T2GR1H, T2CNTH, T4GR1H) and port P5DR,
   and computes a period-delta between successive capture edges into RAM
   0xF5DE (structurally: simple single period-delta, no missing-tooth sync
   logic -- contrast with the confirmed crank ISR isr_tpu3_tgi3a on TPU3/T5,
   which DOES implement gap-ratio missing-tooth sync against F9A0-F9A8; the
   simplicity here fits a sensor that produces one clean pulse per event,
   not a multi-tooth wheel). F5DE feeds a shift-register chain (F5DE->F384->
   F5CA->F5CC->F5CE->F5D0) into `engine_torque_pct_scale_calc` (0x2184b),
   whose \"torque\" label was itself inherited/asserted without independent
   trace -- see logging.txt session 5 citation, which only asserts F5CA/F5CC
   are \"confirmed engine torque values\" parenthetically, no trace shown.
   User confirmed the RVR's camshaft has 2 teeth: 2 pulses per cam rev,
   cam turns at half crank speed, so this reduces to exactly 1 pulse per
   crank revolution -- a genuine (coarse) engine-speed signal, not torque.
   Consistent with: (a) the ISR's simple period-delta structure (every cam
   pulse is equally valid, no sync-tooth search needed), (b) no separate
   cam-sync ISR found elsewhere in the ROM (isr_tpu3_tgi3b, the other TPU3
   channel, is PWM ch0/1 period tracking, unrelated) -- consistent with a
   batch/group-fire injection scheme on this ROM not needing one, and (c)
   downstream consumption by tcu_shift_torque_and_knock_mgmt (TCU shift/
   torque scheduling), not any injection-timing/cylinder-sync code.
   NOT YET CONFIRMED: which physical pin P5DR bit 4 (polled in the ISR) is
   wired to, per the H8/539F pspec port-5 assignment, cross-checked against
   the RVR wiring diagram -- this is the concrete next step to settle it.
   If confirmed, F17A/F17B's \"REFUTED, do not resume searching here\" status
   from the 2026-07-12 session above should be walked back -- this would be
   a real (if coarse, 1-sample-per-crank-rev) RPM-equivalent signal, and
   `engine_torque_pct_scale_calc`/isr_sci3_eri should be renamed accordingly
   once the pin mapping confirms it.",
  "description": "Add new RPM lead (cam-sensor-derived period signal) discovered this session, reopening the RPM identity open item"

8. H8/538 pattern file wired up but unverified against real H8/538 ROM data
   File: h8\data\patterns\h8538pattern.xml (new H8:BE:32:H8538F entry in
   patternconstraints.xml)
   The function-start pattern file for H8/538 is a verbatim copy of
   h8539pattern.xml (H8/539F) -- same four patterns (link FP,#imm:8/16;
   stm reglist,@-SP; prts; prtd), same hit-count claims, all of which
   actually describe the H8/539F RVR 21000011 ROM, not any H8/538 ROM.
   Comments have been corrected to say so explicitly rather than implying
   538-specific verification. H8/538 and H8/539F share the same core ISA
   and likely the same compiler prologue/epilogue idioms per NOTES.TXT, so
   this is a reasonable starting point, but needs the same verification
   pass h8539pattern.xml got (load a real H8/538 ROM, check hit counts and
   false-positive rate for each pattern) before it should be trusted.

9. Function purge accounting (`prtd`) not modeled -- see item 2's bullet
   above for the current description. Calling this out as its own item
   because it's a real correctness gap (decompiler shows wrong stack depth
   for functions using `prtd #n`), not just a cosmetic/reference one like
   the rest of item 2's list, and because it's core-decoder-adjacent
   (needs a plugin analogous to Ghidra's `X86FunctionPurgeAnalyzer`) rather
   than something item 10's core-unification port will fix for free.

10. Unify H8/520, H8/538, and H8/539F onto a single shared instruction-decode
    core, instead of three independent implementations
    Confirmed this session, via the grepable hardware manuals and IDA's own
    ana.cpp (which is a single generic decoder for the entire H8/500 family,
    never branching on chip model or mode): the full H8/500 instruction set
    (63 instructions) and control-register set (SR/CCR/CP/DP/EP/TP/BR) are
    identical across H8/520, H8/538, H8/539, and H8/539F. Only the
    memory map and peripheral register set differ per chip -- already
    correctly isolated in each chip's .pspec.
    Current state is three independent, unsynchronized implementations:
      - h8539f.slaspec (+ 5 .sinc files): the mature, actively-verified one.
        Has had the MAP5 work, the CR8/CR16 guard fix, sleep/rtd opcode
        fixes, MAP4 dispatch fixes, cmp:g cross-EA fixes, and this
        session's compile verification.
      - h8520.slaspec: a fully separate, monolithic 179KB/1827-line
        grammar with zero @include, written independently (different
        token names throughout: addrMode/instr8/special/addrByte/
        addrLong/pageByte vs h8539f's opcode/opcode_special/map4/map5/i8/
        i16/eab_*/eaw_*). Confirmed this session to still have the exact
        same CR8/CR16 unguarded-fallback bug (BUG 7) that was found and
        fixed in h8539f.slaspec -- bare `& CR8`/`& CR16` constructors with
        no index constraint in its stc/ldc/andc/orc/xorc forms (lines
        842-857, 1019-1020, 1030-1031, 1041-1042, 1074-1091). `sleep`
        appears entirely absent (grep for "sleep"/"SLEEP" returns zero
        matches) -- needs checking whether that's a gap or just a naming
        difference. Other known h8539f bug categories (MAP4 dispatch gaps,
        cmp:g cross-EA gaps, the rtd/bra collision) have not yet been
        checked against it.
      - h8538f.slaspec: essentially an empty stub (40 lines, one dummy
        `:MOV.W is op8=0x5f {}` constructor, 16-bit-only address space, no
        24-bit FP/SP extension). Not usable as-is.
    Decision (this session): hold off on porting until h8539f's own open
    items are fully resolved, since a unification done now would just be
    porting known-incomplete work. Once h8539f is stable, the plan is to
    factor its branch/arith/logic/bit/mem .sinc files out as the shared
    canonical core, with each chip keeping only a thin .slaspec wrapper
    (register/address-space setup + @include) and its own .pspec. This
    will retroactively fix h8520's CR8/CR16 bug and everything else h8520
    independently diverged on, without hand-porting each fix individually.
    Two things intentionally NOT yet resolved and out of scope for the
    port itself:
      - Which operating mode (minimum/maximum) the real H8/538 and H8/520
        target ROMs actually run in. Confirmed this doesn't affect the
        shared instruction-decode grammar (ana.cpp/emu.cpp treat page
        registers as IDA-style tracked segment registers -- minimum mode
        is just maximum mode with them pinned at 0), but it does affect
        each chip's .pspec context-register defaults, which stay
        chip-specific after the port.
      - A completeness audit of h8520.slaspec against h8539f's .sinc
        files hasn't been done yet -- the datasheet says the ISA is
        identical, but that hasn't been mechanically verified instruction-
        by-instruction, so there's a small chance something genuinely
        520-specific would need preserving rather than dropped in the
        swap-over.

Priority
--------
Item 4 (Step 5d XML verification) is the highest-leverage next step -- it's
the tool needed to systematically resolve item 3's five uninvestigated
address tables instead of manually re-deriving each one. Item 5 is confirmed
low priority and doesn't block anything else. Items 1 and 2 are reference
material and longstanding carryover items. Items 6, 7, and 8 are
lower-priority re-verification/import housekeeping (items 6/7 for
old-grammar-era documentation, item 8 for the newly-wired but unverified
H8/538 pattern file). Item 9 (function purge) is a real correctness gap,
independent of everything else, worth picking up whenever there's bandwidth
for a self-contained analyzer-style task. Item 10 (single-core unification)
is intentionally deferred -- explicitly NOT started yet, on hold until the
rest of this file's h8539f-specific items are resolved, so the eventual
port carries forward a clean, fully-verified core rather than known-open
bugs.

Build/test workflow (Sleigh compile + deploy) -- reference, add once, stop asking
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
3. Copy the compiled .sla into the Ghidra install so it can be tested there:
   Copy-Item "...\github\Ghidra-H8-Processor\h8\data\languages\h8539f.sla" "...\ghidra_12.0.4_PUBLIC\Ghidra\Processors\h8\data\languages\h8539f.sla" -Force
4. Test in the Ghidra project as normal (reanalyze / re-open the program to pick up
   the new .sla).
5. Safety net: if a bad compile or bad copy breaks the installed language, just
   delete the .sla in the Ghidra install languages folder above -- Ghidra
   regenerates it from the baseline/source shipped there. Nothing is unrecoverable.
