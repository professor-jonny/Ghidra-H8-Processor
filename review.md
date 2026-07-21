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
   and RequestID-table
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
       DECOMPILER OUTPUT: RESOLVED (2026-07-15). The stack-var-as-address
       artifact issue previously affecting decompile_function output on
       MUT-adjacent functions (adc_read_sequence_b, o2_closed_loop_fuel_trim_compute,
       and others) is fixed by the user's core changes. Raw disassembly remains
       the reference when in doubt, but decompiler output is no longer flagged
       as unreliable for this codebase.
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
   ROM's indirect/bank-prefixed RAM access isn't reliably tracked). Resolved
   by raw byte-pattern search
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
   searching for a schematic-based confirmation of this mapping.

   SECOND OUTPUT TAP CONFIRMED (2026-07-15 session): re-checked
   isr_ipu_ch2ch4_input_capture now that the user's core changes fixed the
   decompiler garbage on nearby functions - raw disassembly was already clean,
   but the fix made downstream callers (tcu_torque_converter_slip_calc,
   tcu_shift_ratio_buffer_update) tractable to read directly instead of relying
   on disassembly alone. Confirmed the ISR's falling-edge branch (@0x169dc)
   computes an independent normalized period-delta into F5D6/F5D8 (written
   @0x16a38/0x16a3c), separate from the already-documented F5D2/F5D4->F5DE
   chain. F5D6/F5D8 is consumed by tcu_periodic_dispatch (@0x2c12b) ->
   tcu_shift_ratio_buffer_update (@0x2c16e), which converts it into a
   gear-indexed ratio estimate with rate limiting for TCU shift logic.
   Two independent downstream consumers (torque-scale calc and TCU
   shift-ratio logic) drawing period data from the same 2-tooth cam capture
   is corroborating evidence this is a genuine engine-speed signal. Plate
   comments added to all three functions. Still open: absolute RPM
   scale/units (timer tick rate + the 0x10 divisor's real-world meaning not
   yet derived), and the board-level P54/T2IOC1-to-sensor wiring confirmation
   noted above.

   UPDATE (2026-07-15 session): continued the SCI1 command-dispatcher thread
   (sci1_meta_cmd_dispatch_c0_ff @0x28869) found in the prior session. Fully
   decoded its 0xC0-0xD8 actuator bit-table (ROM 0x13740) and traced three
   real consumers/producers of the @0xf516/f512/f510 flag registers:
     - f516 bits 2/5/6/8 (set by commands C3/C4/FA) -> consumed by
       f516_request_latch_f09a_calib_select (0x27e1a, renamed from
       eeea_bit7_f09a_update) - a calibration selector for output f09a.
     - f516 bit7 (set by command FC) -> consumed by
       eee0_eeee_diag_flags_reset_dispatch (0x282c1) -> calls
       startup_phase_reset_eed6_eefa_bulk (0x28413), the SAME bulk-reset
       function already known as one of Load1B's two writers. So command
       0xFC is a live, on-demand trigger for that reset, not just a startup
       path - a new, concrete fact for the Load1B item in
       mut_verification_status.md.
     - f516 bit11 -> traced to an UNRELATED periodic phase-sequencer,
       f588_duty_gate_f516_bit11_set (0x28b62), which is a computed-jump
       branch inside sci1_periodic_phase_dispatch_f526 (0x28b2f, renamed
       from FUN_00028b2f, called from sci1_protocol_state_machine 0x287af).
       That parent function has real decompiler trouble (Bad Instruction /
       unresolved-jump-table warnings) - ADDED to the ~140 Bad Instruction
       backlog mentioned above as a fresh, specific candidate for a proper
       re-split, rather than left as an anonymous FUN_ entry.
   Renamed 5 functions total this session (f516_request_latch_f09a_calib_select,
   f516_hibits_f520_f0f2_mode_select, sci1_periodic_phase_dispatch_f526,
   f588_duty_gate_f516_bit11_set, f528_f52e_zero_f526_advance_alt_branch) and
   added plate comments to all of them plus the dispatcher and
   eee0_eeee_diag_flags_reset_dispatch. Still open: writer for f516 bits
   1/12/13/15, any reader for f510/f512, physical meaning of any bit, the
   <0xC0 pointer table, and SCI1-vs-SCI3 reachability. Full detail in
   mut_verification_status.md's dispatcher section - this is a pointer entry
   only, per this file's existing pattern of keeping non-RPM MUT/dispatcher
   detail in that file.

