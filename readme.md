# Hitachi H8/500 Processor Module for Ghidra

A Ghidra processor module for the Hitachi H8/500 family, with full support for the
**H8/539F** as used in Mitsubishi ECUs (RVR X3, Evo5, etc.).

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
- MAP3/MAP4/MAP5 dispatch fully implemented (single-operand, bit-op, and immediate-EA
  instruction families), split across `h8539f-arith.sinc`, `h8539f-logic.sinc`,
  `h8539f-mem.sinc`, `h8539f-bit.sinc`, `h8539f-branch.sinc`
- Function-start pattern matching (`h8539pattern.xml`, wired into `patternconstraints.xml`
  for `H8:BE:32:H8539F`) -- auto-detects function starts from compiler prologue idioms
  (`link FP,#imm`, `stm (reglist),@-SP`) and far-return boundaries (`prts`, `prtd`),
  the automated equivalent of the manual "search for 11 19" technique
- Setup script (`h8539_ecu_master_setup_new.py`) marks the interrupt vector table
  (`0x10000-0x1013F`) as data and auto-creates functions at every unique handler address
  it points to, using the vector table itself rather than pattern/byte searching

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
h8539_ecu_master_setup_new.py   (category: MitsubishiECU)
```

The script presents a GUI dialog for each step so you can toggle them individually.
It will:

1. Validate the import base address (aborts with a clear message if wrong), and print a
   ROM signature banner (first 16 bytes) to help tell ROMs apart across sessions
2. Create the on-chip RAM memory block (`0xEE80-0xFFFF`)
3. Set CP/DP/TP context registers over both ROM pages
4. Read the reset vector and create the `entry` function
   - **4b.** Mark the interrupt vector table (`0x10000-0x1013F`) as data, auto-create
     functions at every unique handler address it points to, flag duplicate targets
     that aren't the shared default stub, flag targets outside ROM, and flag any ISR
     whose last instruction isn't `rte`/`sleep`/`rts`/`prts`/`prtd`
   - **4c.** (report only) Scan the ROM for `prts`/`rts` boundaries not already at a
     defined function and print candidate function-start addresses to review manually
5. Test the decompiler -- aborts if it fails so you don't waste time on a broken analysis
6. Run auto-analysis (finds ~600+ functions on a typical ECU ROM)
   - **6b.** (report only) Scan for contiguous undefined-byte gaps (>=16 bytes) left
     after auto-analysis and print them
7. Apply EcuFlash XML table labels (optional -- file browser prompt, ROM ID verified before labelling)
8. Run the ROM header scraper (optional -- MUT table, scaling tables, 2D/3D value tables by byte pattern)
   - **8d.** (report only) Print a count of labeled symbols in page 2 (`0x20000+`) as a
     reminder that the scraper only scans page 1

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

Auto-analysis now uses `h8539pattern.xml` to detect function starts automatically from
compiler prologue idioms and far-return boundaries (`prts`/`prtd`), so most of what used
to require a manual search is found during auto-analysis itself. The setup script's
**Step 4c** also runs an automated version of the manual search below (report only --
it prints candidates rather than creating functions, since a byte scan can false-positive
inside data). If code is still missed after both of those:

- Search Memory (`Search > Memory`) for the byte pattern `11 19` (mnemonic `prts` --
  the far-call return instruction used by most functions). Look for hits not already
  inside a defined function.
- Similarly search for `19` alone (`rts`, near-call return).
- Or check **Step 6b**'s undefined-byte gap report, which lists leftover gaps after
  auto-analysis regardless of what caused them.

## File layout

```
h8\data\languages\
    h8539f.slaspec      -- H8/539F instruction set (SLEIGH source, top-level)
    h8539f-arith.sinc   -- arithmetic instruction family (add/sub/cmp/mulxu/divxu/etc, MAP5)
    h8539f-logic.sinc   -- logic instruction family (and/or/xor/andc/orc/xorc, MAP5)
    h8539f-mem.sinc     -- move/load instruction family (mov/ldc, MAP5)
    h8539f-bit.sinc     -- bit-test/set/clear instruction family
    h8539f-branch.sinc  -- branch/jump/return instruction family (bra, jmp, rtd, prtd, etc)
    h8539f.sla          -- compiled SLEIGH binary (generated by sleigh)
    h8539f.pspec        -- processor spec: peripheral registers, default symbols
    h8539f.cspec        -- compiler spec: calling conventions, stack, global ranges
    h8539pattern.xml    -- function-start byte patterns (prologues, prts/prtd), wired
                            into patternconstraints.xml for H8:BE:32:H8539F
    patternconstraints.xml -- maps each language ID to its pattern file
    h8.cspec            -- shared compiler spec for H8/520 and H8/538F
    h8.ldefs            -- language definitions (all variants)
    h8520.slaspec       -- H8/520 instruction set
    h8538f.slaspec      -- H8/538F instruction set
    h8520.pspec         -- H8/520 processor spec
    h8538f.pspec        -- H8/538F processor spec

