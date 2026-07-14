# Changelog

All notable changes to the Ghidra H8/500 Processor Module are recorded here.

---
### fixed the badspace error in c output

The compiler did not track the stack variables properly so the c output was
filled wits offsets and pointers in stead of proper variables.
This is a big plus for C code output it looks much better.

### Fixed — stale "scraper only scans page 1" comments in `h8539_ecu_master_setup_new.py`

`MUT_OFFSET` (0x1FAD0) is a CPU offset from `ROM_BASE`, not an absolute address, so the
scraper's `0x0..MUT_OFFSET` scan loops (`protect_data_regions_early()` in Step 5b and
`run_rom_scraper()` in Step 8) actually run from absolute 0x10000 to ~0x2FACA — essentially
the entire ROM, covering all of page 1 and nearly all of page 2, stopping only ~0x530 bytes
short of the MUT table itself (absolute 0x2FAD0). There is no real page-2 scan gap; the
"page 1 only" comments (~949-956, ~1177-1179, ~1533-1549) and the Step 8d print message were
stale leftovers, corrected to describe the actual scan range. If page-2 tables still turn up
unlabeled, the cause is a byte-signature mismatch, not an unreached region. review.md's item 2
has been updated to drop this as a resolved item; the README's matching "page 1 only" wording
still needs a separate check.
## [Unreleased]

### Added — `H8FunctionPurgeAnalyzer`: stack-purge-size analyzer for `prtd`/`rtd`

Added a Ghidra `Analyzer` (`h8/data/src/main/java/h8539f/H8FunctionPurgeAnalyzer.java`,
package `h8539f`) that reads the stack-adjustment immediate off `prtd`/`rtd` return
instructions and sets the containing function's `stackPurgeSize` accordingly, modelled on
Ghidra's own `X86FunctionPurgeAnalyzer`. Resolves the correctness gap noted in review.md
(functions using `prtd #n`/`rtd #n` to clean caller-pushed arguments would otherwise show
wrong stack depth in decompiler output). Runs as a `FUNCTION_ANALYZER`-type pass gated to
after `FUNCTION_ANALYSIS`; logs a warning instead of silently overwriting if a function has
multiple return sites with conflicting purge values.

Compiled and packaged manually against the installed Ghidra 12.0.4 jars (no Gradle
available in this environment) as `h8539f-analyzers.jar`, dropped into
`Ghidra\Processors\h8\lib\`; `extension.properties` added to the module. Confirmed loaded
via `ClassSearcher.getInstances(Analyzer.class)` (headless) and confirmed present/enabled
in the Auto Analysis options dialog and analyzer timing report (`H8 Function Purge
Analyzer   0.136 secs`) after a full Ghidra restart.

**Not yet confirmed against a real in-ROM case.** Searched the disassembled listing of
`RVR_1998_x3 4g63t 21000011 md352553.hex` directly (`getMnemonicString()` walk, not a raw
byte-pattern search — an initial `11 14` byte search returned six hits that turned out to
be either undefined bytes or a `mov` operand coincidence, not real opcodes) and found zero
`prtd`/`rtd` instructions currently disassembled anywhere in this ROM; every return seen so
far uses plain `rts`/`prts` with caller-side `adds SP,#n` cleanup instead. The six
candidate `11 14` byte sequences all sit in the undiscovered low-memory region below the
lowest defined function (`0x14000`), with zero xrefs — the same region already tracked as
open in review.md items 3/4 (unverified jump tables / Step 5d classification design). Grammar
and analyzer are compile-sound, derivation-confirmed, and verified functionally correct on
their own terms, but whether this ROM's compiler ever actually emits `prtd`/`rtd` (and thus
whether this analyzer changes anything in practice) remains unresolved pending that region
being disassembled/classified.

### Verified — CR8 RES1/CP rejection guard for MAP5 andc/orc/xorc (h8539f-logic.sinc)

The TP/BR/EP/DP immediate forms of `andc`/`orc`/`xorc` were flagged as not yet carrying
the RES1/CP rejection guard that `ldc`/`stc`/`andc`/`orc`/`xorc` are all supposed to share
per `ana.cpp` lines 588-597 (`if (insn.Op2.reg == RES1 || insn.Op2.reg == CP) return 0;`).
Investigation found the guard was already in place implicitly: the register enum order is
`SR, CCR, RES1, BR, EP, DP, CP, TP`, and this file's `andc`/`orc`/`xorc` constructors only
ever match `CR8=1` (CCR), `CR8=3` (BR), `CR8=4` (EP), `CR8=5` (DP), or `CR8=7` (TP) — there
is no `CR8=2` (RES1) or `CR8=6` (CP) constructor anywhere, so those two encodings simply
fail to decode, the Sleigh equivalent of ana.cpp's `return 0`. A project-wide grep for
unconstrained `& CR8` usage (no explicit value) returned zero matches, ruling out a stray
wildcard/catch-all that could accidentally accept RES1/CP. This is the same mechanism
already used (and already credited as correct) by `ldc`/`stc`'s EA-sourced forms and is
consistent with the CR8 attach table's own `_` placeholders at indices 0/2/6. Re-compiled
full-project via `sleigh.bat` after updating the file's comment to reflect this: exit 0, no
new warnings/errors. No functional code change was needed — this was a documentation gap,
not a grammar gap.

