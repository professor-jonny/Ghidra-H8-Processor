# H8/500 Instruction Ground Truth Table

Source of truth: `source\ida-sdk-main\src\module\h8500\ana.cpp` (read directly,
line-by-line, July 2026 -- not re-derived from memory or from the old README's
bug list, per the refactor plan's step 1). Every row below is transcribed from
the live tables/switch statement, not inferred.

**Status legend:** `todo` = not yet ported to new `.sinc` structure -- everything
below is `todo` until the migration actually starts moving code.

---

## Verification pass 2 (self-check against source, same session)

Re-read the raw `A2`/`A3`/`A4`/`A5`/`A6` array literals a second time, byte value
by byte value, against the first-pass table below (not just against my own
summary of them). Found and fixed two real transcription errors:

1. **`A2[0x04]` was mislabeled.** First pass called it "payload only, unclear
   target." It is actually `MAP5` (`A2` row `/* 00 */`, offset 4) -- a first
   MAP5 entry point mirroring the `0x05`=`MAP4` pattern from the re-opened
   BUG 9 finding below: byte `0x04` parses an `imm8` payload into `Op1`
   (`case 0x04: aux_byte; [[fallthrough]]; case 0x14: imm8(...)`), then the
   `while` loop still runs (itype is still `MAP5`) and reads the real MAP5
   dispatch byte. This is now folded into the top-level table row below and
   the open-questions list has been shortened accordingly -- it was answerable
   directly from `ana.cpp`, no live ROM check needed.
2. **`A4` head-table row `0x01-0x07` was wrong.** First pass copied `A3`'s
   all-null `0x01-0x07` row across all four MAP columns. Re-reading `A4`'s own
   literal (`/* 00 */` row) shows `A4[4]=cmp_g`, `A4[5]=cmp_g`, `A4[6]=mov_g`,
   `A4[7]=mov_g` -- MAP4 diverges from MAP3/MAP5/MAP6 in this range. This
   matches the later `case H8500_cmp_g`/`case H8500_mov_g` handlers (byte
   form when `code==0x04`/`0x06`, word form when `code==0x05`/`0x07`), so the
   correction is internally consistent with code already read in pass 1, just
   not carried into the table grid. Fixed in the head table below. Every other
   row of `A3`/`A4`/`A5`/`A6` (head and tail) was re-checked value-by-value
   against pass 1 and confirmed correct -- these two were the only errors.

Flagging this here deliberately rather than silently fixing it: the whole point
of this table is to be trustworthy enough that `.sinc` files get written against
it without re-deriving from `ana.cpp` each time, so an error caught by a second
pass and left undocumented would defeat that purpose. Any future edit to this
table should log a similar note if it changes a previously-stated row.

---

## FINDING: old BUG 9 "SUPERSEDED" note is itself wrong -- re-open BUG 9 as originally written

The previous README marked BUG 9 (MAP4 absolute-addressing entry points at
`0x05`/`0x0D`/`0x15`/`0x1D`) as **SUPERSEDED**, claiming these are "plain
immediate/absolute operand-fetch cases, not a second MAP4 entry point."

Reading `ana.cpp`'s `h8500_ana()` directly (lines 259-282) shows this is wrong:

```c
if ( code < 0x60 )
  insn.itype = A2[code];        // <-- A2[0x05]=A2[0x0D]=A2[0x15]=A2[0x1D] = MAP4, set HERE
...
switch ( code )
{
  case 0x05:  // #aa:8.B
    aa8(insn, insn.Op1, dt_byte);   // <-- just parses the address payload into Op1
    break;
  ...
}
while ( insn.itype > H8500_last )   // <-- itype is still MAP4 at this point, so this loop runs
{
  ...
  code = insn.get_next_byte();      // <-- reads the REAL dispatch byte, indexes A4/A4tail
  insn.itype = tables[index].head[code]; // or .tail[...]
  ...
}
```

So `A2[0x05]` genuinely is `MAP4`. `case 0x05` in the switch only parses the
address-payload operand (`Op1`) -- it does **not** clear `insn.itype`, so the
`while (insn.itype > H8500_last)` loop still runs afterward and reads one more
byte to resolve the real MAP4 mnemonic from `A4`/`A4tail`, exactly as the
*original* (pre-supersede) BUG 9 text said. The byte layout really is
`[fixed opcode byte 0x05/0x0D/0x15/0x1D][address payload][MAP4 dispatch byte]`.

**Action:** re-open BUG 9 as originally written; the "SUPERSEDED" correction
should itself be treated as incorrect until/unless contradicted by a live ROM
byte read. This is exactly the failure mode the refactor plan is trying to stop
-- a "verified" claim that wasn't actually re-checked against the primary source
before being written down. Don't trust the old bug list's later corrections any
more than its original entries; both need re-verification against `ana.cpp` (and
ultimately live ROM bytes) before being acted on.

---

## Structural facts confirmed directly from `h8500_ana()` (lines 259-650)

These are the load-bearing facts the new `.sinc` files must be written against.

1. **Two-tier top-level dispatch on the first byte:**
   - `code < 0x60` -> `A2[code]` (flat 96-entry table, one byte = one lookup)
   - `code >= 0x60` -> `A2tail[(code>>4)-6]` (16-wide groups: `0x60-6F`, `0x70-7F`,
     `0x80-8F`, `0x90-9F`, `0xA0-AF`=MAP3, `0xB0-BF..0xF0-FF`=MAP4 x5)
2. **MAP resolution is a loop, not a single step** (`while (insn.itype > H8500_last)`)
   -- `H8500_last` is a sentinel; MAP3/4/5/6 constants sort above it. This matters
   because **MAP3 and MAP4's own second-byte value `0x00` is itself `MAP6`**
   (`A3[0] = MAP6`, `A4[0] = MAP6`). So `0xA0 0x00` and `0xB0 0x00` (etc.) are
   **three-byte** MAP3-then-MAP6 / MAP4-then-MAP6 chains, decoded by the same loop
   running twice. This is a direct analog to Z80's `DD CB` / `FD CB` two-prefix
   chains and must be modeled the same way (chain a second literal constraint),
   not as a dead/unreachable byte value.
3. **Second-byte dispatch within a MAP is genuinely two different shapes, not one:**
   - second byte `< 0x20`: direct index into the MAP's `head` table (`A3`-`A6`,
     32 entries, no operand register implied by the dispatch byte itself)
   - second byte `>= 0x20`: `tail[(code>>3)-4]`, i.e. **8-wide groups**, and in
     this branch the dispatch byte's low 3 bits are *also* used as the `Op2`
     register (`opreg(insn.Op2, code, dtype)`) -- register and opcode-selector
     share the same byte. This confirms the old BUG 11 resolution (`m4sz` as an
     8-wide family selector, not the earlier wrong 16-wide `m4op` grouping) was
     correct.
