# Changelog

All notable changes to the Ghidra H8/500 Processor Module are recorded here.

---

## [Unreleased]

### Fixed — `h8539f.slaspec`: MAP4 load/store forms missing (BUG 4b)

Added 34 missing MAP4 second-byte constructors for the `mov:g` load
(`EA -> Rn`, second byte `0x80-0x8F`) and store (`Rn -> EA`, second byte
`0x90-0x9F`) forms, in both byte and word sizes, across all EA addressing
sub-modes (`direct`, `indirect`, `disp8`, `disp16`, `predec`, `postinc`,
`abs8_br`, `abs16`, plus `imm8`/`imm16` for the load form).

These were documented in the existing header comment (`0x8X = mov:g load
EA -> Rn`, `0x9X = mov:g store Rn -> EA`) but never implemented — only the
three immediate-to-register forms (`m4op=0`, `m4op=1`) existed. Any MAP4
first byte (`0xB0-0xFF`, now correctly gated by `map4_page` per BUG 4a)
followed by a second byte in `0x80-0x9F` failed to resolve a constructor.

Verified: `0x20663` now decodes as `mov:g.w #0xe15:16,R2`; `0x14df6` now
decodes as `mov:g.b #0x4:8,FP`. `Unable to resolve constructor` errors at
both addresses no longer appear after recompile and forced re-disassembly.

Not yet fixed by this change: MAP4 second bytes `0x80-0x8F` are correctly
handled, but first bytes in the `0x80-0x8F` range belong to **MAP3**
(separate gate, BUG 5, not yet implemented) — e.g. `0x14bce` (`?? 88h`)
remains broken and is MAP3, not MAP4.

---

### Fixed — `h8539f.slaspec`: CR8/CR16 invalid-index varnode error (BUG 7)

Removed 9 bare `ldc.w EA,CR16` fallback constructors (all forms: `eaw_direct`,
`eaw_indirect`, `eaw_disp8`, `eaw_disp16`, `eaw_predec`, `eaw_postinc`,
`eaw_abs8_br`, `eaw_abs16`, `eaw_imm16`) that used an unguarded `CR16` attach
operand with no index constraint.

The `CR16` attach table is `[ SR _ _ _ _ _ _ _ ]` — only index 0 (`SR`) is
valid. All other indices map to `_` (a hole), producing a
`Failed to resolve varnode <CR8>, index=2` error at runtime whenever a byte
sequence decoded a non-zero CR16 index. IDA's `ana.cpp` guards against this
explicitly; the slaspec had no equivalent guard.

All `ldc.w EA,"SR"` forms were already fully covered by the explicit
`opcode=17 & CR16=0` constructors above. The fallbacks were redundant and
harmful. Removed rather than patched with `CR16=0` to avoid duplicate
constructor conflicts.

The `stc.w CR16` and `andc/orc/xorc CR16` bare fallbacks had already been
removed in a prior session. This change completes the BUG 7 fix across all
affected instruction groups (`stc`, `ldc`, `andc`, `orc`, `xorc`).

Verified: `Failed to resolve varnode` error at `0x14e31` no longer appears
after recompile and Ghidra restart.

---

### Fixed — `h8539f.slaspec`: `sleep` and `rtd` opcode corrections (BUGs 2 & 3)

#### `sleep` bound to wrong opcode (`0x2C` → `0x1A`)

`sleep` was assigned `opcode_special=0x2C`, which is the `bhi`/`bls`/... branch group
in the `A2` table. The correct opcode per `ana.cpp` line 24 is `A2[0x1A] = H8500_sleep`.
Fixed to `opcode_special=0x1A`. Eliminates `?? 1Ah` errors at `0x12170`, `0x12171`,
`0x12173`, and other locations.

#### `rtd` s8/s16 bound to wrong opcodes (`0x30`/`0x34` → `0x04`/`0x0C`)

`rtd s8` was using `opcode_special=0x30` (`bra:16`) and `rtd s16` was using
`opcode_special=0x34` (`bcc:16`), leaving the real `rtd` opcodes `0x04` and `0x0C`
unrecognised and causing false constructor conflicts on branch instructions. Corrected
per `ana.cpp` switch cases (lines 347–366):

- `rtd s8`  → `opcode_special=0x04`  (was `0x30`)
- `rtd s16` → `opcode_special=0x0C`  (was `0x34`)