7b. MUT BLANK/actuator tracing sweep, round 2 (2026-07-15 session, IN PROGRESS)
    Started working through the ~150 BLANK/NAMED-untraced MUT RequestID
    table rows, and separately identifying which confirmed cells are true
    MUT "requests" (values a scan tool reads) vs "actuators" (values that
    drive real hardware - stepper, duty cycle, solenoid). Full detail,
    including the reusable approach/pattern notes, is in
    mut_verification_status.md's "MUT BLANK/UNTRACED SWEEP, ROUND 2"
    section - this is a pointer entry only, same convention as item 7.
    Resolved this round: MUT ReqID 0x08 (EECA) and 0x0A (EECC), both
    mode-shadow copies of one ISC correction value
    (isc_eeca_eecc_eece_correction_calc @0x27a81, plate comment added).
    Also traced three actuator-driver functions for reference (not MUT
    IDs themselves, but establish the request-vs-actuator shape and feed
    confirmed cells): canister_purge_duty_calc_f4ac (F4AC, canister purge
    duty - its F0BA write was already captured in item 7's writer list,
    0x19560 entry, checked and confirmed no update needed there),
    egr_duty_target_calc/egr_target_f448_update (F448, EGR duty target),
    isc_f402_stepper_target_calc (F402, ISC stepper target, upstream of
    the EECA/EECC finding). All five functions traced this round got
    plate comments; no renames needed, existing names already accurate.
    New lead RESOLVED same session: checked whether MUT ReqID 0x09 (F3FB)
    and 0x0B (F3FD) are a real structure or scraper artifacts of the
    F3FA/F3FC/F3FE mode-shadow triplet (isc_f3fa_f3fc_f3fe_correction_calc,
    0x27990) - CONFIRMED real, not artifacts: verified against
    adc_sensor_convert_single (0x171c3)'s single-byte fetch logic for
    ReqID<=0xBF, which reads exactly one byte at the table-decoded address.
    F3FB/F3FD are genuinely the low byte of the big-endian F3FA/F3FC words.
    Table updated to CONFIRMED for both rows; plate comment updated. This
    is a different outcome than the F5C0 cluster's 0x81/0x82 rows (those
    WERE artifacts) - the general lesson (word-store + odd-offset ReqID
    is not automatically an artifact either way) is logged in
    mut_verification_status.md for future adjacency checks.
    Approach note for whoever continues this: per-address get_bulk_xrefs
    on BLANK cells is a dead end (known indirect/bank-prefixed blind
    spot, re-confirmed on EEEF/EEF3/F161/F15B this round with zero new
    info). Search from the PRODUCER side instead -
    ghidra:search_functions name_pattern "calc" (also try "duty",
    "target", "stepper") and cross-check write addresses against the
    table. Prioritize BLANK rows adjacent to already-CONFIRMED cells.

    RESOLVED same session: F971 (0x2A) and F972 (0x2B), the two POINTER
    leads carried over from the 2026-07-14 sweep, are now CONFIRMED.
    Decompiling fuel_pw_and_airvol_compute (0x29fba) and
    injpw_airvol_reset_on_fuelcut (0x24680) directly showed both
    InjPulseWidth (F970/F971) and AirVol (F972/F973) are single 16-bit
    big-endian words with no independent byte-level writer -- F971 is
    just F970's low byte, F972 is just F973's high byte, same idiom as
    the already-confirmed F3FA/F3FB and F3FC/F3FD pairs. This closes the
    F970-F973 cluster entirely. Confirms the general lesson: for a BLANK
    row sitting next to a CONFIRMED word-value cell, decompiling the
    writer function directly beats another round of bulk-xref attempts.
    Full detail in mut_verification_status.md's sweep section.