### Verified — MAP5 escape forms compile cleanly (h8539f-arith.sinc, h8539f-logic.sinc, h8539f-mem.sinc)

The MAP5 (0x04/0x0C top-level literal-escape) forms added for `add:g`/`adds`/`sub`/`subs`/
`cmp:g`/`addx`/`mulxu`/`subx`/`divxu` (arith), `or`/`and`/`xor`/`andc`/`orc`/`xorc` (logic),
and `mov:g`/`ldc` (mem) had been written and cross-checked against `ana.cpp`'s A5/A5tail
derivation but were flagged in each file as untested against the real Sleigh compiler.
Ran a full-project compile via `sleigh.bat` against `h8539f.slaspec` (which `@include`s all
five `.sinc` files): exit code 0, zero ERROR lines. All WARN lines present (24 NOP
constructors, size-0 `reloffs8`/`reloffs16` tables, 40 extension/truncation-to-copy
conversions, ~19 unreferenced tables) are the same pre-existing/expected warnings noted in
prior compiles — none touch the MAP5 constructors. Confirms the MAP5 grammar is
syntactically sound and free of dispatch collisions with the rest of the project.
Note: this verifies compile-soundness only, not hardware-behavior correctness — semantic
verification against `ana.cpp`/the hardware manual (and live-ROM testing where encodings
exist) remains open, tracked alongside the CR8 RES1/CP guard item in review.md.

### Fixed — `cmp:"g.w"` mislabeled as `cmp:"g.b"` (h8539f-arith.sinc)

Two instances of the word-sized compare-immediate constructor (16-bit `i16` operand,
`eaw_imm16` word EA, `opcode_special=0x05`/`0x0C`) were mnemonic-tagged `"g.b"` instead
of `"g.w"` — a copy-paste artifact from the byte-sized block above each one. Disassembled
with the wrong size suffix. Fixed both instances (line ~445 and a second, previously
undocumented instance at line ~855). Compile-verified via full-project `sleigh.bat`
(exit 0, no errors).

### Added — `bnot.b`/`bnot.w Rs,<EAd>` register-source form (h8539f-bit.sinc)

`bset`/`bclr` both had register-bit-position and immediate-bit forms; `bnot` was missing
its register-source form entirely (`opcode=13`, tail-array index 9, byte range
`0x68-0x6F`) — confirmed via `ana.cpp`'s dispatch math, the project's own
instruction-table grid, and the H8/500 hardware manual (sec 2.2.8, documents both
`BNOT #xx,<EAd>` and `BNOT Rs,<EAd>` formats). Added all 8 EA modes x 2 sizes (16
constructors). Compile-verified (exit 0, no new warnings) and live-ROM re-analysis run
against `RVR_1998_x3 4g63t 21000011 md352553.hex` produced no new Bad Instruction
bookmarks. Note: this ROM contains zero live instances of the register-source encoding
to test against (7 `bnot` instructions present, all pre-existing immediate-bit form) —
grammar is compile-sound and derivation-confirmed, but not yet confirmed against a real
in-ROM encoding.

### Fixed — `switchD_00028b50::caseD_4` stale label causing orphaned function split

`FUN_00028b2f` was reported as spanning `0x20640-0x2ffff` due to a stale/orphaned
Ghidra-generated jump-table case label incorrectly attaching a distant 6-byte fragment
(`0x20640`) to the switch's owning function. Investigation (session 4) proved the label
was stale: none of the switch's real 8 table entries (read directly from the EP-relative
table at `0x28b52`) land anywhere near `0x20640`, and `get_xrefs_to(0x20640)` returns
zero references. Deleted and recreated `FUN_00028b2f` as a clean 35-byte body. The
orphaned fragment at `0x20640` was given its own placeholder function
(`sci1_boot_switch_case4_frag_20640`) pending identification of what (if anything)
actually reaches it — not yet resolved, tracked as an open low-priority item.

### Fixed — `flash_write_or_verify` truncated function body

