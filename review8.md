COMPUTED-CALL STATE-TABLE DISPATCH: f502_state_table_dispatch AND ITS
UNRESOLVED HANDLER TARGETS
====================================================================

GOAL: review6.md's zero-caller cohort sweep (17 functions, confirmed via
get_xrefs_to with zero references of any kind) was correct given what it
checked -- but "zero references Ghidra can see" is not the same as "zero
callers." This file documents a real, confirmed computed-call dispatch
mechanism that Ghidra's static xref analysis cannot see through, which
explains at least 4 of those 17 "dead" functions and additionally surfaces
16 more handler targets that are not even disassembled as functions yet.

--------------------------------------------------------------------
THE MECHANISM (confirmed, not guessed -- cross-checked against an existing
Ghidra bookmark at 0x27ed4/0x136e2 plus independent byte-level decode)
--------------------------------------------------------------------
f502_state_table_dispatch (0x27e9c) reads a state byte from RAM at 0xf502,
splits on `cmp:g.b #0xc,@0xf502` (0x27eb2) into two contiguous sub-tables,
computes `mulxu.w #6,Rn` to index by 6-byte record, and calls the resolved
handler via `pjsr @R0` at 0x27ed4 -- a genuine computed indirect SUBROUTINE
call, not a jump table Ghidra's own jump-table recovery would catch.

Two sub-tables:
  - state < 12: base 0x1369a, 12 records (states 0-11)
  - state >= 12: base 0x136e2, 9 records (states 12-20)

Record format, 6 bytes: [flags:16][bank:8, constant 0x02][pad:8, constant
0x00][handler-offset:16]. Real target address = bank<<16 | offset.

Companion function f502_state_index_update (0x27f60) almost certainly
writes the 0xf502 state byte that drives this dispatch -- not yet
investigated in this file, worth a look when picking this back up.

--------------------------------------------------------------------
FULL DECODED TABLE (both sub-tables, all 21 states, verified against the
live function list 2026-08-09)
--------------------------------------------------------------------
State < 12 (base 0x1369a):
  state 0  flags=0002  -> 0x27fb1  f17a_load_zone_and_ef96_f1d8_check   [FN EXISTS, 0 xrefs]
  state 1  flags=0040  -> 0x27fea  [NOT A FUNCTION -- undisassembled]
  state 2  flags=0080  -> 0x2800a  phase_dispatch_efa2_f500_f5ee_gate_check [FN EXISTS, 0 xrefs]
  state 3  flags=0101  -> 0x28038  FUN_00028038                          [FN EXISTS, 0 xrefs, unnamed]
  state 4  flags=0108  -> 0x28082  f17a_f13c_load_zone_and_f514_gate_check [FN EXISTS, 0 xrefs]
  state 5  flags=0140  -> 0x280be  [NOT A FUNCTION -- undisassembled]
  state 6  flags=0180  -> 0x280d3  [NOT A FUNCTION -- undisassembled]
  state 7  flags=0201  -> 0x280d8  [NOT A FUNCTION -- undisassembled]
  state 8  flags=0020  -> 0x280dd  [NOT A FUNCTION -- undisassembled]
  state 9  flags=0110  -> 0x28151  [NOT A FUNCTION -- undisassembled]
  state 10 flags=0120  -> 0x28253  [NOT A FUNCTION -- undisassembled]
  state 11 flags=0301  -> 0x28258  [NOT A FUNCTION -- undisassembled]

State >= 12 (base 0x136e2, index adjusted via adds.b 0xb8,R2 at 0x27ec2):
  state 12 flags=0002  -> 0x27fe5  [NOT A FUNCTION -- undisassembled]
  state 13 flags=0104  -> 0x2816c  [NOT A FUNCTION -- undisassembled]
  state 14 flags=0004  -> 0x28192  [NOT A FUNCTION -- undisassembled]
  state 15 flags=0008  -> 0x281a1  [NOT A FUNCTION -- undisassembled]
  state 16 flags=0102  -> 0x281b6  [NOT A FUNCTION -- undisassembled]
  state 17 flags=0204  -> 0x281e4  [NOT A FUNCTION -- undisassembled]
  state 18 flags=0208  -> 0x28210  [NOT A FUNCTION -- undisassembled]
  state 19 flags=0210  -> 0x28215  [NOT A FUNCTION -- undisassembled]
  state 20 flags=0220  -> 0x28234  [NOT A FUNCTION -- undisassembled]

VERIFICATION METHOD: independently byte-decoded both sub-tables directly
from ROM memory (ghidra:read_memory at 0x13690-0x136e2 and cross-checked
part 2 against the existing bookmark's own pasted per-state list at
0x136e2) -- the two sources agree on every value checked. Function-name
lookup via search_functions_enhanced sorted by address confirms the
function list jumps from f17a_f13c_load_zone_and_f514_gate_check (0x28082)
directly to eee4_eeda_bit6_update_from_f0f8_bit12 (0x28279) with NOTHING
in between -- all 16 of the states-1/5-20 targets sit in that gap as raw
undisassembled bytes, not functions.