4. **MAP6 has an extra legality filter keyed on the *original* first byte**
   (`saved_code`, captured before any MAP escape), not just the dispatch byte:
   entry byte `0x01`/`0x06`/`0x07` only ever produce `scb`; entry byte `0x11`
   only produces `prts`/`prtd`/`jmp`/`pjmp`/`jsr`/`pjsr`; every other MAP6 entry
   only produces `movfpe`/`movtpe`/`dadd`/`dsub`. Since the only bytes that ever
   route into MAP6 are `0x01`, `0x06`, `0x07`, `0x11` per `A2` -- **plus the
   MAP3/MAP4-chained `0x00` second-byte case, which also lands here and needs
   its own legality check confirmed against a live ROM byte**, since the
   switch's `default` branch (`movfpe`/`movtpe`/`dadd`/`dsub`) doesn't obviously
   correspond to any of the four `A2`-level entry points -- flagged as a genuine
   open question, not yet resolved, needs a live ROM instance to confirm which
   entry path actually reaches the `default` case.
5. **`CP`/context-dependent decode:** none found in `h8500_ana()` itself --
   `CP` only matters for computing the final target address of far jumps at
   `case 0x10`/`0x18` (`insn.ea & ~0xFFFF`) and isn't used to *select* which
   instruction to decode. This narrows old BUG 8 to a pure semantics/decompiler
   correctness issue (target address resolution), not a disassembly-dispatch
   issue -- good, lower risk than initially scoped.
6. **Byte-vs-word size for the whole `0x60-0xFF` A2tail range is decided by
   first-byte bit 3** (`code & 8`), read once before any MAP dispatch, and
   carried in `insn.auxpref` (`aux_word`/`aux_byte`) rather than being
   re-derived from the second byte. This confirms BUG 11's "Part B" (first-byte
   bit for size) was on the right track -- the bit is literally `bit 3 of the
   MAP-family first byte`, i.e. `opcode47`'s low bit within its own nibble
   (`opcode47 & 1` in the old field naming), needs a real SLEIGH field for it.