Function body was truncated to 4 bytes (`0x20844-0x20847`, prologue only); the
`mov:g.w` tail at `0x20848` (the `0x1D` literal-prefix-escape encoding) disassembled
cleanly on its own but wasn't included in the function. Deleted and recreated with
`disassemble_first` — body now correctly spans the full 68 bytes (`0x20844-0x20887`),
ending in a clean `rts`. Closed a 64-byte orphaned-instruction gap
(`find_code_gaps` count dropped 83 → 82).

### Resolved — three stale "Bad Instruction" / analysis-noise bookmarks

- `0x2da69-0x2da6b` ("unable to resolve constructor" / conflicting data at `0x2da6c`):
  resolved on its own once jump-table fixups settled; not separately root-caused.
- `0x20353` ("address out of bounds"): traced to a post-flash checksum-verify loop
  (`0x20345-0x2035f`) whose range bounds (R4/R5) and bank (EP) are loaded from RAM at
  runtime from `sci1_boot_ihex_data_byte_store`, not compile-time constants — the
  static analyzer's speculative resolution of the indirect target is expected to land
  outside the mapped ROM range. Confirmed the H8/500 bank-register pairing (`R4-R5` via
  EP) is correctly implemented in `Rn_banked`, not a grammar gap. Documented with an EOL
  comment at `0x20353`; bookmark cleared (11 → 10 remaining).
- `0x2f1b6` / `0x2e7af` ("maximum run of repeated byte instructions exceeded"): confirmed
  benign ROM padding/unused flash space, same category as the `0x20353` resolution.

### Retracted — `0x20843`/`0x20640` "confirmed live jump-table overlap" claim

Prior sessions concluded `0x20843` was a genuine live entry point via
`switchD_00028b50::caseD_4`. Re-traced properly in session 4: the switch's real 8 case
targets (read directly from ROM) all land next to the switch itself; none near `0x20640`.
Zero xrefs to `0x20640`. A binary-wide search for the address's low word inside any of
the 7 known jump/address tables found no matches. Conclusion: the label was stale
Ghidra metadata from an earlier incorrect analysis pass, not a real relationship. Left
the function in place (bytes decode as real, deliberate-looking instructions, not
padding) but downgraded from "confirmed live" to "currently unreached" pending further
investigation into what, if anything, reaches `0x20640`.


### fixed jump call function.

 Both :pjmp and :pjsr's @aa:24 forms now compute a local addr:4 = zext(addr24:3) from the raw address token and use goto [addr] / call [addr] — matching every other jump/call constructor in the file

### Fixed — `h8538f.pspec`: missing data space, wrong RAM block, no peripheral registers

Three issues fixed, bringing the H8/538F pspec up to the same standard as H8/520 and
H8/539F:

- Added the missing `<data_space space="ram" />` declaration.
- Corrected the on-chip RAM block: was `initialized="true"` at `0x0000` spanning
  `0xF000` bytes (code space, not RAM). Per the H8/538-539 hardware manual, the H8/538
  has 2KB of on-chip RAM at `0xF680-0xFE7F`. Fixed to `start_address="ram:0xF680"
  length="0x800" mode="rwv" initialized="false"`.
- Ported the full on-chip peripheral register map (SCI1/2/3, ports, A/D converter,
  timers 1-7, interrupt controller, DTC, WDT, multiplier, PWM, system/bus control --
  ~190 symbols) from `h8539f.pspec`, since the H8/538 shares the same peripheral set at
  the same I/O addresses. Excluded the flash memory control registers (`FLMCR`,
  `FLM_EBR1`, `FLM_EBR2`, `FLMER`, `FLMSR`), which are 539F-specific since the H8/538
  uses EPROM/masked ROM rather than flash.

---

### Fixed — `h8520.pspec`: vector table collision and missing RAM block

`ADC_ADI_vector` and `SCI1_ERI_vector` were both mapped to `ram:0x00D0`. Cross-checked
against the H8/520 hardware manual (Table 5-2, "Interrupts, Vectors, and Priorities"):
each on-chip module reserves 4 vector slots in the exception vector table regardless of
how many interrupt sources it uses, and the A/D converter's ADI vector falls in the slot
at `0x00F0` in maximum mode, not `0x00D0`. `SCI1_ERI_vector` at `0x00D0` was already
correct. `ADC_ADI_vector` corrected to `ram:0x00F0`.

Also uncommented and fixed `<default_memory_blocks>`, which was present but disabled and
pointed at the wrong addresses/sizes. Now defines the correct 512-byte on-chip RAM block
at `ram:0xFD80–0xFF7F` per the manual's memory map, so a fresh H8/520 ROM import gets its
RAM block created automatically instead of requiring manual setup.

---

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