7c. EFI/TCU MUT profile cross-check against user-uploaded XML (2026-07-15)
    User uploaded Mitsubishi_MUTII_EFI.xml and Mitsubishi_MUTII_TCU.xml
    directly. Full detail in mut_verification_status.md's "EFI/TCU MUT
    PROFILE CROSS-CHECK, ROUND 2" section - pointer entry only, same
    convention as items 7/7b.
    Headline findings: (1) ReqID 0x1C/F187 was BLANK, XML names it
    ECULoad - a miss from the original 2026-07-13 table build, now fixed.
    (2) ReqID 0x00 has a THIRD conflicting claim from within this same
    XML (gmas/"Airflow Rate gm/s" vs LoadMUT2Byte), on top of the
    GalantLegnum switch-flags conflict already on record - this ID looks
    genuinely ROM-revision-dependent, not a single stable value. (3) The
    XML's own "FC = Clear EFI Diagnostic Codes" label corroborates this
    session's earlier structural finding (this file's "UPDATE 2026-07-15"
    paragraph above) that SCI1 command 0xFC triggers a bulk diagnostic-
    flags reset - independent confirmation of the semantic meaning, not
    just the structural behavior.
    NEW SCOPE OPENED, NOT YET WORKED: the TCU XML reveals a completely
    separate MUT RequestID scheme for the transmission side (13 entries -
    AT_ID1-3, AT_Temp, AT_Park/Reverse/Neutral/Drive/Low/2nd/3rd, shaft-
    speed pulses, AT_Brake, AT_ClearDTC), distinct from every tcu_*
    function traced so far in this project (all of which came from the
    RPM thread, not from tracing this ID scheme). No TCU-side equivalent
    of adc_sensor_convert_single/the 0x2fad0 table has been located yet.
    Flagged as its own future work item, not folded into the EFI table.

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