Inline comments added at the fix sites documenting the old (wrong) values and why they
were wrong. Eliminates `?? 0Ch` at `0x24d24`, `?? 1Ch` at `0x12175`, and the `prtd`
cascade at `0x12170`.

Note: the `bra:16` / `rtd s8` opcode collision at `0x30` is a pre-existing ISA-level
ambiguity between the 16-bit-displacement `bra` encoding and `rtd`'s 8-bit-displacement
encoding. This cannot be resolved without understanding how IDA/real hardware disambiguates
on a later byte. Left as a known limitation — see README BUG 3 note.

---

### Fixed — `h8539f.slaspec`: Multiple bad-instruction decode failures

A comprehensive rework of the SLEIGH instruction set to resolve several categories of
`Unable to resolve constructor` / `?? xxh` bad-instruction errors observed across ECU ROMs.

#### MAP4 dispatch (`?? EEh` — opcode prefix `0xE0`–`0xEF`)

The MAP4 opcode range routes to immediate-to-register `mov:g` forms via a second byte.
There was no `map4b` token or constructors for this prefix — the entire range was
unrecognised. Added a new `map4b` token (`m4op`, `m4sz`, `m4Rn` fields) and three new
constructors:

- `mov:"g.b" #imm8, Rn` — m4op=0, m4sz=0 (covers the failing `EE 06 04` → `mov:g.b #0x4, R6` case)
- `mov:"g.w" #imm8 (sign-extended), Rn` — m4op=0, m4sz=1
- `mov:"g.w" #imm16, Rn` — m4op=1, m4sz=0

#### `cmp:g` cross-EA constructors (`?? DCh`)

`cmp:g` (opcode_special=4/5) was missing constructors for mixed EA/immediate widths.
Byte `0xDC` selects a word-indirect EA (`@R4`), but a byte-immediate second byte is a
valid H8 encoding per IDA SDK `ana.cpp`. Added:

- `cmp:"g.b" i8, eaw_*` (all word EAs) — opcode_special=4, zero-extends `i8` to word
- `cmp:"g.w" i16, eab_*` (all byte EAs) — opcode_special=5, symmetric counterpart

#### `bra` unconditional branch spurious fallthrough

The generic `cc` table returned `1:1` for `cond=0` (branch-always), producing
`if (1) goto target` pcode — a conditional-goto shape that keeps a phantom fallthrough
edge. Split `bra` out with a `cond=0` constraint to emit a bare `goto reloffs8` with no
condition, eliminating the spurious edge. The 16-bit displacement form (`bra:16`) shares
opcode `0x30` with `rtd s8` — an ISA-level ambiguity, left as a known limitation.

> **SLEIGH modelling note.** The hardware is unambiguous — `bra` never falls through.
> The split is a workaround for SLEIGH's `cc` table not distinguishing conditional from
> unconditional branch shape; it correctly represents the silicon behaviour.

#### `pjmp` / `pjsr` indirect dereference fix

Both instructions previously used `absaddr24` which exports `*[const]:4 addr24` — a
dereference of the address constant rather than a direct call to it. This caused Ghidra
to render targets as `DAT_0000xxxx` pointer loads instead of clean code labels. Fixed
by computing `addr:4 = zext(addr24:3)` and using `goto [addr]` / `call [addr]` directly,
consistent with all other jmp/jsr constructors in the file.

#### `prts` two-byte encoding

`prts` (far return) was matched on `opcode_special=0x19` alone — identical to `rts`
(near return), making the two indistinguishable. Corrected to the proper two-byte
sequence `0x11 0x19`.

#### `prtd` far return-and-deallocate (s8 and s16 forms)

Both forms were missing entirely. Added constructors for `prtd s8` (prefix `0x11 0x14`)
and `prtd s16` (prefix `0x11 0x1C`), each popping CP and PC then adjusting SP by the
signed immediate.

#### Register layout: `PC16` removed, `FPH` added

`PC16` was a dead definition (offset `0x81`, mid-parent inside `PC` at `0x80 size=4`)
never referenced anywhere in the slaspec. Suspected cause of
`encodeTranslator(): Marshaling error: syntax error` in `DecompInterface.openProgram()`.
Removed. Added `FPH` at offset `0x4C` to support `orc/andc/xorc TP` side-effects
propagating into the frame pointer high byte.

