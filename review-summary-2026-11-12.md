# Review summary (2026-11-12)

Short account of what survives from the closed review threads. Written from
the headers, status lines and cross-checks of the files named; the long
chronological files were not re-read in full, so treat details below as
"as recorded in those files". Originals are untouched apart from status
banners at the top.

## 1. register0x0e / auStack_ / muldiv_* / #9561 (review15-26, review-9561-merge-ordering, review-calling-convention-regression)

- **Outcome:** closed. #9561 is fixed by upstream Ghidra code (user,
  2026-11-12; upstream commit hash not recorded, add it to `todo.md`).
- `todo.md` ("State in one paragraph") records that almost all of these
  "decompiler bugs" (#9540/#9541 register0x0e, #9561 sat_add_u16 arrays,
  the muldiv_u16_scaled crash) came from the language's p-code shape or from
  project data, not the core. The language had built addresses as
  `SEGMENTOP(TP,FP)+disp` and used pointer stores into register space; both
  were fixed in the language.
- **Real fix that stayed true:** `muldiv_u16_scaled`'s parameter-offset bug
  was an extrapop/stackshift problem on far calls (review-9561 Findings
  9-11). That thread is the same family as the later stackshift 0 / purge
  work in section 3.
- **Walked back:** the headline "muldiv_* is a correctness regression"
  (review20) was corrected inside review20 and by review21 (display/naming
  only). review-9561's "output is confirmed wrong" status was a snapshot
  of 2026-09-14/15 and is closed by the upstream fix.
- **Falsified hypotheses, do not retry:** `RangeHint::merge` "confuse"
  branch; SEGMENTOP exclusion in `gatherAdditiveBase`; `RuleAddMultCollapse`;
  killedbycall for muldiv_u16; blaming `register0x0e_crossregister_fix.xml`.
- **Unreconciled (low value):** the index attributes review17-19's cause to
  displacement order / RdN pointer store / param_fpN offsets; review19
  describes its fix as unwrapped offset arithmetic overflowing a 16-bit
  address space. The register0x0e fix is cited as 920fcd6 (index) and
  aadd7ee (review16).

## 2. R0-R5 displacement addressing (review27, 28, 29, todo-r0-r5-displacement-order, review13 Issue A)

- Final design: sign-split hybrid grammar (displacement sign bit clear:
  `spSegment(PAGE,Rn)+disp`, set: add-then-segment) together with
  `<funcptr align="1" />` in `h8539f.cspec`. Either alone breaks the 0x28b2f
  switch; both together are needed.
- "Regression 1" (0x28b2f) is resolved by that combination. The "hybrid grammar
  hole" was stale instruction prototypes stored in the Ghidra project; no
  sleigh bug, nothing to report upstream.
- **Rule:** after any `.slaspec`/`.sinc` change run `scripts\ReDisasm.java`
  before measuring p-code shape or decompiling an existing project.
- review28's absolute numbers were measured on stale prototypes (slightly
  off, conclusions look unaffected); the other ROMs (`multi\`, `multi2\`)
  were not re-run.

## 3. Stackshift 0 and stack purge (review32, todo.md, NOTES.TXT)

- The decompiler uses extrapop = purge + stackshift; the analyzers store the
  whole return pop (return address included), so stackshift above 0 counts
  it twice. Fix: `stackshift="0"` on every prototype (deployed; the eight
  `_ns0*`/`_ns2*` experiment prototypes removed; 26 prototypes; 078ee5f, not
  pushed). Return-address stores: 353 to 0.
- Five functions had wrong stored purges (`sat_add_s16`, `sat_sub_u16_clamp0`,
  `select_min_xy_triple`, `muldiv_u16_scaled`, `muldiv_s16_rounded_3op`);
  all really 4; fixed in the project copies. `H8PurgeEnforcementAnalyzer`
  is deployed and verified (719 correct, 0 corrected in a real run).
- Do not revert the cspec: SP consistency is the correctness criterion.

## 4. bra:16 phantom fall-through (HANDOVER-2026-11-12, todo.md "2026-11-12 part 2")

- Cause: the `bra:16` sleigh constructor was a CBRANCH with constant 1, so
  Ghidra saw a conditional jump with a fall-through. Fixed with one line in
  `h8539f-branch.sinc` (`bra:16` with `cond=0` is now a `goto`). All 117
  `bra:16` sites are `UNCONDITIONAL_JUMP`; `table_lookup_interp` @00014656
  lost its ghost stack params.
- Open: nine orphan blocks after `bra:16` jumps (check for jump tables),
  user commit/push of the sleigh edit (repo `h8539f.sla` is the old
  compile), CHANGELOG/NOTES entries (NOTES.TXT has no `bra:16` mention).

## 5. Still open elsewhere (not part of the closed threads)

- review7: `tcu_shift_ratio_buffer_update` (0x2c16e) R2 upper-byte question;
  two undefined return types (as of 2026-08-09).
- review8: `f502_state_index_update` (0x27f60), 13 unchecked zero-caller
  functions, DAT_0001f1fe bitfield, review6 footnote.
- review10: five suspect table headers; review14: seven verification TODOs.
- Re-check whether PR #9522 is still needed.