---

## Top-level dispatch table (`A2`, `code < 0x60`)

| First byte | Mnemonic / target | Category | SLEIGH note |
|---|---|---|---|
| `0x00` | `nop` | branch/misc | literal, no payload |
| `0x01` | MAP6 (-> `scb/f`, `saved_code=0x01`) | branch | MAP6 chain, `aux_f` |
| `0x02` | `ldm.w @sp+,<reglist>` | mem | reads reglist byte |
| `0x03` | `pjsr @aa:24` | branch | reads page byte + word |
| `0x04` | MAP5 | -- (see MAP5 table) | literal escape, address payload (`imm8`,`aux_byte`) parsed first, then dispatch byte -- first MAP5 entry point, same pattern as the re-opened BUG 9 MAP4 case below |
| `0x05` | MAP4 | -- (see MAP4 table) | literal escape, address payload (`aa8`,`dt_byte`) parsed first, then dispatch byte -- re-opened BUG 9 case |
| `0x06` | MAP6 (`scb/ne`, `saved_code=0x06`) | branch | `aux_ne` |
| `0x07` | MAP6 (`scb/eq`, `saved_code=0x07`) | branch | `aux_eq` |
| `0x08` | `trapa #xx` | branch | reads extra byte, must be `0x1N` or invalid |
| `0x09` | `trap/vs` | branch | **confirms old BUG 10's proposed fix (`0x05`->`0x09`) was right, but for the wrong reason -- `0x05` was never free, it's MAP4 (re-opened BUG 9), not an incidental collision** |
| `0x0A` | `rte` | branch | literal |
| `0x0B` | `bpt` | branch | literal |
| `0x0C` | MAP5 | -- | first MAP5 entry point |
| `0x0D` | MAP4 | -- | second MAP4 literal entry point, `aux_word`, needs address payload first (`aa8`, `dt_word`) |
| `0x0E` | `bsr d:8` | branch | reads disp8 |
| `0x0F` | `unlk` | branch | literal, implicit `FP` operand |
| `0x10` | `jmp @aa:16` | branch | far target via `CP` page fold |
| `0x11` | MAP6 (`prts`/`prtd`/`jmp`/`pjmp`/`jsr`/`pjsr` only) | branch | MAP6 chain w/ legality filter |
| `0x12` | `stm.w <reglist>,@-sp` | mem | mirrors `0x02` |
| `0x13` | `pjmp @aa:24` | branch | mirrors `0x03` |
| `0x14` | `rtd #xx:8` | branch | see reconciliation note below re: old BUG 3 |
| `0x15` | MAP4 | -- | third MAP4 literal entry point, `aux_byte`, `aa16`/`dt_byte` payload first |
| `0x16` | `H8500_null` | -- | invalid opcode, `ana.cpp` returns 0 |
| `0x17` | `link #xx:8` | branch | implicit `FP`, imm8 |
| `0x18` | `jsr @aa:16` | branch | mirrors `0x10` |
| `0x19` | `rts` | branch | literal |
| `0x1A` | `sleep` | branch/misc | literal -- **confirms old BUG 2's fix (`0x2C`->`0x1A`) was correct** |
| `0x1B` | `H8500_null` | -- | invalid |
| `0x1C` | `rtd #xx:16` | branch | see reconciliation note below |
| `0x1D` | MAP4 | -- | fourth MAP4 literal entry point, `aux_word`, `aa16`/`dt_word` payload first |
| `0x1E` | `bsr d:16` | branch | disp16 |
| `0x1F` | `link #xx:16` | branch | implicit `FP`, imm16 |
| `0x20-0x2F` | `bra`/`brn`/`bhi`/.../`ble` (d:8) | branch | 16 condition codes, disp8 |
| `0x30-0x3F` | same 16 conditions (d:16) | branch | disp16 |
| `0x40-0x47` | `cmp:e #xx:8,Rn` | arith | imm8 + reg from low 3 bits |
| `0x48-0x4F` | `cmp:i #xx:16,Rn` | arith | imm16 + reg |
| `0x50-0x57` | `mov:e #xx:8,Rn` | mem | imm8 + reg |
| `0x58-0x5F` | `mov:i #xx:16,Rn` | mem | imm16 + reg |