> **SLEIGH modelling note.** The `PC16` removal is a workaround for a SLEIGH serialisation
> constraint — SLEIGH does not permit a named sub-register at a misaligned offset within a
> 4-byte parent. The removal was not driven by the hardware spec (the H8/500 does have a
> 16-bit PC view), but it was a dead definition with no references, so removing it has no
> effect on disassembly or decompilation correctness. `FPH` is architecturally correct —
> the high byte of FP is genuinely modified by `orc/andc/xorc TP` on the silicon.

### Added — `test/h8539_ecu_master_setup.py` (replaces `ecu_full_setup.py`)

Complete rewrite of the ECU setup script as a single all-in-one file with an
interactive GUI. Each of the 8 steps is individually toggleable via Ghidra's
built-in `askYesNo` / `askFile` dialogs -- no need to edit variables before running.

**Step 1 — Base address validation** (always runs)
Checks that a ROM block exists at `0x00010000`. Aborts with a clear message if the
ROM was imported at the wrong address.

**Step 2 — On-chip RAM block**
Creates an uninitialised volatile RAM block at `0xEE80–0xFFFF` (4480 bytes).
Skips silently if the block already exists, so it is safe to re-run.

**Step 3 — CP/DP/TP context registers**
Sets page-context registers over both ROM pages so the SLEIGH disassembler resolves
far calls correctly: CP=1 over page 1, CP=2 over page 2, DP=1 and TP=0 over the
full ROM range.

**Step 4 — Reset vector / entry function**
Reads the CP and PC words at `ROM_BASE`, computes the flat 32-bit entry address, pins
the CP register at that point, disassembles from it, and creates the `entry` function.

**Step 5 — Decompiler health check** (always runs, gates Step 6)
Opens the decompiler interface and verifies it initialises cleanly against the current
program. Aborts before auto-analysis if the decompiler is broken, saving time on a
failed run.

**Step 6 — Auto-analysis**
Calls `analyzeAll()`. Reports the function count on completion.

**Step 7 — EcuFlash XML table labelling**
Prompts for an XML file via a native file-browser dialog. Before applying any labels
the script reads `<internalidaddress>` and `<internalidhex>` from the XML and compares
them against the actual ROM bytes -- a mismatch skips labelling with a clear warning
rather than silently applying wrong labels.

Label placement:
- 2D tables: labeled at `xml_addr - 4` (header address, where code xrefs point)
- 3D tables: labeled at `xml_addr - 7`
- 1D scalars: labeled at `xml_addr` directly (no ROM header exists)

Plate comments record table name, category, type, scaling, and both header and data
addresses. `<include>` chains are followed recursively with cycle detection.

If no XML is chosen the script immediately offers to run the ROM scraper as a fallback.

**Step 8 — ROM header scraper**
Four separate passes:

- **8a MUT table** -- 256 × 2-byte RAM pointer entries at fixed offset `0x1FAD0`.
  Labels each entry in ROM and the corresponding RAM variable.
- **8b Scaling tables** -- 6-byte header pattern `[F0-F7] xx [E0-FE] xx 00 [02-90]`.
  Sanity-checks the first three data words (max delta 0x1000). Labels output and
  input RAM pointers.
- **8c 3D value tables** -- 7-byte header `0x03 | pad | X-ptr (word) | Y-ptr (word) | nrows`.
  Sanity-checks first three data words (max delta 0x4000). Labels X/Y axis RAM
  variables and advances the scan past the detected data block.
- **8c 2D value tables** -- 4-byte header `0x02 | pad | axis-ptr (word)`.
  Same sanity check and scan-advance logic.

All passes use `getPrimarySymbol()` for existence checks (avoids the deprecated
`hasNext` iterator bug). Existing labels are never overwritten; plate comments are
append-only and deduplicated.

### Changed

- Script renamed from `ecu_full_setup.py` to `h8539_ecu_master_setup.py`.
- XML path is no longer a hardcoded variable at the top of the file -- it is now
  selected at runtime via `askFile()`.
- ROM ID verification added to Step 7; previously labels were applied without checking
  whether the XML matched the loaded ROM.
- Table labels now target the **header address** (`xml_addr - header_size`) rather than
  the raw XML data address, aligning labels with code cross-references.
- 1D scalars correctly labeled at `xml_addr` directly (no header offset applied).

---

## Earlier history

Initial H8/539F language core, pspec, cspec, and slaspec work -- see git log.
