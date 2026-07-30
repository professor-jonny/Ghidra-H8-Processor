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

    STATUS: XML file has NOT been modified. Two real bugs confirmed (Warmup
    Retard, Injector Battery Voltage Latency Compensation) but not fixed pending
    a verified replacement address for each -- do not guess-write these, both
    prior guesses in this session turned out to be mismatches on closer check.
    One optional addition identified (Air Temperature Compensation @ 0x11d7a)
    but not added pending same level of confidence as the confirmed fixes.