**`rtd` reconciliation note:** this table shows `A2[0x14]`/`A2[0x1C]` as the real
`rtd` entries (`ana.cpp` line 621-627 picks imm8 vs imm16 by testing `code==0x14`),
while `A2[0x04]`/`A2[0x0C]` are bare immediate-fetch cases whose consuming
mnemonic isn't obvious from the top-level table alone. The old README's BUG 3
claimed the fix was `0x04`/`0x0C` -- that doesn't match what's read here
(`0x14`/`0x1C`). **Do not trust either the old "Fixed" status or this table's
first pass blindly -- re-verify against a live ROM `rtd` instance before writing
the `branch.sinc` constructor.**

## `A2tail` (`code >= 0x60`, indexed by `(code>>4)-6`, 16-wide groups)

| First byte range | Target | Category |
|---|---|---|
| `0x60-0x6F` | `mov:l @aa:8,Rn` (`aa8` + reg) | mem |
| `0x70-0x7F` | `mov:s Rn,@aa:8` (reg + `aa8`) | mem |
| `0x80-0x8F` | `mov:f @(d:8,R6),Rn` (`ds8` w/ `R6` base + reg) | mem |
| `0x90-0x9F` | `mov:f Rn,@(d:8,R6)` (reg + `ds8` w/ `R6` base) | mem |
| `0xA0-0xAF` | MAP3 | -- (see MAP3 table) |
| `0xB0-0xFF` | MAP4 (5 groups) | -- (see MAP4 table) |

Note the switch statement (lines 441-476) further splits `0xA0-0xFF` into
sub-ranges for the *first-operand* addressing mode (`Rn,Rn` / `@-Rn,Rn` /
`@Rn+,Rn` / `@Rn,Rn` / `@(d:8,Rn),Rn` / `@(d:16,Rn),Rn`) **before** the MAP
dispatch loop even runs -- this is `Op1`'s addressing mode, separate from the
MAP second byte which supplies the mnemonic and (sometimes) `Op2`. Two
independent axes: first byte -> `Op1` EA shape; MAP second byte -> mnemonic (+
sometimes `Op2` register). The existing `eab_*`/`eaw_*` addressing-mode
subtables in `h8539f.slaspec` already model this axis reasonably -- keep them,
they were never the broken part.

## MAP3/MAP4/MAP5/MAP6 head tables (second byte `< 0x20`)

| Second byte | MAP3 (`A3`) | MAP4 (`A4`) | MAP5 (`A5`) | MAP6 (`A6`) |
|---|---|---|---|---|
| `0x00` | MAP6 (chain!) | MAP6 (chain!) | null | null |
| `0x01` | null | null | null | null |
| `0x02` | null | null | null | null |
| `0x03` | null | null | null | null |
| `0x04` | null | `cmp_g` (imm8/byte form) | null | null |
| `0x05` | null | `cmp_g` (imm16/word form) | null | null |
| `0x06` | null | `mov_g` (imm8/byte form) | null | null |
| `0x07` | null | `mov_g` (imm16/word form) | null | null |
| `0x08` | `add_q` | `add_q` | null | null |
| `0x09` | `add_q` | `add_q` | null | null |
| `0x0A-0x0B` | null x2 | null x2 | null x2 | null x2 |
| `0x0C` | `add_q` | `add_q` | null | null |
| `0x0D` | `add_q` | `add_q` | null | null |
| `0x0E-0x0F` | null x2 | null x2 | null x2 | null x2 |
| `0x10` | `swap` | null | null | null |
| `0x11` | `exts` | null | null | null |
| `0x12` | `extu` | null | null | null |
| `0x13` | `clr` | `clr` | null | null |
| `0x14` | `neg` | `neg` | null | `prtd` |
| `0x15` | `not` | `not` | null | null |
| `0x16` | `tst` | `tst` | null | null |
| `0x17` | `tas` | `tas` | null | null |
| `0x18` | `shal` | `shal` | null | null |
| `0x19` | `shar` | `shar` | null | `prts` |
| `0x1A` | `shll` | `shll` | null | null |
| `0x1B` | `shlr` | `shlr` | null | null |
| `0x1C` | `rotl` | `rotl` | null | `prtd` |
| `0x1D` | `rotr` | `rotr` | null | null |
| `0x1E` | `rotxl` | `rotxl` | null | null |
| `0x1F` | `rotxr` | `rotxr` | null | null |

## MAP3/MAP4/MAP5/MAP6 tail tables (second byte `>= 0x20`, 8-wide groups, `Op2` = dispatch-byte low 3 bits)