--------------------------------------------------------------------
IMPACT ON PRIOR FILES
--------------------------------------------------------------------
review6.md's zero-caller-cohort conclusion for these 4 functions needs a
footnote, not a retraction: f17a_load_zone_and_ef96_f1d8_check,
phase_dispatch_efa2_f500_f5ee_gate_check, FUN_00028038, and
f17a_f13c_load_zone_and_f514_gate_check are NOT dead code. They are real
handlers reached only via f502_state_table_dispatch's computed pjsr, which
review6.md's get_xrefs_to sweep could not see (computed calls don't
register as static references the way direct calls or resolved jump
tables do). The other 13 functions in that cohort are unaffected by this
finding -- no evidence yet ties them to this or any other computed-call
mechanism, they remain correctly classified as dead pending a similar
check.

--------------------------------------------------------------------
PLAN: H8StateTableDispatchAnalyzer
--------------------------------------------------------------------
New analyzer, same conflict-safe/evidence-only posture as
H8FramePointerParamAnalyzer and H8FunctionPurgeAnalyzer (see those files'
own doc comments for the house style this follows):

1. Locate dispatch sites matching the confirmed idiom: a `cmp:g.b` against
   a RAM state byte, immediately followed by a `mulxu.w #0x6,Rn`
   size-6-record index computation, followed by a `pjsr @Rn`. Start from
   the two known, confirmed sites (0x27e9c region / table bases 0x1369a
   and 0x136e2) rather than a blind ROM-wide pattern scan for the first
   version -- generalize to a wider scan only after this known-good case
   is handled correctly end to end.
2. For each table, parse every 6-byte record: flags (2 bytes, informational
   only, not a param -- do not confuse with H8FramePointerParamAnalyzer's
   FP-offset params), bank (1 byte, expect constant 0x02 -- log and skip
   the record if it's ever anything else, do not guess), pad (1 byte,
   expect 0x00), offset (2 bytes). Real target = bank<<16 | offset.
3. For each resolved target address:
   a. If no Function exists there yet, disassemble at that address and
      create a Function (mirrors what a human would do via "Create
      Function" in the listing -- this is mechanical, the address is
      already unambiguous real evidence, not a guess).
   b. Add a COMPUTED_CALL reference from the pjsr instruction to the
      target, so Ghidra's own xref graph -- and any later
      H8FramePointerParamAnalyzer pass over these newly-defined functions
      -- sees a real caller instead of zero.
4. Log every record decoded and every action taken (function created /
   already existed / reference added / record skipped and why), same
   logging discipline as the two existing analyzers.
5. Explicitly OUT OF SCOPE for v1: general ROM-wide pattern scanning for
   other instances of this same dispatch idiom (flagged as a possible v2
   once this known case is proven correct); retyping the newly-created
   functions' return types or parameters (that's H8FramePointerParamAnalyzer's
   and review4/6.md's job, run those AFTER this analyzer, not instead of
   it); the flags field's meaning (informational bitmask, not touched).

--------------------------------------------------------------------
RUNNING LOG
--------------------------------------------------------------------
2026-08-09: File created. Discovered while investigating the person's
hypothesis that many "dead" zero-caller functions might actually run via
a background scheduler/interrupt/GPIO mechanism not visible to static
xref analysis. Confirmed correct -- found and fully decoded the
f502_state_table_dispatch computed-call mechanism (cross-checked against
an existing Ghidra bookmark, not a fresh guess), identified 4 previously
"dead" functions as real handlers, and surfaced 16 additional handler
targets with no Function defined at all. Scoped H8StateTableDispatchAnalyzer
to fix both problems (missing functions + missing references) for this
specific, fully-verified dispatch site. NEXT STEP: implement the analyzer
(H8StateTableDispatchAnalyzer.java), starting from the known table
addresses rather than a general pattern scan, per the PLAN section above.
Also flagged for later, not yet done: check f502_state_index_update
(0x27f60) to understand what actually drives state selection, and re-check
the other 13 zero-caller-cohort functions from review6.md against this or
any other computed-call mechanism before treating them as settled dead
code.
2026-08-09 (session 2): Implemented H8StateTableDispatchAnalyzer.java (see
that file's own doc comment for full detail). Scoped strictly to the two
known/verified table addresses per the PLAN above, not a general pattern
scan. Not yet compiled/run in Ghidra -- no Java compiler available in the
tool environment used to write it, so it has only been checked by careful
manual read-through (imports, API usage against the same Ghidra API
surface H8FramePointerParamAnalyzer/H8FunctionPurgeAnalyzer already use
successfully) rather than an actual build. NEXT STEP: build the h8
extension (existing project build process -- same one that produced the
.class files for the other three analyzers) and run it against the RVR
md352553 program, then verify: (a) all 16 missing functions get created,
(b) all 21 COMPUTED_CALL references land correctly, (c) the 4
already-existing functions pick up their new reference without any other
change, (d) re-run H8FramePointerParamAnalyzer afterward to see if the 16
newly-created functions get real FP-relative parameter storage now that
they're reachable, which would be the real end-to-end validation of this
whole investigation.
