# Hitachi H8/500 Processor Module for Ghidra

A Ghidra processor module for the Hitachi H8/500 family, with full support for the
**H8/539F** as used in Mitsubishi ECUs (RVR X3, Evo5, etc.).

> **Current status (July 2026): top-level cutover is DONE; `MOV:G` gap is**
> **FIXED and compile-verified, install/live-ROM re-test still pending.**
> `h8539f.slaspec` is 1,338 lines -- the smaller size is expected, not a
> regression: every instruction constructor has been moved out into the five
> functional `.sinc` files (`h8539f-mem.sinc`, `h8539f-arith.sinc`,
> `h8539f-logic.sinc`, `h8539f-bit.sinc`, `h8539f-branch.sinc`), all wired in
> via real `@include` lines at the bottom of `h8539f.slaspec`. Backups of the
> pre/post-cutover state exist alongside the live file for reference
> (`h8539f.slaspec.pre_cutover_backup_20260706_061122` and
> `...post_cutover_backup_20260706_061122`) -- useful for diffing what moved
> where, not something to build against.
>
> **`MOV:G` fix (July 2026, this session): DONE, scratch-compiled clean --**
> **install + live-ROM confirmation still outstanding.** The entire `MOV:G`
> (general EA-sourced `mov`) constructor family had been silently dropped
> during the cutover and was never carried into `h8539f-mem.sinc` -- this was
> the actual root cause of the "Unable to resolve constructor" disassembly
> failures at ROM addresses `0x20027` and `0x20a86` (byte `0xCC` at `0x20027`
> is `eaw_postinc`, needing the `mov:"g.w" eaw_postinc,Rd is eaw_postinc;
> opcode=16 & Rd` constructor, which simply didn't exist anywhere live). A
> previous session had wrongly diagnosed this as a stale Ghidra install (see
> "superseded diagnosis" note below) -- that refresh was harmless but never
> actually fixed the bug, since the missing code was absent from the live
> file, not just the installed one.
>
> **What was fixed:** all three missing `MOV:G` blocks --
> `MOV:G <EAs>,Rd` (load), `MOV:G Rs,<EAd>` (store), and `MOV:G #xx,<EAd>`
> (immediate-to-EA) -- were ported verbatim from
> `h8539f.slaspec.pre_cutover_backup_20260706_061122` (lines 669-754) into
> `h8539f-mem.sinc`, placed next to the existing MAP5-immediate `mov:"g"`
> forms. The two `# DEAD (removed July 2026)` comment lines that used to sit
> between these blocks (`eab_imm8`/`eaw_imm16`-gated duplicates) were
> deliberately **not** resurrected -- those were correctly deleted as
> unreachable dead code in an earlier, unrelated fix and must stay deleted.
>
> **Verified so far:** scratch-compiled in an isolated throwaway copy (all
> five `.sinc` files + the top-level `.slaspec`, `sleigh.bat` run directly,
> not the live install) -- **exit code 0, no errors**, only the same
> pre-existing warning set every other `.sinc` in this repo already produces
> (unreferenced `_2`-suffixed tables, NOP constructors, `reloffs8`/`reloffs16`
> exporting size 0). No new constructor collisions from adding the `MOV:G`
> blocks.
>
> **Not yet done -- do this next, in order:**
> 1. Copy `h8539f.slaspec` and all five `.sinc` files to the Ghidra install's
>    `Processors\h8\data\languages\` directory and recompile there with
>    `sleigh.bat` (not just the scratch copy).
> 2. Hash-compare the installed `.slaspec`/`.sla` against the repo's current
>    copies (see "process lesson" below -- don't trust timestamps alone, and
>    don't assume "compiled in scratch" means "installed correctly").
> 3. Fresh ROM re-import + full auto-analysis; confirm `0x20027` and
>    `0x20a86` actually clear.
> 4. Once confirmed against the live ROM, update this entry to a short
>    "fixed and confirmed on hardware/ROM" note.
>
> **Superseded diagnosis (kept only as a process lesson, not a current fix):**
> a previous session diagnosed these same two failure addresses as caused by
> a stale installed language file at
> `%USERPROFILE%\Downloads\ghidra_12.0.4_PUBLIC\...\h8\data\languages\`
> (67KB installed vs. 215KB repo copy at the time) and "fixed" it by copying
> the live `.slaspec` over the stale install and recompiling. That refresh
> was a legitimate thing to do and should still be done as part of the
> install step above, but it did **not** actually fix `0x20027`/`0x20a86` on
> its own, because the `MOV:G` constructor that address needs was missing
> from the live `h8539f.slaspec`/`h8539f-mem.sinc` at the time too -- the
> stale-install theory was based on a byte-level check against the
> *pre-cutover backup* file, not the file that was actually live and
> installed. **Process lesson:** when a fix is verified by checking that a
> specific constructor exists, check it against the exact file that was just
> installed, not against a backup or an old scratch-test copy that happens to
> have the code -- the two can silently diverge, as they did here.
>
> `h8539f-instruction-table.md` (project root) is the ground-truth instruction
> table extracted from `ana.cpp` -- treat it as a reference, not a to-do list.
> This README's "To-do (current)" list below is the actual to-do list.
> `source\` holds reference Ghidra modules (Z80, H8/300) and the IDA SDK's
> `ana.cpp` (ground-truth opcode tables) used as structural/reference models
> only, not something to modify.
>
> **Process lesson for future sessions (general):** "the fresh compile is
> genuinely installed and complete" needs to mean hash-comparing the
> *installed* `.slaspec`/`.sla` against the *repo's* current copies, and
> spot-checking that specific constructors actually exist in the file being
> compiled/installed -- not just confirming a compile succeeded, or that a
> `.sla`'s timestamp looks recent, or that a fix existed in some backup or
> scratch-test file at some point. A "compiled clean" or "fixed" claim in a
> past session summary is not evidence a file's *current* disk content is
> correct, and a clean **scratch** compile is not evidence the **installed**
> copy is correct either -- re-verify against the live/installed file before
> trusting the claim, especially across a session boundary or after a
> structural refactor like the cutover.



Forked and substantially extended from [c4ashley/ghidra-h8-500](https://github.com/c4ashley/ghidra-h8-500)
(which itself extended [Hurricos](https://git.laboratoryb.org/hurricos/ghidra-h8-500)).
H8/539F-specific work by [professor-jonny](https://github.com/professor-jonny).

## Features

- Full H8/539F instruction set (cross-checked against IDA SDK `src/module/h8500/`)
- Working decompiler -- produces C output via Ghidra's decompiler window
- 32-bit flat address space (`H8:BE:32:H8539F`) matching the chip's maximum mode
- Correct ROM memory map: 128KB mapped at `0x10000-0x2FFFF` (per hardware manual)
- On-chip RAM at `0xEE80-0xFFFF` created automatically by the setup script
- Full H8/539F peripheral register map in `h8539f.pspec` (SCI1/2/3, timers, ADC, ports)
- Also supports H8/520 and H8/538F (separate language IDs)

## Install

1. Make sure Ghidra is installed. Note the path to its install directory.
2. Edit `h8\data\languages\Makefile` -- set `GHIDRADIR` to your Ghidra install path.
3. Run `make && make install` from the `h8\data\languages\` directory.

Alternatively, copy the contents of `h8\data\languages\` into:
```
<GhidraInstall>\Ghidra\Processors\h8\data\languages\
```
and run `sleigh.bat` (Windows) or `sleigh` (Linux/Mac) from `<GhidraInstall>\support\`
to compile the `.sla`:
```powershell
.\sleigh.bat "<GhidraInstall>\Ghidra\Processors\h8\data\languages\h8539f.slaspec" `
             "<GhidraInstall>\Ghidra\Processors\h8\data\languages\h8539f.sla"
```

## Opening a ROM in Ghidra

### 1. Import

- **File > Import File**, select your `.hex` or `.bin` ROM file.
- Format: **Raw Binary**
- Language: **H8:BE:32:H8539F**
- Under **Options**, set **Base Address** to `0x00010000`

  > This is critical. The H8/539F's ROM is physically mapped starting at H'10000, not H'00000.
  > Getting this wrong will cause all far-call targets to be off by 0x10000.

### 2. Do NOT click Analyze yet

Click OK to finish the import, then double-click the file to open it in the Code Browser.
**Do not click "Analyze" when prompted** -- use the setup script instead.

### 3. Run the setup script

In Ghidra's Script Manager (`Window > Script Manager`), find and run:

```
h8539_ecu_master_setup.py   (category: MitsubishiECU)
```

The script presents a GUI dialog for each step so you can toggle them individually.
It will:

1. Validate the import base address (aborts with a clear message if wrong)
2. Create the on-chip RAM memory block (`0xEE80-0xFFFF`)
3. Set CP/DP/TP context registers over both ROM pages
4. Read the reset vector and create the `entry` function
5. Test the decompiler -- aborts if it fails so you don't waste time on a broken analysis
6. Run auto-analysis (finds ~600+ functions on a typical ECU ROM)
7. Apply EcuFlash XML table labels (optional -- file browser prompt, ROM ID verified before labelling)
8. Run the ROM header scraper (optional -- MUT table, scaling tables, 2D/3D value tables by byte pattern)

### 4. EcuFlash XML labels (optional)

If you have an EcuFlash ROM definition XML for your specific ECU, select it via the
file browser when prompted at Step 7. The script verifies the ROM ID against the XML
before applying any labels -- a mismatch skips labelling with a clear warning.

Tables are labeled at their **header address** (the address code xrefs point to), not
the raw data address in the XML:

- 2D tables: labeled at `xml_addr - 4`
- 3D tables: labeled at `xml_addr - 7`
- 1D scalars: labeled at `xml_addr` directly (no header)

`<include>` references in the XML are followed automatically.

If no XML is selected, the script offers to run the ROM scraper as a fallback.


### 5. Finding additional functions

Auto-analysis will find most functions but may miss some. To find un-disassembled code:

- Search Memory (`Search > Memory`) for the byte pattern `11 19` (mnemonic `prts` --
  the far-call return instruction used by most functions). Look for hits not already
  inside a defined function.
- Similarly search for `19` alone (`rts`, near-call return).

## File layout (current, pre-refactor)

```
h8\data\languages\
    h8539f.slaspec      -- H8/539F instruction set (SLEIGH source)
    h8539f.sla          -- compiled SLEIGH binary (generated by sleigh)
    h8539f.pspec        -- processor spec: peripheral registers, default symbols
    h8539f.cspec        -- compiler spec: calling conventions, stack, global ranges
    h8.cspec            -- shared compiler spec for H8/520 and H8/538F
    h8.ldefs            -- language definitions (all variants)
    h8520.slaspec       -- H8/520 instruction set
    h8538f.slaspec      -- H8/538F instruction set
    h8520.pspec         -- H8/520 processor spec
    h8538f.pspec        -- H8/538F processor spec

test\
    h8539_ecu_master_setup.py  -- Ghidra script: full ROM setup with GUI (run this first)
    rvr\                -- example ROM files and EcuFlash XMLs

datasheets\h8539f\      -- Hitachi hardware/programming manuals

source\
    Z80\                -- official Ghidra Z80 module (reference model, prefix+bitfield dispatch)
    ghidra-h8-300\      -- community H8/300 module (reference model, functional-area .sinc split)
    ida-sdk-main\src\module\h8500\ana.cpp  -- ground-truth opcode tables (A2/A2tail/A3-A6)
```

This layout stays the same after the refactor described below -- only the internal
structure of `h8539f.slaspec` (and its new `.sinc` includes) changes.

`h8539f-instruction-table.md` (project root) is the ground-truth instruction
table extracted directly from `ana.cpp` -- see "To-do" and "Migration steps"
below for how it's used.

## Refactor plan (July 2026)

### To-do (current)

**Completed so far** (context for a fresh session -- don't redo these):

- [x] Ground truth extracted from `ana.cpp` into `h8539f-instruction-table.md`
      -- full `A2`/`A2tail` dispatch + all four MAP head/tail tables,
      transcribed directly and re-verified across three passes (two real
      transcription errors caught and fixed; see the table's "Verification
      pass 2" section).
- [x] **Finding:** old BUG 9 ("MAP4 abs-addressing entry points superseded")
      was itself wrong -- `A2[0x05]`/`0x0D`/`0x15`/`0x1D` really are `MAP4`.
      Re-opened, not superseded. Also resolved the old BUG 3 `rtd` byte
      question with no live ROM check needed (`0x14`/`0x1C` are the real
      `rtd` bytes). See the table's "FINDING" and "Verification pass 2"
      sections.
- [x] `h8539f-mem.sinc` started at `h8\data\languages\h8539f-mem.sinc`. All
      seven literal (non-MAP) forms -- `mov:l`/`mov:s`/`mov:e`/`mov:i`/`mov:f`/
      `ldm`/`stm` -- checked against `h8539f.slaspec` and the ground-truth
      table before assuming a rewrite was needed; all matched exactly and
      were relocated as-is. `ldm`/`stm` also picked up a `reglist!=0` fix for
      an all-zero-reglist gap versus `ana.cpp`.
- [x] `h8539f-mem.sinc`'s literal forms are **compile-tested** (via
      `sleigh.bat`, isolated scratch copy, not the live build -- exit code 0,
      no errors). Two real SLEIGH mistakes were caught and fixed during that
      test; both are now written up as general lessons in
      `h8539f-instruction-table.md`'s "SLEIGH lessons" section and should be
      applied to every `.sinc` file below, not just `mem.sinc`:
      1. `@include` order matters -- a `.sinc` file must be included *after*
         every subtable/field it references is defined in the top-level
         file, or SLEIGH errors with "No matching global symbol".
      2. In a multi-token pattern (`is tokenA=X; tokenB=Y & ...`), a field
         constraint must go in the clause for the token it actually belongs
         to. Putting a second-token field in the first token's clause
         produces "Mismatched tokens when combining patterns". This applies
         directly to the MAP3/4/5/6 files below -- they're all
         prefix-byte-then-dispatch-byte, i.e. exactly this two-token shape.
- [x] **Finding, confirmed against `ana.cpp` lines 420-620 (`h8500_ana()`):**
      the existing `map4_page`/`m4op`/`m4sz`/`m4CR` + `eab_indirect`/`eab_disp8`/
      etc. `ldc`/`stc` constructors (`h8539f.slaspec` lines 807-888) are wrong,
      not just stale -- they re-derive Op1's EA from a phantom third byte via
      the `addrMode` token, but the real decoder never does that. Ground truth:
      - Op1's EA is resolved from **byte 1 alone**, in the top-level switch
        (`ana.cpp` lines 420-476) that runs *before* the MAP dispatch loop even
        starts -- e.g. `0xB0-0xBF` -> `phrase(Op1, code, ph_pre)` (predec),
        `0xE0-0xEF` -> `ds8(insn, Op1, code, dtype)` (disp8, byte consumed
        inline immediately after byte 1). This switch fires on the raw fetched
        byte regardless of whether that byte is *also* a MAP escape trigger.
      - The MAP tail-dispatch loop (lines 478-492) fetches exactly one more
        byte and uses it *only* for the mnemonic (head/tail table index) and
        Op2: `opreg(insn.Op2, code, dtype)` unconditionally builds Op2 from
        that byte's low 3 bits -- there is no second EA byte, ever.
      - For `ldc`/`stc` specifically (lines 591-599): Op2 gets `+= SR` to land
        in control-register space, rejects `RES1`/`CP` and byte/word-vs-`SR`
        mismatches (old BUG 7, still valid, re-expressed not re-derived), and
        for `stc` only, Op1/Op2 are swapped afterward for `CR, EA` order.
      - **Resolution (applied, July 2026, compile-tested clean):** turned out
        the whole `map4_page`-gated `mov:g.b`/`ldc`/`stc` block (old lines
        761-888) wasn't just wrong, it was **entirely dead duplicate code**.
        `mov_g`/`ldc`/`stc` aren't MAP4-exclusive -- ground truth has them
        shared across MAP3/4/5 -- and this file already had a complete,
        correct implementation elsewhere: the `MOV:G <EAs>,Rd` / `Rs,<EAd>`
        block (`opcode=16/18 & Rd/Rs`, gated on `eab_*`/`eaw_*` directly) and
        the `ldc.b`/`stc.b` block (`opcode=17/19 & CR8`), both already
        covering every EA submode (mode 10-15) via the eab_* subtable as the
        byte-1 gate. `opcode` (instr8, byte 2) and `map4b`'s `m4op*2+m4sz`
        are numerically identical reconstructions of the same tail-group
        field, so the two blocks were 100% overlapping. First attempt was to
        *fix* the block in place (embed the EA in the byte-1 gate); compiling
        that against an isolated scratch copy via `sleigh.bat` immediately
        threw "Constructors with identical patterns" against the two blocks
        above, which is what surfaced the duplication. Deleted the whole
        block instead (see the comment left in its place in
        `h8539f.slaspec`). Isolated scratch-copy recompile is clean (exit 0,
        no errors) as of this fix.
- [x] **`xch` done (July 2026), compile-tested clean.** Confirmed against
      `ana.cpp`'s `A3tail`/`A4tail` tables (lines 66/92): MAP3's tail
      `0x90-97` is `xch`, MAP4's is `mov_g` instead -- so `xch` only ever
      gates on `eab_direct`/`eaw_direct` (mode=10), which never collides with
      the `mov:g` store block (starts at mode=11/`eab_predec`). No `+SR`
      register offset or CP/RES1 legality exclusion needed (that was
      `ldc`/`stc`-specific) -- `xch` is a plain two-way exchange.
      Along the way, found and fixed a real bug in the pre-existing `.w`
      form (`h8539f.slaspec`, `xch.w`): it wrote `Rd = eaw_direct` before
      writing `eaw_direct = Rd`, so the second assignment wrote back the
      value `eaw_direct` already had -- the swap silently never happened.
      Fixed to use the saved `tmp` on both sides. Also added the `.b` byte
      form, which didn't exist at all.
- [x] **`movfpe`/`movtpe` done (July 2026), compile-tested clean --
      completes the full MAP-tail entry list from step 2.** Ground truth:
      `ana.cpp`'s `A6` head/tail tables (lines 127-151) plus the `tables[]`
      dispatch array (lines 153-165) and the `index==3` legality switch
      (line 493). MAP6 is only reachable for these two mnemonics via a
      *nested* escape -- byte 1 triggers MAP3 (`eab_*`, mode=10 only) or
      MAP4 (mode=11-15) exactly as for `mov_g`/`ldc`/`stc`/`xch`, byte 2 is a
      fixed literal `0x00` (MAP3/4's own head-table index 0 = MAP6 escape,
      `A3[0]`/`A4[0]`), and byte 3 is MAP6's *own* tail dispatch (new `m6b`
      token: `m6grp` = byte3>>3, `m6Rn` = byte3&7, plain GPR, no `+SR`
      offset). `movtpe` swaps operand order (falls through from `stc`'s
      swap in the `ana.cpp` switch, lines 598-607); `movfpe` doesn't.
      Straightforward once the byte-1-is-the-EA model from the earlier
      finding was in hand -- no new bugs found this time. `map3_page` is now
      an unreferenced table (harmless compiler warning) since nothing left
      in the file still uses it as a first-byte gate; everything that used
      to route through it now gates on `eab_*`/`eaw_*` directly. Leaving it
      defined for now in case a future MAP3-only instruction needs a bare
      gate with no EA operand, but flagging it as a candidate for deletion
      if it's still unused once the rest of the instruction set is filled
      in.
- [x] **Resolved (July 2026):** the open question about which literal byte
      reaches MAP6's `default` case is answered by the `movfpe`/`movtpe`
      finding above -- it's exactly the guessed MAP3/MAP4-chained
      `0x00`-second-byte MAP6 entry (`A3[0]`/`A4[0]` in `ana.cpp`), confirmed
      while implementing `movfpe`/`movtpe`. `dadd`/`dsub` will reach MAP6 the
      same way (same nested escape, different byte-3 group per `A6tail`
      lines 145-146) -- no separate investigation needed when `arith.sinc`
      gets to them.
- [x] **MAP5 design resolved; arith-family slots written (July 2026), not yet
      scratch-compiled.** MAP5 is entered via two literal top-level bytes,
      `0x04`/`0x0C` (`A2[4]`/`A2[12]`), each reading an immediate payload
      first and then a MAP5 dispatch byte -- three bytes deep total, unlike
      MAP3/MAP4's two-byte escape. `A5tail` shares `add_g`/`adds`/`sub`/
      `cmp_g`/`addx`/`mulxu`/`subx`/`divxu` with MAP3/MAP4 at the same
      opcode groupings; these are now written in `h8539f-arith.sinc`.
      **Not the same as MAP3/4 for every slot:** `0x40-6F` is `orc`/`andc`/
      `xorc` on MAP5 (`logic.sinc`'s scope, not yet written) vs. `bset`/
      `bclr`/`bnot` on MAP3/4, and `0x80-8F` is `mov_g`/`ldc` (`mem.sinc`'s
      scope, not yet written). MAP5's head table (byte2 `< 0x20`) is
      entirely `null`, so MAP5 needs tail-dispatch only. **Do not assume
      symmetry with MAP3/4 when writing the remaining logic/mem slots.**
      Next: scratch-compile `arith.sinc`'s MAP5 addition via `sleigh.bat`,
      then write MAP5's `logic.sinc` and `mem.sinc` slots the same way.
- [x] **MAP5's `logic.sinc` slots written (July 2026), not yet scratch-compiled
      -- turned out to be two gaps, not one.** Initially only added
      `orc`/`andc`/`xorc` (MAP5's `0x48-4F`/`0x58-5F`/`0x68-6F` dispatch
      range, `opcode=9/11/13`). **Follow-up correction, same session:**
      checked the ground-truth tail grid and found `or`/`and`/`xor`
      (`0x40-47`/`0x50-57`/`0x60-67`, `opcode=8/10/12`) are shared
      identically across MAP3/MAP4/**MAP5** too -- but the pre-existing
      constructors for those are gated on `eab_*`/`eaw_*` (MAP3/4-only),
      the exact same bug class as `mem.sinc`'s `mov_g` gap below. Fresh
      escape-gated `or`/`and`/`xor` constructors were added alongside the
      CR-immediate forms. Do the same `sleigh.bat` scratch-compile check as
      `arith.sinc`'s MAP5 section before trusting any of this.
- [x] **`h8539f-mem.sinc`'s MAP5 slots written (July 2026)** -- stale header
      comment fixed, real escape-gated `mov:"g.b"`/`mov:"g.w"`/`ldc.b`/`ldc.w`
      constructors added (`opcode_special=0x04`/`0x0C` + `imm8`/`imm16` +
      `opcode=16 & Rd` or `opcode=17 & CR8`/`CR16`), see lines 121-161 of the
      file.
- [x] **BLOCKING item RESOLVED (July 2026):** the MAP5 `mem.sinc` scratch-compile
      failure below is superseded -- root cause was the 58 dead `eab_imm8`/
      `eaw_imm16`-gated constructors (see the "RESOLVED" entry above and the
      session summary at the top of this file), which are now deleted from
      `h8539f.slaspec`. `arith.sinc` was also missing `subs`'s MAP5 forms; added.
      `logic.sinc` confirmed already complete. **Original failure report kept
      below for context, not because it's still an open problem:**
- [ ] **BLOCKING, found this session: MAP5 `mem.sinc` scratch-compile FAILED --
      real byte-1 ambiguity, not a scratch-copy mistake.** Isolated the new
      MAP5 section (only it, not the rest of `mem.sinc`, which still has
      pre-cutover duplicates for its other content) into its own scratch
      `.sinc`, `@include`d it into a throwaway copy of `h8539f.slaspec`, ran
      `sleigh.bat` directly. Result: **7 "Constructors with identical
      patterns" errors**, e.g.:
      ```
      ERROR h8539f-mem-map5only.sinc:33: Constructors with identical patterns:
         table "instruction" constructor from h8539f-mem-map5only.sinc:33
         table "instruction" constructor from h8539f_map5memtest.slaspec:681
      ```
      (line 681 there is the pre-existing `mov:"g.b" eab_imm8,Rd` constructor;
      the other 6 errors are the same clash against `ldc.b`'s `eab_imm8`
      CCR/TP/BR/EP/DP forms and one more `mov:"g.w"`/`eaw_imm16` pair.)

      **Root cause, traced via the token definitions (`h8539f.slaspec` lines
      55-81):** `eab_imm8` is defined as `Rn=4 & sz=0 & mode=0` on the
      `addrMode` token (`Rn=(0,2)`, `sz=(3,3)`, `mode=(4,7)`) -- bit-packed,
      that's byte value `0b0000_0_100` = **`0x04`**. The new MAP5 escape uses
      `opcode_special=0x04` on the separate `special` token (`opcode_special
      =(0,7)`, i.e. the whole byte) -- but both tokens read the *same*
      physical first byte of the instruction. So `eab_imm8`'s existing MAP3/4
      immediate-EA submode and the new MAP5 escape produce byte-for-byte
      identical 3-byte sequences: byte1=`0x04` (either way), byte2=an
      unconstrained immediate, byte3=`opcode=16 & Rd` (or the `CR8`/`CR16`
      variants) -- SLEIGH is correctly flagging a genuine decode ambiguity in
      the model, exactly the same failure class as the `cmp:g` MAP3 false
      positive already caught in `arith.sinc` (guessed field reuse never
      checked against `ana.cpp`'s real addressing-mode legality).

      **Not yet resolved -- do NOT guess-patch this.** Need to check
      `ana.cpp`'s addressing-mode table for whether `mode=0`/`sz=0`/`Rn=4`
      (i.e. byte1=`0x04`) is actually a legal `eab_imm8` EA submode for
      MAP3/4's `mov_g`/`ldc`, or whether real hardware reserves that specific
      byte1 value for the MAP5 escape and the existing `eab_imm8`-gated
      MAP3/4 constructors are themselves over-broad (same bug shape as the
      `cmp:g` MAP3/MAP4 mixup, just one token layer up). Whichever is true,
      the fix is probably: either (a) exclude byte1=`0x04` from `eab_imm8`
      explicitly if MAP3/4 truly can't produce it, or (b) find what actually
      disambiguates a real `0x04` first byte between "MAP3/4 immediate-EA
      mov_g/ldc" and "MAP5 escape" on real hardware (there may be none, i.e.
      one of these two readings is simply wrong and should be deleted, not
      patched around).

      **Also worth checking before re-attempting the scratch-compile:** the
      arith.sinc and logic.sinc MAP5 sections use the same
      `opcode_special=0x04`/`0x0C` escape bytes -- they likely hit the exact
      same `eab_imm8`/`eaw_imm16` collision (`cmp:g`'s and `orc`/`andc`/`xorc`'s
      MAP3/4 immediate forms). Don't scratch-compile those in isolation and
      declare them clean without checking this first; it's probably one root
      cause showing up in all three files, not three independent bugs.

      Scratch-test scaffold used this session (for reference, not persisted --
      built in `$env:TEMP\h8_map5_mem_scratch`, not checked into the repo):
      copy `h8539f.slaspec` unmodified + append a real `@include` for an
      isolated copy of just the new MAP5 block (lines 121-161 of
      `h8539f-mem.sinc`), both files BOM-stripped, run through `sleigh.bat`
      directly via the Ghidra install at
      `$env:USERPROFILE\Downloads\ghidra_12.0.4_PUBLIC`.
- [x] **RESOLVED (July 2026), checked directly against `ana.cpp`'s
      `h8500_ana()` (lines 259-476), not guessed.** The MAP5 escape
      constructors above are correct; the collision is the OTHER side --
      **the pre-existing `eab_imm8`/`eaw_imm16`-gated constructors are dead,
      unreachable code and need deleting, and the bug is far bigger than
      `mov_g`/`ldc` alone.**

      `eab_imm8`/`eaw_imm16` are defined (`h8539f.slaspec` line 662-663) as
      `Rn=4 & sz=0 & mode=0` / `Rn=4 & sz=1 & mode=0` on the `addrMode`
      token (`Rn=(0,2)`, `sz=(3,3)`, `mode=(4,7)`) -- bit-packed, that's
      byte1=`0x04` / byte1=`0x0C`. Checked against `ana.cpp`'s top-level
      `switch(code)` (lines 285-476) and `A2[]`/`A2tail[]`: **byte1=`0x04`
      and `0x0C` are assigned to `MAP5` in `A2[]`, never `MAP4`.** The
      switch's `case 0x04`/`case 0x14` (lines 347-351) confirms this
      concretely -- it reads the *next* byte directly into `Op1` as an
      8-bit immediate (`imm8(insn, insn.Op1)`), then the MAP5 tail-dispatch
      loop (lines 478-492) reads a *third* byte for the mnemonic group and
      `Op2`. So the real 3-byte shape for these is: byte1=escape,
      byte2=immediate (consumed directly), byte3=MAP5 dispatch -- exactly
      what the new `mem.sinc` MAP5 section above already implements.

      By contrast, `eab_abs8_br`/`eaw_abs8_br`/`eab_abs16`/`eaw_abs16`
      (`Rn=5 & mode=0`/`mode=1`, byte1=`0x05`/`0x0D`/`0x15`/`0x1D`) are
      legitimate: `A2[]` assigns all four of *those* bytes to `MAP4`,
      matching the already-documented "old BUG 9" finding
      (`A2[0x05]`/`0x0D`/`0x15`/`0x1D` really are `MAP4`) -- same
      byte1-is-both-EA-and-escape mechanism, just a different byte1 range
      that genuinely does belong to MAP4's own tail-dispatch entry set.

      **So `eab_imm8`/`eaw_imm16` can never legitimately fire as a MAP3/4
      tail-dispatch EA submode -- byte1=`0x04`/`0x0C` is exclusively the
      MAP5 escape, full stop.** Grepped every constructor gated on
      `is eab_imm8;`/`is eaw_imm16;` in `h8539f.slaspec`: **58 total**,
      spanning `mov_g`, `ldc`, `add:g`, `sub`, `adds`, `subs`, `addx`,
      `subx`, `andc`/`orc`/`xorc`, and `cmp:g` (line numbers ~681-1553).
      Every one of these is dead/unreachable code inherited from before the
      "byte1 is the EA" model was established (same root cause class as the
      `cmp:g` MAP3/MAP4 false positive already caught, just one token layer
      up and far more widespread).

      **Next steps, concretely:**
      1. ~~Delete all 58 `eab_imm8`/`eaw_imm16`-gated constructors listed
         above -- they're unreachable, not real ISA behavior.~~ **DONE (July
         2026)** -- all 56 constructor lines removed (the other 2 of the 58 were
         `eab_imm8`/`eaw_imm16`'s own subtable definitions, kept), each replaced
         with a comment pointing to its MAP5-owning `.sinc` file.
      2. ~~Write MAP5 escape-gated replacements...~~ **DONE (July 2026), except
         `arith.sinc`'s `cmp:g` note below was already resolved in a prior
         session (see line ~1021-1022 of `h8539f-arith.sinc`) and `subs.b`/
         `subs.w` were found missing and added this session.** All of `mem.sinc`/
         `arith.sinc`/`logic.sinc`'s MAP5 replacements are now written and
         accounted for.
      3. ~~Re-run the scratch-compile once all of the above land together
         (mem/arith/logic in one throwaway copy)~~ **DONE (July 2026).** Exit 0
         on the first attempt for mem/arith; logic.sinc had a real bug (12
         `orc`/`andc`/`xorc` TP/BR/EP/DP constructors comparing bare `imm8`
         with no size annotation -- "Could not resolve at least 1 variable
         size"). Fixed (sized as `imm8:1`) and re-compiled clean -- see the
         session summary at the top of this file for full detail. No
         cross-file collisions found once the dead code was gone, confirming
         this finding really was just dead code, not a deeper byte1=0x04/0x0C
         ambiguity.
- [ ] **Follow-up, not yet checked:** whether `dadd`/`dsub` (MAP3-nested-into-
      MAP6, currently `mode=10` only) also need a MAP4-nested path, per the
      README's own note that `A3[0]` and `A4[0]` both escape to MAP6. Confirm
      against `movfpe`/`movtpe`'s implementation once MAP5 is resolved.
- [ ] **MAP6 gap, confirmed this session by reading `h8500_ana()` in full --
      only half of MAP6 is implemented, and the missing half isn't in any
      `.sinc` file's stated scope yet.** MAP6 has two distinct entry paths,
      not one:
      1. **Nested inside MAP3/MAP4** (byte 1 triggers MAP3/MAP4 via
         `eab_*`/`eaw_*`, byte 2 is literal `0x00` -- `A3[0]`/`A4[0]` --
         byte 3 is MAP6's own dispatch via `A6`/`A6tail`). **Done** for
         `movfpe`/`movtpe` (`A6tail` `0x80-87`/`0x90-97`). **NOT done** for
         `dadd`/`dsub` (`A6tail` `0xA0-AF`/`0xB0-B7`) -- this is the
         "Follow-up, not yet checked" item directly above. Also not done:
         `scb` (`A6tail` `0xB8-BF`) and the `pjmp`/`pjsr`/`jmp`/`jsr` group
         reachable via this nested path (`A6tail` `0xC0-FF`).
      2. **Direct top-level literal bytes** `0x01`/`0x06`/`0x07`/`0x11`
         (`A2[1]`/`A2[6]`/`A2[7]`/`A2[0x11]` are all `MAP6` directly, no
         MAP3/4 nesting at all) -- confirmed against `ana.cpp`'s
         `h8500_ana()` switch: `0x01`/`0x06`/`0x07` set `aux_f`/`aux_ne`/
         `aux_eq` (the three `scb` variants) and MUST resolve to
         `H8500_scb`; `0x11` MUST resolve to one of
         `prts`/`prtd`/`jmp`/`pjmp`/`jsr`/`pjsr` (the `index==3` legality
         switch at `ana.cpp` line 493 enforces this and returns invalid
         otherwise). **CORRECTION (July 2026): this direct-entry path already**
         **exists in the main `h8539f.slaspec` -- the "NONE of this exists yet"**
         **claim previously here was written without re-checking the file and**
         **was wrong.** `scb`/`jmp`/`jsr`/`pjmp`/`pjsr`/`prts`/`prtd`/`rts`/`bsr`
         are all already present, gated on these same escape bytes. Not yet
         relocated into any `.sinc` file, and a real bug (`pjmp`/`pjsr`'s
         tail-dispatch values swapped) was found auditing it against the
         ground-truth table -- see the session summary at the top of this file
         and step 6 below for full detail and the fix.
      - **Why this matters for `branch.sinc`:** `scb`, `jmp`/`jsr`/`pjmp`/
        `pjsr` (in their MAP6 forms), and `dadd`/`dsub`'s MAP4-nested path
        are all squarely `branch.sinc`/`arith.sinc` territory. The
        "MAP6 saved-code legality filter" open question further down (which
        original entry byte reaches which MAP6 mnemonic) applies directly
        to this direct-entry path. **RESOLVED FROM SOURCE (July 2026, no
        live-ROM check needed):** `ana.cpp`'s `index==3 switch(saved_code)`
        (lines 493-520) is itself a complete, exhaustive legality table, not
        an open question -- `saved_code` is the *original* first byte, saved
        before any MAP dispatch began, and the switch enforces: `0x01`/`0x06`/
        `0x07` -> must resolve to `H8500_scb` or invalid; `0x11` -> must
        resolve to one of `prts`/`prtd`/`jmp`/`pjmp`/`jsr`/`pjsr` or invalid;
        `default` (every other `saved_code`, i.e. every MAP3/4-nested entry,
        since those all start with an `eab_*`/`eaw_*` byte never equal to
        `0x01`/`0x06`/`0x07`/`0x11`) -> must resolve to one of `movfpe`/
        `movtpe`/`dadd`/`dsub` or invalid. The three legality sets are
        disjoint and byte-complete -- this can be modelled directly against
        the source switch, no ROM disassembly required to determine it.
      - **Plan:** (1) ~~resolve the `dadd`/`dsub` MAP4-nesting follow-up~~
        **DONE (July 2026), not yet scratch-compiled.** Turned out less
        "cheap" than expected: `mode=10` is MAP3's exclusive direct-register
        submode (MAP4 has no `mode=10` at all, confirmed against
        `addrMode`'s token definition), so the existing `Rn,Rd` form only
        ever covered the MAP3-nested path. Added 5 more constructors per
        `dadd.b`/`dsub.b` (`eab_predec`/`eab_postinc`/`eab_indirect`/
        `eab_disp8`/`eab_disp16`, mode=11-15) mirroring `movfpe`'s non-direct
        forms exactly, with the EA-sourced byte substituted for `Rn` in the
        BCD math. (2) do the live-ROM check
        for the direct-entry legality question; (3) write `scb` and the
        MAP6-reachable `jmp`/`jsr`/`pjmp`/`pjsr` forms into `branch.sinc`
        once both of those are settled -- don't start `branch.sinc` before
        this, since guessing the direct-entry gating wrong would silently
        misdecode real ROM bytes the same way the `cmp:g` MAP3 false
        positive did.

**Sequencing decision (July 2026):** originally step 1 was "split the top-level
file first, then fill in `.sinc` files against it." Changed after `mem.sinc`
work showed the categories are interleaved in the current file (`mov_g`/`ldc`/
`stc`/`xch`/`movfpe`/`movtpe` share the same `opcode=N & Rd/Rs/CR8` block as
the whole `add`/`sub`/`adds`/`subs`/`addx`/`subx`/`cmp_g` arithmetic family
that `arith.sinc` needs). Splitting the top file early would mean cutting that
block twice. New order: write and verify each `.sinc` file's content
standalone against ground truth first (scratch-test by commenting out the old
constructors it replaces in a throwaway copy + `@include`-ing the new file,
never touching the real main file's structure), and only do the actual
top-level split -- strip shared infra, wire real `@include`s, delete the old
constructors for good -- once *every* category is done. That's one clean
cutover instead of several partial ones, and the real Ghidra install doesn't
get touched until after that cutover + a full recompile.

**Next steps, in order** (this is the actual plan to work through):

1. ~~**Write the remaining MAP-tail entries**~~ **DONE (July 2026)** --
   `mov_g`/`ldc`/`stc`/`xch`/`movfpe`/`movtpe` are all in place in the main
   file now (see findings above), compile-tested clean. This content will
   move into `h8539f-mem.sinc` as part of the final cutover (step 3 below),
   not before -- see "Sequencing decision" above for why.
2. ~~**Write `h8539f-logic.sinc`'s content, scratch-tested standalone**~~
   **DONE (July 2026)** -- `or`/`and`/`xor`/`andc`/`orc`/`xorc`, split out of
   arith.sinc's original scope into its own file (see
   `h8539f-instruction-table.md`'s design-outline entry for why). All six
   already existed in the main file, relocated verbatim, text-verified
   byte-for-byte match. **Correction:** this entry originally claimed
   "scratch-compiled in isolation ... exit 0, no errors" at this point, but
   the compile had not actually been run yet -- the file's own header still
   said "DRAFT -- not yet scratch-compiled", a direct contradiction caught
   during a later verification pass on `arith.sinc`. That same pass also
   found `not.b`/`not.w` (ground-truth head `0x15`) missing from every
   functional `.sinc`'s stated scope -- still sitting unclaimed in
   `h8539f.slaspec`, which would have silently dropped it at the step-6
   cutover. Both are now actually fixed: `not.b`/`not.w` added to this file
   (same head-table family as `clr`/`neg`/`tst`, `opcode_special=0x15`, no
   field overlap with `or`/`and`/`xor`/`andc`/`orc`/`xorc`'s `opcode=8-13`),
   and the real scratch compile run (throwaway copy of `h8539f.slaspec` with
   all seven blocks deleted + real `@include`, both files BOM-stripped, run
   through `sleigh.bat` directly): **exit 0, no errors**, same familiar
   pre-existing warning set as every other `.sinc` file, no new collisions.
   One open item still carried forward into the file itself: the `CR8`
   `RES1`/`CP` rejection-guard question needs the same double-check
   `ldc`/`stc` got.
3. ~~**Write `h8539f-arith.sinc`'s content, scratch-tested standalone**~~
   **DONE (July 2026)** -- all 28 blocks (`add:g`/`sub`/`subx`/`adds`(`add:q`)/
   `addx`/`dadd`/`dsub`/`swap`/`btst`(reg and imm4 forms)/`clr`/`neg`/`tst`/
   `cmp:g`/`cmp:e`/`cmp:i`/`extu`/`exts`/`shal`/`shll`/`shar`/`shlr`/`rotl`/
   `rotr`/`rotxl`/`rotxr`/`mulxu`/`divxu`/`tas`) already existed in the
   pre-split `h8539f.slaspec` and matched the ground-truth table's rows
   exactly (grepped and confirmed, same as `mem.sinc`/`logic.sinc`) --
   relocated verbatim via PowerShell line-range extraction, not manual
   transcription, to avoid transcription error at this volume. Scratch-
   compiled in isolation (throwaway copy of `h8539f.slaspec` with the 28
   corresponding blocks deleted + real `@include "h8539f-arith.sinc"`, run
   through `sleigh.bat` directly): **exit 0, no errors.** Only pre-existing
   warnings surfaced (NOP constructors, unnecessary extension/truncation
   conversions, `reloffs8`/`reloffs16` exporting size 0, and a batch of
   already-dead unreferenced tables -- `map3_page`, `Rs32`/`Rn32`,
   `disp8_banked`, the `eab_*2`/`eaw_*2`/`Rn_banked2` byte-2-scoped family
   from the superseded TST BUG 5 v2 attempt, `absaddr24`) -- none new, all
   pre-existing cleanup candidates, not arith regressions. One real snag
   along the way: both the scratch `h8539f-arith.sinc` copy and the
   generated `h8539f_arithtest.slaspec` carried a leading UTF-8 BOM that
   made `sleigh.bat`'s lexer bail on line 1 ("extraneous input"); stripping
   the 3 BOM bytes from each file fixed it -- a byte-level artifact of how
   the scratch copies were written/extracted, not a content bug, but worth
   remembering for the real cutover copy too. Full detail in
   `h8539f-arith.sinc`'s own "Verification record" section.
   **Correction (July 2026):** the compile-clean result above was syntactic
   only -- a follow-up pass tracing `mode`/`opcode47` against `ana.cpp`'s
   `A3`/`A4` head tables found `cmp:g`'s immediate forms
   (`opcode_special=4`/`5`) wrongly included an `eab_direct`/`eaw_direct`
   branch, which is MAP3-exclusive (`mode=10`) -- but `ana.cpp`'s `A3[4]`/
   `A3[5]` are `H8500_null`; only MAP4 (`A4[4]`/`A4[5]`) has `cmp_g` there.
   That branch would have false-positive-decoded real MAP3 bytes (e.g.
   `0xA0 0x04 <imm8>`) as a `cmp:g` instruction that doesn't exist on real
   hardware. Fixed by removing the `eab_direct`/`eaw_direct` lines from both
   blocks; re-compiled clean (exit 0, same warnings, no new collisions).
   Full detail, including the "spot-checked but not exhaustively
   re-derived" caveat for the file's other 26 blocks, is in
   `h8539f-arith.sinc`'s verification record.
4. **BLOCKING -- make `mem.sinc`/`arith.sinc`/`logic.sinc` 100% correct before
   touching `bit`/`branch` or the cutover.** Two things, both required:
   - **Exhaustive re-derivation, not spot-check.** Every block in all three
     completed files gets checked row-by-row against `ana.cpp`'s `A3`/`A4`/
     `A5`/`A6` arrays (the same process that caught the `cmp:g` MAP3 false
     positive), not just re-confirmed against the "mode=10-is-MAP3-only" fact
     that one bug happened to hinge on. Track this per-block in
     `h8539f-instruction-table.md`'s verification record so "done" means
     "row-checked," not "compiled clean" -- compiling clean only proves the
     SLEIGH is syntactically valid, not that it decodes the right bytes.
   - ~~**Implement MAP5.**~~ **DONE (July 2026), combined scratch-compile clean.**
     New top-level literal-byte entry (`0x04`/`0x0C`, `A2[4]`/`A2[12]`) plus its
     immediate-then-dispatch-byte shape, wired into `mem`/`arith`/`logic` per
     `A5tail`, Z80-style (one literal constraint for the escape, then bitfield
     constructors on the byte that follows -- no named dispatch subtable).
     Still owed: the exhaustive row-by-row re-derivation below covers MAP5's
     constructors too, not just MAP3/4 -- the `imm8:1` size-fix this session
     was a compile-error fix, not a semantic re-derivation of the TP/BR/EP/DP
     flag-update behavior against `ana.cpp`.
   - Resolve the `dadd`/`dsub` MAP4-nesting follow-up (see finding above)
     while `arith.sinc` is back open for this pass.
   - **Confirm `A4` head table excludes `swap`/`exts`/`extu` (`0x10-0x12`).**
     ~~Per the ground-truth head table, MAP3 has these three, MAP4 does not --
     same shape of bug as the `cmp:g` false-positive that already got caught.
     Confirm `arith.sinc`'s constructors for these three actually gate MAP3
     only, not MAP3+MAP4.~~ **DONE (July 2026), confirmed clean.** `A4[0x10-
     0x12]` are all `H8500_null` in `ana.cpp`; `arith.sinc`'s `swap.b`/
     `exts.b`/`extu.b` all gate on `eab_direct`/`mode=10` only, no MAP4-
     reaching form exists. No bug found; see session summary at top of file.
   - **Confirm every `H8500_null` cell is actually rejected, not silently
     matched.** `A2[0x16]`, `A2[0x1B]` at the top level, and the various
     `null` cells across the MAP3-6 head/tail tables (e.g. `0x01-0x03`,
     `0x0A-0x0B`, `0x0E-0x0F` in every MAP head table) are invalid on real
     hardware. Check the `.sinc` bitfield constraints actually exclude these
     ranges rather than falling through to an adjacent constructor.
     **DONE (July 2026)** -- confirmed clean: `A2[0x16]`/`A2[0x1B]`
     (no bare top-level literal collision, only legitimate MAP3/4 second-byte
     uses of those values for `tst`/`shlr`); `arith.sinc`'s own head-table
     range (`0x11-0x1B` used, nothing in the `0x01-0x0B` null band); MAP5's
     entirely-null head table (`A5[]`, confirmed its escape bytes never
     double as an internal MAP5 head dispatch). **This session, closed for**
     **the remaining four files:** `mem.sinc`/`logic.sinc`/`bit.sinc` never
     gate any constructor on head-table (second-byte `<0x20`) space at all --
     every constructor in them matches an explicit tail-group `opcode`/
     `opcode47` value with no wildcard, so there's no null band they could
     ever reach. `branch.sinc` (the only file using head-table space, via
     MAP6 nesting) row-checked: every `opcode_special` literal used avoids
     both real top-level nulls (`A2[0x16]`/`A2[0x1B]`); the MAP6-nested
     head-table matches (`prts`=`0x19`, `prtd`=`0x14`/`0x1C`) are `A6`'s only
     two real entries; the MAP6 tail forms all land on `A6tail`'s populated
     groups with nothing spilling into surrounding nulls. No bug found.
     Full detail in the session summary at the top of this file.
   - **Confirm the byte/word size flag is read consistently.** Per the
     ground-truth table's structural fact #6, size for the whole `0x60-0xFF`
     range is decided once from bit 3 of the *first* byte and carried through
     (`aux_byte`/`aux_word`), not re-derived per instruction. Spot-check that
     each block actually reads this shared bit rather than reconstructing
     size some other way -- easy to get subtly wrong across 28+ blocks.
     **DONE (July 2026):** checked how each `.sinc` file selects byte vs.
     word and confirmed all of them derive it from a single byte-1 field
     read, never re-derived downstream. `mem.sinc`'s literal forms
     (`mov:l`/`mov:s`/`mov:f`) select via `opcode=12/13`,`14/15`,`16/17`,
     `18/19` -- since `opcode` is bits(3,7) of byte 1, the field's own low
     bit *is* bit 3 of the byte, so byte/word falls out of the same single
     read, not a second derivation. `logic.sinc`/`bit.sinc`'s MAP3/4/5 forms
     select via the `eab_*` vs `eaw_*` addressing-subtable choice on byte 1
     -- same single-read story. `branch.sinc`'s MAP6-nested `dadd`/`dsub`
     use `mode=10 & sz=0` directly on byte 1. No file re-derives size from a
     second byte or reconstructs it some other way. No bug found.
   - **MAP6 saved-code legality filter (open question 2 in the ground-truth
     table) -- RESOLVED FROM SOURCE (July 2026), no longer blocking
     `branch.sinc`.** Which original first byte (`0x01`/`0x06`/`0x07`/`0x11`,
     or the MAP3/MAP4-chained `eab_*`/`eaw_*` entry) is allowed to reach which
     MAP6 mnemonic is fully specified by `ana.cpp`'s `index==3
     switch(saved_code)` (lines 493-520) -- a complete, disjoint legality
     table, not something that needs live-ROM disassembly to determine:
     `0x01`/`0x06`/`0x07` only `scb`; `0x11` only `prts`/`prtd`/`jmp`/`pjmp`/
     `jsr`/`pjsr`; every other (MAP3/4-nested) `saved_code` only `movfpe`/
     `movtpe`/`dadd`/`dsub`. `branch.sinc` can be written directly against
     this table.
   - **Fixed (July 2026):** `ldc.b`'s `eab_imm8` immediate form only existed
     for `CCR`/`TP`, missing for `BR`/`EP`/`DP` -- confirmed against `ana.cpp`
     lines 588-598 that the `H8500_ldc` legality check doesn't restrict
     immediate addressing by which `CR8` index is targeted (only `RES1`/`CP`
     and word/byte-vs-`SR` mismatches are rejected), so this was a real
     coverage gap, not an intentional omission. Added `eab_imm8,"BR"`/`"EP"`/
     `"DP"` constructors (`h8539f.slaspec`, opcode=17 & CR8=3/4/5). First
     attempt introduced a duplicate-constructor collision (accidental double
     insert) caught immediately by `sleigh.bat` -- ERROR at 1368/1369,
     1378/1379, 1388/1389. Removed the three duplicate lines and re-compiled
     clean: exit 0, same pre-existing warning set as before, no new
     collisions.
   - Also confirmed correct during this pass (no fix needed): `mov:g`'s
     store block (opcode=18, byte-1 EA excludes `eab_direct`/`eaw_direct`)
     and `xch` (opcode=18, EA is exactly `eab_direct`/`eaw_direct`) share the
     `opcode=18` field without collision, because the EA-subtable choice
     itself encodes MAP3 vs MAP4 (mode=10 vs 11-15) -- matches `A3tail`/
     `A4tail`'s `0x90-97` split exactly. `mov:g`'s two-directional immediate
     mismatch handling (byte immediate to word EA via sign-extend, word
     immediate truncated to byte EA) also matches `ana.cpp`'s `aux_mov16`
     special-case logic (lines 549-565) exactly.
   Only once all three files pass both checks are they considered "100%
   correct" and ready to be treated as finished inputs to the later cutover.
5. ~~**Write `h8539f-bit.sinc`'s content, scratch-tested standalone**~~
   **DONE (July 2026)** -- `bclr`/`bset`/`bnot` relocated verbatim from the
   main file (grepped and confirmed match, same treatment as every prior
   `.sinc`). `btst` deliberately excluded from this file: confirmed already
   present in `h8539f-arith.sinc` (32 matching lines, both register and
   immediate forms) per the project's existing category split, so it was
   not duplicated here -- worth noting the "two constructors sharing a
   display name" fork this step originally flagged (register form vs.
   immediate-bit-number form) is therefore already handled inside
   `arith.sinc` for `btst`, and within this file for `bclr`/`bset`/`bnot`'s
   own register-vs-immediate split. Scratch-compiled in isolation (throwaway
   copy of `h8539f.slaspec` with the `bclr`/`bset`/`bnot` blocks deleted +
   real `@include "h8539f-bit.sinc"`, run through `sleigh.bat` directly):
   **exit 0, no errors**, same familiar pre-existing warning set, no new
   collisions. One real snag along the way, root-caused and fixed: the
   build script's delete-range list had only one range this time
   (`@(1156,1250)`), and PowerShell auto-flattens a single-element
   array-of-arrays (`@( @(1156,1250) )` collapses to `@(1156,1250)`),
   which silently broke the range-pair iteration and deleted nothing on
   the first attempt -- fixed with the unary comma operator
   (`@( ,@(1156,1250) )`). Every prior scratch-test script happened to have
   2+ ranges and never hit this. One open item carried into the file
   itself, not yet resolved: `bnot`'s immediate form gates on `map4_page`
   while `bclr`/`bset`'s immediate forms gate on `opcode47=13`/`12`
   directly -- inherited as-is from the pre-split file, needs the same
   `A3tail`/`A4tail` row-check the other files are owed.
   **RESOLVED (July 2026):** confirmed against the ground-truth tail table --
   `bnot`'s row is `0xE0-E7`/`0xE8-EF`, the same shape as `bset`(`0xC0-CF`)/
   `bclr`(`0xD0-DF`), i.e. `opcode47=14 & op_imm4` applied in the second
   clause after `eab_*`/`eaw_*` consumes byte 1 -- not `map4_page`, which
   reads byte 1's top nibble and was the wrong byte position entirely. All
   16 `bnot.b`/`bnot.w` constructors changed accordingly. **Now also
   scratch-compiled standalone (July 2026): exit 0, no errors** -- see the
   session summary at the top of this file for the full run detail. This
   file (and the fix) count as verified.
6. **Relocate + audit `h8539f-branch.sinc`'s content -- CORRECTION (July**
   **2026): this is a relocation + fix job, not a from-scratch write.** MAP6's
   nested-in-MAP3/4 path is proven correct for `movfpe`/`movtpe`, and
   `dadd`/`dsub` now have the same treatment applied (July 2026, not yet
   scratch-compiled -- turned out to need 5 more EA-sourced constructors each,
   not a trivial follow-up; see "Completed so far" above). MAP6's *other*
   entry path -- direct top-level literal bytes `0x01`/`0x06`/`0x07`/`0x11`
   reaching `scb` and the `jmp`/`jsr`/`pjmp`/`pjsr` group -- **already exists**
   **in the main `h8539f.slaspec`** (a previous version of this README wrongly
   said it didn't; see the session summary at the top of this file). Its
   legality doesn't need a live-ROM check either: `ana.cpp`'s
   `index==3 switch(saved_code)` (line 493) is a complete, disjoint legality
   table by itself (see "MAP6 saved-code legality filter" entry further down
   for the full breakdown). **What's actually needed for this step:**
   1. ~~**Fix the confirmed bug:** `pjmp`/`pjsr`'s tail-dispatch `opcode`
      values are swapped (`pjmp` uses `0x19`, `pjsr` uses `0x18` -- backwards
      per `A6tail`'s `0xC0-C7`/`0xC8-CF` rows).~~ **DONE (July 2026):** swapped
      -- `pjmp` now `opcode=0x18`, `pjsr` now `opcode=0x19`, matching ground
      truth. Not yet scratch-compiled as part of this file.
   2. ~~**Row-check the rest of the existing `scb`/`jmp`/`jsr`/`pjmp`/`pjsr`/**~~
      ~~`prts`/`prtd`/`rts`/`bsr` block against `ana.cpp`/the ground-truth table**~~
      **DONE (July 2026):** `jmp`/`jsr`/`prts`/`prtd`/`scb`/`rts`/`bsr` all
      row-checked against the ground-truth `A2`/`A6` head/tail tables -- all
      clean, no bugs found (full breakdown in the session summary at the top
      of this file). `pjmp`/`pjsr`'s swap fix from the prior session was
      re-confirmed still in place while doing this pass. Audit-only, no code
      changed -- the exhaustive row-by-row treatment step 4 requires of the
      other files is now satisfied for this block too.
   3. ~~Then scratch-compile standalone (same throwaway-copy `sleigh.bat` rule~~
      ~~as steps 2-5), then relocate into `h8539f-branch.sinc`.~~ **DONE (July**
      **2026):** relocated verbatim into `h8539f-branch.sinc` and scratch-
      compiled standalone -- exit 0, no errors, same warning set as every
      other `.sinc` (see session summary at the top of this file for full
      detail). `branch.sinc` is now verified to the same standard as
      `mem`/`arith`/`logic`/`bit.sinc`. ~~Two items carried forward, not
      blocking: (a) re-confirm the `bra`/`Bcc` 16-bit-form comment's claimed
      `rtd s8`/`opcode_special=0x30` collision is actually stale now that
      `rtd s8` is gated on `0x14`; (b) `bpt` and `dadd`/`dsub`'s missing EA-
      sourced forms are still open (see the file's own "KNOWN GAPS"
      header).~~ **BOTH RESOLVED (July 2026):** (a) confirmed stale, comment
      rewritten to say so; (b) `bpt` implemented (confirmed against
      `ana.cpp`/`ins.cpp`, disassembly-level only, no public source for
      further behavior), `dadd`/`dsub`'s "5 missing EA forms" confirmed via
      GNU binutils' H8/500 `as` reference to have never been real ISA
      behavior -- the direct-register form was always the complete
      instruction. See the session summary at the top of this file for full
      detail. `branch.sinc` now has no open items of its own.

7. **Do the real top-level split + cutover, once, for everything above.**
   Strip `h8539f.slaspec` down to endian/alignment/address-space/register/
   token/context/attach definitions plus the shared macros -- work out the
   dependency order first (which shared subtables each functional file
   needs: `r6b_disp8`/`r6w_disp8`, the reglist push/pop chain, `eab_*`/
   `eaw_*` addressing-mode subtables, register attaches) and place them
   before any `@include`, per lesson 1 above. Wire in real `@include`s for
   `h8539f-mem.sinc`/`-logic.sinc`/`-arith.sinc`/`-bit.sinc`/`-branch.sinc`.
   Delete the old in-place constructors these now replace. Single recompile
   against the assembled result.
8. **Install + full regression test.** Only now -- copy the assembled
   result into the real Ghidra language directory (see "do i need to copy
   the files" answer below for the exact path), run a fresh ROM import +
   full auto-analysis per "Migration steps" below. This is the first point
   real (not just compile-time) correctness gets checked against everything
   done since the refactor started.
9. **Independent, can happen anytime, not blocking anything above:**
   - `CP_ctx` context variable + mirroring `setContextVar` calls in
     `h8539_ecu_master_setup.py` (narrowed scope confirmed during table
     verification: `CP` only affects far-jump target address resolution,
     not instruction dispatch/decoding).
   - Interrupt-vector-table marking and ROM-header-scraper page-2 scan
     range (see "Deferred, non-structural items" below).

### Why

`h8539f.slaspec` grew bug-by-bug against a base structure that was wrong from the
start: an `opcode47`-gated, subtable-heavy MAP dispatch model that doesn't match how
the real H8/500 decoder (`ana.cpp`'s `h8500_ana()`) actually works, plus several
generations of patch-on-patch fixes (`map4_page`/`map3_page`/`m4full` subtables,
inline `Rn_banked`/`mode`-gated one-offs, dead top-level `opcode=16/18/19`
constructors) layered on top of each other. The result is a single ~3000-line file
where every new instruction risks colliding with leftover machinery from an earlier,
abandoned theory of how dispatch works. The bug log in the previous version of this
README is the evidence: most entries are "wrong premise, superseded" corrections to
earlier corrections, not new ISA coverage.

Rather than continue patching that structure, the base is being rebuilt against two
official/reference Ghidra modules that already solve this class of problem cleanly,
both present in `source\`:

- **Z80** (`source\Z80\data\languages\z80.slaspec`) -- official NSA Ghidra module.
  The Z80 ISA has the same shape as H8/500's MAP3-MAP6: a small set of escape/prefix
  bytes (`CB`/`ED`/`DD`/`FD`) that redirect decoding into a secondary opcode space.
  Verified directly against the live file (not assumed): Z80 does **not** flatten
  every prefixed opcode into its own literal constructor, and it does **not** use a
  separate named dispatch subtable either. It does something simpler than both:
  chain one literal `op0_8=0xNN` constraint for the escape byte itself, then decode
  the byte(s) that follow with ordinary bitfield constraints on the *same* token
  type, exactly as if the escape byte weren't there. E.g. the whole `CB`-prefixed
  bit-op space (192 of 256 opcodes) is three constructors:
  ```sleigh
  :BIT bits3_3,reg0_3  is op0_8=0xcb; op6_2=0x1 & bits3_3 & reg0_3 { ... }
  :SET bits3_3,reg0_3  is op0_8=0xcb; op6_2=0x3 & bits3_3 & reg0_3 { ... }
  :RES bits3_3,reg0_3  is op0_8=0xcb; op6_2=0x2 & bits3_3 & reg0_3 { ... }
  ```
  `bits3_3`/`reg0_3`/`op6_2` are plain bitfields sliced from the second byte --
  only the prefix byte is a literal. A handful of `DD`/`FD`/`ED` instructions (the
  `IX`/`IY`/16-bit-load/arithmetic ones) do end up as one-off literal second bytes,
  but that's because those particular opcodes don't share a regular bit-grouping,
  not because the model demands literal enumeration everywhere. No `map4_page`-style
  named subtable is inserted between the prefix and the field decode at any point.
  Also confirmed directly: Z80 does **not** split into `.sinc` files at all --
  `z80.slaspec` is one 2583-line file with no `@include`. Its dispatch model is
  lean enough (no subtable layer, no per-instruction abstraction) that it stays
  manageable as a single file even with ~250 instructions. That's a separate
  property from the H8/300 point below, not something the escape-byte model
  requires.

  This is the actual model for H8/500's MAP3-MAP6: pin the escape byte with one
  literal constraint, then decode the following byte(s) with ordinary field
  constraints matching `ana.cpp`'s real bit groupings (`m4op`/`m4sz`/`m4Rn`-style,
  which `h8539f.slaspec` already has the right instinct for) -- with **no**
  intermediate `map4_page`/`map3_page` subtable layer, and with the field widths
  and groupings corrected to actually match `A4tail`/`A3`/`A5tail`/`A6` instead of
  the mismatched 16-wide/8-wide splits the old file had.
- **H8/300** (`source\ghidra-h8-300\`) -- community module, not officially merged,
  but a directly relevant structural reference: it's a much closer size/complexity
  analog to `h8539f.slaspec` than Z80 is, since both H8/300 and H8/500 carry a lot
  of addressing-mode variants per instruction (the real source of bloat in these
  files, more than escape-byte dispatch). Verified directly against the live
  source: `h8-insn-300.sinc` keeps shared tokens/meanings/macros in the top file
  and pulls instructions in via `@include` of four files split by **functional
  area**, not by encoding group:
  ```sleigh
  @include "h8-insn-300-arith.sinc"
  @include "h8-insn-300-bit.sinc"
  @include "h8-insn-300-branch.sinc"
  @include "h8-insn-300-mem.sinc"
  ```
  This is the model for splitting `h8539f.slaspec`, independent of the
  dispatch-model fix above -- see "New base structure" below.

Both source trees are already checked into `source\` specifically so they can be
read directly (via Pulsar's Run-Command / read-file tools) rather than worked from
memory -- every dispatch-shape or file-layout claim in this plan should be
re-verified against the live `.slaspec`/`.sinc` files before being coded against,
the same way `ana.cpp` was used as ground truth for the old bug list.

### New base structure

Split by functional area, mirroring H8/300's `h8-insn-300*.sinc` layout: instructions
are grouped by what they *do*, not by which MAP/prefix byte encodes them. A `mov` and
an `add` that both happen to be MAP4-encoded still belong in different files;
grouping by MAP number instead would scatter related logic (e.g. every `mov` variant,
however encoded) across multiple files for no reason:

```
h8539f.slaspec           -- top only: endian/alignment, address spaces, registers,
                             tokens, context fields, attach tables, shared flag
                             macros, @include list
h8539f-mem.sinc           -- mov/ldc/stc/push/pop and other data-movement forms,
                             across all MAPs and the literal A2tail ranges (mov:l,
                             mov:s, mov:f)
h8539f-arith.sinc         -- add/sub/cmp/mulxu/divxu/addx/subx/adds/subs/neg/
                             shal/shar/shll/shlr/rotl/rotr/rotxl/rotxr/inc/dec,
                             across all MAPs
h8539f-bit.sinc           -- bset/bclr/bnot/btst and related bit-op forms,
                             across all MAPs
h8539f-branch.sinc        -- bcc/bra/jmp/jsr/rts/prts/prtd/trap/rtd and other
                             control-flow forms
h8539f-logic.sinc         -- or/and/xor (register tail-group forms) and
                             andc/orc/xorc (control-register imm8/imm16
                             forms), across all MAPs -- split out as its own
                             file (July 2026) since these are full-width
                             boolean logic ops, not arithmetic (add/sub/mul/
                             div, arith.sinc's scope) or single-bit ops
                             (bset/bclr/bnot/btst, bit.sinc's scope); flagged
                             as an open question during arith.sinc's design
                             pass and resolved here rather than folded
                             silently into either neighbor
```

Each escape/prefix byte (MAP3/4/5/6, and the literal `A2tail` ranges) is still
decoded the Z80 way -- one literal constraint for the prefix, then bitfield
constructors on the following byte(s) matching `ana.cpp`'s real groupings, no
`map4_page`-style dispatch subtable -- but that decoding now lives wherever the
*instruction* belongs functionally, not in a MAP-numbered file. If a single
instruction genuinely has meaningfully different behavior per MAP (rare -- worth
checking against `ana.cpp` case by case) it still lives in one functional file,
just with multiple constructors gated on the different prefix/opcode values.

Whether to keep everything in one file (Z80-style) or split by functional area
(H8/300-style) is a separate decision from the dispatch-model fix -- the Z80
escape-byte model doesn't require a split. Given `h8539f.slaspec`'s size (already
~3000 lines before MAP5 and the MAP4 abs-entry points are even filled in) and its
history of collisions between old and abandoned constructors going unnoticed in one
giant file, the functional split above is the current plan.

### Migration steps

1. **Extract ground truth first -- done.** `h8539f-instruction-table.md`
   (project root) now has the full `A2`/`A2tail` top-level dispatch and all
   four MAP head/tail tables transcribed directly from
   `source\ida-sdk-main\src\module\h8500\ana.cpp`, plus a list of structural
   facts (MAP3/MAP4-chained-into-MAP6, the 8-wide tail-table grouping, the
   `bset`/`bclr`/`bnot`/`btst` register-vs-immediate fork, etc.) and three open
   questions that still need a live-ROM check before `branch.sinc` can be
   written. This table, not `ana.cpp` directly and not the old bug list, is now
   the single source of truth for the `.sinc` ports below.
2. **Stand up the new top-level `h8539f.slaspec`.** Keep the existing register/
   token/context/attach definitions (these were never the problem) but strip out
   every instruction constructor; add the `@include` list for the new `.sinc`
   files (`h8539f-mem.sinc`, `h8539f-arith.sinc`, `h8539f-bit.sinc`,
   `h8539f-branch.sinc`, `h8539f-logic.sinc`, empty stubs to start).
3. **Port instructions from the ground-truth list into the matching functional
   `.sinc` file**, Z80-style for any MAP/escape-byte decoding involved: one
   literal constraint for the escape/first byte, then group the following byte(s)
   into bitfield constructors that match `ana.cpp`'s real table groupings (only
   fall back to a literal second-byte value for genuine one-offs that don't share
   a regular grouping, as Z80 does for a handful of `DD`/`FD`/`ED` instructions).
   Do not port forward any of the old `map4_page`/`map3_page`/`m4full`/
   `Rn_banked`-gated-inline patterns -- rewrite each instruction fresh against the
   ground-truth table, filed under whichever `.sinc` matches what it does
   (`mem`/`arith`/`bit`/`branch`/`logic`), not which MAP encodes it.
4. **Work through the five functional `.sinc` files one at a time** (suggested
   order: `mem` first since it's the largest and most-referenced category, then
   `arith`, `logic`, `bit`, `branch` -- `logic` slots in right after `arith`
   since `or`/`and`/`xor`/`andc`/`orc`/`xorc` share the same
   opcode/CR8-gated tail-group shape `arith.sinc`'s work just settled, so
   it's cheap to do while that shape is fresh, rather than saving it for
   last), porting every instruction in that category regardless of which
   MAP/escape byte encodes it.
5. **Recompile and regression-test after every `.sinc` file lands** (not just at
   the end): `sleigh.bat` compile -> copy `.sla` to the Ghidra install's
   `Processors\h8\data\languages\` -> restart Ghidra -> fresh re-import of the
   RVR ROM into a new project -> full auto-analysis -> diff the error log against
   the previous file's result. This catches structural regressions immediately
   instead of after the whole rewrite is done.
6. **Carry forward only verified-correct fixes** from the old model where they
   represent real ISA behavior confirmed against live ROM bytes (e.g. `tst.b`/
   `tst.w`'s EA-byte-then-opcode_special-then-payload ordering, `mov:f`'s
   `0x80-0x9F` literal-byte range, the `CR8` valid-index set for `stc`/`ldc`).
   These are ISA facts, not artifacts of the old dispatch model, and should be
   re-expressed in the new style (functional `.sinc`, escape-byte-then-bitfield
   decode) rather than re-discovered.
7. **`CP_ctx` context variable** (see old BUG 8) and the interrupt-vector-table/
   ROM-header-scraper items below are independent of the dispatch rewrite and
   can be picked up in parallel or after, whichever the current ROM error log
   makes higher priority.

### Deferred, non-structural items (carried forward)

These are correctness/tooling gaps independent of the dispatch rewrite above and
don't block it:

- `CP` is not a SLEIGH context variable -- add `CP_ctx = (6,7)` to `contextreg`
  and mirror every `setRegisterValue("CP", ...)` call in
  `h8539_ecu_master_setup.py` with a matching `setContextVar("CP_ctx", ...)`.
- The H8/539F interrupt vector table (`0x10000`-`0x10140`) is not marked as data
  by the setup script; auto-analysis occasionally walks into it as code. Should
  be defined as a `pointer32`/`addr` array before auto-analysis runs.
- The ROM header scraper in `h8539_ecu_master_setup.py` only scans page 1
  (`0x0 .. MUT_OFFSET`); page-2 (`0x20000+`) inline tables need a second scan
  range.
- `prtd` (far return with immediate stack pop) decodes correctly but stack purge
  accounting isn't modelled -- would need a plugin equivalent to Ghidra's
  `X86FunctionPurgeAnalyzer`.
- The decompiler may report "unable to track spacebase fully for stack" on some
  functions despite `SP24` being declared unaffected in the cspec.
- Some preserved registers (R3-R5, FP) may still show as explicit push/pop in
  decompiler output rather than being recognized as callee-saved.
- `patternconstraints.xml` doesn't include `H8:BE:32:H8539F`, so the
  function-start byte pattern in `patterns.xml` is inactive for H8/539F ROMs --
  verify against real ECU ROM prologues and add the language ID if it matches.

### H8/520 (upstream, unverified)

- `ADC_ADI_vector` in `h8520.pspec` is assigned the same address as `SCI1_ERI_vector`
  (`ram:0x00D0`) -- one is wrong. Needs checking against the H8/520 hardware manual.
- `<default_memory_blocks>` in `h8520.pspec` is commented out -- no RAM block is created
  automatically when loading an H8/520 ROM.

### H8/538F (upstream, unverified)

- `<data_space space="ram" />` is missing from `h8538f.pspec`.
- The RAM block in `h8538f.pspec` is `initialized="true"` spanning `0x0000` for `0xF000`
  bytes, covering code space rather than on-chip RAM only. Should be uninitialised and
  sized to actual RAM only.
- No peripheral register symbols exist in `h8538f.pspec`. The H8/538 shares the same
  peripheral map as the H8/539F. The full register map from `h8539f.pspec` can be ported
  across, excluding the flash control registers (`FLMCR`, `FLM_EBR1/2`, `FLMER`, `FLMSR`)
  which are 539F-specific (the 538 is EPROM, not flash).

## References

- Hitachi H8/538-539 Hardware Manual (OMC942723072) -- `datasheets\h8539f\H8 538-539.pdf`
- H8/500 Series Programming Manual -- `datasheets\h8539f\H8 500 programming.pdf`
- EcuFlash ROM definitions: https://github.com/EcuFlash/OpenECU (community ROM XMLs)
- Ghidra Z80 module (official) -- `source\Z80\data\languages\z80.slaspec`
- Ghidra H8/300 module (community) -- `source\ghidra-h8-300\`
- IDA SDK H8/500 module (ground truth opcode tables) --
  `source\ida-sdk-main\src\module\h8500\ana.cpp`
- GNU binutils `as` H8/500 machine-dependent reference (independent opcode/
  addressing-mode cross-check, incl. legend of which mnemonics do/don't take
  an EA operand) -- https://www.sourceware.org/binutils/docs-2.10/as_8.html
  (section 8.7.5)