| Group (`0xNN-0xN7`) | MAP3 (`A3tail`) | MAP4 (`A4tail`) | MAP5 (`A5tail`) | MAP6 (`A6tail`) |
|---|---|---|---|---|
| `0x20-27` | `add_g` | `add_g` | `add_g` | null |
| `0x28-2F` | `adds` | `adds` | `adds` | null |
| `0x30-37` | `sub` | `sub` | `sub` | null |
| `0x38-3F` | `subs` | `subs` | `subs` | null |
| `0x40-47` | `or` | `or` | `or` | null |
| `0x48-4F` | `bset` | `bset` | `orc` | null |
| `0x50-57` | `and` | `and` | `and` | null |
| `0x58-5F` | `bclr` | `bclr` | `andc` | null |
| `0x60-67` | `xor` | `xor` | `xor` | null |
| `0x68-6F` | `bnot` | `bnot` | `xorc` | null |
| `0x70-77` | `cmp_g` | `cmp_g` | `cmp_g` | null |
| `0x78-7F` | `btst` | `btst` | null | null |
| `0x80-87` | `mov_g` | `mov_g` | `mov_g` | `movfpe` |
| `0x88-8F` | `ldc` | `ldc` | `ldc` | null |
| `0x90-97` | `xch` | `mov_g` | null | `movtpe` |
| `0x98-9F` | `stc` | `stc` | null | null |
| `0xA0-A7` | `addx` | `addx` | `addx` | `dadd` |
| `0xA8-AF` | `mulxu` | `mulxu` | `mulxu` | null |
| `0xB0-B7` | `subx` | `subx` | `subx` | `dsub` |
| `0xB8-BF` | `divxu` | `divxu` | `divxu` | `scb` |
| `0xC0-C7` | `bset` (imm) | `bset` (imm) | null | `pjmp` |
| `0xC8-CF` | `bset` (imm) | `bset` (imm) | null | `pjsr` |
| `0xD0-D7` | `bclr` (imm) | `bclr` (imm) | null | `jmp` |
| `0xD8-DF` | `bclr` (imm) | `bclr` (imm) | null | `jsr` |
| `0xE0-E7` | `bnot` (imm) | `bnot` (imm) | null | `jmp` |
| `0xE8-EF` | `bnot` (imm) | `bnot` (imm) | null | `jsr` |
| `0xF0-F7` | `btst` (imm) | `btst` (imm) | null | `jmp` |
| `0xF8-FF` | `btst` (imm) | `btst` (imm) | null | `jsr` |

`bset`/`bclr`/`bnot`/`btst` at `0xC0+` take an **immediate bit number**
(`code & 15`) instead of a register operand (`ana.cpp` lines 535-544: `if (code
< 0xC0) opreg(...) else immv(code & 15)`) -- this is a real semantic fork inside
one mnemonic, not two different mnemonics; needs two constructors in
`h8539f-bit.sinc` (register form vs. immediate-bit form) sharing the display
name.

`ldc`/`stc`/`andc`/`orc`/`xorc` add `SR` to the register index (`insn.Op2.reg +=
SR`) and reject `RES1`/`CP` (lines 588-597) -- confirms old BUG 7's fix
(explicit valid `CR8` enumeration) was on the right track, though the exact
reject condition (`RES1 || CP`, plus a word/byte-vs-`SR` consistency check) is
more specific than "just those two indices" and should be re-expressed as a
guard matching this exact logic, not re-derived from scratch.

---

## Port status: literal (non-MAP) `mov` forms -- verified already correct, ported as-is

Checked each literal `mov` constructor in the current `h8\data\languages\h8539f.slaspec`
against this table's `A2tail` rows before assuming a rewrite was needed. All five
match the ground truth exactly, byte for byte:

| Form | Current constructor | Field constraint | Byte range | Matches table row |
|---|---|---|---|---|
| `mov:l.b`/`mov:l.w` | line 2232-2233 | `opcode=12`/`13` (`opcode`=bits(3,7)=byte>>3) | `0x60-67`/`0x68-6F` | `0x60-0x6F` `mov_l` |
| `mov:s.b`/`mov:s.w` | line 2239-2240 | `opcode=14`/`15` | `0x70-77`/`0x78-7F` | `0x70-0x7F` `mov_s` |
| `mov:e` | line 2129 | `mode=5 & sz=0` (`mode`=bits(4,7)=top nibble) | `0x50-57` | `0x50-0x57` `mov_e` |
| `mov:i` | line 2136 | `mode=5 & sz=1` | `0x58-5F` | `0x58-0x5F` `mov_i` |
| `mov:f.b`/`mov:f.w` (load) | line 2246-2247 | `opcode=16`/`17` | `0x80-87`/`0x88-8F` | `0x80-0x8F` `mov_f` |
| `mov:f.b`/`mov:f.w` (store) | line 2248-2249 | `opcode=18`/`19` | `0x90-97`/`0x98-9F` | `0x90-0x9F` `mov_f` |

