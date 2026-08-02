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
   (0x156ce).

   BIT NUMBERING CORRECTED (2026-07-26): the two entries below marked
   "bit3"/"bit7" in earlier notes were WRONG -- both were pin-name-correct
   but bit-number-wrong (an old miscount, never independently re-verified
   until the "~20 untraced writer sites" sweep below closed every remaining
   xref and forced a re-check of the full bit map against
   mirror_status_f0e6_to_ports itself). Corrected, full bit map:
   bit0 (isc_f0e6_bit0_update, P1DR.4, knock-gated, not SCI1-reachable),
   bit1 (EGR solenoid, P2DR.7, egr_f0e6_bit1_update -- has two writers, one
   unconditional at cold-init (engine_state_f498_init), the other the real
   RPM/warmup-gated ongoing control (egr_f0e6_bit1_update); the "interaction"
   is just normal init-then-steady-state override, not actually mysterious),
   bit2 (canister purge, P4DR.7, purge_f0e6_bit2_update -- CONFIRMED
   forceable via SCI1 cmd 0xD1, the strongest real actuator-test candidate
   found on this ROM. NOTE 2026-07-26: there is a SEPARATE, still-
   unresolved DUTY-CYCLE purge path too -- canister_purge_duty_calc_f4ac
   (F4AC) -- gated in part by a live TCU serial link (see item 6's TCU
   sub-note below). Not confirmed whether F4AC and this on/off F0E6.bit2
   path drive the same physical solenoid or two different ones), bit3
   (PCDR.3, INVERTED -- NOT EGR, previously
   unmentioned. Two writers found: knock_octane_f0e6_bit3_gate_dispatch
   (RPM/knock-pattern-gated, see below) and warmup_state_f594_f0e6_init
   (NEW 2026-07-26, unconditional set at warmup-state init, same
   init-then-steady-state pattern as bit1) -- plausibly a MIL/check-engine
   or knock-warning lamp), bit4+bit5 (EGR valve position, P4DR.4/PCDR.6,
   egr_f0e6_valve_bits_update, orchestrated by egr_mode_dispatch/
   egr_sequence_control), bit6 (PCDR.7, via dispatcher cmd 0xD2), bit7
   (P1DR.5, ign_advance_f0e6_bit7_update -- previously unmentioned,
   forceable via SCI1 cmd 0xD8, ignition-adjacent per inherited naming,
   unconfirmed). Separately,
   f0e6 bits 8-11 are an unrelated O2 sensor upstream/downstream control
   mode field (via o2_sensor_control_dispatch). bit13 (P6DR.2): CHECKED
   2026-07-23 via xref trace (corroborates a prior 2026-07-22 byte-pattern
   sweep) -- no directly-encoded writer exists anywhere in this ROM
   (mirror_status_f0e6_to_ports reads/forwards it to P6DR.2 faithfully, but
   nothing else touches bit 0x2000). Consistent with this ROM's known
   static-analysis blind spot for bank-prefixed/indirect RAM writes -- not
   proof no writer exists at all, just that none is reachable via a literal-
   address instruction. Low priority to pursue further absent a new lead.
   Separately, SCI1 cmd 0xCC (CORRECTED 2026-07-26 -- was misattributed to
   0xCD in earlier notes; re-verified via direct read_memory at the table
   entry, 0x13770 = 00 FF 20 00) sets f510 bit13 (a different bit13,
   different RAM word, read by o2_upstream_enable_check) -- a fourth SCI1-
   reachable actuator chain, but it doesn't terminate in a physical pin the
   way the other three do. This correction was part of a larger fix: the
   whole cmd_c0_d8_actuator_bit_table CC-D8 region was off-by-one in all
   prior notes (full corrected table and the real f00e/f25a gate mechanism
   now in the sci1_meta_cmd_dispatch_c0_ff plate comment and
   mut_verification_status.md) -- this also retroactively resolved two
   previously-flagged "table anomalies" (the D3 dual-bit entry and the D8
   pattern-break), which turn out to be the same single fact seen from two
   wrong offsets: the real dual-bit entry is D2, not D3, and D8 correctly
   continues an uninterrupted 13-entry bit sweep from CC down to D8 with no
   break at all.

   FIFTH chain found 2026-07-26, and the strongest one yet: cmd 0xCD (f510
   bit12) or 0xCE (f510 bit11) -> check_mode_gate_f510 (0x18ae5) -> forces
   egr_position_target_f494_calc's output (f494) to a fixed ROM calibration
   value -> scaled and written to T6GR1 (ROM 0xff88-89), a REAL, confirmed
   H8 Timer 6 PWM duty/compare register (not an inferred port pin). This is
   the ACTIVE EGR control mechanism on this ROM -- confirmed by reading ROM
   config byte 0x102e4 directly, value is 2, selecting this PWM variant
   over the relay-style two-bit sequence (which is present in the ROM but
   dead code here). Timer 6 is corroborated as a genuinely configured PWM
   channel by its cold-boot init function (period + duty register pair
   both set with matching scale). Strongest physical-actuator evidence
   found in this whole investigation, though the exact vehicle-side wiring
   of Timer 6's output pin is still unconfirmed. Full detail in
   mut_verification_status.md "FIFTH SCI1 ACTUATOR-FORCE CHAIN".

   Separately found 2026-07-26 (not SCI1-related, but same actuator-tracing
   thread, triggered by a question about RAM cell F4CA): a checksummed TCU
   (transmission control unit) serial RX frame inside tcu_rx_main_scheduler
   (0x2aa36) -- F4C4/F4C6/F4C8/F4CA + checksum F4CC, latched into confirmed
   copies F4BC/F4BE/F4C0/F4C2 on a checksum match. Confirmed genuinely
   serial (F4C2 is also written directly by serial_fec5_byte_to_fifo,
   inside the known SCI1/2/3 UART register range). F4BC/F4BE feed directly
   into canister_purge_duty_calc_f4ac (item 1's bit2 purge note above) --
   i.e. canister purge duty is influenced by live TCU-link data, not just
   engine-side state. All cells renamed in Ghidra (tcu_rx_frame_raw_byte0-
   3_*, tcu_rx_frame_checksum_f4cc, tcu_rx_confirmed_byte0-3_*, tcu_rx_
   frame_state/timeout_counter_*); f226_bit7_update_from_f4c2_check
   renamed to tcu_link_confirmed_flag_f226_bit7_update. Full detail in
   mut_verification_status.md "TCU SERIAL RX FRAME FOUND".

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

   CORRECTED 2026-07-26 (cross-checked against dasm85, an independent H8/500
   disassembler, plus a fresh byte-by-byte hand-trace of ana.cpp's actual
   h8500_ana() logic): the original "divxu.w" decode below was WRONG --
   off-by-one in the A4tail pairing. dasm85 independently decoded the real
   bytes as `subx.w @(0x123C:16,R7),R7`, and re-tracing ana.cpp confirms
   dasm85 is right:

   FF 12 3C B7 9C 1D -> `subx.w @(0x123C:16,R7),R7` (R7 = SP by H8 convention).

   Byte 1 (0xFF): code>=0x60 and code&8!=0 -> word-size. insn.itype =
   A2tail[(0xFF>>4)-6] = A2tail[9] = MAP4. Confirmed correct. Then the main
   switch(code) hits case 0xF0-0xFF: `ds16(insn, insn.Op1, code, dtype)` --
   this happens at BYTE-1 TIME, before the MAP4 tail lookup below. reg =
   code&7 = 7 = R7. This consumes bytes 2-3 (12 3C) as the Op1 displacement:
   Op1 = @(0x123C:16, R7). Matches the original trace so far.

   Byte 4 (0xB7) is what the MAP4-resolution loop (ana.cpp lines ~478-492)
   consumes next: index = -(3 + short(MAP4)) = -(3 + -4) = 1 ->
   tables[1] = {A4, A4tail}. code=0xB7 >= 0x20, so
   insn.itype = A4tail[(0xB7>>3)-4] = A4tail[22-4] = A4tail[18].

   THE BUG IN THE ORIGINAL TRACE: A4tail[] is laid out in PAIRS per ana.cpp
   (20:add_g/adds, 30:sub/subs, ... B0:subx/divxu, ...). Counting pair-wise,
   index 18 is the FIRST of the B0 pair (18,19) = H8500_subx, not
   H8500_divxu (which is index 19). The original entry misread which half
   of the pair index 18 lands on.

   opreg(insn.Op2, code=0xB7, dtype) -> reg = 0xB7&7 = 7 = R7. Op2 = R7.

   VERIFIED GROUND TRUTH: `subx.w @(0x123C:16,R7), R7`. This changes the fix
   target: the grammar gap is NOT in a divxu.w EA form (SUPERSEDED THEORY 2
   below can stay retired, it was about divxu.w and is moot either way since
   the instruction isn't divxu). The missing/broken construct is whatever
   handles `subx.w` under this exact MAP4(word-size, A2tail[9]) ->
   ds16(byte-1) -> A4tail[18] dispatch path. Check h8539f-arith.sinc's
   subx.w constructor(s) for the same byte-position-scoped eaw_disp16 issue
   diagnosed below (still the right mechanism, wrong opcode target).
   NEXT STEP: grep h8539f-arith.sinc for existing `subx` constructors,
   confirm whether a word-sized EA form under this MAP4/A4tail[18] path
   exists at all, and check for the same eaw_disp16-vs-MAP4-byte-position
   collision already suspected below.

   UPDATE (2026-07-26, isolation test) -- CONFIRMED the constructor exists
   (h8539f-arith.sinc line 79: `:subx.w eaw_disp16,Rd is eaw_disp16;
   opcode=22 & Rd`) and cross-verified the whole ana.cpp trace above
   byte-by-byte against the live A2tail[]/A4tail[]/tables[] source (ana.cpp
   lines 35-47, 83-99, 159-165, 265-282, 465-492) -- every step of the
   corrected `subx.w @(0x123C:16,R7),R7` decode checks out exactly as
   written above. Live-read raw bytes at 0x20843 (FF 12 3C B7 9C 1D) and
   0x16671 (FF F1 3F F1) both still match the documented pattern.

   TESTED AND REJECTED: the "same token, different canonical byte position"
   hypothesis (the literal BUG-5 mechanism, i.e. `instr8`'s `opcode`/`Rd`
   fields being anchored to byte 1 by their dominant usage elsewhere --
   mov:l/mov:s/mov:f/cmp:e/cmp:i in h8539f-mem.sinc/h8539f-arith.sinc all
   use `opcode`/`Rd` bare at byte 1 -- preventing SLEIGH's compiled decision
   tree from shifting to byte 4 for this constructor). Added a duplicate,
   never-elsewhere-used token (`instr8_map4tail` with `opcodeM4`/`RdM4`) and
   a parallel test constructor (`subx.w_t4`) using it instead of `instr8`,
   with the real constructor temporarily disabled to avoid an ambiguous-
   pattern compile error. Compiled clean (exit 0, same pre-existing WARN
   set), installed, reloaded live via ReloadSleighLanguage.java. Result:
   0x20843 STILL produced only a 1-byte function body (create_function
   dry_run) -- no change at all. Also re-checked 0x16671 (btst.w, untouched
   by this edit) as a control: also still stuck at 1 byte, as expected.
   CONCLUSION: the BUG-5-style token/byte-position collision is NOT the
   cause here -- ruling this out is useful negative data, don't re-try it.
   All test files reverted from backup, recompiled (identical WARN line
   numbers to the pre-test baseline, confirming a clean revert), reinstalled
   (sha256-verified match against the source copy), and reloaded live before
   ending the session -- project is back to its pre-test state.

   REVISED NEXT STEP: since a fresh, non-conflicting token for the byte-4
   opcode/Rd read didn't help, the fault more likely sits earlier in the
   chain -- in `eaw_disp16` itself (mode=15/sz=1 gating via `Rn_banked`,
   h8539f.slaspec line 635) or in how SLEIGH resolves the *whole* pattern
   for 0xF0-0xFF once `disp16` is chained after the addrMode constraint,
   rather than in the trailing opcode field specifically. Both known-broken
   instances (subx.w, btst.w) share `eaw_disp16` but use unrelated final
   opcodes (22 vs whatever btst's is) and unrelated A4tail indices (18 vs
   26) -- the one thing they share is `eaw_disp16` and the word-size MAP4
   escape, so that's the next place to isolate. Concrete next test: try a
   completely standalone constructor that consumes ONLY `eaw_disp16` (no
   trailing opcode/Rd byte at all, just 3 bytes) to see whether `eaw_disp16`
   matches on its own at 0x20843's first 3 bytes -- this isolates whether
   the EA subtable itself is reachable at all for this byte class, independent
   of any opcode-field collision. Note this test constructor will need a
   throwaway disambiguating constraint to avoid an ambiguous-pattern clash
   with the real opcode-bearing constructors that also start with
   `eaw_disp16` -- don't install a version of this test that could leave
   real subx.w/btst.w unreachable if left in by mistake.

   PATTERN NOTE (2026-07-26): two more 0xFF-prefixed MAP4 1-byte-stub
   occurrences found via dasm85 diffing of unrelated ROM ranges, both with
   ZERO xrefs (unreached, per get_xrefs_to):
     - 0x14655: FF 17 F8 12 ... -> byte4=0x12 resolves to A4[0x12]=H8500_null
       (ana.cpp itself rejects this as not a valid instruction -- likely
       genuine dead/unreached bytes between two real functions at 0x14653
       and 0x14735, not a grammar bug).
     - 0x16671: FF F1 3F F1 ... -> byte4=0xF1 resolves to A4tail[26]=
       H8500_btst (ana.cpp says `btst.w #1,@(0xF13F:16,R7)` IS valid,
       matching dasm85's own read) -- yet Ghidra still produces only a
       1-byte stub here too. Also zero xrefs, so likely unreached, but
       unlike 0x14655 this is a case where the bytes ARE valid per ana.cpp
       and the grammar still fails to produce them -- same failure class as
       the main 0x20843 bug, just reached via a different opcode
       (btst vs subx). Strengthens the case that the bug is systemic to the
       whole MAP4(word)->ds16(byte1)->A4/A4tail dispatch path, not specific
       to one opcode -- worth keeping in mind when designing the fix so it
       covers the general path rather than just the subx case.
     Neither address has been fixed or further investigated -- noted here
     as corroborating data points for whoever works the TO FIX section above.

   SUPERSEDED THEORY 1 (grammar gap): initially looked like the Sleigh
   grammar only implements MAP4 for opcode47=14 (0xE0-0xEF, 8-bit
   displacement) and is missing an opcode47=15 (0xF0-0xFF, 16-bit
   displacement) mirror. WRONG -- the EA-addressing infrastructure
   (eab_disp16/eaw_disp16, mode=15) is already generic across all of
   mode=10-15 and does not need a MAP4-specific opcode47=15 family; see
   h8539f.slaspec's "BUG 4b" comment (~line 813-824), which already found
   and removed a MAP4-only 0x80-0x9F duplicate block for the same reason.

   SUPERSEDED THEORY 2 (missing divxu.w EA form): this whole theory is now
   MOOT -- see the 2026-07-26 correction above. The instruction at 0x20843
   is `subx.w`, not `divxu.w`, so whether a divxu.w EA form exists in
   h8539f-arith.sinc is irrelevant to this bug. (For the record, the
   original note found `:divxu.w eaw_disp16,Rd is eaw_disp16; opcode=23 &
   Rd { ... }` at line 716 and confirmed it compiles -- that finding may
   still be true, it just isn't the fix for THIS address.)

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

   TO FIX (updated 2026-07-26 for the corrected subx.w target): trace the
   compiled .sla's actual decision tree for this byte pattern (not just the
   .sinc source text) to find where the real MAP4-then-subx path diverges
   from whatever construct is supposed to match `subx.w` under
   MAP4(word)->ds16(byte-1)->A4tail[18]. Likely needs the same fix pattern
   as BUG 5 (a byte-position-scoped duplicate token/subtable, e.g. an
   "eaw_disp16_map4" analogous to the existing _2-suffixed byte-2-scoped
   forms) rather than reusing a plain eaw_disp16 subtable as-is inside the
   MAP4 dispatch path -- same mechanism as originally suspected, just the
   wrong opcode was named. FIRST STEP: grep h8539f-arith.sinc for the
   existing `subx` constructor(s) (there should be at least one for the
   A3tail path per the "Verified correct" list above) and check whether a
   word-sized, MAP4-routed EA form analogous to the divxu.w one at line 716
   exists for subx at all -- if not, that absence (not a collision) may be
   the actual bug. After fixing, re-run the build/test workflow below and
   re-disassemble 0x20843 (currently a stuck 1-byte FUN_00020843 stub) to
   confirm a real multi-byte `subx.w @(0x123C:16,R7),R7` instruction is
   produced instead.

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
     - f516 bit1/bit12 writer -- CLOSED (2026-07-26): search_byte_patterns
       for the literal address bytes across the whole ROM found 27 touches
       of RAM f516 (vs 10 via plain xref lookup; the rest were individual
       instructions in already-known multi-branch functions, plus a
       previously-undefined jump-table case (0x28cc8) now disassembled and
       confirmed not to touch f516, plus one false positive at 0x232d0 --
       coincidental bytes inside an unrelated pointer table, ruled out by
       reading the table directly). None of the 26 genuine hits set bit1 or
       bit12. Same conclusion as bit13 above: closed as "no writer reachable
       via literal addressing," not "confirmed no writer exists" -- the
       ROM's bank-prefixed/indirect blind spot still applies. Full detail
       and method in mut_verification_status.md.
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

    UPDATE (2026-07-24, later same day) -- addr16_dp theory RULED OUT, all 77 remaining CONCATs
    investigated and traced to their real sources. None are addressing-grammar bugs:

    - addr16_dp (h8539f-arith.sinc: clr.b/w, neg.b/w, tst.b/w, not.b/w, shal/shll/shar/shlr.b/w
      under Rn=5 & mode=1; h8539f-branch.sinc: jmp) IS live in the grammar, but it operates on a
      compile-time literal addr16 baked into the instruction, not a runtime register -- so if it
      fired it would decompile as CONCAT12(DP, 0xLITERAL). None of the 18 remaining CONCAT12
      sites in this ROM match that shape. Same story as eab_predec/eaw_postinc from the earlier
      pilot: grammar-correct, just not exercised by this ROM's actual code.

    - CONCAT12 (18 sites, all of them): genuine 24-bit far-call pointer reconstruction from
      jump-table bytes, e.g. `(*(code *)(uint)CONCAT12(table_entry_addr[6],table_entry_addr[7]))()`
      -- a 1-byte bank/segment byte concatenated with a 2-byte offset word read out of a dispatch
      table at runtime to build a callable far pointer. Inherent to how this compiler encoded
      jump tables; NOT an addressing-mode artifact, NOT fixable via SLEIGH grammar changes (pure
      memory-read + indirect call, not an instruction-operand decode). Several of these functions
      already have in-source comments (dated 2026-07-15, predating this investigation) flagging
      their decompile as "untrustworthy"/"garbage" for exactly this reason -- a known, separate,
      already-tracked issue, not something introduced or explained by today's bankifyDP work.

    - CONCAT22 (15 sites): two distinct sources. (a) ~10 sites are genuine 32-bit dividend/
      remainder reconstruction from hi/lo 16-bit halves inside the division routines (CheckDivide
      area) -- correct, expected, not a bug. (b) ~5 sites are `byte_sum_banked(...)` call sites
      building a pointer from what looks like the Rs32/Rn32 constructs (h8539f.slaspec lines
      495-506: `(zext(R0)<<16)|zext(R1)` etc. for R0:R1/R2:R3/R4:R5/FP:SP register PAIRS) -- a
      separate manual zext/shift/OR family, unrelated to DP banking entirely. Could potentially
      get the same spSegment-style treatment as a future optional cleanup, but it's a different
      mechanism/different bug and not required -- not a fix, just possible further polish.

    - CONCAT11 (44 sites, all of them): byte-pair-to-word math inside fixed-point/multiply/
      division helper functions (e.g. term_y1/term_a_lo_x_frac interpolation, product/shift
      helpers) -- genuinely "combine a hi-byte and lo-byte computation into a 16-bit result,"
      not an artifact of any banked-addressing construct.

    CONCLUSION: the CONCAT cleanup effort (this item) is effectively DONE. The remaining 77
    CONCATs are correct representations of genuine byte/word-combining operations or a separate,
    already-tracked jump-table issue -- not grammar bugs -- so there is nothing further to fix
    here via SLEIGH changes. Item 13 (DAT_ renaming) and struct work can now proceed on top of
    a decompile that is understood and trustworthy everywhere except the already-flagged
    far-call/jump-table functions noted above (treat those specific functions' decompile with
    caution; use raw disassembly there instead, per the existing in-source warnings).

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

15. Prototype-pass CONCAT/extraout_/unaff_ regression (2026-07-24, discovered via
    Rs32/Rn32 investigation) -- ROOT CAUSE FOUND, NOT YET FIXED. This is UNRELATED
    to Rs32/Rn32 or any SLEIGH grammar work; item 14's CONCAT cleanup remains
    genuinely complete as concluded above.

    DISCOVERY PATH: while investigating whether Rs32/Rn32 (h8539f.slaspec lines
    499-506, unreferenced dead grammar, see item 14's CONCAT22 note) needed a fix,
    deleted them, recompiled clean (exit 0), reinstalled, and re-diffed decompile
    output against baseline (md352553.hex.c) expecting zero change. Instead found
    CONCAT total 77->92 (+15: CONCAT11 44->57, CONCAT22 15->17), extraout_ 526->532
    (+6), unaff_ 99->103 (+4), WARNING unchanged 644->644. Restored Rs32/Rn32,
    recompiled, reinstalled, re-diffed again -- new output (md352553_fix4.hex.c) was
    BYTE-IDENTICAL (sha256 match) to the regressed one (md352553_fix3.hex.c),
    proving Rs32/Rn32 had zero effect either way and the regression predates/is
    independent of that edit entirely.

    TRACED TO: the item 12/13 function-prototype-setting pass on the 4g63t ROM
    (functions_evo5.md, ~85 of 302 functions marked [x] same day). Cross-referenced
    every function containing a new CONCAT11/CONCAT22 site against functions_evo5.md's
    [x] list: 10 of ~28 flagged functions (div_s32_s16_rounded, mul_u16_x2_sat,
    mul_u16_x2_sat_alt, axis_lookup_interp, weighted_blend_u8frac,
    serial_fec3_load_byte0_init, muldiv_s16_rounded_3op, div_u32_u16_sat,
    adc_sensor_convert_single, sci1_boot_rxbuf_read) are THEMSELVES newly-prototyped
    functions now showing new CONCATs inside their own decompiled bodies; the
    remaining ~18 (egr_f0e6_bit1_update, isc_f0e6_bit0_update,
    sci1_boot_cmd_dispatch, o2_heater_duty_f4da_calc, tcu_shift_ratio_buffer_update,
    etc.) are CALLERS of newly-prototyped functions, now showing new CONCATs at
    the call site instead.

    MECHANISM (confirmed for egr_activity_condition_check as a concrete example):
    prototyped `[x]` with no annotation in functions_evo5.md (unlike its immediate
    neighbor isc_dashpot_override_check, one line above, which IS annotated "FIXED
    -- __stdcall_far root cause, resolved"). Its decompiled body now carries an
    explicit decompiler comment: "WARNING: Unknown calling convention -- yet
    parameter storage is locked" -- and its caller (egr_f0e6_bit1_update) reads its
    bool return via `CONCAT11(extraout_var,bVar2)` instead of a clean bool, the
    exact symptom already diagnosed and fixed elsewhere in this same session for
    update_max/o2_*/fuel_cut_rpm_offset_select/etc. via the __stdcall_far pattern.

    IMPORTANT CAVEAT: checked egr_activity_condition_check's call site directly --
    it's an ordinary same-page call inside egr_f0e6_bit1_update (no far-return
    stack-offset shift, no extra far-call artifact like update_max's diagnosis
    required). This does NOT cleanly match the __stdcall_far-vs-__stdcall_far_allstack
    diagnosis used for the other fixes; it may be a different flavor of the same
    underlying "unknown calling convention" family (possibly needing an explicit
    non-far convention specified rather than left as default_proto), or an actually
    distinct root cause that happens to produce the same CONCAT11/extraout_ symptom.
    TO CONTINUE: do NOT assume __stdcall_far is the fix here just because it worked
    for the far-called cases -- confirm what real calling convention this function
    (and the other ~27 flagged, most of which have not yet been individually
    checked for far-vs-near) actually needs before changing prototypes, the same
    per-function verification discipline already used for update_max/o2_*/etc.
    rather than a blanket reapplication of __stdcall_far to the whole flagged list.

    NEXT STEPS: (1) for each of the ~28 flagged functions, determine actual
    calling context (far-called via computed jump table vs plain same-page call)
    the same way update_max was diagnosed; (2) apply the calling-convention fix
    each one actually needs (not necessarily __stdcall_far uniformly); (3) re-run
    the CONCAT/WARNING/extraout_/unaff_ diff against md352553.hex.c baseline after
    each batch to confirm convergence back to 77/644/526/99; (4) once clean,
    resume item 13 DAT_ renaming/struct work as already sequenced above, now on
    a decompile that reflects BOTH the CONCAT cleanup (item 14) and a fully
    verified prototype pass (this item), not just the former.

    UPDATE (2026-07-24, later same day) -- LIKELY REAL ROOT CAUSE FOUND, supersedes
    the __stdcall_far/calling-convention hypothesis above as the primary suspect
    (that may still be a real, separate issue for some functions, but is probably
    not the main driver of this regression). The custom "H8 ExtraPop/Return Purge
    Analyzer" logged explicit conflicting-purge-value warnings during this same
    analysis pass:
      sat_add_s16: existing 12, new 4 (from prts at 0x14034) -- kept existing (12)
      sat_sub_u16_clamp0: existing 12, new 4 (from prts at 0x1405a) -- kept existing (12)
      muldiv_u16_scaled: existing 2, new 4 (from prts at 0x14217) -- kept existing (2)
      muldiv_s16_rounded_3op: existing 2, new 4 (from prts at 0x14291) -- kept existing (2)
      select_min_xy_triple: existing 16, new 4 (from prts at 0x144b2) -- kept existing (16)
    muldiv_s16_rounded_3op is directly on this item's CONCAT-delta list (one of the
    10 functions with new CONCATs inside its own decompiled body); the other 4 are
    good candidates to re-check against that list too (not yet cross-referenced).

    MECHANISM: this project's custom analyzer computes each function's stack-purge
    amount (the H8 prts/rts variable-purge return convention) from the actual
    prts/rts instruction bytes it finds, but when it encounters a SECOND prts site
    with a different apparent purge value for a function it already has a value
    for, it logs a conflict and keeps the OLD value rather than resolving which is
    correct. If the true/uniform purge for these functions is actually 4 (all five
    conflicts agree on 4 as the "new" value, suggesting 4 is a real, consistent
    finding, not noise) and the stale existing values (12/2/16) are wrong -- e.g.
    left over from an earlier, less-informed analysis pass, or from before some
    other grammar/prototype fix changed how these functions are called -- then
    every caller of these functions is being decompiled against a WRONG stack purge
    amount, which would directly explain the extraout_/CONCAT/unaff_ garbage: the
    decompiler's stack-effect modeling for the call would be off, producing exactly
    this class of symptom.

    OPEN QUESTIONS, not yet resolved: (1) why does a single function have multiple
    prts sites with different implied purge values in the first place -- multiple
    return points in the same function should agree, unless some sites are in
    dead/unreachable code, a different function's body was mis-absorbed (same
    class of bug as item 11/item 6's absorption bugs), or the analyzer's byte-level
    purge computation itself has a bug; (2) which value (existing or new-4) is
    ACTUALLY correct for each function -- not yet independently verified by reading
    the real prts operand bytes at both the old and new sites; (3) is 4 uniformly
    correct across all five, or coincidentally the same wrong value from a common
    analyzer bug; (4) does fixing the analyzer's conflict-resolution (or manually
    overriding these 5 functions' purge to 4, if confirmed correct) actually close
    the CONCAT/extraout_/unaff_ gap back to baseline -- not yet tested.

    TO CONTINUE: for each of the 5 (starting with muldiv_s16_rounded_3op since it's
    already confirmed on the CONCAT-delta list), read the raw prts instruction
    bytes at BOTH the site backing the existing purge value and the new one at
    the addresses logged above, per H8/500 Programming Manual prts encoding (purge
    count is encoded in the instruction itself), to determine which value is
    actually correct before overriding anything. Do NOT blanket-apply 4 to all
    five without this check -- same discipline as the __stdcall_far fixes above,
    which were resolved individually, not by pattern-matching. Once the correct
    value per function is confirmed, re-run the CONCAT/WARNING/extraout_/unaff_
    diff to see how much of the 15/6/4 gap (CONCAT/extraout_/unaff_) these 5
    account for; remaining gap (if any) still needs the calling-convention check
    described above for the other ~23 flagged functions.

    CORRECTION (2026-07-24, later still) -- the "~28 flagged functions" scope
    above (10 self + ~18 callers) was WRONG, from a buggy analysis method: a
    regex-based per-function body extraction (matching up to the next standalone
    "}") mis-attributed several functions as unchanged/changed due to overlapping
    matches -- confirmed muldiv_s16_rounded_3op specifically was a false positive
    (its body is byte-for-byte identical between fix2/fix3; its CONCAT22 at the
    uVar1 reassignment line is the pre-existing, already-documented-correct 32-bit
    dividend-reconstruction pattern from item 14's CONCAT22 case (a), not a new
    regression site). Re-ran with a proper line-level Compare-Object diff instead:
    actual scope is 2499 differing lines (1251 added/changed, 1248 removed),
    covering roughly 100+ function signatures gaining explicit calling-convention
    annotations they lacked in fix2 (__stdcall_far_allstack, __stdcall_far_allstack_32ret,
    __stdcall_far, or newly-explicit return/param types on previously-untyped
    functions), plus at least 22 new DAT_/UNK_ global variable declarations. This
    is consistent with the item 12/13 prototype pass being far larger in its
    actual decompile impact than the ~28-function estimate suggested -- the
    real diff touches a large fraction of the ~85-of-302 functions marked [x],
    not a small isolated subset. UPDATE (2026-07-24, live ROM verification): the
    5-function purge-conflict list from the ExtraPop/Return Purge Analyzer
    (sat_add_s16, sat_sub_u16_clamp0, muldiv_u16_scaled, muldiv_s16_rounded_3op,
    select_min_xy_triple) is DROPPED IN FULL, not just narrowed. Checked the
    analyzer source (H8FunctionPurgeAnalyzer.java): it only reads a purge value
    off `prtd`/`rtd` mnemonics (they carry an s8/s16 scalar operand in the
    grammar); `prts` has no purge operand at all and is invisible to this
    analyzer. Live-disassembled all five functions from the running Ghidra
    instance (sat_add_s16 @0x1401f, sat_sub_u16_clamp0 @0x14045, muldiv_u16_scaled
    @0x141dc, select_min_xy_triple @0x14471, plus the already-cleared
    muldiv_s16_rounded_3op): each has exactly ONE return, always `prts`, at
    exactly the addresses the log lines cited (0x14034, 0x1405a, 0x14217,
    0x144b2) -- no `prtd`/`rtd` anywhere in any of the five bodies. So the logged
    "conflicting purge value ... from prts" messages cannot have come from this
    analyzer under any reading (not a second real return site, not a mis-logged
    address) -- the whole lead does not explain the CONCAT/extraout_/unaff_
    regression and should not be pursued further.

    TO CONTINUE (revised): (1) [CLOSED -- see update above, no re-verification
    needed, this lead is dead] (2) given the much larger true scope, prefer
    diffing at the level of "which functions have a changed signature line"
    (the list above) as the primary map of what actually changed, rather than
    trying to hand-verify calling conventions one at a time across 100+
    functions; (3) the size of this diff makes a systematic tool the right
    approach -- e.g. a script that, for each function whose signature changed,
    reads its actual prts/rts purge bytes directly (same technique as the
    ExtraPop analyzer) and cross-checks against what Ghidra now has recorded,
    flagging real mismatches -- rather than continuing manual spot-checks.

    UPDATE (2026-07-24, later still) -- ROOT CAUSE FOUND for a real subset of the
    regression, likely CONNECTED TO ITEM 10. Live-verified counts (fix2 baseline
    vs fix5, exported after a real reanalyze): CONCAT11 +13, CONCAT22 +2,
    extraout_ +6, unaff_ +4, WARNING -6 (WARNING went DOWN, everything else stayed
    flat vs fix3 -- confirms this is real, not just line-count noise from the
    prototype pass, and confirms progress on the WARNING front specifically).

    Traced 8 of the flagged call sites (isc_f0e6_bit0_update,
    f0ea_bit6_update_from_mode_check, egr_f0e6_bit1_update,
    f0ea_bit7_rpm_zone_update, f20e_f210_clear_chain_and_o2_closedloop_gate,
    o2_closed_loop_fuel_trim_compute, f26e_o2_closed_loop_output_blend_via_table,
    eeac_adaptive_trim_learn_update_via_table) to 6 distinct callee functions, all
    sharing one symptom: each callee had "WARNING: Unknown calling convention --
    yet parameter storage is locked" in its own decompile, and each callee is a
    plain near function (confirmed via live disassembly: simple stm/mov prologue,
    ends in bare prts, no purge operand, no far-call artifact) that had been left
    with an unresolved calling convention by the item 12/13 batch prototype pass.

    FIXED (verified): set all 6 callees to explicit __stdcall bool/undefined1
    return types -- egr_activity_condition_check@0x18628,
    knock_condition_eval@0x174d4, engine_mode_f512_bit4_check@0x185de,
    rpm_zone_enable_check@0x192ac, o2_closed_loop_config_check@0x1a15c,
    o2_downstream_type34_check@0x1a1cc. Each callee's OWN decompile is now clean
    (warning gone, tight bool return, e.g. knock_condition_eval went from an
    opaque one-liner to its full real logic being readable for the first time).
    This is real, durable progress -- confirmed by the WARNING count dropping
    644->638 after a real reanalyze (not just force_decompile).

    NOT FIXED: the CALLER side (e.g. egr_f0e6_bit1_update calling
    egr_activity_condition_check) still shows CONCAT11(extraout_var, bVar) at the
    call site, unchanged, even after: force_decompile on the caller, a full
    program reanalyze, ReloadSleighLanguage, AND a full delete+recreate of the
    caller function itself. Ruled out as caching/staleness at every layer
    reachable via the MCP tools -- the caller's decompile is being freshly
    regenerated each time and is genuinely still choosing to CONCAT-pad the
    return read.

    DEAD END, DO NOT RETRY: tried adding a tight 1-byte output pentry
    (`<register name="R0:1"/>`) to the __stdcall prototype in h8539f.cspec to
    stop the decompiler reserving R0's phantom high byte for byte-sized returns.
    This is INVALID Ghidra syntax -- threw CompilerSpecNotFoundException /
    "Unknown pentry register: R0:1" (XmlParseException in AddressXML.restoreXml)
    on load, confirmed via the exact Ghidra stack trace. Ghidra <register> pentry
    entries must name an actual defined register; h8539f.slaspec has no
    byte-sized sub-register of R0 (R0 is a single 2-byte register at offset
    0x00; the R0:R1 pairing idea was ALSO tried and reverted 2026-07-22, same
    area, see h8539f.slaspec's own comment there). REVERTED same day, .cspec
    restored to byte-identical original `<output>` block (just
    `minsize="1" maxsize="2"` on plain R0), re-validated as parseable XML,
    recompiled (sleigh.bat exit 0), recopied to the Ghidra install, timestamps
    confirmed matching. The attempt and revert are documented inline in
    h8539f.cspec's own comments at the same location, so this dead end doesn't
    get rediscovered blind.

    RULED OUT the pentry-width theory entirely (2026-07-24, cross-checked
    against Ghidra's own shipped x86-16.cspec, which review.md's own extrapop
    history already cites as this file's precedent). x86-16.cspec's
    __stdcall16near/default_proto uses the EXACT SAME pattern h8539f copied --
    extrapop="unknown" plus a bare `minsize="1" maxsize="2"` output pentry on
    the full 16-bit AX register, no separate byte-sized AL output pentry
    anywhere, across all 5 of its prototypes. This is standard, shipped,
    working Ghidra practice for a 16-bit near-call ABI -- so a bare 2-byte
    output pentry was never the actual defect; the R0:1 idea was solving a
    problem that pentry sizing doesn't actually cause.

    LIKELY REAL MECHANISM (not yet fixed, not yet proven, next concrete lead):
    this may be THE SAME underlying issue as item 10's "Unable to track
    spacebase fully for stack" warning, not a separate bug. Item 10 already
    root-caused that a function with extrapop="unknown" makes the decompiler's
    stack-effect solver build a system of equations across every call site,
    and CALLOTHER ops (like the spSegment used throughout this cspec, see item
    9/14) aren't one of the solver's 5 recognized shapes -- so the solver can't
    fully resolve calls through such functions and falls back to conservative,
    padded reads at the CALLER. All 6 functions fixed in this item still sit
    under __stdcall, which -- like item 10's default_proto -- has
    extrapop="unknown". If item 10's mechanism is the actual cause, the fix
    isn't anything in the output pentry at all: it's item 10's own untried
    fix candidate (a <callotherfixup> that expands spSegment(TP, SP) into
    concrete arithmetic when TP==0, making the address transparent to the
    spacebase solver in the common case). NOT YET ATTEMPTED -- item 10's own
    entry describes this as "NOT YET IMPLEMENTED OR TESTED", and it has a much
    larger blast radius (every function using spSegment, not just these 6) so
    it needs the same caution as the R0:R1/R0:1 attempts, not another
    live-database trial-and-error pass. TO CONTINUE: before touching the
    cspec/pcode again, first confirm the connection is real -- e.g. check
    whether the 6 fixed functions (or their callers) actually go through
    spSegment/CALLOTHER at all in their pcode (egr_activity_condition_check's
    own body, at least, does NOT touch DP/EP/stack-relative addressing per its
    disassembly, so this connection is a hypothesis from shared extrapop
    behavior, not yet a confirmed shared code path -- may need a different or
    additional mechanism specific to return-value tracking rather than
    stack-address tracking).

----------------------------------------------------------------------------------
16. dasmh85 vs ana.cpp disagreement at 0x14655 -- CLOSED (2026-07-26). dasmh85's
    EXTU.W @(H'17F8:16,R7) decode at this address is confirmed WRONG against the
    H8/500 Programming Manual (EXTU is register-direct only, fixed 2-byte
    encoding, byte-sized -- it can never take a disp16 EA or .W form). ana.cpp's
    original read (byte4=0x12 -> H8500_null, genuine dead/unreached flash filler)
    stands as correct. Root cause of the dasmh85 false positive (getea() greedily
    consumes any EA-mode-shaped prefix with no check that the following opcode
    byte is actually legal in that addressing mode) is documented in
    disasembler/dasmh85/KNOWN_BUGS.txt -- see that file for the full mechanism
    and a general caution about trusting dasmh85 after any EA-prefixed byte.

    ADDENDUM to item 4, NEW LEAD for the actual open bug (2026-07-26): Rn_banked's
    Rn=7 case (h8539f.slaspec ~line 583) is not a plain "R7" -- it's named "SP"
    and its pcode is `local ptr24:4 = spSegment(TP, SP); export ptr24;`. Since
    eaw_disp16 (the subtable subx.w's EA form is built on) is built directly on
    Rn_banked, the EA computation at 0x20843 (`@(0x123C:16,R7)`) is not flat
    R7+disp16 as item 4's manual trace phrased it ("R7 = SP by H8 convention"
    was noted only as an aside) -- it is a SEGMENTED pointer computed via the
    exact same spSegment(TP, ...) CALLOTHER pcodeop that item 10's entire
    "Unable to track spacebase" investigation is about. This had not been
    connected before. NOT YET TESTED: whether Sleigh's compiled decision tree
    has trouble routing through a subtable whose export ultimately depends on
    a pcodeop (spSegment) rather than plain arithmetic -- a materially
    different shape than most other EA subtables in this grammar -- which
    could explain the "compiles fine, doesn't match at runtime" failure
    independently of the byte-position/token-collision theory already tested
    and ruled out above. TO CONTINUE: isolation test -- temporarily change
    Rn_banked's Rn=7 case to a plain `zext(SP)`-style export (no spSegment),
    recompile, reinstall, reload, and check whether 0x20843 still gets stuck
    at a 1-byte function body. If it starts disassembling, spSegment/CALLOTHER
    in this subtable position is implicated; if it's still stuck, this lead is
    ruled out same as the token-collision theory. MUST revert after the test
    either way, following the same backup/revert discipline as the earlier
    instr8_map4tail isolation test above.

    TESTED AND REJECTED (2026-07-26, same day): ran the isolation test above.
    Backed up h8539f.slaspec/.sla, changed Rn_banked's Rn=7 case to
    `local ptr24:4 = zext(SP); export ptr24;` (no spSegment call), compiled
    clean (exit 0, identical pre-existing WARN set), reinstalled, sha256-
    verified match, reloaded live via ReloadSleighLanguage.java. Result:
    0x20843 STILL produced only a 1-byte function body -- create_function
    (both dry_run and real) reported body_size=1, and the decompile showed the
    exact same "WARNING: Control flow encountered bad instruction data" /
    "Bad instruction - Truncating control flow here" / halt_baddata() failure,
    byte-for-byte identical to the pre-test state. CONCLUSION: spSegment/
    CALLOTHER inside Rn_banked's Rn=7 case is NOT the cause -- ruling this out
    is useful negative data, don't re-try it. All test files reverted from
    backup (diff-confirmed byte-identical), recompiled (identical WARN line
    numbers), reinstalled (sha256-verified match), reloaded live, and a fresh
    XML export of sci1_boot_switch_case4_frag_20640 confirmed byte-for-byte
    identical to the pre-test export (same size=1 function, same tracked
    context values) -- project is back to its pre-test state. Combined with
    the earlier instr8_map4tail rejection, TWO separate hypotheses are now
    ruled out for this bug: (1) BUG-5-style token/byte-position collision on
    the trailing opcode/Rd field, and (2) spSegment/CALLOTHER appearing inside
    the Rn_banked EA subtable. The fault most likely sits somewhere in how
    Sleigh's compiled decision tree resolves the overall MAP4(word)->
    ds16(byte1)->A4tail(byte4) multi-stage chain itself, independent of what
    any individual leaf subtable's pcode body contains -- next investigator
    should look at the compiled .sla's actual decision tree structure (not
    just source text) for this byte pattern, per the original TO FIX note
    above, rather than trying further leaf-subtable substitutions.

    MAJOR BREAKTHROUGH (2026-08-02, session 3, continued): used
    ghidra.app.plugin.processors.sleigh.SleighDebugLogger directly (via a real
    .java script file copied into Ghidra's ghidra_scripts path -- inline
    scripts hit the same OSGi ClassNotFoundException gotcha noted elsewhere;
    also note the correct API is `new SleighDebugLogger(Program, Address,
    SleighDebugLogger.SleighDebugMode.VERBOSE)` -- there is no `Verbosity`
    enum, that was a wrong guess corrected via `javap` on the real class from
    SoftwareModeling.jar) to get the actual low-level parse trace for
    0x20843, rather than continuing to infer from create_function's
    pass/fail summary.
    RESULT: the parse SUCCEEDS COMPLETELY. Every decision-tree node, every
    byte-pattern mask/value check, matches correctly, all the way through:
    `Prototype parse successful: subx.w @(0x123c:16,SP),SP / Instruction
    length = 4 bytes`. This is byte-for-byte consistent with the
    independently-verified ground truth (dasm85 + hand-traced ana.cpp:
    `subx.w @(0x123C:16,R7),R7`, R7=SP by convention). THE GRAMMAR/PATTERN
    WAS NEVER BROKEN. This retroactively explains why all four leaf-level
    isolation tests (token/byte-position collision, spSegment/CALLOTHER,
    addrMode field collision, full subtable inlining) changed nothing --
    there was never anything wrong with the leaf pattern for them to fix.
    CRITICAL DETAIL: this successful parse ran with
    `initial context bits: 00000000.00000000.00000000.00000000` -- a blank,
    default all-zero context, NOT necessarily whatever context register
    state (CP, DP, TP) Ghidra's real flow-based disassembly actually carries
    when it arrives at 0x20843 via normal analysis from wherever this
    function's real entry point/control flow originates. This is a
    completely different variable from anything the four rejected leaf
    tests touched.
    NEW LEAD, STRONGLY SUPPORTED: this project already has a separate,
    independently-documented limitation that fits perfectly here -- CP is
    not modeled as a SLEIGH context variable (see the
    knock_octane_dual_axis_blend_far_trampoline far-call mis-resolution
    elsewhere in this file, and the general CP-register limitation noted in
    the README). If real disassembly reaches 0x20843 carrying a wrong/stale
    context register value inherited from upstream control flow, the exact
    same bytes could resolve completely differently (or get blocked/produce
    a 1-byte stub) under real analysis conditions, while a standalone
    SleighDebugLogger test with a clean default context parses perfectly --
    which is exactly the discrepancy observed. Also consistent with
    disassemble_bytes(00020843, length=6) reporting success=true earlier
    this same session (a standalone/direct disassembly call, not going
    through normal function-creation flow) while create_function's dry_run
    at the same address kept reporting body_size=1 (which DOES go through
    normal flow-based context propagation) -- same pattern, now explained.
    NEXT STEP (not yet done): check what context register value(s) are
    actually active/propagated at 0x20843 during real flow-based
    disassembly (vs. SleighDebugLogger's default zero), likely by examining
    the calling code path into this address and/or the CP-register handling
    specifically. This is a genuinely different investigation thread from
    the leaf-substitution approach (now confirmed exhausted and,
    retroactively, never applicable) -- treat prior TO FIX guidance in this
    item as superseded by this finding; the fix, if confirmed, will be in
    context propagation/CP-register modeling, not in eaw_disp16, Rn_banked,
    addrMode, or any subx.w constructor variant.

    TESTED AND REJECTED (2026-07-26, session 2): a third leaf-level hypothesis --
    byte-position-scoped duplicate of `addrMode`'s mode/sz/Rn fields themselves
    (not just instr8's opcode/Rd, already ruled out above), on the theory that
    `eaw_disp16`'s own EA-description fields might be the ones colliding with
    byte-1 usage when reached via the MAP4 tail, independent of the two already-
    ruled-out mechanisms. Added a fresh token `addrModeM4` (RnM4/modeM4/szM4,
    identical bit layout to addrMode, never used elsewhere), a parallel subtable
    `eaw_disp16_map4`/`RnM4_banked` mirroring Rn_banked/eaw_disp16, and a parallel
    test constructor `subx.w_t4` using it instead of eaw_disp16, with the real
    subx.w eaw_disp16 constructor temporarily disabled to avoid an ambiguous-
    pattern compile error -- same discipline as the two prior isolation tests.
    Compiled clean (exit 0, same pre-existing WARN set), installed, reloaded live.
    Result: 0x20843 STILL produced only a 1-byte function body (create_function
    dry_run, body_size=1) with the identical "WARNING: Control flow encountered
    bad instruction data" / halt_baddata() failure signature as every prior
    attempt -- no change at all. CONCLUSION: addrMode's mode/sz/Rn fields
    colliding with byte-1 usage is NOT the cause either -- ruling this out is
    useful negative data, don't re-try it. All test scaffolding (addrModeM4
    token, RnM4_banked/eaw_disp16_map4 subtables, subx.w_t4 constructor, the
    disabled real constructor) removed from h8539f.slaspec and h8539f-arith.sinc,
    recompiled (identical WARN line numbers to the pre-test baseline, confirming
    a clean revert), reinstalled (timestamps verified matching), reloaded live,
    and re-verified at 0x20843 back to the pre-test body_size=1 state via a real
    create_function dry_run call. Combined with the earlier instr8_map4tail and
    Rn_banked/spSegment rejections, THREE separate leaf-level hypotheses are now
    ruled out for this bug: (1) BUG-5-style token/byte-position collision on the
    trailing opcode/Rd field, (2) spSegment/CALLOTHER appearing inside the
    Rn_banked EA subtable, and (3) addrMode's own mode/sz/Rn fields colliding
    with byte-1 usage. Every individual leaf-subtable substitution tried so far
    has failed to change the outcome. This further reinforces that the fault
    sits in how SLEIGH's compiled decision tree resolves the overall
    MAP4(word)->ds16(byte1)->A4tail(byte4) multi-stage chain itself, independent
    of any individual leaf subtable's field layout or pcode body -- next
    investigator should inspect the compiled .sla's actual decision tree
    structure directly (e.g. via a disassembly/dump of the compiled tree, or
    Ghidra's SLEIGH debugger), not attempt further token/subtable substitutions
    in source, which is now a well-exhausted approach for this bug.

   TESTED AND REJECTED (2026-08-02, session 3, ISOLATION TEST #4 -- full
   inlining, zero subtables): credited to an external analysis document's
   proposed experiment. Unlike the three prior leaf-substitution tests (all
   of which still routed through a chained subtable pair with fresh tokens),
   this test eliminated subtable indirection entirely: a throwaway
   `:subx.w_t5` constructor consuming `disp16` directly at the top level
   (`is mode=15 & sz=1 & Rn=7; disp16; opcode=22 & Rd`), with pcode written
   by hand to faithfully reproduce Rn_banked's Rn=7/SP case
   (`spSegment(TP, SP)`) without calling through Rn_banked or eaw_disp16 at
   all. The real `:subx.w eaw_disp16,Rd` constructor (h8539f-arith.sinc line
   79) was commented out for the duration of the test to avoid an
   ambiguous-pattern compile error, same discipline as every prior test.
   Backed up h8539f-arith.sinc (h8539f-arith.sinc.bak_fullinline, byte-
   diff-verified identical to the pre-edit source both before the edit and
   again after revert), compiled clean (exit 0, identical 24 NOP / 40
   unnecessary-extension WARN counts to baseline, no ERROR lines),
   installed the full file set (.sla + all .sinc/.pspec/.cspec/.slaspec,
   timestamp-verified matching between source and Ghidra install dirs),
   reloaded live via ReloadSleighLanguage.java (copied into Ghidra's own
   ghidra_scripts search path first, per review2.md's documented gotcha).
   RESULT: 0x20843 STILL produced only a 1-byte function body
   (create_function dry_run, body_size=1) -- no change at all from the
   pre-test state. CONCLUSION: full subtable elimination is NOT the cause
   either -- ruling this out is useful negative data, don't re-try it.
   Reverted h8539f-arith.sinc from backup (byte-diff CONFIRMED IDENTICAL to
   pre-test source), recompiled (identical WARN counts to baseline),
   reinstalled (.sla content-length-verified matching between source and
   install, real .sinc content-verified matching via Compare-Object),
   reloaded live, and re-verified 0x20843 back to the pre-test body_size=1
   state via a real create_function dry_run call. Project confirmed back to
   its pre-test state.
   Combined with the three prior rejections (BUG-5-style token/byte-position
   collision, spSegment/CALLOTHER inside Rn_banked, addrMode field
   collision), FOUR separate hypotheses at the leaf/subtable-substitution
   level are now ruled out for this bug, including the most radical version
   (zero subtables at all). This is strong convergent evidence the fault
   genuinely lives in how SLEIGH's compiled decision tree resolves the
   overall MAP4(word)->ds16(byte1)->A4tail(byte4) multi-stage dispatch
   itself -- independent of literally any leaf construct's field layout,
   token identity, or pcode body, since none of the four different leaf
   substitutions tried have changed the outcome even slightly. Next
   investigator should treat further token/subtable substitution attempts
   at this address as a well-exhausted approach (four independent variants
   tried, zero effect) and instead inspect the compiled .sla's actual
   decision tree structure directly, or consider whether the bug sits
   further up the MAP4/ds16 dispatch chain itself (byte 1-4 routing logic)
   rather than in whatever consumes disp16 at the leaf.

   MAJOR BREAKTHROUGH (2026-08-02, session 3, continued): used
   ghidra.app.plugin.processors.sleigh.SleighDebugLogger directly (via a real
   .java script file copied into Ghidra's ghidra_scripts path -- inline
   scripts hit the same OSGi ClassNotFoundException gotcha noted elsewhere;
   also note the correct API is `new SleighDebugLogger(Program, Address,
   SleighDebugLogger.SleighDebugMode.VERBOSE)` -- there is no `Verbosity`
   enum, that was a wrong guess corrected via `javap` on the real class from
   SoftwareModeling.jar) to get the actual low-level parse trace for
   0x20843, rather than continuing to infer from create_function's
   pass/fail summary.
   RESULT: the parse SUCCEEDS COMPLETELY. Every decision-tree node, every
   byte-pattern mask/value check, matches correctly, all the way through:
   `Prototype parse successful: subx.w @(0x123c:16,SP),SP / Instruction
   length = 4 bytes`. This is byte-for-byte consistent with the
   independently-verified ground truth (dasm85 + hand-traced ana.cpp:
   `subx.w @(0x123C:16,R7),R7`, R7=SP by convention). THE GRAMMAR/PATTERN
   WAS NEVER BROKEN. This retroactively explains why all four leaf-level
   isolation tests (token/byte-position collision, spSegment/CALLOTHER,
   addrMode field collision, full subtable inlining) changed nothing --
   there was never anything wrong with the leaf pattern for them to fix.
   CRITICAL DETAIL: this successful parse ran with
   `initial context bits: 00000000.00000000.00000000.00000000` -- a blank,
   default all-zero context, NOT necessarily whatever context register
   state (CP, DP, TP) Ghidra's real flow-based disassembly actually carries
   when it arrives at 0x20843 via normal analysis from wherever this
   function's real entry point/control flow originates. This is a
   completely different variable from anything the four rejected leaf
   tests touched.
   ALSO CONSISTENT WITH: disassemble_bytes(00020843, length=6) reporting
   success=true earlier this same session (a standalone/direct disassembly
   call, not going through normal function-creation flow) while
   create_function's dry_run at the same address kept reporting
   body_size=1 (which DOES go through normal flow-based context
   propagation) -- same discrepancy, now explained rather than merely
   observed.
   CORROBORATING EXTERNAL EVIDENCE (2026-08-02): Ghidra core issue #817
   (github.com/NationalSecurityAgency/ghidra/issues/817, "Decompiler is not
   handling far pointers to stack/ram data correctly") independently
   confirms Ghidra's <segmentop>/<constresolve> mechanism -- the exact
   mechanism behind this project's own item 9 finding (EP not in
   constresolve because TP already claims that slot) -- has a real,
   maintainer-acknowledged gap: even when a cspec correctly declares a
   segment-register conversion, "it gets ignored within Ghidra" per a
   maintainer reply on that issue. IMPORTANT DISTINCTION: #817 is a
   decompiler-stage bug (pcode emission ignores the segment register for
   an already-correctly-disassembled instruction); the 0x20843 problem
   here is a disassembler-stage bug (SLEIGH fails to produce an
   instruction at all under real context propagation, despite parsing
   perfectly under SleighDebugLogger's default context). Different
   pipeline stage, but plausibly the same underlying root cause: Ghidra's
   context/segment-register modeling is incomplete for architectures with
   multiple banked/segment registers (H8's EP/TP/CP/DP), not just the
   single-DS-register case #817 documents for x86. Useful precedent for a
   future bug report: shows Ghidra's own team already partially
   acknowledges this general problem class exists.
   NEW LEAD, STRONGLY SUPPORTED: this project already has a separate,
   independently-documented limitation that fits perfectly here -- CP is
   not modeled as a SLEIGH context variable (see the
   knock_octane_dual_axis_blend_far_trampoline far-call mis-resolution
   elsewhere in this file, and the general CP-register limitation noted in
   the README). If real disassembly reaches 0x20843 carrying a wrong/stale
   context register value inherited from upstream control flow, the exact
   same bytes could resolve completely differently (or get blocked/produce
   a 1-byte stub) under real analysis conditions, while a standalone
   SleighDebugLogger test with a clean default context parses perfectly --
   which is exactly the discrepancy observed.
   NEXT STEP (not yet done): check what context register value(s) are
   actually active/propagated at 0x20843 during real flow-based
   disassembly (vs. SleighDebugLogger's default zero), likely by examining
   the calling code path into this address and/or the CP-register handling
   specifically. This is a genuinely different investigation thread from
   the leaf-substitution approach (now confirmed exhausted and,
   retroactively, never applicable) -- treat prior "next investigator"
   guidance in this item as superseded by this finding; the fix, if
   confirmed, will be in context propagation/CP-register modeling, not in
   eaw_disp16, Rn_banked, addrMode, or any subx.w constructor variant.

----------------------------------------------------------------------------------
17. Idle Stepper Look-up Table XML address bug -- FIXED (2026-07-27). Both duplicate
    XML entries ("Idle Stepper Look-up Table" and "Idle Stepper Lookup Table",
    21000011_1997-2001_RVR_X3_Mt__4g63t_.xml, new/) declared address="12992",
    matching EcuFlash's own Edit Table Metadata dialog and internally consistent
    with the declared axis addresses (Coolant Temp 2d4c0/8 elements, ISCV Demand
    2d4d6/27 elements). Despite that internal consistency, EcuFlash rendered a
    garbled first row (3, 0, 240, 192, 240, 194, 8, 0) against an otherwise clean,
    monotonic ISCVSteps surface from row 2 onward.

    ROOT CAUSE, traced via code (not guessed): disassembled
    idle_stepper_table_lookup_wrapper (0x268e2), the actual caller of
    table_lookup_interp for this table. Its literal args: table pointer #0x2992
    (bank-relative -> physical 0x12992, matching the XML), but the two preceding
    axis-setup calls push #0xd4ba and #0xd4d0 -- which bank-adjust to
    0x2d4ba/0x2d4d0, SIX BYTES BEFORE the XML's declared axis addresses
    (2d4c0/2d4d6). Direct ROM read at 0x2d4ba confirmed those six leading bytes
    are a header (F0 C0 F1 0E 00 08 -- two live RAM pointers) immediately
    followed by the real axis array starting exactly at 2d4c0 as declared. The
    identical header shape (03 mode byte + RAM pointers 0xf0c0/0xf0c2) is what's
    actually stored at 0x12992 -- confirming 0x12992 is an 8-byte runtime
    lookup-context header (mode + 2 live RAM pointer refs), not the data grid
    itself, which is why EcuFlash renders its bytes as a bogus row 0.

    VERIFIED FIX: real 8x27 (216-byte) ISCVSteps grid starts at 0x1299a (12992+8)
    -- confirmed via direct ROM read: clean monotonic surface
    (0,0,...,10x8,20x8,30x8... ramping to a 160-clamped ceiling) terminating in a
    0xFF sentinel with no overrun into neighboring tables. Both XML entries
    corrected to address="1299a". Logged in CHANGELOG.md.

    BROADER CAUTION this raises for item 3's planned XML verification work, REFINED
    same session after checking a second, neighboring table: initially suspected
    this was a generic "table address points at a stray header instead of the
    data grid" bug that might recur elsewhere (e.g. flagged "Max Total Upward
    WGDC Correction vs TPS", address 12a72, as a second suspected instance).
    Traced that second table's real caller (wgdc_correction_integrator_update,
    0x18fe0) and confirmed its own header bytes (02 00 F0C0 ...) are pushed
    and consumed exactly as designed -- not a bug. table_lookup_interp's own
    in-source plate comment (already documented from an earlier session)
    confirms this whole primitive family expects a small header-record as its
    input (mode byte, mode-selector byte, embedded RAM/axis pointers, stride
    byte) and does its own pointer arithmetic from there; table_3axis_interp_triple
    uses the same record shape. So the "03/02 mode byte + RAM pointers" pattern
    seen at 0x11ef0, 0x12992, and 0x2d5be/0x12a72 is NOT a header-vs-data-offset
    bug in the ROM -- it's the standard calling convention for this whole lookup
    family, and the Idle Stepper table's underlying ROM structure at 0x12992 is
    itself unremarkable/correct by that convention.

    REFINED CONCLUSION: the actual, narrower bug is specific to what EcuFlash
    needs vs. what the firmware's own code passes around. EcuFlash has no
    knowledge of this record-header convention -- it just reads N bytes at a
    declared address as a flat W x H grid. The ROM's real record pointer
    (0x12992) and EcuFlash's needed flat-grid start (0x1299a) are two different,
    both text-book-correct addresses for two different consumers; the XML fix
    (1299a) remains correct for EcuFlash's purposes even though it differs from
    what the firmware's own disassembly passes to table_lookup_interp. This is
    likely why "Max Total Upward WGDC Correction vs TPS" already renders fine in
    EcuFlash despite sharing the same header-record shape internally -- its
    header bytes probably still happen to plot as plausible-looking values under
    its DynamicBoost scaling, unlike the Idle Stepper table's header bytes,
    which spiked outside the sane ISCVSteps range and were visually obvious.
    CONFIRMED NO BYTE-RANGE OVERLAP between the two tables either way -- Idle
    Stepper's real 216-byte grid (1299a-12a71, terminating in a 0xFF sentinel)
    sits back-to-back cleanly against WGDC's declared start at 12a72, no
    collision.

    IMPLICATION FOR item 3's verify_xml_table() design: a per-table check should
    not assume "address points at flat data" universally -- for any table
    reached via table_lookup_interp/table_3axis_interp_triple with visibly
    anomalous leading bytes, the record-header convention should be checked
    first (does record[0] look like a plausible mode byte -- 2 or 3 -- followed
    by what looks like a RAM pointer pair in the F0xx-F7xx range?) before
    concluding the address itself is wrong. Only the Idle Stepper table has been
    confirmed to actually need its XML address adjusted; do not blanket-apply
    the same +8 offset to other type="3D"/table_lookup_interp-backed tables
    without individually confirming their header bytes visibly corrupt the
    EcuFlash rendering the same way.

    RELATED, SAME SESSION: investigated table_3axis_interp_triple (genuine
    3-argument trilinear primitive, distinct from EcuFlash's "3D" table-type
    label) -- only ONE real call site chain found (via
    f250_f252_channel_snapshot_update -> engine_periodic_correction_master_dispatch),
    passing table pointer 0x1ef0 (EP-banked, physical bank not yet resolved) and
    secondary arg 1. NOT YET RESOLVED: the table's first mode byte read via
    `cmp:g.b #0x3,@R4` in the function's disassembly determines whether this call
    takes the true 3-axis path or a simpler 2-point linear-interp fallback --
    determining which requires resolving the live EP value at the call site
    (0x24a3f), not yet done. An earlier same-session flat-address read at
    0x11ef0 assuming no banking is RETRACTED as unreliable -- do not reuse those
    byte values. Also retracted: a mistaken link between this table and the
    unrelated SCALING_OUT_F0CA label (that label comes from a different,
    already-existing scanner-found scaling table elsewhere in ROM, not from this
    one). TO CONTINUE: trace back from 0x24a3f to resolve the actual EP/bank
    value in effect, then re-read the table header correctly banked before
    concluding anything about its real axis/mode structure.

18. table_lookup_interp parameter binding + call-site argument visibility (2026-07-30)
    -- PARTIAL PROGRESS, root cause of the call-site problem still open. Follows
    directly from item 2/4's "Left as void(void)" note on this exact function.

    FIXED (real, durable, confirmed across recompile/reinstall/reload and a full
    Ghidra restart): table_lookup_interp's own two parameters now bind cleanly.
    A new __stdcall_far_2arg calling convention (h8539f.cspec) with extrapop=6,
    pentry1 offset=6 size=1 (ep_val), pentry2 offset=7 size=2 (table) gets the
    convention-level binding half right (ep_val binds, table doesn't via the
    convention alone -- see "NOT FIXED" below). The durable fix that actually
    works end-to-end was a direct per-function override, applied via
    run_script_inline using Function.updateFunction(..., CUSTOM_STORAGE, ...)
    with explicit VariableStorage(program, 6, 1) / VariableStorage(program, 7, 2)
    and a manually-constructed 2-byte pointer type (dtm.getPointer(voidDt, 2) --
    the default void* on this program is 4 bytes, which silently mismatches the
    real 2-byte table-pointer width read by the actual `mov:f.w @(0x8:8,FP),R4`
    instruction). Re-verified live after a full Ghidra restart tonight:
    get_function_variables shows ep_val@Stack[0x6]:1, table@Stack[0x7]:2, both
    resolved, no <UNASSIGNED>.

    NOT FIXED: the calling convention's own pentry resolution (i.e. applying
    __stdcall_far_2arg via set_function_prototype, without the manual storage
    override) still leaves the table parameter <UNASSIGNED> -- confirmed by
    directly re-applying it live and re-checking get_function_variables, which
    regressed back to <UNASSIGNED> until the manual override was re-applied.
    So the convention-level fix and the working fix are two different things;
    only the manual per-function override is proven. TESTED AND REJECTED: moving
    pentry2 to offset=8 with align="2" (an even offset, so alignment isn't
    self-contradictory the way it was at the previously-tried odd offset=7) --
    applied via set_function_prototype + get_function_variables, table came back
    <UNASSIGNED>, same failure as offset=7. This test's validity is itself
    slightly in question (a live CompilerSpecNotFoundException occurred around
    this same edit, root-caused below, so the test may have run against a
    stale/degraded compiler-spec state) and was not re-tried after the fix +
    restart, so this specific idea (offset=8/align=2) is reverted-but-not-fully-
    disproven if anyone wants to retry it cleanly later.

    NOT FIXED, separately and more fundamentally: even with the manual storage
    override in place, table_lookup_interp's own decompiled BODY still ignores
    the bound parameters entirely -- reads a raw `stack0xfffe+7` byte into a
    dead `uVar1` that's never used again, and builds its real working pointer
    from an uninitialized `undefined3 uVar8` instead of the bound `table`
    parameter. Confirmed via repeated force_decompile calls (bypassing any
    decompiler cache) across multiple points tonight, including fresh after the
    Ghidra restart -- byte-for-byte identical output every time, so this is a
    genuine, stable decompiler limitation, not staleness. The same symptom was
    independently found in axis_lookup_interp (already on item 10's list of 18
    spacebase-tracking-affected functions) via a completely separate analysis
    session: its `ldc.b @(0x7:8,FP),EP` load also produces a dead temporary that
    the decompiler never correlates with later EP-banked memory accesses.
    Verified live that `ldc.b ...,"EP"` constructors ARE normal, direct register
    writes in this grammar (e.g. `:ldc.b eab_disp8,"EP" ... { EP = eab_disp8; }`,
    h8539f-mem.sinc line 327) -- not a hidden/CALLOTHER pseudo-register, so the
    write mechanism itself is fine. The likely real explanation: EP's only
    consumer is bank selection for later `Rn_banked`/`spSegment(...)` CALLOTHER
    computations (the exact mechanism item 10 already tracks), and the
    decompiler can't correlate a register write with a downstream consumer that
    goes through an opaque CALLOTHER, leaving the write stranded/dead-looking.
    This reframes item 18's body-level symptom as very likely the SAME root
    cause as item 10, observed from inside a callee instead of at a spacebase
    warning. NOT YET CONFIRMED -- next step is to inspect the actual
    `spSegment` CALLOTHER definition and `Rn_banked`'s pcode directly (same
    verify-before-trusting discipline used throughout this item) rather than
    reasoning about it further.

    SEPARATELY INVESTIGATED, also not fixed: why NO far call anywhere in this
    ROM shows resolved callee names or bound arguments at the call site (all
    130 table_lookup_interp callers decompile as opaque `(*(code *)ADDR)()`
    despite direct, literal `pjsr @ADDR:24` instructions with literal pushed
    args in the real disassembly, e.g. calc_f110_f10e_via_table @ 0x21314
    pushing `#0x1` then `#0x32f8` before `pjsr @0x14656:24`). Root cause
    confirmed: every jmp/jsr/pjmp/pjsr constructor with an absolute/far target
    in h8539f-branch.sinc computes into a local variable and calls/jumps via
    bracket syntax (`addr:4 = zext(addr24:3); call [addr];`), which is a
    genuine indirect call (CALLIND) in pcode terms regardless of the target
    being a compile-time constant -- this prevents Ghidra from ever binding a
    resolved function/prototype at these call sites. Two direct-call fixes were
    tried on pjsr's addr24 form specifically and both failed to compile, then
    were fully reverted (recompiled exit 0, reinstalled, reloaded, re-verified
    byte-identical to baseline):
      1. bare `call addr24;` (matching bsr's working bare-token pattern,
         h8539f-branch.sinc reloffs8/reloffs16) -- fails: "Could not resolve at
         least 1 variable size".
      2. fixing absaddr24's export shape to a bare `export * addr24;` (matching
         h8520.slaspec's sibling grammar, which uses this successfully in its
         own :pjsr/:pjmp) -- fails: "Table 'absaddr24' has inconsistent export
         size". h8520.slaspec is itself unverified/possibly-never-compiled
         reference material (item 8), so this precedent doesn't actually hold.
    Both failure reasons and a "do not retry as-is" note are documented inline
    in h8539f-branch.sinc so this isn't rediscovered blind. This is tracked as
    a separate, likely-secondary issue from the item 10/EP connection above --
    real, confirmed, but not yet fixed, and potentially large blast radius
    (every far call in the ROM, not just this function) if ever revisited.

    CONFIRMED ROOT CAUSE, tying this item's dead uVar1/garbage-uVar8 symptom to
    item 9's already-accepted limitation (2026-07-30): table_lookup_interp's
    prologue immediately transfers its bound ep_val/table parameters into the
    real hardware registers -- `ldc.b @(0x7:8,FP),EP` then
    `mov:f.w @(0x8:8,FP),R4` -- rather than leaving them addressable as ordinary
    stack locals. Every subsequent @R4-style dereference in the function body
    therefore routes through Rn_banked's live definition
    (`local ptr24:4 = spSegment(EP, R4); export ptr24;`), a CALLOTHER pcodeop.
    Per item 9, `<constresolve>` only lists TP (already claimed by SP/FP
    banking) -- EP is deliberately not in there, and a direct attempt to add it
    previously threw a real ValidityViolation and was reverted. So the
    parameters bind correctly at the ABI/call level (this item's fix is real),
    but the moment they're loaded into EP/R4 and dereferenced they vanish into
    an unresolvable CALLOTHER chain the decompiler can't fold -- exactly this
    item's dead-variable pattern, and exactly what item 10's 18-function list
    already describes. This is a confirmed root cause, not a guess, and it's
    the same already-accepted Ghidra architectural limitation as item 9, not a
    new open bug. There is no further Sleigh-level fix available within the
    segmentop/constresolve mechanism itself.

    OPERATIONAL NOTE, unrelated to the H8 grammar itself but cost real time
    tonight: a live CompilerSpecNotFoundException ("the string -- is not
    permitted within comments") was thrown mid-AutoAnalysisManager-init,
    traced to several literal double-hyphen sequences accidentally written
    into h8539f.cspec's own historical comment blocks (this file's dash style
    throughout review.md/chat history uses a bare double-hyphen as a
    separator, which is invalid inside XML comments -- .sinc/.slaspec files
    use "#" line comments so this never bit those files, only .cspec/.pspec's
    XML comments). All instances found via grep for a double-hyphen not
    immediately followed by ">" (to exclude legitimate comment-close markers),
    fixed, and the file re-validated with a real XML parse ([xml] cast in
    PowerShell) before reinstalling -- eyeballing it is not sufficient, a
    literal parse check is required. Also confirmed operationally tonight:
    .cspec-level pentry/prototype changes need a full Ghidra restart to be
    trusted, not just ReloadSleighLanguage.java -- a script-level reload may
    silently leave stale compiler-spec state, consistent with this file's own
    existing warning near the end of the "10." item above. Any future .cspec
    edit in this project should (a) avoid bare double-hyphens in comments, (b)
    validate as XML before installing, and (c) get a full restart before its
    effect is trusted either way.

    TO CONTINUE: (1) inspect spSegment/Rn_banked's pcode directly to confirm or
    rule out the item 10 connection to this function's dead-parameter body
    symptom; (2) if confirmed, this becomes the priority fix since it likely
    explains both the callee-body symptom here and probably contributes to the
    call-site symptom too; (3) the pjsr indirect-call fix remains open and
    separately trackable, but is now considered lower-priority than the item 10
    connection; (4) optionally retry the offset=8/align=2 cspec pentry idea
    cleanly (post-restart, post-XML-fix) if the manual-override approach is
    ever found insufficient for the other 129 callers.

    UPDATE (2026-08-01): replicated the proven CUSTOM_STORAGE fix on the
    other 3 functions in this same lookup family, confirmed via disassembly
    to share the identical prologue shape first (`ldc.b @(0x7:8,FP),EP` /
    `mov:f.w @(0x8:8,FP),R4` at the same offsets in all three):
      axis_lookup_interp (0x14735): bank@Stack[6]:1, record(void*16)@Stack[7]:2
      table_lookup_indexed (0x14854): bank@Stack[6]:1, array_base(void*16)@Stack[7]:2
      table_read_indexed (0x14880): bank@Stack[6]:1, array_base(void*16)@Stack[7]:2
    Applied via the same run_script_inline CUSTOM_STORAGE recipe (VariableStorage
    + dtm.getPointer(voidDt,2)), get_function_variables confirmed no
    <UNASSIGNED> on any of the three. Decompile improvement varies by
    function: table_read_indexed is now fully clean (no warnings at all,
    body is a single-line `return *(ushort*)(array_base + (DAT_0001f1fc&7)*4)`
    -- directly confirms the array-indexed addressing scheme, real_address =
    bank*0x10000 + entry_offset_word, entry = array_base + (global_index&7)*4);
    table_lookup_indexed still carries "WARNING: Unknown calling convention"
    and some unaff_R4/CONCAT residue in its own body (same class of symptom
    already root-caused above for table_lookup_interp -- not re-investigated
    today); axis_lookup_interp is dramatically more readable (named
    value_ptr/axis_ptr/axis_count/axis_table-equivalent accesses via the
    bound `record` parameter, matching this session's independently-verified
    axis_lookup_record struct exactly) but keeps its own pre-existing "WARNING:
    Unable to track spacebase fully for stack" note.
    CONFIRMED STILL TRUE, re-tested today, do not re-attempt without a new
    idea: this fix is calee-body-only. Call sites for all 4 functions still
    decompile as opaque `(*funcname)()` with zero bound arguments -- tested
    by re-decompiling isc_f34e_f34a_correction_calc and
    knock_octane_dual_axis_table_blend_f2a8 (both heavy callers of these 4
    functions) after applying today's fix; both are byte-identical to their
    pre-fix decompile output. This is expected and matches item 18's own
    CALLIND root-cause finding above, not a new failure. Practical upshot:
    for finding a specific literal-push caller of a specific axis/table
    address (the actual recurring need across review2.md's Batch 1/2 work),
    search_byte_patterns on the exact push encoding (`BF 07 <hi> <lo>` for
    the 16-bit offset half, optionally followed by `BF 06 <bank>`) remains
    the correct and only currently-working technique -- this cspec/prototype
    work does not replace it, it only makes the 4 functions' OWN bodies
    easier to read once you're already looking at one of them directly.

    UPDATE (2026-08-02): the above list of "4 functions" was itself
    incomplete -- it was compiled by scanning function NAMES, which is
    unreliable (the ROM's auto-naming heuristic names functions after
    their dominant RAM write target, not their calling convention, so
    family members can end up named almost anything -- e.g.
    "gear_indexed_table_lookup_f1fc" and "read_indexed_byte_f1fc" don't
    look related to "table_lookup_interp" by name at all despite being
    byte-identical in structure). Did the search properly this time: read
    the exact 5-byte prologue signature shared by every confirmed member
    (`ldc.b @(0x7:8,FP),EP` + `mov:f.w @(0x8:8,FP),R4`, encoded as
    `E6 07 8C 8C 08`, verified byte-identical at both table_lookup_interp
    and axis_lookup_interp before trusting it as a signature), then ran
    search_byte_patterns for that exact sequence across the WHOLE ROM.
    Got 15 hits, all fully accounted for: 4 internal occurrences each in
    table_lookup_interp and table_3axis_interp_triple (the instruction
    pair repeats at multiple branch points inside those two, not just
    the prologue), and exactly one occurrence each in the other 7 family
    members. This is a complete, exhaustive, byte-verified list -- no
    name-guessing involved, nothing left unaccounted for. Full family (9
    functions):
      table_lookup_interp (0x14656) -- previously fixed
      axis_lookup_interp (0x14735) -- previously fixed
      table_lookup_indexed (0x14854) -- previously fixed
      table_read_indexed (0x14880) -- previously fixed
      table_read_word_indexed_f1fc (0x14838) -- fixed today
      table_3axis_interp_triple (0x148a2) -- fixed today
      table_3axis_interp_triple_wrapper (0x1497b) -- fixed today
      read_indexed_byte_f1fc (0x1481c) -- CORRECTED today, see below
      gear_indexed_table_lookup_f1fc (0x149a7) -- fixed today (newly
        discovered this pass, not in any prior session's notes at all --
        turned out to be a byte-for-byte functional duplicate of
        table_read_indexed under a different auto-generated name)
    All bound at bank@Stack[6]:1, {record,array_base}@Stack[7]:2 (void*16),
    matching the table_lookup_interp/axis_lookup_interp precedent exactly.
    IMPORTANT CORRECTION: read_indexed_byte_f1fc was already partially
    bound from an unknown earlier session, but at Stack[0x5]:1/Stack[0x6]:2
    -- one slot off from every other family member despite having the
    identical "link FP,#0x0:8" + single "mov:g.w R4,@-SP" prologue shape
    (same shape as table_read_indexed/table_lookup_indexed, which are
    correctly bound at Stack[6]/Stack[7]). The decompiled output with the
    wrong offsets still looked superficially clean (no warnings), which is
    what let it go unnoticed -- worth remembering that a clean-looking
    decompile is not proof a manual storage override is correct, only that
    it didn't hit an edge case that produces a visible warning. Re-bound to
    Stack[6]:1/Stack[7]:2 to match the rest of the family; re-decompiled
    and confirmed still clean afterward with the corrected offsets.
    NOT part of this family despite superficially similar names: checked
    axis_interp_lerp_u8frac (0x147c6) by disassembly -- it's a plain
    3-word arithmetic lerp helper (val_a/val_b/fraction at FP+0x6/0x8/0xa),
    no ldc.b EP-load at all, completely different parameter shape. Did not
    touch it or its _256 sibling. Also did not touch the various
    "*_table_select"/"*_via_table" caller functions (they call INTO this
    family, they aren't members of it -- fixing their own prototypes
    would not help since the call-site CALLIND limitation above is what
    actually blocks their decompiles from showing resolved table/axis
    arguments, not their own parameter binding).

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

CAVEAT ADDED 2026-08-02: steps 1-4 above only reload .sla/.pspec/.sinc content.
.cspec is loaded once per Ghidra session/project and is NOT hot-swapped by
ReloadSleighLanguage.java -- confirmed by direct test (see item 18 continuation
below): a full compile+copy+reload cycle produced a byte-identical decompile
until Ghidra itself was actually closed and reopened. If a change touches
.cspec (tracked_set defaults, calling conventions, pentry storage), a full
Ghidra restart is required before testing, not just steps 2-4.

18 (continuation, 2026-08-02). EP step 3b SEGMENTOP-input tracking limitation --
CONFIRMED, same root cause as item 9, distinct symptom from the
constant-fold/CONCAT12 issue the step 3b comment originally described.

CONTEXT: step 3b (spSegment(EP,...) for all 18 EP-banked sites, EP deliberately
left out of <constresolve>) was on disk but its own comment still said "not yet
compiled/installed/tested." Ran the full build/test workflow above end-to-end
(sleigh.bat exit 0, full file set copied with matching src/dst timestamps,
ReloadSleighLanguage.java clean, THEN a genuine Ghidra restart per the caveat
above) against the repro the .pspec comment names,
flash_vpp_pulse_handshake_echo_verify @0x20992. Decompile was byte-identical
before and after every step, including post-restart -- unaff_R3/extraout_R2
garbage unchanged.

TRACED (ghidra:analyze_dataflow, not just decompile output): the @R4 store at
0x209a4 (`mov:g.b R0,@R4`) DOES route through SEGMENTOP with real inputs (EP,
R3) -- the SLEIGH-level fix is correctly wired, p-code is NOT broken. The
decompiler's own HighVariable for input 2 of that SEGMENTOP resolves to
`unaff_R3` with a backward dataflow trace terminating immediately as
"input/parameter" -- i.e. the decompiler loses the real defining instruction
(`mov:g.w R3,R4` @0x20998, confirmed via raw disassembly) and treats R3 as an
untracked function input instead. So this is NOT the output-side "doesn't
constant-fold EP=0" tradeoff the step 3b comment anticipated -- it's the
decompiler's dataflow/register-copy-propagation pass failing to see past
SEGMENTOP on the INPUT side too, for this call site specifically.

Checked against item 21's return-storage/param-binding family (table_lookup_interp
etc.) -- does NOT match: flash_vpp_pulse_handshake_echo_verify is not a
dispatcher, isn't void-with-discarded-return, and isn't on item 21's checked-function
list. This is a separate, narrower manifestation.

CONCLUSION: this is a real instance of item 9's already-accepted architectural
limitation (SEGMENTOP as an opaque CALLOTHER breaks normal decompiler analysis
around it), just showing up on the input side instead of the output/constant-fold
side originally documented. No further SLEIGH-level fix available -- same
conclusion as item 9, not an open bug. Do NOT attempt to remove spSegment(EP,...)
to "fix" this: DP's identical spSegment(DP,...) fix (item 14 in this file) is
independently verified ROM-wide (CONCAT 315->77, WARNING unchanged, unaff_
IMPROVED 89->83) -- reverting EP's fix would very likely regress all 18
EP-banked sites back to CONCAT12 noise without curing this function's unaff_R3,
since the cause is upstream of spSegment's output-side behavior.
STATUS: step 3b marked CONFIRMED WORKING AS DESIGNED (p-code correct); this
specific decompile artifact marked ACCEPTED LIMITATION (item 9), not a bug to
chase further.

19. XML table address verification pass + table_lookup_interp call-site extraction (2026-07-30)
    -- IN PROGRESS, no XML file changes made yet (see status below).

    Built and validated a working Ghidra script-based pipeline for extracting real
    (table_addr, ep_val) pairs from every table_lookup_interp call site, using
    run_script_inline. NOTE: the inline-script tool auto-wraps submitted code in
    its own class scaffold -- submit only bare statements/method-body code, NOT a
    full "public class X extends GhidraScript" declaration, or the two wrappers
    nest and javac fails with "illegal start of expression" (burned two dead
    script files, TableExtract.java/TableExtractV2.java, learning this; they are
    harmless orphans, ignore the recurring compile-error preamble Ghidra now
    prints on every script run because of them).

    Ran the extractor against table_lookup_interp (0x14656): confirmed real,
    complete 130/130 call sites, (caller function, table_addr, ep_val) for each.
    Two rows (isc_f438_correction_calc, egr_duty_target_calc) returned
    imms=[254,252] -- implausibly small to be real addresses, almost certainly a
    parser mis-grab of the wrong preceding immediates; not yet fixed in the
    extraction script, don't trust those two rows as-is.

    Grouped the 69 distinct callers by subsystem from function names alone (no
    script needed): ISC/idle (~25 functions, by far the largest cluster -- idle
    control leans on this dispatcher more than anything else), ignition, fueling,
    O2/closed-loop, knock/octane, EGR/purge, WGDC/boost, TCU/transmission, plus a
    residual set of still-unlabeled fXXXX-register functions.

    VERIFICATION METHOD ESTABLISHED (two independent checks, both real, both
    useful, neither replaces the other):
      (a) Byte-level plausibility: read raw bytes at a candidate address and
          check for the record-header signature (mode byte 2 or 3, mode-selector
          byte, then for mode 3 two RAM pointers + stride, then a smooth/sane
          data curve) vs garbage. Confirmed on Idle Stepper Table (0x12992,
          matches hand-trace from item 18) and on all four EcuFlash-named fuel
          maps (High/Low Octane Fuel Map, High/Low Octane Fuel Map 1) -- headers
          identical (same axis pointers/stride, as expected for same table
          family), bodies diverge exactly where real tuning data should differ.
      (b) get_xrefs_to / get_bulk_xrefs on the candidate address: a subset of
          tables (Idle Stepper, Boost Enhancement, Low Octane Fuel Map 1, Desired
          ISCV step position, at minimum) are independently pointed to by an
          8-entry data-driven pointer/index block at ~0x2d9xx-0x2daxx (looks like
          a per-condition/per-gear table-select array). A confirmed-real address
          in that family shows exactly 8 DATA xrefs; a wrong/mis-scanned address
          a few bytes off shows ZERO. This is a strong, cheap true/false check
          BUT only applies to tables reached via that index block -- tables
          reached only via a hardcoded literal push at a table_lookup_interp call
          site (the majority, e.g. Idle Stepper, IAT candidate, Warmup Retard
          candidate) will show zero xrefs either way; absence of xrefs is NOT
          evidence of a wrong address for that access style, only presence of 8
          xrefs at a plausible-but-close address is strong evidence of realness,
          and zero xrefs at an address that SHOULD be in the index block (i.e.
          its sibling overlap address has 8) is strong evidence of wrongness.

    XML VERIFICATION RESULTS against
    test/rvr/xml/ecuflash/new/21000011_1997-2001_RVR_X3_Mt__4g63t_.xml (an
    already-real, previously-hand-maintained file -- NOT generated by us; it has
    its own extensive prior-session removal history for a different bad batch of
    guessed addresses, see the "Correction A1-A18..." comment block near EOF):

      CONFIRMED CORRECT, no XML change needed:
      - Low Octane Fuel Map 1 (11bc7) = confirmed real record pointer (11bc0) + 7
        byte header. Convention confirmed: XML data-address = raw record pointer
        + 7 for mode-3 (3D) tables.
      - Boost Enhancement Enrich/Enlean (Anti-lag) Map (124f3) = confirmed real
        record pointer (124ec) + 7. 8/8 xrefs confirm 124ec.
      - Accel Enrichment (11cb5) -- false alarm, NOT an overlap. Low Octane Fuel
        Map 1's real table simply ends before 11cb5 starts (real gap, ~238-241
        bytes, plausible size for a 3D table); Accel Enrichment's own bytes are a
        visibly different pattern, not header/continuation data. Zero xrefs
        either way (expected -- not in the index-block family), but byte-level
        check alone is sufficient here since there's no header collision.
      - Desired ISCV intial step position with AC off-Neutral (128a2) --
        confirmed real, 8/8 xrefs.

      CONFIRMED WRONG, replacement NOT yet verified -- DO NOT EDIT XML YET:
      - Warmup Retard, XML address 12500 (= record pointer 124f9 + 7). 124f9 has
        ZERO xrefs and sits only 13 bytes into Boost Enhancement's own confirmed
        header/data (124ec) -- not a separate table, definitely wrong.
        FALSE LEAD, RETRACTED: warmup_ign_advance_correction_calc's own
        table_lookup_interp call (table_addr decimal 7372 -> 11ccc) was initially
        proposed as the fix. WRONG -- its mode byte (2, single-axis) matches the
        already-correctly-placed "Warmup Ignition Control vs Eng Temp" (127cc,
        2D) far better than "Warmup Retard" (3D, Load+RPM axes, mode byte should
        be 3). Do not reuse 11ccc/11cd3 as the Warmup Retard address.
        NEXT LEAD, not yet checked: Warmup Retard shares its exact axis pair
        (Load 2d382, RPM 2d332) with Boost Enhancement Enrich/Enlean -- same
        category (Timing), same level (1) -- so its real record likely sits
        physically close to 124ec in ROM (adjacent table cluster), not near
        11ccc. Search that immediate neighborhood (both before 124ec and after
        its real end, once known) for a second mode-byte-3 header with the same
        F0-xx RAM-pointer-pair convention, sized to fit a 19x17 grid (per XML's
        own axis element counts for this table).
      - Injector Battery Voltage Latency Compensation, XML address 128a7. Only 5
        bytes past confirmed-real 128a2 (Desired ISCV step position) -- still
        inside that table's real curve data, not a separate table. Zero xrefs.
        DEAD END CHECKED: fueling_inj_pw_calc (real name, found via disassembling
        fueling_lambda_update's call list) looked like the obvious place for
        this -- it is NOT. Contains zero table_lookup_interp/axis_lookup_interp
        calls, pure fixed-point arithmetic on f186/f188/f18a/f18c/f190/f192/f194/
        f196 from constants at 0x810/0xf298/0xf29a/0xf29c. Rule this function out
        entirely for this table.
        NEXT LEAD, not yet checked: table is tiny (XML says byte[4][1]), same
        scale as the already-confirmed-real "Ignition Coil Charge Time -
        Normal/Alt" tables (12808/12816), which use a Battery axis (2d27a) and
        are presumably NOT accessed via the big axis_lookup_interp+
        table_lookup_interp machinery given their size. Check callers of
        table_lookup_indexed (0x14854) and table_read_indexed (0x14880) instead
        of table_lookup_interp for this one -- small tables likely use the
        lighter-weight direct-index path, not the axis-record dispatcher.
      - Air Temperature Compensation (2D): does NOT currently exist as a named
        entry in this XML file at all (original flagged address 0002af74 landed
        on a real beq opcode inside tcu_rx_main_scheduler -- confirmed via
        disassembly, definitely code not data). iat_axis_update (real function)
        calls table_lookup_interp with a real address resolving to 0x11d7a; byte
        check shows a sane monotonic curve (158,143,135,129,122,115,106...).
        Reasonably confident this is the real table, but it has zero xrefs
        (expected -- literal call-site access, not index-block) and there's no
        existing XML entry to compare/replace, so this would be an ADDITION not
        a fix. Not yet added.

    STATUS (updated 2026-07-30): XML file modified -- Warmup Retard and
    Injector Battery Voltage Latency Compensation entries commented out in
    place (not deleted) and documented in a new "CONFIRMED WRONG TABLES"
    block near EOF, following the existing session-10 removed-tables
    convention. No replacement addresses were guessed or written for either --
    both remain open pending a verified address per the leads below.
    One optional addition identified (Air Temperature Compensation @ 0x11d7a)
    but not added pending same level of confidence as the confirmed fixes.

    2026-07-30 AIR TEMPERATURE COMPENSATION ADDED: re-verified independently
    (iat_axis_update, 0x21396, disassembled directly -- confirmed pushes
    #0xd4a6 for axis_lookup_interp then #0x1d7a/mode=1 for table_lookup_interp
    0x14656). Byte-read the header/data/sentinel directly: 02 00 F0D0 header
    at 11d7a, curve 9E 8F 87 81 7A 73 6A (158,143,135,129,122,115,106), 0xFF
    sentinel at 11d85 -- sits exactly back-to-back with Post Start Enrich Trim
    vs Load (11d86), zero gap or overlap. Found the table's own dedicated axis
    at 2d4a6 (F0D0 F118 0007 header, 6 bytes -- same header-then-data shape as
    the Idle Stepper axis documented in item 17), real 7-element breakpoint
    array at 2d4ac (8,33,49,63,78,96,125 -- temperature-shaped values,
    matches the 7-byte data curve exactly, no overrun into the next record).
    Cross-checked XML's own address convention against two already-trusted
    entries before writing anything: 2d418 (Engine/Air Temp axis, already in
    XML) has values starting immediately at the declared address, no header;
    128a2 (Desired ISCV step position, already in XML, confirmed real) uses
    its record/header address directly as the XML address, not header+4 as
    its own plate comment's phrasing suggested -- confirmed by reading the
    live XML rather than trusting the comment. Followed that same header-
    address convention: XML added with address="11d7a" (header, not 11d7e)
    and axis address="2d4ac" (skipping the axis's own 6-byte header, matching
    item 17's precedent exactly, not 2d4a6). Zero xrefs on both (expected,
    literal call-site access). This closes the last open item from the
    H8539F-TABLE-CODE-OVERLAP bookmark list -- Accel Enrichment remains the
    only genuinely unresolved entry from that set.

    2026-07-30 continuation -- Injector Battery Voltage Latency Compensation:
    table_lookup_indexed/table_read_indexed caller lists checked (9 functions:
    closedloop_fuel_ready_check, f33e_bit6_update_from_table_da2c_threshold,
    fueling_base_injection_calc, idle_target_rpm_compute_f400,
    isc_f34e_f34a_correction_calc, isc_f35e_correction_calc,
    isc_f408_f406_stepper_target_calc, isc_f41c_table_lookup,
    knock_octane_dual_axis_table_blend_f2a8, f286_knock_octane_secondary_trim_
    compute_via_table, isc_f41a_correction_calc, isc_f420_correction_calc,
    octane_trim_f262_f264_table_select, table_select_scale_fanout_f1be_f1c2) --
    none are injector/battery related by content (ISC/idle, O2, knock/octane).
    fueling_base_injection_calc's table_lookup_indexed call writes to
    f1be/f1c2, same registers as table_select_scale_fanout_f1be_f1c2 (O2/octane
    trim area) -- ruled out for this table. Named-function search for
    inj/batt/volt found no unexamined candidates (fueling_inj_target_select:
    pure flag logic, no table lookup, ruled out; fueling_coolant_inj_offset_
    calc: saturated-subtract offset, no table lookup, ruled out;
    injpw_airvol_reset_on_fuelcut: fuel-cut zero-reset gate, no table lookup,
    ruled out).

    NEW LEAD: extended the item-18 extraction script to axis_lookup_interp
    (0x14735, distinct from table_lookup_interp 0x14656) -- 83 call sites
    total, extracted clean via the same run_script_inline pipeline (same
    orphan-file compile-error preamble noise, harmless, ignore per item 18's
    note). fueling_lambda_update (the injector pulse-width chain, calls
    fueling_base_injection_calc -> ... -> fueling_inj_pw_calc ->
    axis_lookup_interp as its last step) has exactly one axis_lookup_interp
    call site: 0x21a05, imms=[0x2, 0xd15e, 0x21c2f]. 0xd15e is almost
    certainly the AXIS pointer (not the data table itself -- axis_lookup_interp
    resolves X-axis breakpoints, consistent with the 0x2/mode-byte-style first
    immediate seen across all 83 sites); 0x21c2f is fueling_inj_pw_calc's own
    address, likely a return-context artifact of the backward-scan window, not
    a table value -- do not treat as a real immediate. NOT YET DONE: resolve
    what data table 0xd15e's axis actually indexes into (the corresponding
    table_lookup_interp/table_lookup_indexed call using this axis has not been
    identified yet -- axis and data-table calls are typically paired but the
    pairing call site for 0xd15e is still unknown). This is the most promising
    unexplored lead for this table; pick up here next session.

    2026-07-30 RESOLUTION (via Ghidra bookmark cross-check, prior-session ROM
    scraper pass not previously reflected in this file): Injector Battery
    Voltage Latency Compensation is NOT a real table. Bookmarks
    H8539F-TABLE-DATA-OVERLAP-CORRECTED at 0x128a2 carry a ROM-scraper plate
    comment confirming the real table at that address is "Desired ISCV intial
    step position with AC off-Neutral" -- 4-byte header, data at 0x128a6,
    ending ~0x128d6. The claimed Injector Battery Voltage Latency
    Compensation range (0x128a3-0x128ad, XML address 128a7) falls entirely
    inside that real table's own header+data -- there was never a second,
    independent table there. This supersedes the axis_lookup_interp/0xd15e
    lead above (still an open, real thread about fueling_lambda_update's axis
    call, but it does not lead to this XML table -- no further work needed on
    this specific XML entry). XML updated: entry commented out permanently
    (not "pending a replacement" -- none exists or should be sought).

    Cross-checked the same bookmark set for Warmup Retard: only
    H8539F-TABLE-DATA-OVERLAP-SUSPECT exists at 0x124ec/0x124f9, no -CORRECTED
    bookmark -- confirmed the address was still genuinely unresolved as of
    that check.

    2026-07-30 WARMUP RETARD RESOLVED: no code-side caller found across the
    full warmup_* function family (warmup_ign_advance_correction_calc,
    warmup_correction_f25a_f0f8_f212_calc, warmup_mode_state_machine,
    warmup_complete_gate_check, warmup_state_f594_f0e6_init,
    engine_warmup_dispatch_b, engine_warmup_periodic_dispatch,
    f216_bits_f188_f17a_update_and_warmup_gate all individually checked --
    only one table_lookup_interp call exists across the whole family, in
    warmup_ign_advance_correction_calc, and it resolves to 0x11ccc, the
    already-identified "Warmup Ignition Control vs Eng Temp" table, not
    Warmup Retard). Fell back to the byte-neighborhood lead instead: byte-
    scanned Boost Enhancement Enrich/Enlean's real data (124ec header, 342
    bytes, 0xFF sentinel at 12649) and found an identical-shape header
    immediately following at 1264a (03 14 F0C0 F0C2 12 -- same mode byte,
    stride 0x12=18, same axis pointers as Boost Enhancement), with its own
    distinct 342-byte data curve (confirmed different values from Boost
    Enhancement's own, ruling out a duplicate/copy-paste artifact) and its
    own 0xFF sentinel at 127a7. CONFIRMED via get_xrefs_to: exactly 8 DATA
    xrefs at 1264a (0x2da0c through 0x2da28), matching the same index-block
    confirmation signature established in item 19 for every other verified-
    real table in this file. No collision with any other XML-claimed
    address range. XML corrected: Warmup Retard address="12651" (record
    pointer 1264a + 7, per the mode-3 convention). Axis element counts
    (Load 19, RPM 17) left unchanged since only the address was verified
    wrong -- note the real data is 342 bytes / stride 18, not a clean
    19x17=323, worth a follow-up check if EcuFlash renders a trailing gap.

    2026-07-30 ACCEL ENRICHMENT STILL UNRESOLVED, XML deliberately not
    touched (see the contradiction noted above this section): candidate
    replacement 11ccc remains unverified because fueling_accel_enrichment_calc
    (0x21aa5) contains no table_lookup_interp/axis_lookup_interp/
    table_lookup_indexed call at all -- confirmed its three callees
    (0x144d1/0x1417d/0x14151) are pure fixed-point arithmetic helpers
    (identity_passthrough_arg1, div_u32_u16_rounded, div_s32_s16_rounded),
    not table primitives. This suggests Accel Enrichment may not correspond
    to a real 2D lookup table in this ROM's code at all, which is a
    different and deeper problem than a wrong address -- do not write 11ccc
    or any other guessed address without first finding a genuine
    table-lookup call site backing it.

    2026-07-30 CONTRADICTION FOUND, NOT YET RESOLVED, XML NOT TOUCHED: this
    item's earlier "Accel Enrichment (11cb5) -- false alarm, NOT an overlap"
    conclusion (line ~1596 above) does not hold up against a direct byte read.
    Low Octane Fuel Map 1's real data (11bc7 onward) was byte-scanned in this
    session: monotonic AFR-like surface continues uninterrupted through
    11cb1/11cb5 (bytes at 11cb1: 0B 0A 18 17 -- still curve data, not a
    header), with the actual 0xFF sentinel found at 11ccb (260 data bytes,
    not 261 -- prior estimate was off by one). So Accel Enrichment's claimed
    address (XML 11cb5, header 11cb1) is NOT in a real gap -- it's genuinely
    inside Low Octane Fuel Map 1's tail data, contradicting the earlier
    conclusion in this same file. The byte right after the real sentinel
    (11ccc) is 02 00 F0 C8 -- looks like a plausible next-table header (mode
    byte 2, RAM pointer F0C8) and is a candidate for Accel Enrichment's real
    address, but fueling_accel_enrichment_calc (0x21aa5, the actual named
    caller) was disassembled this session and contains NO table_lookup_interp/
    axis_lookup_interp/table_lookup_indexed call at all -- it's pure
    fixed-point arithmetic via helpers at 0x144d1/0x1417d/0x14151. This means
    Accel Enrichment does not have a code-verified table_lookup call site the
    way every other table in this file does, so 11ccc is an UNVERIFIED guess,
    not a confirmed replacement -- do not write it to the XML. Matching
    Ghidra bookmark (H8539F-TABLE-DATA-OVERLAP-SUSPECT at 0x11cb1) also never
    got a -CORRECTED follow-up, consistent with this being genuinely
    unresolved rather than settled either way. NEXT STEP: check what
    0x144d1/0x1417d/0x14151 actually do (fixed-point helpers, not obviously
    table primitives, but not yet individually inspected) and whether Accel
    Enrichment is a scalar/computed value in this ROM rather than a real 2D
    lookup table -- may mean the XML's "Accel Enrichment" table concept itself
    needs re-examination, not just its address.

Item 20: "Unknown" category scraper-derived TABLE_2D_* placeholder axes (2026-07-31)
------------------------------------------------------------------------------------
- Applied all 3 remaining H8539F-TABLE-DATA-OVERLAP-CORRECTED bookmarks that had
  never been written to the XML (item 19 only covered 2 of 5 total CORRECTED
  bookmarks): TABLE_2D_00011EE2 (11EE2->11EE6), TABLE_2D_0002D3C0 (2D3C0->2D3C4),
  TABLE_2D_0002D668 (2D668->2D66C). All three corrected to header+4-bytes per
  ROM-scraper plate comments, matching the established convention. Placeholder
  "RPM"/2d332/elements=18 axis stub left untouched on all three -- confirmed with
  the user this is deliberate scaffolding (set so data is viewable in EcuFlash,
  not a real axis claim), applies to all ~94 "Unknown" category scraper-derived
  tables in this file, not a bug.

- Found in passing: AXIS_TPS at 0x2d3c2 is likely MISLABELED. Traced its RAM
  input pointer (F4EA) to its actual writer, tcu_shift_torque_and_knock_mgmt
  (0x28fff) -- a TCU shift/knock-management function, not a throttle-position
  read path. F4EA is the high-byte output of axis_interp_lerp_u8frac_256 fed by
  F5DE (an IPU capture-period signal also feeding the RPM breakpoint chain),
  scaled by a 40000-based constant -- the function's own header comment
  independently flags this as "likely a smoothed/averaged metric, possibly
  duty-cycle or dwell-adjacent rather than RPM" and explicitly warns not to
  conflate it with the real RPM/axis-interp thread. NOT YET renamed in Ghidra or
  XML (user chose to scope corrections to addresses only, not names, this
  session) -- flagging here so it isn't lost. Needs its own resolution pass.

- Attempted to script a bulk axis-resolution pass across all 94 "Unknown"
  placeholder tables, per user request ("look up method... in reverse").
  RESULT: could not resolve any of them. Full negative-result chain, in case
  future sessions want to pick this up rather than repeat it:

    1. table_lookup_interp (0x14656) xref scan, loose 12-instruction backward
       window: produced 55 "matches", ALL FALSE POSITIVES on manual check --
       the loose window grabbed unrelated immediates from surrounding
       instructions (e.g. adds.b stack-cleanup operands), same failure mode
       item 19 already flagged for this exact technique.
    2. Rewrote with a strict walk (only consume Scalars from contiguous
       mov...@-SP pushes, stop at first non-mov/non-push instruction).
       Verified correct against a known-good call site (0x25c35, ep=0x1
       table=0x27e4, matches disassembly exactly). Re-ran against all 94
       targets across ALL 22 known table/axis lookup+wrapper functions
       (table_lookup_interp, axis_lookup_interp, table_lookup_indexed,
       table_read_indexed, egr_table_row_lookup_f496, gear_indexed_table_
       lookup_f1fc, idle_stepper_table_lookup_wrapper, ign_advance_table_
       lookup, isc_f352/f354/f41c/f41e/f42a_table_lookup*, table_1e4a_lookup_
       with_f2d6_d8_reset, axis_interp_lerp_u8frac(_256), iat_axis_update,
       knock_octane_dual_axis_*, map_tps_axis_update, table_3axis_interp_
       triple(_wrapper)) checking ALL collected immediates per call site, not
       just positional args. ZERO matches. This is a real result, not a script
       bug -- the strict logic is proven correct on a known site.
    2b. get_xrefs_to on raw target addresses (e.g. 0x13198, 0x2d3c4): zero
       xrefs, code or data.
    3. search_byte_patterns for the target address encoded as a literal
       pointer (16-bit and 24-bit forms) anywhere in ROM: zero hits for every
       address tried (0x13198, 0x2d3c4).
    4. inspect_memory_content on target addresses confirms they ARE real,
       well-formed table data (correct 3-field header + FF-terminated
       breakpoint list shape, byte-identical structure to confirmed-real
       tables elsewhere) -- ruling out "scraper found padding/garbage" as the
       explanation. The tables are real; they're just unreachable by any
       static-reference method tried.
    5. Hypothesis "read via the MUT/SCI1 diagnostic path instead of normal ECU
       code" -- CLOSED, ruled out. Fully decompiled BOTH SCI1 candidates:
         - sci1_meta_cmd_dispatch_c0_ff (0x28869): actuator-test bit-flag
           writer (cmd bytes C0-FF -> f510/f512/f514/f516 RAM flags, per-gear
           byte/word lookups at ROM 0x232/0x252). No table-address references
           at all, only RAM flag words. Already exhaustively documented
           2026-07-14 through 2026-07-26 per its own plate comment; not
           relevant to our 94 tables.
         - adc_sensor_convert_single (0x171c3), the actual MUT live-data read
           path referenced by that first function's own comment: RequestID ->
           16-bit RAM address via indirection table at ROM 0x2fad0 (EP=2
           banked), returns a single BYTE from RAM. This reads live RAM
           values for scan-tool display (RPM/TPS/boost/etc as CURRENT
           readings) -- structurally unrelated to our ROM tuning tables
           (different indirection table, different data shape, RAM not ROM,
           single byte not a breakpoint array). Confirms these 94 tables are
           not part of the MUT read path in any form.
    6. Hypothesis "reached via an indexed/computed pointer array, like MUT's
       own mechanism" -- found a REAL example of this pattern elsewhere,
       but could not connect it to our 94 targets:
         - f27e_table_indexed_clamp_compute_via_table (0x2415b): genuine
           selector-indexed lookup, entry+0x34 struct field as base pointer,
           indexed by (f218 & 0xF)*2. Real mechanism, but traced back through
           its only caller chain (knock_octane_secondary_dispatch (0x23a9a) ->
           status_word_table_subdispatch_group_a (0x23e60) ->
           f27e_table_indexed_clamp_compute_via_table) and found NO explicit
           parameter passing anywhere in the chain -- "entry" is likely a
           fixed global/RAM struct unrelated to our 94 ROM addresses, not a
           generic per-table dispatch mechanism. Dead end for this purpose,
           though the mechanism itself is confirmed real and may be worth
           revisiting for other unrelated tables.

- CONFIRMED WORKING EXAMPLE of the right general mechanism, traced end-to-end
  for comparison (per user request to trace a known-good 3D table): High
  Octane Ignition Map 1 (XML address 11f7b). Real header found at 11f74 (03 14
  F0 C0 F0 C2 12 ... -- 3D shape, RPM+Load out-ptrs), NOT the XML address
  itself (same header-vs-data-address offset pattern as every other table in
  this file). get_xrefs_to(0x11f74) found genuine DATA xrefs from 0x2db6c
  onward -- a pointer array, 4 bytes/entry (e.g. "00 01 1F 74" repeated 8x,
  then "00 01 20 D2" repeated 8x), i.e. a real octane/RPM-zone-selector table
  of table-pointers, exactly the indirect mechanism hypothesized in point 6
  above. However, tracing the array's OWN reader was not completed this
  session: get_xrefs_to on the array base and nearby rounded addresses found
  nothing; search_byte_patterns for "02 DB" found 4 candidate sites but the
  most promising (isc_f038_constant_select @ 0x277e3) was a byte-pattern
  coincidence inside an unrelated instruction, not a real reference.
  ign_advance_table_lookup (0x173e0) computes a plausible octane-blend
  selector (0-3) from knock/RPM/load thresholds, reading a SEPARATE small
  4-entry byte table at 0x31b7 (blend weights, not the pointer array) -- likely
  upstream of whatever consumes the 0x2db6c array, but its own caller
  (ign_advance_f0e6_bit7_update, 0x173c0) is an output-relay-flag writer that
  discards the returned selector value entirely, confirming the real consumer
  of the 0x2db6c array is a different, not-yet-found function. NEXT STEP for
  whoever picks this up: find what reads the 0x2db6c-style array now that its
  existence and shape are confirmed -- likely requires searching for a
  computed-jump/PJSR-via-register pattern (base+selector*4 then indirect call
  or read) rather than any literal-immediate or byte-pattern search, since
  every literal-based method tried above came up empty for this array's own
  base address too.

- NET CONCLUSION for the 94-table placeholder-axis project: the axis data for
  these tables is NOT resolvable by any static xref/byte-pattern method tried
  so far. Either (a) they use a computed-pointer-array indirection like High
  Octane Ignition Map 1's confirmed mechanism, in which case the missing piece
  is finding the array's reader function (not yet found for even the ONE
  confirmed-good example), or (b) some other mechanism not yet hypothesized.
  Recommend either continuing the search for a computed-jump pattern, or
  moving to dynamic analysis (debugger watchpoint on a target table's ROM
  address while running/emulating) if available, since static analysis alone
  has now been tried from multiple independent angles without success.

21. Return-storage audit pass across table/axis dispatcher functions (2026-08-01)
    -- COMPLETE for the ~34-function list checked this session.

    Context: table_lookup_interp (item 18/19) was already known to compute a
    real interpolated result via its final axis_interp_lerp_u8frac call, but
    was declared `void` -- the decompiled callee silently discarded the value
    on every path, while caller-side decompiles (fueling_base_injection_calc,
    iat_axis_update, etc.) clearly captured it (`uVar1 = (*(code*)0x14656)();`).
    That mismatch is the actual bug class this pass checked for across a wider
    function list: "declared void/wrong return, but a real caller captures a
    value" vs "genuinely void, result only ever reaches memory, correctly
    modeled already."

    METHOD: for each function, decompile and check (a) does it end with a
    computed value being discarded on a path a caller might need, (b) do its
    real callers (via get_function_callers) actually capture a return. Only
    fix (a)+(b) together -- do not touch functions that are genuinely void.

    FIXED (real bug, confirmed via a real caller before touching):
    - table_lookup_interp (0x14656) -- ushort return added (item 18/19
      continuation, done first this session, everything below built on top of
      this). set_function_prototype call:
        ghidra:set_function_prototype(function_address="00014656",
          calling_convention="__stdcall_far_2arg",
          prototype="ushort table_lookup_interp(byte ep_val, void *table)")
      RESULT: return value correctly modeled now (`return uVar4;`).
      REGRESSION CAVEAT (see below): this call also silently drops the
      `table` parameter's Stack[0x7]:2 storage back to <UNASSIGNED> every time
      the prototype is re-applied -- this is NOT something this fix broke,
      it's the SAME pre-existing param-binding quirk the function's own plate
      comment already documented before any of this session's edits ("keeps
      re-inferring a 3rd stack param regardless of declared prototype").
      set_variable_storage cannot repair it either -- tool response explicitly
      says programmatic storage control is limited here and requires either
      the Ghidra GUI (right-click variable -> Retype/Edit) or a custom
      Pcode/HighVariable-level script (see FixEBPRegisterReuse.java mentioned
      in the tool's own error text for the pattern to follow). NOT attempted
      this session -- flagged as a real follow-up, not solved.
    - table_3axis_interp_triple (0x148a2) -- same fix, same
      __stdcall_far_2arg/ushort prototype. CONFIRMED via real caller
      f250_f252_channel_snapshot_update (0x249f2): `uStack_2 =
      table_3axis_interp_triple();`. Same param-storage regression as above
      (expected, same underlying quirk, not re-litigated per function).
    - table_lookup_indexed (0x14854) -- same fix. Was declared void while
      internally calling table_lookup_interp() without capturing IT either (a
      second copy of the same bug one level up); CONFIRMED via real caller
      knock_octane_dual_axis_table_blend_f2a8 (`uVar2 =
      table_lookup_indexed(...)`). After fix, decompiles cleanly as
      `uVar1 = table_lookup_interp(); return uVar1;`. Same param-storage
      quirk resurfaced, not fixed.

    CHECKED, ALREADY CORRECT (no change made) -- listed so nobody re-checks
    these from scratch: axis_interp_lerp_u8frac, axis_interp_lerp_u8frac_256,
    iat_axis_update, knock_octane_dual_axis_table_blend_f2a8, map_tps_axis_update,
    table_3axis_interp_triple_wrapper, o2_closed_loop_mode_selector_via_table,
    octane_level_init_or_force_from_gear_table, status_word_bit3_conditional_
    update_via_table, status_word_composite_multibit_update_via_table,
    status_word_table_subdispatch_group_a, table_1e4a_lookup_with_f2d6_d8_reset,
    table_read_indexed, table_read_word_indexed_f1fc,
    table_select_scale_fanout_f1be_f1c2, tcu_shift_solenoid_table_init (great
    confirmation case -- 17 internal table_lookup_interp calls all now
    decompile as `uVar1 = (*(code*)0x14656)(); *(...) = uVar1;` post-fix),
    throttle_param_table_select, tiered_threshold_table_select,
    egr_table_row_lookup_f496, f2b4_threshold_table_lookup (also confirms the
    fix propagates: `sVar3 = (*(code*)0x14656)(); return sVar3 + 0x80;`),
    gear_indexed_table_lookup_f1fc, idle_stepper_table_lookup_wrapper,
    ign_advance_table_lookup, isc_f352_table_lookup, isc_f354_table_lookup_
    conditional, isc_f41c_table_lookup (confirms table_lookup_indexed fix
    propagates), isc_f41e_table_lookup, isc_f42a_table_lookup.
    Most of these are genuinely void by design (result only ever reaches a
    memory-mapped global, e.g. f2a8/f496/f41c/etc, no caller ever captures a
    return) -- correctly modeled already, nothing to fix. A handful already
    had a correct real return type before this pass and independently confirm
    the two fixes above are propagating cleanly through their internal calls.

    NOT FIXED, KNOWN UNRELATED ARTIFACT (do not touch, separate issue):
    - knock_octane_dual_axis_blend_far_trampoline (0x23397) -- decompiles as
      an infinite self-call with no base case. Already flagged in its own
      plate comment as a suspected far-call target mis-resolution tied to the
      known CP-register SLEIGH-context limitation (see README). Unrelated to
      return-storage; do not attempt a prototype fix here, needs the CP-ctx
      fix first.

    NOT FIXED, HARDER PROBLEM CLASS -- flagged for a dedicated follow-up:
    - octane_trim_f262_f264_table_select (0x23abe) -- decompiles with heavy
      extraout_R1/extraout_R1_00/_01/_02 and extraout_R2/_00/_01 register
      artifacts around its table_read_indexed calls, plus unaff_R3/unaff_R4.
      This looks like table_read_indexed's REAL output spans two registers
      (a pointer in one + an index/value in another), not the single-ushort
      return this pass's fix pattern covers. Needs its own investigation into
      table_read_indexed's true multi-register return signature before
      anything here can be safely reprotyped -- do NOT apply the simple
      ushort fix to table_read_indexed blindly, it may already be under-
      modeled in a way a naive single-register fix would make worse, not
      better.
    - read_indexed_byte_f1fc (0x1481c) -- NOT in this session's original
      list, noticed in passing while checking
      octane_level_init_or_force_from_gear_table (which calls it and shows
      an `undefined1 extraout_var` artifact combined via CONCAT11 with the
      real return byte -- classic signature of a return-WIDTH mismatch, byte
      vs word, rather than a void-vs-typed mismatch). Worth checking
      alongside the item above, same general "return spans more than the
      modeled single value" theme.

    STATUS: 3 real fixes applied and confirmed stable/propagating
    (table_lookup_interp, table_3axis_interp_triple, table_lookup_indexed).
    ~28 functions checked and left alone (already correct). 1 known unrelated
    artifact left alone (CP-register trampoline). 2 flagged multi-register
    return candidates NOT touched, need dedicated follow-up
    (octane_trim_f262_f264_table_select's table_read_indexed usage,
    read_indexed_byte_f1fc). Outstanding cross-session issue: the param-
    storage-reverts-to-unassigned quirk on table_lookup_interp/
    table_3axis_interp_triple/table_lookup_indexed (pre-existing, documented,
    not caused by this pass) still needs either GUI manual fix or a custom
    Pcode-level script -- set_function_prototype and set_variable_storage
    both confirmed insufficient for it.

    CLOSING NOTE (2026-08-01, same session): grep-swept the full decompiled .c
    for the same bug signature (bare call immediately before `return;`, i.e. a
    computed value discarded) beyond the original 34-function list. Found 5
    further candidates; ALL 5 verified as false alarms against real
    disassembly, not just decompiler output:
    - egr_sequence_control's discarded call to 0x18b17
      (egr_f490_gear_transition_update) -- already-confirmed genuinely-void
      function, no issue.
    - ign_advance_top_update discarding wgdc_correction_integrator_update's
      return -- CONFIRMED via real disassembly this is intentional: the ROM
      saves ign_advance_base_calc_f860's return into a stack slot BEFORE
      calling wgdc_correction_integrator_update, then reloads that saved
      value (not wgdc's return) to feed wgdc_output_clamp_f44c. wgdc's return
      is genuinely unused at the hardware level, not a decompiler artifact.
    - isc_openloop_stepper_scale_calc discarding muldiv_s16_rounded's result
      -- CONFIRMED via real disassembly this is a decompiler call-site
      cosmetic gap, not a bug: table_lookup_interp's R0 result is actually
      pushed directly as muldiv_s16_rounded's argument (`mov:g.w R0,@-SP`
      immediately before the pjsr), the decompile just doesn't show the
      connection (same general family as the param-binding quirk, but at a
      call site rather than a function's own prototype). muldiv_s16_rounded's
      own final result is genuinely unused afterward (function returns
      immediately after).
    NET RESULT: no new return-storage bugs found beyond the 3 already fixed.
    Good confirmation the 3 fixes (table_lookup_interp, table_3axis_interp_
    triple, table_lookup_indexed) were the real bugs in this codebase, not
    the tip of a larger iceberg. Method note for future passes: grep for
    `^\s*[A-Za-z_]\w*\([^;]*\);\n\s*return;` catches candidates cheaply, but
    every hit needs a real disassembly check (not just decompile re-read)
    before concluding bug vs. false-alarm -- several of these looked
    suspicious in the decompiled C alone and only resolved cleanly once the
    actual instruction stream was checked.

22. Custom analyzer script: explicit references for table_lookup_indexed's
    array-base indirection (2026-08-01) -- RESOLVES the structural blocker
    documented in review2.md item 10 ("array-base pointers themselves are
    apparently never referenced via a discoverable static xref, even for
    tables we're certain are real -- this is a structural limitation").

    DIAGNOSIS (external analysis, credited): Ghidra's static xref engine
    cannot follow this ROM's indirection pattern for table_lookup_indexed --
    callers push an ARRAY BASE pointer (not a direct table address), and the
    function does `table = array[global_index & 7]` at runtime. Since the
    real target is only known via a runtime-computed index, there is no
    static address-of relationship for Ghidra to record automatically. This
    is structurally different from table_lookup_interp's callers (which push
    a literal bank+offset directly, hence ARE statically discoverable).

    FIX: rather than asking Ghidra's general xref engine to infer something
    it structurally cannot, wrote a script (run_script_inline, bare
    method-body -- NOT a full class declaration, see item 19's gotcha) that
    encodes the ROM's own convention directly:
      1. get_function_callers on table_lookup_indexed (0x14854) -- Ghidra
         DOES track direct calls to the function itself fine, just not the
         indirection inside it. Found 14 real call sites (9 distinct calling
         functions, some with multiple array-selecting call sites, e.g.
         isc_f34e_f34a_correction_calc has 4).
      2. For each call site, backward-scan (same method as item 19's
         extractor) for the two pushed immediates (offset, bank) to resolve
         the real array base address (bank*0x10000+offset).
      3. refMan.addMemoryReference(callSite, arrayBaseAddr, RefType.DATA,
         SourceType.USER_DEFINED, 0) -- creates the previously-missing
         call-site -> array-base reference.
      4. Read each array's 8 pointer-array slots (4 bytes each: byte0=00
         (unused/pad), byte1=bank, bytes2-3=offset -- confirmed format from
         review2.md's earlier manual reads), resolve each to a real address,
         and add a further reference from the slot -> its real target table.
      5. Label each array base (ARRAY_<callerName>_<hex> convention).
    Dry-run first (confirmed clean output for all 14 sites), then applied for
    real. VERIFIED applied: get_xrefs_to(0x2da0c) now shows the new
    call-site reference from isc_f34e_f34a_correction_calc @0x257a0 -- this
    exact address previously returned ZERO xrefs (review2.md item 10's
    negative-result baseline).

    RESULT -- all 14 call sites resolved cleanly to sensible array bases,
    each array's 8 slots internally consistent (all 8 slots identical per
    array in every case checked, matching the pattern already established on
    known-real tables like the Idle Stepper table). Full mapping:
      isc_f35e_correction_calc (0x25880) -> array 0x2da2c -> table 0x127be
      f33e_bit6_update_from_table_da2c_threshold (0x24f87) -> array 0x2da2c
        -> table 0x127be (SAME array as isc_f35e_correction_calc -- two
        different callers legitimately sharing one array, consistent with
        method note in review2.md about RAM-tag/array reuse)
      isc_f408_f406_stepper_target_calc (0x2716b) -> array 0x2d92c
        -> table 0x128a2 (matches already-confirmed-real Desired ISCV step
        position table -- cross-validation the script's resolution is sound)
      isc_f41c_table_lookup (0x275ad) -> array 0x2d94c -> table 0x128ae (NEW,
        not previously identified in review.md/review2.md)
      fueling_base_injection_calc (0x21a36) -> array 0x2da8c -> table 0x11880
        (NEW)
      idle_target_rpm_compute_f400 (0x262aa) -> array 0x2d8ec -> table
        0x1288a (NEW)
      idle_target_rpm_compute_f400 (0x262cc) -> array 0x2d90c -> table
        0x12896 (NEW -- same caller, second independent array)
      closedloop_fuel_ready_check (0x2271e) -> array 0x2da4c -> table 0x11cea
        (NEW)
      isc_f34e_f34a_correction_calc (0x25777) -> array 0x2dbac -> table
        0x12230
      isc_f34e_f34a_correction_calc (0x257a0) -> array 0x2da0c -> table
        0x1264a (matches already-confirmed-real Warmup Retard table --
        second cross-validation)
      isc_f34e_f34a_correction_calc (0x257c9) -> array 0x2db8c -> table
        0x120d2 (matches already-confirmed-real High Octane Ignition Map 2
        per review2.md item 12 -- third cross-validation)
      isc_f34e_f34a_correction_calc (0x25790) -> array 0x2dbcc -> table
        0x1238e (NEW)
      knock_octane_dual_axis_table_blend_f2a8 (0x233d9) -> array 0x2d9cc
        -> table 0x11bc0 (matches already-confirmed-real Low Octane Fuel Map
        1 -- fourth cross-validation)
      knock_octane_dual_axis_table_blend_f2a8 (0x23400) -> array 0x2d98c
        -> table 0x119b8 (matches already-confirmed-real High Octane Fuel
        Map 1 -- fifth cross-validation)

    5 genuinely NEW table addresses surfaced this way (0x128ae, 0x11880,
    0x1288a, 0x12896, 0x11cea, 0x1238e -- six, corrected count), all via real
    resolved data rather than guesses, directly extending the review2.md
    XML-verification project. NEXT STEP: cross-check these against the XML
    for further address fixes (in progress, see following entry).

    METHOD NOTE for future use: this script targeted table_lookup_indexed
    specifically because get_function_callers already gave a clean, small,
    complete call-site list (14) to work from. The SAME technique should
    generalize to any other indexed/array-base lookup function in this ROM
    (table_read_indexed, gear_indexed_table_lookup_f1fc, etc.) once their own
    caller lists are pulled the same way -- worth doing as a follow-up rather
    than assuming table_lookup_indexed was the only function with this
    indirection pattern.

    XML CROSS-CHECK of the 6 new addresses (2026-08-01, same session):
    - 0x128ae, 0x12896: CONFIRMED already correct in XML (exact address
      match: "Desired ISCV intial step position with AC off-Drive",
      "Desired Idle RPM-Drive"). Excellent independent validation of the
      whole array-reference script's resolution logic -- these came out
      correct without ever having been targeted or reverse-engineered from
      the XML side. No action needed.
    - 0x11880: found as TABLE_2D_00011880, one of the ~94 "Unknown"-category
      Batch 2 placeholder tables. NEW LEAD for Batch 2: real caller now known
      (fueling_base_injection_calc via array 0x2da8c) -- gives a real
      subsystem identity (fueling) even though the axis itself still needs
      separate resolution. Worth prioritizing in Batch 2 given this head
      start.
    - 0x1288a, 0x11cea, 0x1238e: NOT PRESENT in the XML at all (zero grep
      matches for any of the three). These aren't mis-addressed existing
      entries -- they're genuinely undocumented tables with no XML entry
      whatsoever. Adding them is a bigger task than this review's stated
      scope (address-only fixes to existing entries): would need a type,
      axis, and scaling worked out from scratch, not just an address
      correction. NOT attempted this session -- flagged as a separate,
      larger follow-up (new-table-addition project) rather than folded into
      the address-fix pass.

23. Traced the bank+offset far-pointer construction through the pipeline for a
    known-good example, per an external analysis document's suggested
    experiment (H8 bytes -> SLEIGH -> pcode -> bank+offset -> far pointer ->
    decompiler -> ROM address), to determine whether item 22's pointer-
    indirection difficulties are a SLEIGH/pcode problem or a decompiler
    pointer-analysis problem (the class of issue Ghidra core issue #817
    describes: "Decompiler is not handling far pointers to stack/ram data
    correctly" -- confirmed real and maintainer-acknowledged, but for a
    DIFFERENT pipeline stage than what's actually happening here, see below).

    METHOD: picked the already-confirmed-real table_lookup_interp call site
    pushing offset=0x1ccc, bank=1 (real caller: warmup_ign_advance_correction_
    calc @ 0x2280f) and decompiled the caller to see whether the bank+offset
    construction survives to the decompiler's output.

    RESULT: it does NOT survive -- but not for the reason initially
    suspected. The decompile shows:
      bVar2 = 1;
      table_lookup_interp();
    with ZERO arguments displayed at the call site. This is NOT a case of
    Ghidra failing to recognize bank<<16|offset as a meaningful far pointer
    (the #817-style decompiler pointer-analysis question) -- the pointer
    construction never even reaches that stage. This is the ALREADY-
    DOCUMENTED param-storage quirk from item 21: table_lookup_interp's own
    `table` parameter storage reverts to <UNASSIGNED> every time its
    prototype is (re-)set via set_function_prototype (set_variable_storage
    confirmed unable to fix it, GUI or custom Pcode/HighVariable script
    required). Since the callee has no bound parameter to attach the pushed
    values to, the decompiler has nothing to show at any of its call sites --
    the arguments aren't being lost in a pointer-translation step, they were
    never connected to begin with.

    CONCLUSION: the trace-through stops at the parameter-binding stage,
    before p-code semantics get a chance to construct the far pointer, and
    well before the decompiler's pointer-analysis layer (the #817-relevant
    layer) is ever reached. This NARROWS rather than deepens the
    investigation: the fix is not "Ghidra's segmented-pointer decompiler
    analysis is broken for this architecture" (a much harder, more open-
    ended problem) -- it's "table_lookup_interp's own parameter storage
    needs to actually bind," which is a known, scoped, already-flagged
    problem from item 21.
    NEXT STEP: attempt the custom Pcode/HighVariable-level Ghidra script
    (referenced by set_variable_storage's own tool error text, pattern per
    FixEBPRegisterReuse.java) to force table_lookup_interp's `table`
    parameter storage to actually stick. ONLY ONCE that's done can the
    original #817-style question (does Ghidra's decompiler correctly
    recognize bank*0x10000+offset as a meaningful ROM far-pointer once the
    argument is actually visible at the call site) be meaningfully tested at
    all -- it currently cannot be tested because the more basic parameter-
    binding problem blocks the question from being askable. This also means
    item 22's array-base indirection difficulties may have TWO stacked
    causes rather than one: (a) this same param-binding issue on
    table_lookup_indexed (already confirmed reverting the same way in item
    21), compounding (b) the genuine runtime-computed-index problem the
    custom reference-creation script in item 22 was built to route around.
    Fixing (a) may make some of item 22's manual reference-creation
    unnecessary going forward, or may reveal (b) was the only real blocker
    for the direct table_lookup_interp callers all along -- worth re-
    checking once the param-binding fix lands.

24. RESOLVED: table_lookup_interp param-storage quirk fixed via custom
    HighVariable-level script (2026-08-02) -- closes the outstanding
    follow-up from items 19/21/23. The bank+offset argument now displays
    correctly at every real caller for the first time this whole
    investigation.

    METHOD: set_function_prototype (used in items 19/21) and
    set_variable_storage (confirmed insufficient, see item 21) cannot force
    exact parameter storage here -- both let Ghidra's automatic storage
    assignment silently win, reverting `table`'s binding to <UNASSIGNED>
    every time. The real fix is Function.updateFunction() with an explicit
    List<Variable> built from VariableStorage(program, stackOffset, size)
    and FunctionUpdateType.CUSTOM_STORAGE + force=true -- this bypasses
    Ghidra's automatic storage assignment entirely rather than asking it
    nicely. Script: FixTableLookupInterpStorage.java (real .java file
    copied into Ghidra's ghidra_scripts path, NOT inline -- inline still
    hits the OSGi ClassNotFoundException gotcha for anything non-trivial).

    GOTCHAS HIT AND FIXED while getting the storage sizes right (useful
    reference for fixing table_lookup_indexed and table_3axis_interp_triple
    the same way):
    - Pointer DataType size must be explicitly constructed to match the
      real storage width: `new PointerDataType(dtm.getDataType("/void"), 2,
      dtm)` -- `dtm.getPointer(voidType)` alone defaults to 4 bytes and
      throws "Storage size does not match data type size" against a 2-byte
      VariableStorage slot.
    - INITIAL ATTEMPT (ep_val=Stack[0x6]:1 byte, table=Stack[0x7]:2 ptr)
      compiled and applied without error, but produced GARBAGE at every
      caller: `table_lookup_interp(0x1c,(void*)(CONCAT22(0x1ccc,unaff_R3)
      >>8))` -- looked like a pointer question but was actually a width
      bug. Real cause: the disassembly's `adds.b 0x4,SP` after the call
      site proves BOTH pushes are 2-byte wide (`mov:g.w`, word-sized
      writes, regardless of how small the immediate value is) -- so
      ep_val's real storage is 2 bytes, not 1. Declaring it as 1-byte
      caused the decompiler to misattribute the adjacent byte, producing
      CONCAT/unaff_* garbage that superficially looked like a much deeper
      pointer-propagation problem but was just a wrong width declaration.
      ALWAYS check the real disassembly's post-call stack-cleanup
      instruction (`adds.b/adds.w #N,SP`) to get the true total argument
      byte count before guessing storage sizes.
    - SECOND ATTEMPT (ep_val=Stack[0x6]:2, table=Stack[0x8]:2) fixed the
      width/CONCAT garbage but had the two parameters' STACK SLOTS swapped
      -- the pointer value consistently resolved correctly at Stack[0x6]
      regardless of which logical parameter I assigned there, meaning
      Stack[0x6] genuinely holds the offset/pointer (the FIRST-pushed,
      deeper value) and NOT ep_val as originally guessed.
    - THIRD ATTEMPT (table=Stack[0x6]:2, ep_val=Stack[0x8]:2) fixed the
      pointer arg cleanly (`(void*)0x27cc` -- exactly right) but left
      ep_val unresolved (`unaff_retaddr`) -- Stack[0x8] was past the real
      argument range.
    - FOURTH ATTEMPT, CORRECT: table=Stack[0x6]:2, ep_val=Stack[0x4]:2 --
      the LAST-pushed value (bank/ep_val, per the disassembly's push
      order: offset pushed first/deeper, bank pushed second/closer to SP)
      lands at the LOWER FP-relative stack offset, not the higher one.
      RESULT, both real callers checked: isc_f352_table_lookup now
      decompiles as `uVar1 = table_lookup_interp(1,(void *)0x27cc);` and
      warmup_ign_advance_correction_calc as
      `table_lookup_interp(1,(void *)0x1ccc);` -- both exactly matching
      their real disassembly bytes (bank=1 in both cases, offset=0x27cc
      and 0x1ccc respectively), no CONCAT garbage, no unaff_* artifacts,
      clean real values.
    FINAL WORKING STORAGE: ep_val = Stack[0x4]:2 (ushort), table =
    Stack[0x6]:2 (2-byte void*), return = ushort, calling convention
    __stdcall_far_2arg, all applied via CUSTOM_STORAGE + force=true.

    SIGNIFICANCE: this closes item 23's blocker -- the bank+offset far
    pointer NOW visibly reaches the decompiler's call-site output as a
    single, correctly-formed argument (`(void *)0x27cc`), which means the
    ORIGINAL #817-style question (does Ghidra's decompiler correctly treat
    bank*0x10000+offset as a meaningful ROM far-pointer once the argument
    is actually visible) can finally be tested -- see next item for that
    follow-up. Also directly unblocks re-examining whether item 22's
    manual array-reference script is still necessary for the DIRECT
    (non-array-indexed) table_lookup_interp/table_3axis_interp_triple
    callers, since their arguments are now visible to any future
    xref/reference-recovery pass in a way they weren't before.
    NOT YET DONE: apply the same fix to table_lookup_indexed (0x14854) and
    table_3axis_interp_triple (0x148a2), which have the identical
    param-storage quirk (confirmed in item 21) and almost certainly the
    same correct final answer (ep_val=Stack[0x4]:2, table=Stack[0x6]:2,
    same calling convention) given they share the same call-site push
    pattern. Worth doing next -- should be fast now that the correct
    offsets are known rather than needing re-discovery via trial and
    error.

25. Applied item 24's confirmed-correct storage fix to the other two
    functions with the identical quirk (2026-08-02) -- table_lookup_indexed
    (0x14854) and table_3axis_interp_triple (0x148a2). Extended
    FixTableLookupInterpStorage.java into a loop over all three addresses
    using the SAME confirmed offsets (ep_val=Stack[0x4]:2 ushort,
    table=Stack[0x6]:2 void*, __stdcall_far_2arg, CUSTOM_STORAGE+force)
    rather than re-discovering them via trial and error -- applied cleanly
    on the first attempt for both, no further width/offset debugging
    needed.
    VERIFIED against real callers for both:
    - knock_octane_dual_axis_table_blend_f2a8 now decompiles
      table_lookup_indexed calls as `table_lookup_indexed(2,pvVar4)` with
      pvVar4 cleanly resolved to the real array-base addresses (0xd9cc/
      0xd9ac/0xd98c/0xd96c depending on condition) -- notably, this is one
      of item 22's exact array-indirection callers, so the array-base
      pointer is now directly visible in the decompiled C without needing
      item 22's manual reference-creation script for this call site.
    - f250_f252_channel_snapshot_update now decompiles
      table_3axis_interp_triple(1,(void *)0x1ef0) cleanly.
    STATUS: all three functions sharing this param-storage quirk (items 19/
    21/24) are now fully fixed and cross-verified. This is a genuine,
    durable improvement to decompilation quality across every caller of all
    three functions (130+ call sites for table_lookup_interp alone, per
    item 19's extraction), not just the specific ones checked here.
    NOT YET DONE: re-run item 22's array-reference script logic (or
    reconsider whether it's still needed at all for the DIRECT
    table_lookup_interp/table_3axis_interp_triple callers, as opposed to
    table_lookup_indexed's genuine runtime-index case) now that arguments
    are visible without it. Also not yet done: the original item-23
    follow-up question (does Ghidra's decompiler/pointer-analysis layer
    correctly recognize a visible bank+offset pair as a meaningful combined
    ROM far-pointer, i.e. the #817-style question) -- now finally testable
    since the arguments are visible, but not yet tested.
    AUTOMATION NOTE: per discussion, this fix is not currently part of
    Ghidra's auto-analysis pipeline -- it's a standalone script
    (FixTableLookupInterpStorage.java) that must be run manually after each
    fresh import/re-analysis. Turning it into a true auto-running Analyzer
    would need a compiled Ghidra extension (proper Analyzer subclass,
    packaged as a .jar module) -- out of scope for what's doable through
    the current MCP script-running tools. For now: re-run this script
    manually any time the program is freshly imported or re-analyzed.

26. Checked item 22's array-reference script against item 24's param-storage
    fix (2026-08-02) -- two findings, one confirming nothing broke, one
    resolving item 23's flagged follow-up question.

    CHECK 1 -- is item 22's manual reference-creation still necessary now
    that arguments are visible in the decompiler (item 24)? YES, fully,
    nothing changed. Verified via get_xrefs_to on two of item 22's 14 array
    bases (0x2da0c and 0x2d9cc, the latter being knock_octane_dual_axis_
    table_blend_f2a8's array, one of the callers re-verified working in
    item 25): both show EXACTLY the same single reference item 22 created,
    no automatic duplicate or new xref appeared as a side effect of item 24's
    fix. CONFIRMED: decompiler display (item 24, what a human reads in the
    C output) and the reference database (item 22, what Ghidra's own xref/
    data-flow graph actually knows about) are fully independent layers --
    fixing one does not touch the other. Both fixes remain necessary and
    complementary, not overlapping.

    CHECK 2 -- this also resolves the #817-style question flagged as an
    open follow-up in items 23/24 (does Ghidra's decompiler recognize
    bank*0x10000+offset as a meaningful combined ROM far-pointer once both
    values are visible at a call site?). ANSWER: NO. Confirmed via
    knock_octane_dual_axis_table_blend_f2a8's now-clean decompile:
    `table_lookup_indexed(2,pvVar4)` where pvVar4 = (void *)0xd9cc -- that
    0xd9cc is the RAW, un-bank-adjusted offset; the real address is
    bank*0x10000+offset = 0x2d9cc (confirmed via get_xrefs_to, matches the
    caller). The decompiler shows the bank (2) and the raw offset (0xd9cc)
    as two separate, unrelated-looking arguments -- it never combines them
    into a single recognized far-pointer value anywhere in the output, even
    now that both halves are individually visible and correctly bound. This
    is the same class of bug Ghidra core issue #817 documents for x86
    segmented pointers ("Decompiler is not handling far pointers to stack/
    ram data correctly") -- confirmed to apply here too, at the decompiler
    pointer-recognition layer, layered on top of the now-fixed parameter-
    binding layer from item 24. A human reading this decompiled C still has
    to manually apply bank*0x10000+offset to get the real address; the
    decompiler will not do it automatically, and there is currently no
    further fix applied for this (would require the same kind of
    segmentop/constresolve mechanism #817 discusses, or a manual high-level
    annotation/comment convention -- not attempted this session).

27. Built and ran AnnotateBankOffsetCallSites.java (2026-08-02) -- adds an
    EOL comment at every real call site of table_lookup_interp,
    table_lookup_indexed, and table_3axis_interp_triple showing the
    human-readable resolved address (bank*0x10000+offset), directly
    addressing item 26's finding that Ghidra's decompiler never combines
    the two visible arguments into a recognized far pointer on its own.
    Saved in the project at "ghidra scripts/AnnotateBankOffsetCallSites.java"
    (copy into Ghidra's own ghidra_scripts search path before running, per
    the usual gotcha).

    METHOD: reuses the backward-immediate-scan technique from items 19/22
    (walk backwards from each call instruction collecting the last two
    "mov"-family immediates, stopping at the previous call/pjsr/jsr/bsr),
    applied via get_function_callers's real reference list for all three
    target functions rather than a byte-pattern search. Comment format:
    "-> 0x%08x (bank=%d, offset=0x%x)", appended to any existing EOL
    comment rather than overwriting, and skips call sites already annotated
    (idempotent -- safe to re-run after further analysis/renames).

    RESULT: 146 call sites annotated (130 for table_lookup_interp, 14 for
    table_lookup_indexed, 2 for table_3axis_interp_triple), 0 unresolved.
    Cross-validates cleanly against item 22's independently-derived array
    base list -- all 14 table_lookup_indexed entries match exactly.

    KNOWN FALSE POSITIVES, flagged, do not trust these three specific
    annotations:
    - isc_f438_correction_calc @ 0x26b67 and egr_duty_target_calc @
      0x18744, both resolving to bank=252, offset=0xfe -> 0x00fc00fe.
      These are the exact two rows already flagged in item 19 as
      "implausibly small, likely a parser mis-grab" -- 0xfc00fe is clearly
      outside the ROM's real address range, confirming rather than
      resolving that original suspicion. The backward-scan is grabbing
      unrelated immediates from further up the function, not this call's
      real arguments.
    - table_3axis_interp_triple_wrapper @ 0x1499b, resolving to bank=2,
      offset=0x8 -> 0x00020008. This wrapper is a pure passthrough with NO
      arguments of its own (confirmed decompile: `table_3axis_interp_
      triple(); return;`, item 21) -- the backward-scan walked past this
      tiny function's boundary into unrelated preceding code and grabbed
      garbage immediates. Same failure mode as the two rows above: the
      technique assumes the two nearest preceding immediates belong to
      this call, which fails when the caller doesn't actually push its own
      arguments (either genuinely arg-less passthrough, or -- as seen with
      the 252/254 pair -- possibly a real args a different way this scan
      doesn't capture).
    GOOD CONFIRMATION, worth noting: table_lookup_indexed's own internal
    call to table_lookup_interp (at 0x14874, inside table_lookup_indexed's
    body) got correctly annotated too, matching the item 21 decompile
    exactly (`uVar1 = table_lookup_interp(); return uVar1;` -- now resolves
    to a real address via this script).

    NOT YET DONE: clean up/exclude the 3 known-bad annotations (either
    remove the misleading comment or mark it clearly as unresolved rather
    than a wrong address) -- left as-is this session since they're now at
    least flagged here for anyone reading the annotated listing. A more
    robust version of the backward-scan (e.g. verifying the two immediates
    are pushed by immediately-adjacent instructions with no unrelated code
    between them, or cross-checking against get_xrefs_to counts before
    trusting a resolution) would avoid this failure mode -- not
    implemented this session.
