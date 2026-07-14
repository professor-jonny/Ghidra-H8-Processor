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

2. Address Table bookmark at 0x13898 (5 entries) -- still unresolved
   No code xref, no clean repeating structure, sits in a messy byte region
   alongside other coincidental-looking pointer values -- treat with
   suspicion pending the Step 5d verification tool (item 4 below).
   The other 6 Address Table bookmarks originally listed here (0x10140,
   0x2d8ec, 0x2d9ac, 0x2d9ec, 0x2da6c, 0x2db2c) are resolved: none were
   jump/dispatch tables. 0x2d8ec is a genuine ISCV/idle-RPM dispatch
   structure; 0x2d9ac/0x2d9ec/0x2da6c/0x2db2c are a real calibration-table
   catalog (headers + findings documented via Ghidra bookmarks, category
   "H8539F-Analysis", at each address); 0x10140 is confirmed not a jump
   table but its exact purpose is unresolved/low-confidence. See those
   in-place bookmarks for detail rather than duplicating it here.
   Follow-up for item 4: Step 5d's verify_xml_table() design should be able
   to use the same 0x03/0x02 header-signature check plus this table-of-
   tables catalog pattern as an additional independent corroborating
   signal, not just the XML-vs-scraper comparison originally scoped.

3. XML table verification design -- Step 5d, not yet implemented
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