**Conclusion:** the literal top-level dispatch was never the broken part of this
file -- confirms the refactor's diagnosis. Only the MAP3/4/5/6 second-byte
tables (`mov_g`/`ldc`/`stc`/`xch`/`movfpe`/`movtpe`, still `todo`) need real
rework. These five forms are ported into `h8539f-mem.sinc` unchanged (register
attach lists, `r6b_disp8`/`r6w_disp8` subtables, and flag-update logic carried
forward as-is).

**Status:** `mov:l`/`mov:s`/`mov:e`/`mov:i`/`mov:f`/`ldm`/`stm` = `ported and
compile-tested` (via sleigh.bat against an isolated scratch copy, July 2026 --
exit code 0, no errors; the `reglist!=0` guard closing the all-zero-reglist
gap versus `ana.cpp` also compiles clean, placed in the correct token clause
after two real placement mistakes were caught and fixed during testing --
see `h8539f-mem.sinc`'s header comments for both). Not yet tested against a
live ROM. `mov_g`/`ldc`/`stc`/`xch`/`movfpe`/`movtpe` = `todo`, still need the
MAP-table rework.

## SLEIGH lessons from compile-testing `h8539f-mem.sinc` (apply to every future `.sinc`)

1. **`@include` order matters.** SLEIGH requires a symbol (subtable, token
   field) to be declared before it's used. A `.sinc` file that references
   `r6b_disp8` or the `r*_push`/`r*_pop` subtables must be `@include`d
   *after* those are defined in the top-level file, not before. Caught this
   by compiling with the include placed too early -- got "No matching global
   symbol" errors, moved the include past the dependent definitions, error
   went away. Apply this when writing the real top-level `h8539f.slaspec`
   skeleton: work out the dependency order of the four functional `.sinc`
   files (and the shared subtables in the top file) before wiring up
   `@include`, don't just list them alphabetically.
2. **Multi-token patterns: constrain each field in the clause for its own
   token.** A pattern like `is opcode_special=0x12; reglist!=0 & ...` reads
   two tokens (`special` then `regListByte`), separated by `;`. A field
   belonging to the *second* token (`reglist`) must go in the *second*
   clause. Bundling it into the first clause with `opcode_special` (i.e.
   `is opcode_special=0x12 & reglist!=0;`) produces "Mismatched tokens when
   combining patterns" -- SLEIGH is trying to satisfy both fields from the
   same (first) token's bit width and failing. Worth checking for this
   pattern specifically in the MAP3/4/5/6 `.sinc` files, since those all
   have this exact two-token shape (prefix byte, then dispatch byte) and
   will need field constraints like `bset`/`bclr`'s register-vs-immediate
   fork placed in the right clause the same way.

## Design outline per remaining `.sinc` file (content + dependencies, not code)

Written against the ground-truth tables above so step 1's `@include` ordering
can be planned correctly before any of these files exist, without needing to
guess or pre-create empty stubs. Each file's dependency list should be
double-checked against what actually gets written -- this is a plan, not a
guarantee -- but it's a much better starting point than discovering
dependencies one compile error at a time.

### `h8539f-mem.sinc` (remaining MAP-derived work, not yet written)
- **Instructions:** `mov_g` (MAP3/4/5 tail `0x80-87`, MAP6 tail `0x80-87`
  separately = `movfpe`), `ldc` (MAP3/4/5 tail `0x88-8F`), `xch` (MAP3 tail
  `0x90-97` only), `stc` (MAP3/4 tail `0x98-9F`), `movtpe` (MAP6 tail
  `0x90-97`).
- **Dependencies:** `CR8` register attach (already exists in top file, needs
  the `RES1`/`CP` rejection guard re-applied per `ana.cpp` lines 588-597),
  `SR` register offset arithmetic for `ldc`/`stc`, whatever `eab_*`/`eaw_*`
  addressing subtable covers `Op1`'s EA shape for the tail-table range (`Rn`/
  `@-Rn`/`@Rn+`/`@Rn`/`@(d:8,Rn)`/`@(d:16,Rn)`, per the structural fact about
  the switch at `ana.cpp` lines 441-476) -- these already exist in the top
  file per the "Port status" section above, just need referencing here too.