test\
    h8539_ecu_master_setup_new.py  -- Ghidra script: full ROM setup with GUI (run this first)
    rvr\                -- example ROM files and EcuFlash XMLs

datasheets\h8539f\      -- Hitachi hardware/programming manuals

source\ida-sdk-main\src\module\h8500\ana.cpp  -- ground-truth opcode reference (IDA SDK)
```

## Known limitations and open work

**`ana.cpp` addressing-mode table** (found this session, keyed on a byte's top nibble, for
the generic operand-decode switch mentioned above):
```
0x60-0x6F: @aa:8, Rn         0xA0-0xAF: Rn, Rn (direct)
0x70-0x7F: Rn, @aa:8         0xB0-0xBF: @-Rn, Rn (predecrement)
0x80-0x8F: mov:f @(d:8,R6),Rn  0xC0-0xCF: @Rn+, Rn (postincrement)
0x90-0x9F: mov:f Rn,@(d:8,R6)  0xD0-0xDF: @Rn, Rn (indirect)
                             0xE0-0xEF: @(d:8,Rn), Rn (disp8)
                             0xF0-0xFF: @(d:16,Rn), Rn (disp16)
```
This matches the slaspec's own `mode` field values (10=direct,11=predec,12=postinc,
13=indirect,14=disp8,15=disp16) nibble-for-nibble -- reassuring, but confirm which
itype/switch actually owns a given byte range before using this table alone to diagnose.

**Working method for the next session (repeat per address):**
1. `ghidra:read_memory` starting a few bytes before the "flow from" address, ~12 bytes.
2. Work out exactly how many bytes the preceding (successfully-decoded) instruction
   consumes, to find which byte the failure actually starts on.
3. Decode that byte both as `mode`(bits4-7)/`sz`(bit3)/`Rn`(bits0-2) and as
   `opcode`(bits3-7)/`Rd`(bits0-2) -- same bits, different field names used by different
   constructor families -- check both interpretations.
4. Cross-reference against `ana.cpp`'s A2/A3/A4/A5(tail) tables and the addressing-mode
   table above.
5. Grep the live `.sinc` files (not just `h8539f.slaspec` -- checking only the top-level
   file gave a false "MAP5 is unimplemented" negative earlier this project) before
   concluding a constructor is missing.
6. Decide: genuine sleigh gap (write a constructor) vs. stale pre-fix analysis data (Clear
   Code Bytes + re-analyze) vs. genuine data region (mark as data, not code).

### Other open items

- **`CP` is not a SLEIGH context variable.** The hardware CP register is set via
  `setRegisterValue("CP", ...)` in the setup script, which works at decompile time, but
  SLEIGH pattern matching can't gate constructors on a register value -- only on context
  variable fields. Instructions folding CP into a 24-bit target address can't resolve
  targets at disassembly time. Fix: add a `CP_ctx` context variable (2 bits) alongside the
  existing `targetBase`/`targetReg` fields, and mirror every `setRegisterValue("CP", N, ...)`
  call in `h8539_ecu_master_setup_new.py` with a matching `setContextVar("CP_ctx", N, ...)`.
  - **Confirmed instance (RVR X3 ROM):** `pjsr @<target>:24` far-call trampolines
    (2-instruction functions of the form `pjsr @X:24; prts`) decompile with the call
    target resolved back to the trampoline's *own* entry address instead of `X`, making
    the decompiler show an infinite self-call (e.g. `FUN_00023397` "calling"
    `FUN_00023397`, `FUN_0002bddb` "calling" itself). The raw disassembly is correct in
    both cases -- `pjsr`'s *display* string is built straight from the 24-bit immediate
    in the encoding, but the decompiler derives the call graph from `pjsr`'s p-code
    export, which appears to mis-resolve/mis-attach the target. Since display and p-code
    come from different parts of the constructor, one can be right while the other is
    wrong, which is exactly what's happening here. Likely the same root cause as the
    `CP_ctx` gap above, or at least in the same `pjsr` p-code template. Any other
    `pjsr ...; prts` trampoline in a loaded ROM should be assumed to have the same
    problem until `CP_ctx` (or the specific `pjsr` export bug) is fixed -- don't trust
    the decompiler's call target for these; check the disassembly's literal operand
    instead.
  - **Second confirmed instance (RVR X3 ROM, 2026-07-09 session):** the switch dispatch
    in `FUN_00028b2f` (`DAT_0001f526`-indexed, 8 cases) uses an indirect jump through a
    table of 16-bit offsets at `0x28b52-0x28b61` (8 entries x 2 bytes). Ghidra's own
    disassembly resolves several of these to `halt_baddata()` (cases 0, 2, 6), and
    `get_function_jump_targets` returns scattered garbage xrefs across totally unrelated
    ROM regions (`0x2800c`, `0x2f490`, `0x21df4`, etc.) instead of real targets -- almost
    certainly the same missing-page/bank-byte problem as the `pjsr` bug above, just hit
    from a register-indirect jump instead of `pjsr`. Manually reconstructing the table by
    reading raw bytes and assuming an implied page byte of `0x02` (the switch's own page)
    gives self-consistent, cleanly-decompiling targets, all landing inside the previously
    -unlabelled gap at `0x28b52-0x28d1a`:
    ```
    case 0: 0x028b62   (confirmed -- clean 6-line handler, decompiles correctly)
    case 1: 0x028b89   (confirmed -- clean 7-line handler, decompiles correctly)
    case 2: 0x028ba8   (predicted from table, not yet created)
    case 3: 0x028c5a   (predicted from table, not yet created)
    case 4: 0x028c78   (predicted from table, not yet created)
    case 5: 0x028c83   (predicted from table, not yet created)
    case 6: 0x028cba   (predicted from table, not yet created)
    case 7: 0x028cc8   (predicted from table, not yet created)
    ```
    Caveat: `create_function` on cases 0/1 produced wildly oversized `body_size` (372B,
    333B) that both linearly overlap the *same* set of downstream addresses -- the
    decompiler correctly prunes each down to a small "unreachable block"-trimmed real
    body, but this means the auto-detected function *boundary* (not just the jump target)
    is unreliable here too, likely because the instruction that should terminate each
    handler isn't decoding as a return either. Don't bulk-apply `create_function` across
    the remaining 6 entries without first manually finding each handler's true end (e.g.
    disassemble narrow ranges between consecutive table entries) or the function DB will
    end up with overlapping bodies.
  - Also note: the prior XML export (`RVR_1998_x3 4g63t 21000011 md352553.hex.xml`) has
    its own guesses for two of this switch's targets -- `caseD_1` at `0x2800c` and
    `caseD_0` at `0x2f490` -- both wrong (same root cause, different mis-resolution). The
    XML is generally reliable when its declared function size matches what fresh
    disassembly independently produces, but should not be trusted blindly around any
    indirect jump/call.
- The ROM header scraper in `h8539_ecu_master_setup_new.py` only scans `0x0 .. MUT_OFFSET`
  (page 1). Embedded calibration/lookup tables that appear inline in page 2 code
  (`0x20000+`) aren't reached by the current scan range. Scraper needs a second range
  covering page 2. **Step 8d** prints a page-2 labeled-symbol count as a reminder of
  this gap, but doesn't fix it.
- `prtd` (far return with immediate stack pop) decodes correctly, but stack purge
  accounting isn't modelled -- functions using `prtd #n` to clean caller-pushed arguments
  will show slightly wrong stack depth in decompiler output. Would need a plugin
  equivalent to Ghidra's `X86FunctionPurgeAnalyzer`.
- The decompiler may report "unable to track spacebase fully for stack" on some functions
  despite `SP24` being declared unaffected in the cspec, which can cause local variables to
  be missed or misassigned.
- Some preserved registers (R3-R5, FP) may still appear as explicit push/pop in decompiler
  output for functions using them as general-purpose callee-saved registers.

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