3. 0x20640/0x20843 reachability -- low priority, does not block anything
5. logging.txt (test/rvr/) - MUT verification log - RE-VERIFICATION IN PROGRESS,
   CONFIRMED + REFUTED(partial) sections now done
   Separate from the old imported-XML plate comments (previously tracked as a separate
   item here, dropped since there's no ROM available to re-verify them against --
   left to the community to re-check on publish): a hand-curated, already-deduplicated summary
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
       - EFEA: RE-VERIFIED 2026-07-14. CONFIRMED refuted. Traced the F13C/F140/DE8
         gating block in tcu_rx_main_scheduler (~0x2b0af-0x2b118): EFEA is either
         cleared to 0 or set to a fixed ROM constant (@0xDE8), gated by comparisons
         of F13C (current cycle) against F140 (previous cycle) and several
         threshold constants (DDE/DE0/DE2/DE6). Only ever read as a boolean
         (tst.w @0xEFEA, != 0) - never as a magnitude. Same throttle/load-transient
         hold-flag family as the already-confirmed EFC2 mislabel, not RPM. Plate
         comment added to tcu_rx_main_scheduler (0x2aa36) documenting this.
       - F0C0: RESOLVED 2026-07-14 via review.md item 3's table-of-tables
         investigation. The 150+ raw byte-pattern hits landing in
         calibration/scaling-table regions (0x11xxx-0x13xxx, 0x2dxxx) are
         axis-pointer occurrences inside real 2D/3D calibration table
         headers (0xF0C0 is the standard axis register for this table
         family) -- not code, and not a MUT_83/MUT_E1-style collapse.
         logging.txt's original "one odd COMPUTED_CALL xref" claim remains
         unverified (no address given), but the broader "unsupported, no
         support either way" framing is superseded: F0C0 does have a clear,
         confirmed role, just not as a MUT RequestID-readable sensor value.
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
   DONE (2026-07-13 session): non-RPM content extracted into mut_verification_status.md
   (new tracked file, repo root). Covers CONFIRMED items, the REFUTED knock_flag
   mislabel, the tcu_shift_torque_and_knock_mgmt structural fix, the tuning-XML
   speculative-table cleanup, RETRACTED dead ends, and the non-RPM open items
   (Load1B, WGDC vs WGDCCorr, coolant-temp four-way conflict, gear_config tables,
   o2_downstream_clamp, AirFlowMUT2Byte, Bad Instruction backlog). RPM identity
   itself was deliberately left out of that file and stays tracked here / via the
   isr_sci3_eri lead above.

   NEW FINDING (2026-07-13, follow-up session): MUT RequestID table @0x2fad0 is
   larger than previously assumed and contains a block of placeholder/collapsed
   entries. The bound constant at ROM 0x13282 (TCU_Gear_Ratio_Periods+2, read by
   adc_sensor_convert_single @0x171c3) is 0x10F (271), meaning the table actually
   has 272 entries (544 bytes), not the 150 checked in the original CONFIRMED pass
   above. Reading the full 544 bytes shows ~55 of those 272 RequestIDs (~20%) do
   not resolve to distinct RAM cells at all -- they collapse onto just two shared
   addresses:
     - 0xF0BB (existing Ghidra label MUT_83) -- target for RequestIDs 0x83,
       0x94-0x98, 0xA0-0xA1, 0xB3-0xBE (20 IDs)
     - 0xF0BA (existing Ghidra label MUT_E1) -- target for RequestIDs 0xE0-0xF8,
       0xF9-0xFB, 0xFE, 0x10A-0x10F (35 IDs)
   All 272 decoded addresses do fall inside the legal 0xEE80-0xFFFF on-chip
   RAM/IO block per the pspec (including 12 entries at table indices 164-175 =
   0xFE82-0xFE97, which are legitimate port data registers, not bugs) -- so this
   is not an out-of-range-pointer bug, it's a duplication/placeholder-collapse
   pattern. Most likely interpretation: MUT_83 and MUT_E1 are the one genuine
   value in each block, and the other ~53 RequestIDs are unimplemented/reserved
   slots defaulted to a filler address at table-build time -- querying MUT for
   those IDs would silently return an unrelated cell's byte rather than real data.
   UPDATE (2026-07-13, same-day follow-up): get_bulk_xrefs showed zero code
   cross-references to either address, but that's a static-xref blind spot (this
   ROM's indirect/bank-prefixed RAM access isn't reliably tracked -- see the
   decompiler-reliability note above). Resolved by raw byte-pattern search
   (`F0 BB` / `F0 BA`) across the whole image, filtered to hits landing inside an
   actual function body (checked via get_function_by_address; several raw hits
   were false positives sitting inside unrelated data tables, e.g. 0x133a0 and
   the 0x2d1xx-0x2d7xx idle-RPM scaling-table cluster, and were excluded):
     - 0xF0BB (MUT_83, 20 IDs): CONFIRMED dead. Every occurrence of the byte
       pattern in the ROM is inside the MUT table itself (0x2fbd6-0x2fc4e) --
       no function anywhere reads or writes it. Safe to treat as unimplemented;
       do not log these 20 RequestIDs.
     - 0xF0BA (MUT_E1, 35 IDs): CONFIRMED live, but as a *shared scratch cell*,
       not a dedicated sensor register. It's touched by a dozen-plus unrelated
       functions: wgdc_correction_integrator_update (0x18fe0),
       canister_purge_duty_calc_f4ac (0x19560), calc_f110_f10e_via_table
       (0x21314), knock_octane_dual_axis_table_blend_f2a8 (0x2339d),
       f0ba_f2b2_threshold_blend_calc (0x238d8 -- already named after this
       address in an earlier session), isc_f34e_f34a_correction_calc (0x25742),
       isc_f374_correction_calc (0x25e8b), f4de_f4e2_octane_correction_calc
       (0x265c9), idle_stepper_table_lookup_wrapper (0x268e2), and
       isc_f408_correction_calc (0x272c6). One address, many unrelated callers,
       is the signature of a shared temp/scratch cell reused across WGDC,
       canister-purge, knock/octane, and ISC correction routines -- whatever
       byte sits there depends on whichever routine last ran. Worse than dead
       for logging purposes: it looks like a real reading but is transient
       noise from an unrelated calculation. Do not log these 35 RequestIDs
       either. Open item: whether any tooling/spec built on top of the MUT
       table (e.g. the ecu_master scraper or an EcuFlash-side RequestID list)
       currently treats these 55 collapsed IDs as valid/distinct and needs a
       fix or an explicit "unimplemented/unreliable" flag.

   NOTE on a Sleigh decode issue mentioned in logging.txt: that file recorded six
   byte-identical "Unable to resolve constructor" sites (opcode `A0 16`, misread as
   `tst.b R0`) as an open bug. Per the user (2026-07-13), that was a bug in the OLD
   grammar only -- the Sleigh implementation has since been updated and all such
   decode bugs are confirmed gone in the current live Ghidra project. Recorded in
   mut_verification_status.md as a resolved historical note, not an open item; no
   action needed unless a genuinely new "Unable to resolve constructor" bookmark
   turns up in the live project, which should be treated as a fresh finding rather
   than a recurrence of this one. DONE (2026-07-14): test/rvr/logging.txt has been
   deleted by the user, its content having been fully captured above and in
   mut_verification_status.md.

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