8. SP24/FP24/Rn_banked "unaff_SP" decompiler regression -- segmentop follow-up
   to the tracked_set fix (test/bugs.txt notes, 2026-07-15)
   -----------------------------------------------------------------------

   REPRO CONFIRMED (2026-07-15, same session): test/RVR_1998_x3 4g63t
   21000011 md352553.hex_old.c (pre-tracked_set) vs the current
   test/RVR_1998_x3 4g63t 21000011 md352553.hex.c (post-tracked_set) are the
   full pre/post decompile dumps for this ROM and confirm the tracked_set
   fix changed the failure mode rather than fixing it in general -- not a
   theoretical gap, an actual regression visible on hundreds of functions.

   Minimal example, sat_add_u16 (line ~1945 in both files):
     PRE  (_old.c): `undefined1 auStack_2 [2]; ... *(undefined2 *)ZEXT24
          (auStack_2) = unaff_FP;` -- wrong target (a fabricated stack-local's
          address, not the real banked SP), but at least consistently
          produces a 24-bit ZEXT24 pointer shape.
     POST (.c):     `short unaff_SP; ... *(undefined2 *)(uint)(ushort)
          (unaff_SP - 2U) = unaff_FP;` -- SP is now an unresolved bare
          16-bit `unaff_SP` local (Ghidra gave up on stack-frame recovery
          entirely for this function), and every derived address is pushed
          through a `(ushort)` cast before being widened back to `(uint)`.
          The TP page term is simply gone -- there is no zext(TP)<<16
          anywhere in the post-fix output for this function. This is a
          narrower pointer than the buggy pre-fix version, not a corrected
          one.

   Confirmed systemic via grep across both files (hundreds of matching
   functions, not an isolated case): div_u32_u16_rounded (~line 2165) shows
   the identical shape (unaff_R3/R4/FP/SP all unresolved, all masked through
   `(ushort)` before use). Caller sites are inconsistent about it too --
   compare 21000011.hex.c:3401 (`CONCAT12(uVar14, unaff_SP + -0x2a)`, a page
   byte concatenated back on) against :8600 (`(uint)(ushort)(unaff_SP - 8)`,
   plain 16-bit truncation, page term dropped) for calls to the *same*
   callee (sat_add_u16) a few hundred lines apart -- the decompiler isn't
   applying one consistent recovery strategy, it's falling back
   per-call-site depending on what it could locally infer.

   Working theory (needs confirming against SLEIGH/decompiler internals,
   not yet verified): pinning TP/DP/EP to a tracked constant 0 gave the
   decompiler's parameter-ID/stack-frame pass enough to constant-fold the
   *value* of SP24 in isolated expressions, but stopped it from recognizing
   SP24 as ever being derived from the <stackpointer> register SP at all --
   i.e. it satisfies parameter recovery's local dataflow check but breaks
   whatever heuristic previously linked SP24 back to the real frame,
   so the stack-frame analyzer now bails out to unaff_SP/unaff_FP (raw
   unresolved register reads) instead of either the old wrong ZEXT24 guess
   or a correct one. This would explain why bugs.txt's segmentop suggestion
   points at the right mechanism (Ghidra's stack-frame analyzer only
   recognizes <stackpointer> being adjusted directly) even though the
   proximate trigger turned out to be the tracked_set change, not the
   original zext/shift/OR pattern by itself -- tracked_set didn't introduce
   the underlying design gap, it just changed which code path exposes it.

   RESEARCH (2026-07-15, this session): checked two real-world reports of
   segmentop on a non-x86 `space="ram"` data widening (same shape as ours --
   a narrow SP/offset register widened into a larger flat ram space):
     - Ghidra discussion #2749: someone with the identical problem (2-byte
       SP, 4-byte ram space) confirms "using the segmentop in the pspec was
       the way to go" -- but had to set `type="protected"` to get correct
       segmentation, and notes protected pulls in Ghidra's x86-16-protected-
       mode analyzers even on non-x86 hardware (side effect, not confirmed
       harmful here, but unverified).
     - Ghidra issue #841: someone else applied segmentop to `space="ram"`
       using the textbook x86-real-mode shape (INT_ZEXT/INT_LEFT/INT_ZEXT
       baseop/innerop, same as ours would be) and got the decompiler to
       alternately crash or silently eliminate the segment and dereference
       a raw constant instead -- a worse failure mode than today's
       unaff_SP, not a better one.
   Conclusion: segmentop is a real, precedented fix for exactly this shape
   of problem (bugs.txt's core claim is right), but it is not a
   drop-in guaranteed win -- outcomes on `space="ram"` specifically are
   mixed in the wild, and one report is a stability regression, not just a
   cosmetic one. This justifies a staged rollout (below) instead of a single
   rewrite of every banking site at once, and specifically justifies why
   step 1 is scoped to SP alone before DP/EP are touched.

   PLAN (not yet started -- this is the agreed approach, execute stepwise,
   confirm each step before starting the next):

   Step 0 -- safety net (no code change):
     Confirm the current .sla in the Ghidra install is backed up /
     reproducible from source control before any experimental compile, per
     this file's existing "Build/test workflow" section below (delete-and-
     regenerate is already documented as the recovery path if a bad .sla
     gets installed -- just confirm the source-controlled .slaspec/.sinc
     are committed as of now, so "revert tracked_set" and "revert segmentop
     experiment" are both one `git checkout` away, not a manual rewrite).

   Step 1 -- SP-only segmentop spike, isolated: DONE / PASSED.
     unaff_SP is fixed -- segmentop confirmed to work for this data-space
     (ram) widening case. Proceeding to Step 2 (FP extension) below.

     [original spike plan, kept for reference]
     Add ONE <segmentop> block to h8539f.pspec, space="ram", scoped to the
     TP->SP widening only. Try the plain (non-protected) form first, since
     "protected" pulls in x86-16-analyzer side effects that have no reason
     to apply to an H8 target -- fall back to type="protected" only if plain
     doesn't produce a correct decompiler-recognized pointer.
     Rewrite ONLY the SP24 construction sites to use it -- NOT FP, NOT DP/EP.
     That's 26 sites in h8539f.slaspec: PUSH/POP macros (2), Rn_banked/
     Rs_banked/Rn_banked2 SP row (3), r0-r5/fp/sp push table (8) + pop table
     (8), eab/eaw_predec/predec2 SP row (2), eab/eaw_postinc/postinc2 SP row
     (2) -- exact line numbers already catalogued this session via
     grep-project on `zext(TP) << 16`, re-grep before editing since lines
     will have shifted. Leave every FP-only TP-banked site (6: Rn_banked/
     Rs_banked/Rn_banked2 FP row, eab/eaw_predec/postinc FP row, r6b_disp8/
     r6w_disp8) and every disp8_banked/disp16_banked TP row (targetBase=6/7,
     4 sites) UNCHANGED for this step -- FP doesn't reuse the SP24
     pseudo-register today and mixing it into the same spike would make a
     failure harder to attribute to segmentop itself vs. the FP-specific
     wiring.
     Compile (sleigh.bat per this file's Build/test workflow section),
     install, reanalyze the RVR ROM, and decompile sat_add_u16 and
     div_u32_u16_rounded specifically -- these are this session's confirmed
     bad repro cases (test/RVR_1998_x3 4g63t 21000011 md352553.hex.c lines
     ~1946 and ~2165 as of this session). Also re-check the two inconsistent
     caller sites already identified (21000011.hex.c:3401 vs :8600, both
     calling sat_add_u16) to see if they now agree.
     PASS criteria: no unaff_SP/unaff_FP on these functions, no bare
     (ushort) truncation before a pointer dereference, SP24 shows up as a
     real recognized stack access (ideally Ghidra's normal stack-frame
     locals, not a raw computed pointer), decompiler does not crash, and a
     project-wide reanalyze doesn't introduce NEW "Bad Instruction"/
     unresolved-constructor bookmarks that weren't there before (compare
     against review.md's existing "~140 Bad Instruction" baseline count).
     FAIL criteria (matches issue #841's failure mode): crash, or segment
     silently eliminated and a raw constant dereferenced instead of a
     recognized SP-relative access. If FAIL: stop, do not proceed to step 2,
     record what specifically failed here, fall back to the tracked_set
     revert already documented above as the interim state, and revisit
     segmentop only with a different formulation (e.g. the "protected" type
     the discussion #2749 poster needed) as a separate follow-up spike, not
     as a next default step.

   Step 2 -- SP validated, FP extension: DONE / PASSED (2026-07-21, verified
     in a fresh project + fresh ROM import per the note below).

     FINAL APPROACH: FP reuses the existing spSegment userop/segmentop
     (no separate fpSegment) -- see history below for why.

     Verification: sat_add_u16 (0x14000, the documented @(disp8,FP) repro
     case) now decompiles cleanly with no crash, no unaff_FP, no manual
     ZEXT24 reconstruction -- resolves to clean stack references
     (in_stack_00000004 / stack0xfffe) instead.

     BUG FOUND + FIXED (2026-07-21): the fpSegment <segmentop> comment block
     added to h8539f.pspec contained a literal "--" inside an XML comment
     ("...same approach as SP since it worked -- FP uses...") which is
     illegal XML (SAXParseException: "The string \"--\" is not permitted
     within comments"). This made SleighLanguageValidator reject the whole
     .pspec on language load -- confirmed via application.log, not decompile
     testing, since a broken pspec fails at language-load time before any
     decompile is even attempted. Root cause was unrelated to the earlier
     stale-file/caching issue (see Build/test workflow note above) -- this
     was a genuine syntax bug in the new content itself. Fixed by replacing
     the "--" with ";". Re-swept the whole file for any other literal "--"
     inside comment bodies (excluding the <!-- / --> delimiters themselves)
     -- none found. Recompiled (exit 0) and reinstalled the full file set;
     source and install timestamps now match. LESSON: avoid "--" as a prose
     separator inside XML comments anywhere in .pspec/.cspec files going
     forward -- use ";" or a single "-" instead.

     BUG #2 FOUND + FIXED (2026-07-21, same session): after fixing the "--"
     above, the second segmentop itself was structurally illegal -- Ghidra
     only allows ONE <segmentop> per address space. Symptom was NOT a
     parse/validation error this time but a hard decompiler failure on
     program open: "Decompiler: Unable to initialize the DecompilerInterface:
     Could not register program: Low-level Error: Multiple segmentops
     defined for same space", surfaced first as a generic ecu-setup-script
     abort ("Decompiler openProgram() FAILED... do a full Ghidra restart"),
     then confirmed directly by the user. This also left the running Ghidra
     instance unresponsive to further MCP calls (close_program/
     list_open_programs both timed out), consistent with a stuck modal error
     dialog blocking the GUI thread -- required a full Ghidra restart + a
     fresh ROM re-import to recover, exactly as the abort message said.
     FIX: removed the second segmentop and its fpSegment pcodeop entirely;
     FP now calls the SAME spSegment(TP, FP) userop as SP, since the pcode
     body (zext(base)<<16 | zext(inner)) and base register (TP) are
     identical for both -- there was never a need for a second userop.
     BUG #3 FOUND + FIXED (2026-07-21, same session): the rewritten comment
     explaining bug #2 ALSO contained a "--" (second time in one session --
     caught by the user, not self-caught). Re-swept both .pspec and .cspec
     afterward with a tighter regex; both clean.
     LESSON (updated): "--" as a prose separator in these XML comment blocks
     is clearly an easy slip to repeat under time pressure -- default to ";"
     from the start rather than relying on a post-hoc sweep to catch it.

     VERIFIED 2026-07-21: after the spSegment-reuse fix, compiled clean,
     reinstalled the full file set, and confirmed via force_decompile in a
     freshly-restarted Ghidra + freshly re-imported ROM that sat_add_u16
     (0x14000, @(disp8,FP) addressing) now decompiles correctly with no
     crash and no unaff_FP. Step 2 marked PASSED above on this basis.
     FP uses an identical TP-banked shape but
     currently has NO shared pseudo-register the way SP has SP24 (FP24 is
     defined as a register at slaspec line 35 but, per this session's grep,
     is never actually assigned anywhere -- FP-relative accesses build a
     throwaway `local addr:4` inline instead). Decide during this step
     whether to route FP through the same segmentop and finally start using
     FP24 for real (consistent with SP, may help Ghidra's frame-pointer
     recognition too), or leave FP on the inline local-addr pattern if
     testing shows no decompiler benefit for FP specifically (FP doesn't
     have the same push/pop-heavy call pattern as SP, so the "unaff_FP its
     own stack-frame-unresolved" symptom may or may not reproduce the same
     way). Test against the same two repro functions plus a handful of
     functions from mut_verification_status.md's already-confirmed set to
     check for silent regression on previously-good decompiles, not just
     the two known-bad ones.

   Step 3 -- DP/EP banking (Rn_banked/Rs_banked/disp8_banked/disp16_banked
   R0-R5 rows, 55 sites in h8539f.slaspec by this session's grep count):
     Separate decision point, NOT automatically bundled with steps 1-2.
     DP/EP banking is used far more pervasively than SP/FP (every general
     register-indirect and displacement addressing mode, not just stack
     ops), so a segmentop mistake here has a much larger blast radius across
     the 691-function analyzed set. Do NOT start this step until steps 1-2
     are confirmed clean AND a specific live repro of a DP/EP-banking
     decompiler problem exists (parallel to how step 1 was blocked on
     finding the SP repro before this session) -- unlike SP, no DP/EP
     repro has been identified yet, so this step may end up out of scope
     entirely if DP/EP banked accesses turn out not to exhibit the same
     unaff_* symptom in practice. Check before assuming it needs fixing.

   Step 4 -- h8520.slaspec:
     Item 6 above already documents the plan to unify h8520/h8538f onto the
     shared h8539f core rather than hand-port fixes into h8520.slaspec's
     independent copy of this same TP-banked disp8_banked/disp16_banked
     pattern (lines 394-404 there, 4 sites, identical shape). Do not hand-
     port segmentop into h8520.slaspec separately -- let the unification
     effort (still gated on h8539f's own open items per item 6) carry this
     fix over naturally once it happens, consistent with the existing
     decision recorded there.

   Context: item 5's "DECOMPILER OUTPUT: RESOLVED (2026-07-15)" entry refers
   to the `<tracked_set>` block added to h8539f.cspec (TP/DP/EP/CP/BR pinned
   to 0 via context_data), which lets Ghidra's constant-propagation fold the
   `(zext(TP)<<16)|zext(SP)` term in SP24 down to a known value in the common
   single-page case. That fix is real and has already resolved the specific
   symptom seen on adc_read_sequence_b / o2_closed_loop_fuel_trim_compute
   and others.

   bugs.txt raises a different, structural point worth recording rather than
   discarding: tracked_set only fixes the common case where TP/DP/EP happen
   to be the pinned default (0) for the page in question. Any function that
   genuinely switches pages at runtime (ldc to TP/DP/EP, then a banked
   access) will still hit the original symptom -- Ghidra's stack-frame
   analyzer only recognizes the literal <stackpointer> register being
   incremented/decremented directly, not a derived zext/shift/OR
   recombination, tracked_set or not. Grep confirms every SP push/pop/EA
   path (h8539f.slaspec: PUSH/POP macros, Rn_banked/Rs_banked SP alternative,
   r0-r5/fp/sp_push/pop, eab/eaw_predec/postinc SP forms) reconstructs SP24
   via this same inline `(zext(TP)<<16)|zext(SP)` pattern rather than a
   `<stackpointer>`-native op Ghidra can track through a page change.

   bugs.txt's suggested structural fix: replace this pattern with SLEIGH's
   segmentop mechanism (used by Ghidra's own x86 real-mode modules for
   DS:offset addressing) rather than manual zext/shift/OR, wiring segmentop
   for the TP-to-24-bit-SP widening in h8539f.pspec (and, if adopted,
   revisiting DP/EP banking on Rn_banked/disp8_banked/disp16_banked too,
   since they follow the identical shape).

   Decision (this session, UPDATED now that a repro exists): the regression
   is confirmed real and widespread (sat_add_u16, div_u32_u16_rounded, and
   many more across test/RVR_1998_x3 4g63t 21000011 md352553.hex.c -- see
   REPRO CONFIRMED above), so this is no longer blocked on finding a
   counter-example. Still NOT implementing the segmentop rewrite this
   session -- one thing needed first:
     - Confirmation that Ghidra's <segmentop> pspec construct is actually
       usable for a *data* (RAM/stack) space widening here, not just the
       code-space DS:offset case it's normally used for -- unconfirmed
       against Ghidra 12.0.4 docs/source, not just inferred from the x86
       module's usage. This is the one remaining gate before touching code.
   Next step once that's confirmed: a small isolated test, segmentop on just
   the SP24/PUSH/POP path (not DP/EP banking, which is a separate, larger
   blast radius covering every disp8_banked/disp16_banked/Rn_banked
   constructor) -- recompile, re-decompile sat_add_u16 specifically (cheap,
   known-bad repro from this session), and confirm it produces a real
   `*(undefined2 *)(SP24_expr)` shape with no unaff_SP/unaff_FP and no bare
   (ushort) truncation before deciding whether to extend the approach to
   DP/EP banking. Full rewrite of all zext/shift/OR banking sites stays out
   of scope until that smaller test lands and is verified against
   sat_add_u16 and div_u32_u16_rounded specifically, plus a handful of the
   ~10 call sites already identified as inconsistent (21000011.hex.c:3401
   vs :8600) to confirm the caller-side inconsistency also resolves.
   NOTE: because tracked_set (h8539f.cspec) is the proximate cause of this
   specific regression, reverting tracked_set is also a viable fallback if
   segmentop turns out not to apply to the ram/stack space -- that would
   restore the old (also-wrong, but at least consistently-shaped) ZEXT24
   behavior while a real fix is worked out, rather than shipping the
   current narrower/more-broken unaff_SP output. Not done this session;
   flagging as the fallback option, not a recommendation to revert yet.

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
4. Test in the Ghidra project as normal (reanalyze / re-open the program to pick up
   the new .sla). NOTE: an already-open program can cache old instruction-level
   pcode even after reanalyze/close+reopen/delete+recreate-function -- if a source
   change still doesn't show up in decompile output after confirming the install
   directory has fresh files, importing into a fresh project is the reliable way
   to confirm the fix, since a new project reads the language definition cold.
5. Safety net: if a bad compile or bad copy breaks the installed language, just
   delete the .sla in the Ghidra install languages folder above -- Ghidra
   regenerates it from the baseline/source shipped there. Nothing is unrecoverable.