- **Two-token shape:** `eab_*`/`eaw_*` as the byte-1 EA gate, `opcode`/`Rd`/`CR8`
  as the byte-2 dispatch byte (8-wide tail group + low-3-bits register) --
  apply SLEIGH lesson 2.

### `h8539f-arith.sinc` (not yet written)
- **Instructions:** `add_g`/`adds`/`sub`/`subs`/`addx`/`subx`/`mulxu`/`divxu`
  (MAP3/4/5 tail groups `0x20-3F`/`0xA0-BF`), `cmp_g`/`cmp_g`(imm, `A4` head
  `0x04-05`)/`btst` (tail `0x70-7F`, register form)/`btst`(imm, tail
  `0xF0-FF`), plus head-table `neg`/`clr`/`tst`/`tas`/`swap`/`exts`/`extu`/
  `shal`/`shar`/`shll`/`shlr`/`rotl`/`rotr`/`rotxl`/`rotxr` (MAP3/4 head
  `0x10-1F`, MAP4 missing `0x10-12`).
- **Dependencies:** same `eab_*`/`eaw_*` addressing subtables as `mem.sinc`
  (this axis is shared across every MAP-tail instruction, not
  category-specific -- both files reference the same subtables, which is
  fine, SLEIGH subtables can be referenced from multiple `.sinc` files once
  `@include`d).
- **Watch:** `A4` head `0x04-07` divergence (`cmp_g`/`mov_g` imm8/imm16, not
  null like `A3`/`A5`/`A6`) -- found during table verification pass 2, easy
  to silently drop if not written against this table directly.
- **Two-token shape:** same as `mem.sinc` -- apply SLEIGH lesson 2, likely
  reuse whatever pattern shape gets settled there.