5b. continued from 5


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
   once the pin mapping confirms it.

   SILICON-LEVEL PIN MAPPING CONFIRMED (2026-07-14 session): per the H8/539F
   hardware manual (Appendix D.3, Table D-19 / Fig 10-27), P5DR bit 4 = P54,
   which is multiplexed with T2IOC1 (16-bit IPU Timer 2, Input Capture/Output
   Compare channel 1) -- a genuine hardware timer capture-capable pin, not an
   arbitrary GPIO. The ISR polls it via plain software bit-test
   (btst.b 0x4,@0xfe8a:16), not via the IPU capture hardware path. This
   supports (does not refute) the cam-position-sensor theory. Note: the
   function has since been renamed isr_ipu_ch2ch4_input_capture, correcting
   the isr_sci3_eri mislabel referenced above -- so that rename is DONE.
   Plate comment added at 0x168e3 documenting the pin-mapping confirmation.
   REMAINING OPEN: this only confirms the SILICON pin identity (P54/T2IOC1).
   The BOARD-level wiring -- whether P54/T2IOC1 on this specific ECU's
   pinout is physically connected to the RVR's camshaft position sensor --
   is a separate step. PARTIAL PROGRESS (2026-07-14, continued): the user's
   "RVR GTA AIRTREK space gear 4cyc PCM.xls" harness pinout was read. It
   confirms the RVR harness has TWO separate, distinct sensor pins relevant
   here, both populated on the RVR column (not just 4G64-specific):
     - Pin 45 (wire G-R): "E/C; Crank angle sensor"
     - Pin 56 (wire L-Y): "E/C; Cam position (exhaust VVT 4g64)" -- despite
       the "(4g64)" suffix in the label text, this pin IS populated with a
       wire color for RVR (C69='L-Y'), so it is present on the RVR harness,
       not 4G64-exclusive as the label might suggest at a glance.
   This is ECU-CONNECTOR-pin numbering (1-66ish), NOT H8 chip pin numbering.
   No connector-pin-to-H8-chip-pin schematic exists for this ECU (confirmed
   by the user, 2026-07-14) -- CLOSING this item at the current confidence
   level rather than leaving it open pending a document that won't surface.
   FINAL STATE: P54/T2IOC1 (polled by isr_ipu_ch2ch4_input_capture) is the
   best available RPM candidate. Structural evidence (simple single-edge
   period-delta, no missing-tooth sync logic, unlike the confirmed crank ISR
   isr_tpu3_tgi3a which does implement missing-tooth sync) favors this being
   the cam-position signal (harness pin 56) rather than the crank-angle
   signal (harness pin 45), consistent with the original 2026-07-13
   reasoning. This is inference from ISR structure, not a proven pin-level
   trace, and should be labeled as such wherever cited. Do not resume
   searching for a schematic-based confirmation of this mapping.",
  "description": "Add new RPM lead (cam-sensor-derived period signal) discovered this session, reopening the RPM identity open item"

6. Unify H8/520, H8/538, and H8/539F onto a single shared instruction-decode
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
        matches). Per the user (2026-07-14), not worth a standalone check --
        this and any other h8520-specific divergence will be resolved
        naturally once the single shared-core unification described below
        replaces h8520's independent grammar. Other known h8539f bug
        categories (MAP4 dispatch gaps, cmp:g cross-EA gaps, the rtd/bra
        collision) have not yet been checked against it, same reasoning.
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

--------

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