### `h8539f-logic.sinc` (split out of arith.sinc's original scope, July 2026 -- not yet scratch-tested)
- **Instructions:** `or`/`and`/`xor` (register tail-group forms, MAP3/4/5 tail
  `0x40-47`/`0x50-57`/`0x60-67`) and `andc`/`orc`/`xorc` (control-register
  `imm8`/`imm16` forms sharing the `ldc`/`stc` CR8 gate, tail `0x48-4F`/
  `0x58-5F`/`0x68-6F` -- but only the odd/half of each pair not already
  claimed by `bset`/`bclr`/`bnot`, per the table's tail-table grid).
- **Status:** all six already exist in the pre-split `h8539f.slaspec`
  (grepped and confirmed present July 2026: `and.b`/`and.w` at `opcode=10`,
  `or.b`/`or.w` at `opcode=8`, `xor.b`/`xor.w` at `opcode=12`, `andc`/`orc`/
  `xorc` at `opcode=11`/`9`/`13` gated with `CR8`/`CR16`, matching the
  table's tail-group bytes exactly) -- same "already correct, just needs
  relocating" story as `mov_g`/`add_g`/etc. in `mem.sinc`/`arith.sinc`. Not
  yet scratch-compiled in isolation as this file; do that before treating
  the relocation as done, per the project's standing rule (see `mem.sinc`'s
  compile-testing note) that nothing counts as ported until it's actually
  been run through `sleigh.bat` on its own.
- **Dependencies:** same `eab_*`/`eaw_*` addressing subtables as
  `mem.sinc`/`arith.sinc` for the register forms; `CR8`/`CR16` register
  attach (already exists, shared with `ldc`/`stc`) for the `andc`/`orc`/
  `xorc` control-register forms, including the same `RES1`/`CP` rejection
  guard those need.
- **Why split from `arith.sinc`:** flagged as an open question in
  `arith.sinc`'s own header rather than silently folded into either
  neighbor -- these are full-width boolean logic ops, not arithmetic
  (`add`/`sub`/`mul`/`div`, `arith.sinc`'s actual scope) and not single-bit
  ops (`bset`/`bclr`/`bnot`/`btst`, `bit.sinc`'s actual scope). Resolved as
  its own file rather than picking one of the two by default.
- **Two-token shape:** same as `arith.sinc`/`mem.sinc` -- prefix byte then
  dispatch byte, apply SLEIGH lesson 2 for the `CR8`/`CR16` clause exactly
  as `ldc`/`stc` already do.

### `h8539f-bit.sinc` (not yet written)
- **Instructions:** `bset`/`bclr`/`bnot` (MAP3/4 tail `0x40-6F` register form
  + `0xC0-EF` immediate-bit form), `btst` handled in `arith.sinc` instead
  (grouped with `cmp_g` there per `ana.cpp`'s tail-table layout, not with the
  other three bit ops -- worth double-checking this grouping choice once
  actually writing the file; `ana.cpp` doesn't itself categorize
  functionally, this project's `mem`/`arith`/`bit`/`branch` split is our own
  choice per the H8/300 model, so it's fine to move `btst` here instead if
  it reads more naturally next to `bset`/`bclr`/`bnot` when the code is
  actually in front of you).
- **Dependencies:** register attach for the tail-table low-3-bits operand
  (register form only, `code < 0xC0`), immediate bit-number field (`code &
  15`) for the `0xC0+` form -- this needs a new field declaration, doesn't
  exist in the current top file under this name, check `ana.cpp` lines
  535-544 for the exact split logic before writing.
- **Two-token shape:** same as above, but this file is the one that most
  directly exercises SLEIGH lesson 2 -- deliberately test the
  register-vs-immediate fork placement here first before assuming it's
  settled from `mem`/`arith`.

### `h8539f-branch.sinc` (not yet written, blocked on the open question above)
- **Instructions:** `bra`/16 condition codes (`A2` `0x20-3F`, literal, no MAP
  involvement -- lowest-risk part of this file), `bcc`... wait, condition
  codes already covers this; `bsr`/`jmp`/`jsr`/`pjmp`/`pjsr`/`rts`/`rtd`/
  `trapa`/`trap/vs`/`rte`/`bpt`/`sleep`/`link`/`unlk` (all `A2` literal,
  `0x00-1F` range, no MAP -- also low-risk, mechanical port from the current
  file once checked the same way `mem.sinc`'s literal forms were), `scb`/
  `prts`/`prtd`/`pjmp`/`pjsr`/`jmp`/`jsr`/`dadd`/`dsub` (MAP6-derived, the
  actually-new work, blocked on the open question).
- **Dependencies:** `CP` far-jump target folding (relevant to `CP_ctx` item
  #7 in the main to-do, semantics only, doesn't block dispatch), disp8/disp16
  tokens (already exist).
- **Recommendation:** split this file's own work into two waves when writing
  it -- port the literal `0x00-1F` instructions first (same
  verify-before-rewrite approach as `mem.sinc`, likely low effort since nothing
  in the "why" section suggested these were broken), then tackle the MAP6
  instructions once the open question is resolved, rather than blocking the
  whole file on one unresolved byte.


## Open questions to resolve before coding (live-ROM checks needed)

1. `rtd` byte reconciliation (old BUG 3 claimed `0x04`/`0x0C` as the `rtd`
   bytes). Resolved on re-read, no live check needed: `A2[0x14]`/`A2[0x1C]` are
   the real top-level `rtd` entries (imm8/imm16 respectively); `A2[0x04]`/
   `A2[0x0C]` are unrelated MAP5 entry points (imm8/imm16 *payload*, not the
   `rtd` operand itself -- see the corrected top-level table row above). Old
   BUG 3's byte pair was wrong; `0x14`/`0x1C` is correct. No longer an open
   question -- kept here only as a record that it was checked.
2. Which literal path actually reaches MAP6's `default` case
   (`movfpe`/`movtpe`/`dadd`/`dsub`) -- doesn't obviously match any of the 4
   `A2`-level MAP6 entries; likely the MAP3/MAP4-chained `0x00`-second-byte MAP6
   entry, needs a live ROM instance to confirm. **Still open -- the only thing
   blocking `branch.sinc`.**

## Next steps

See the README's "To-do (current)" section under "Refactor plan" for the full
ordered plan -- this table is the ground-truth reference it's written
against, not a duplicate task list. Short version: stand up the real
top-level `h8539f.slaspec` next (with `@include` ordering worked out per the
"SLEIGH lessons" section above), then write `mem.sinc`'s remaining MAP-derived
entries per the "Design outline" section above, recompile + regression test,
then `arith` -> `bit` -> `branch` in that order.
