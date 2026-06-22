# H8/539F Ghidra Processor Module — Project Handoff

## Goal

Build (or finish) a Ghidra processor module for the Hitachi H8/539F, accurate enough to
disassemble and decompile real Mitsubishi ECU ROMs (RVR engine/transmission, Evo5 engine),
so we can trace the inter-ECU UART communication protocol and ultimately determine what it
would take to make an Evo5-based engine ROM talk to the RVR's factory automatic transmission
ECU (TCU).

This document is the handoff of everything established so far, plus a concrete task list,
so the Ghidra-module work can continue locally with Pulsar MCP / Ghidra MCP while I keep
working on analysis that doesn't require compiling/running Ghidra.

---

## 1. Background — why we need this

Two physical facts, established by direct binary analysis (not guesswork):

- The RVR's engine ECU and transmission ECU (TCU) are **separate H8/539F chips with no shared
  memory** — they only talk over a serial UART (SCI) link.
- Comparing SCI register init code across three ROMs:

  | Register | Evo5 (stock) | RVR engine (5-MT) | RVR transmission (4-AT) |
  |---|---|---|---|
  | SCI1 BRR (`0xFEC9`) | `0xFF` | `0xFF` | `0x1F` |
  | SCI2 BRR (`0xFED1`) | `0xFF` | `0xFF` | `0x07` |
  | SCI3 SCR (`0xFEC2`) | `0xB0` | `0xB0` | `0x70` |

  The Evo5 ROM's serial setup is **byte-for-byte identical** to the RVR's own 5-speed manual
  ROM (173 contiguous identical bytes around the init routine) — i.e. the Evo5 ECU was never
  built to talk to a TCU, same as a manual-transmission RVR.

- Comparing all 80 interrupt vectors (4 bytes each, `0x0000`–`0x013C`) between the RVR engine
  ROM and RVR transmission ROM: **vector slot #53 is populated in the transmission ROM and
  points to the generic "unused" stub in the engine ROM.** Per the official Hitachi H8/500
  exception vector table (recovered from `ghidra-h8-500/NOTES.TXT`, see §3 below),
  **vector 53 = SCI1.RXI** (receive-complete interrupt). This lines up exactly with what we
  found by hand: the transmission ECU has a receive handler that the engine ECU (in both RVR
  manual and stock Evo5 form) simply does not have installed.

- Hand-tracing that handler (at file offset `0x16267` in the RVR transmission ROM) without a
  real disassembler, by eyeballing H8/500 opcode bytes:
  - It clears what look like SCI status-register flags, then stores received bytes into RAM at
    `0xF25C` and `0xF25E`.
  - A third RAM cell, `0xF3A2`, is read in **11 separate places** scattered through ordinary
    main-loop code (not clustered near the interrupt) — consistent with a **packed status/flag
    byte** that multiple parts of the shift-control logic consult continuously, not a one-off
    diagnostic value.
  - Four of those read-sites share an identical "read byte → test one bit → call a shared
    subroutine with a different per-bit target" shape, testing bits 0, 2, 3, 5 of that byte.

**This hand-tracing is the ceiling of what's safely inferable without a real disassembler.**
The bit-level interpretation (which bit means "brake pressed," "kickdown," etc.) is informed
guesswork from code shape, not verified. We need an actual Ghidra disassembly + decompilation
to go further reliably — particularly to find what the four per-bit subroutines *write to*,
which would tell us concretely which TCU behaviors (lock-up, line pressure, gear hold) depend
on which incoming bit.

---

## 2. ROM files in play (for reference)

| File | Role | Notes |
|---|---|---|
| `RVR_1998_x3_4g63t_21000011_md352553.hex` | RVR engine ECU, 5-speed manual | 128KB, H8/539F |
| `RVR_1998_x3_w4a51_21451005_md352554.hex` | RVR transmission ECU (4-AT/TCU) | 128KB, H8/539F |
| `22580006_EVO5_Stock.hex` | Evo5 engine ECU, stock | 128KB, H8/539F |

Address convention used throughout our analysis: **XML/logical address = file byte offset +
`0x10000`.** Verified directly (ROM ID bytes `21 00 00 11` sit at file offset `0x021A`, which
is XML address `0x1021A`, matching each ROM's own `<internalidaddress>` metadata).

Vector table: **4 bytes per vector** (not 2), spanning file offsets `0x0000`–`0x013C` (80
vectors). Confirmed by reading the table as big-endian 32-bit words and checking that all
values land inside the 128KB ROM range as plausible code pointers; reading as 16-bit words
does not.

---

## 3. Source material already gathered

Three existing community/vendor projects were located and pulled into the project folder
(see your local copy / what I could clone):

### a. `OZVR4/Ghidra-H8-Processor` (github.com/OZVR4/Ghidra-H8-Processor)
- Explicitly targets H8/539F ("used by Mitsubishi Motors in their ECUs").
- **Status: stub.** `data/languages/h8.slaspec` defines only ~15 instruction rules
  (`mov.i.w`, `mov.e.b`, `pjsr`, `jsr`, `prts`, `and.w`, `nop`, `sleep`, `link`, `unlk`,
  `extu.b`, `cmp.i.w`, `cmp.e.b`). At least two rules look buggy on inspection (`unlk` pushes/
  pops in the wrong order vs. its own pairing with `link`; `and.w` has a body with no `is`
  constraint, won't compile or won't match anything). Useful as a sanity cross-check, **not**
  a usable foundation on its own.

### b. `c4ashley/ghidra-h8-500` (github.com/c4ashley/ghidra-h8-500)
- Contains **two** language definitions:
  - `h8538f.slaspec` — 39 lines, essentially an empty placeholder (one instruction: `MOV.W`
    with an empty semantic body). Not usable as-is.
  - `h8520.slaspec` — **1826 lines, ~806 instruction-rule definitions covering 84 distinct
    mnemonics.** This is real, substantial work, forked from an earlier H8/538-focused project
    by the original author ("laboratoryb.org", repo: `git.laboratoryb.org/hurricos/ghidra-h8-500`
    — not yet checked, may be worth pulling directly too since it's described as the most
    actively developed one for H8/538 specifically).
  - Confirmed on inspection: correctly implements **24-bit "Maximum/Advanced mode" addressing**
    for `pjmp`/`pjsr` (page jump/jsr with proper `CP` register page handling and stack-push
    semantics) — this is exactly the addressing mode our ROMs use (vector table holds 4-byte/
    24-bit-capable pointers, e.g. vector 0 → `0x0001517C`, clearly a 24-bit code address, not
    16-bit). This is the strongest sign this base is compatible with the H8/539F's actual mode
    of operation.
  - Implements proper register-list bitfield decoding for `stm`/`ldm` (used in function
    prologues/epilogues — matches the `PATTERNS.TXT` prologue/epilogue patterns below).
  - `PATTERNS.TXT` in this repo documents known byte patterns for function prologues,
    epilogues, and return instructions — directly useful as ground truth:
    ```
    Function prologue (FP-based frame):
      0x17 0x..       link     #..:8
      0x12 0x..       stm      (..), @-SP
      0xaf 0x0d       add:q.w  #-2, SP
      0xd7 0x9c       stc.b    EP, @SP
      0xe7 0x01 0x9d  stc.b    DP, @(0x1,SP)

    Function epilogue (FP-based frame):
      0xd7 0x8c       ldc.b    @SP,EP
      0xe7 0x01 0x8d  ldc.b    @(0x1:8,SP),DP
      0xaf 0x09       add:q.w  #2,SP
      0x02 0x20       ldm.w    @SP+,(R5)
      0x0f            unlk     FP
      [return]

    Return patterns:
      0x11 0x19         prts
      0x11 0x14 0x..     prtd  #..:8
      0x11 0x1c 0x....   prtd  #..:16
      0x19               rts
      ... or rtd #..:8 / #..:16
    ```
  - `NOTES.TXT` in this repo gives the **official Hitachi H8/500 exception vector table**
    (this is what confirmed vector 53 = SCI1.RXI):
    ```
    0  Reset                          32 IRQ0         48 SCI1.ERI
    1  -- (reserved)                  33 IRQ1         49 SCI1.RXI
    2  Invalid Instruction            34 IRQ2         50 SCI1.TXI
    3  DIVXU (zero divide)            35 IRQ3         51 --
    4  TRAP/VS                        36 IRQ4         52 SCI1.ERI   <- note: this list has
    5–7  reserved                     37 IRQ5         53 SCI1.RXI      SCI1 ERI/RXI/TXI twice
    8  Address error                  38 IRQ6         54 SCI1.TXI      at 48-50 AND 52-54 in
    9  Trace                          39 IRQ7         55 --           the raw notes; this needs
    10 --                             40 FRT1.ICI     56 SCI2.ERI      reconciling against the
    11 NMI                            41 FRT1.OCIA    57 SCI2.RXI      real H8/539F datasheet
    12–15 reserved                    42 FRT1.OCIB    58 SCI2.TXI      vector map (H8/539 has
    16–31 TRAPA (x16)                 43 FRT1.FOVI    59 --            SCI1/SCI2/SCI3, possibly
                                       44 FRT2.ICI     60 ADC.ADI       numbered differently
                                       45 FRT2.OCIA    61–63 --         from the H8/520 the notes
                                       46 FRT2.OCIB                     describe — TASK: confirm
                                       47 FRT2.FOVI                     against H8/538-539
                                                                        hardware manual §interrupt
                                                                        controller, not the 520's)
    ```
    **Important caveat already flagged to self:** this vector list is for the **H8/520**
    (per the repo's own framing), not the H8/539F directly. H8/520 and H8/539F share the same
    H8/500 CPU core and instruction set, but **peripheral vector assignments can differ
    between H8/500 family members** depending on which peripherals are present and in what
    quantity (H8/539F has more timer/ATU channels and 3 SCI channels per `ecurom.idc`'s
    register definitions, e.g. SCI1=`0xFEC8`, SCI2=`0xFED0`, SCI3=`0xFEC0`). The vector-53
    match against our own empirical finding is a very strong signal, but **should still be
    double checked against the actual H8/538/539 Hardware Manual's interrupt vector table**
    (PDF already located, see §5) before treating it as gospel.

### c. `HexRaysSA/ida-sdk`, `src/module/h8500/` (github.com/HexRaysSA/ida-sdk)
- This is Hex-Rays' **actual shipped IDA Pro analyzer source** for the H8/500 family
  (`ana.cpp` 650 lines, `ins.cpp`/`ins.hpp` mnemonic tables, `out.cpp` formatting, `emu.cpp`
  emulation/xref generation, `reg.cpp`).
- `ana.cpp` contains the **authoritative byte-level opcode dispatch tables** (`A2`, `A3`,
  `A4`, `A5`, `A6` arrays + tail arrays), e.g.:
  ```
  A2[0x00] = nop      A2[0x10] = jmp      A2[0x20-0x3F] = Bcc (16 conditions, two banks)
  A2[0x02] = ldm      A2[0x12] = stm      A2[0x40-0x47] = cmp.e   A2[0x48-0x4F] = cmp.i
  A2[0x03] = pjsr      A2[0x13] = pjmp     A2[0x50-0x57] = mov.e   A2[0x58-0x5F] = mov.i
  A2[0x08] = trapa    A2[0x18] = jsr
  A2[0x09] = trap_vs  A2[0x19] = rts
  A2[0x0A] = rte      A2[0x1A] = sleep
  A2[0x0E] = bsr       A2[0x1E] = bsr
  A2[0x0F] = unlk     A2[0x1F] = link
  ```
  and a second-level table (`A3`/`A4`/`A5`/`A6`, selected by an `0x80`+ prefix byte) covering
  `add/sub/and/or/xor/cmp/mov/bset/bclr/bnot/btst/addx/subx/mulxu/divxu/ldc/stc/xch` etc.
- `ins.hpp` gives the complete, authoritative mnemonic enum/list — useful as the master
  checklist to confirm the slaspec covers everything.
- This is **ground truth from a commercial disassembler vendor**, the best cross-check
  available without buying IDA itself.
- **This is the piece to lean on hardest when resolving any disagreement** between
  `h8520.slaspec`'s rules and what a byte sequence "ought" to decode as.

### d. Not yet obtained — blocked on my end
- `codeberg.org/shiz/ghidra-h8-300` (Hitachi H8/300 series — a *different*, simpler H8 family,
  not H8/500, but may still have useful generic Ghidra-H8-module scaffolding/build setup).
  My sandbox's network egress allowlist blocks `codeberg.org` entirely (returns a 403 with
  `x-deny-reason: Host not in allowlist`). **You'll need to pull this one yourself** and drop
  it in the project folder if you want it considered.
- The original upstream this all forked from: `git.laboratoryb.org/hurricos/ghidra-h8-500`
  (mentioned in `c4ashley/ghidra-h8-500`'s README as "still under active development... focuses
  on the H8/538"). Worth pulling directly — may be ahead of the fork we have.

---

## 4. What I can keep doing without Ghidra installed

I don't have Ghidra, `sleigh`, or any H8/500 emulator in my sandbox, so I can't compile or
test-load a processor module. What I *can* usefully do in parallel, and will keep doing:

1. **Rule-by-rule diff of `h8520.slaspec` against the IDA SDK's `ana.cpp` opcode tables** —
   going through each of the ~84 mnemonics, checking the slaspec's bit-pattern constraints
   against IDA's dispatch tables, flagging mismatches or gaps (e.g. anything in `ins.hpp`'s
   mnemonic list that has no corresponding slaspec rule at all).
2. **Draft the H8/539F-specific `.pspec` / `.cspec` / `.ldefs`** (currently only H8/520 variants
   exist), pointing at the same instruction `.sla`, with H8/539-correct memory map basics
   (128KB ROM at the right base, RAM region, I/O register region).
3. **Convert `ecurom.idc`'s `H8RegisterNames()` function into a Ghidra-importable peripheral
   register map** — it already has every SCI/timer/ADC/port register address and name for the
   H8/539F hand-mapped (e.g. `0xFEC8 SCI1_SMR`, `0xFEC9 SCI1_BRR`, `0xFECA SCI1_SCR`,
   `0xFECD SCI1_RDR`...), which is exactly what Ghidra needs to show `SCI1_RDR` instead of a
   bare address in the decompiler.
4. **Propose specific `.slaspec` patches** once you report back compile errors or obviously-
   wrong disassembly for known regions (we have several known-good anchor points to validate
   against — see §6).

---

## 5. Reference documents already located

- Hitachi/Renesas **H8/538, H8/539 Hardware Manual** (OMC942723072) — PDF mirror found at
  `https://evoecu.logic.net/mirror/cpudocs/h8539f/H8%20538-539.pdf`. This is the primary
  source to confirm the *real* H8/539F interrupt vector table (resolving the §3 caveat above),
  on-chip register addresses, and electrical/addressing mode details.
- H8/500 Series Programming Manual — referenced by the hardware manual for full CPU/ISA
  details; not yet located/downloaded, worth finding (likely same `laboratoryb.org` documents
  archive referenced in `c4ashley`'s README, e.g.
  `downloads.laboratoryb.org/insight/documents/H8/H8_500_programming.pdf`).
- `ecurom.idc` (already in our project files) — IDA auto-disassembly script written for these
  exact Mitsubishi ROMs; contains the full H8/539F peripheral register name map and known
  library-function addresses (e.g. table-lookup, axis-lookup, multiply/divide helpers) that
  should be ported into the Ghidra module as default symbols once a working disassembly exists.

---

## 6. Known-good anchor points for testing the module

Once a processor module loads in Ghidra, these are concrete, already-verified locations to
sanity-check the disassembly against (cross-checked manually, not yet via real disassembler):

| ROM | File offset | What's there | Expected shape |
|---|---|---|---|
| RVR transmission | `0x0000`–`0x013C` | Interrupt vector table, 80× 4-byte entries | All values should resolve to valid code addresses inside the 128KB ROM |
| RVR transmission | `0x16267` | SCI1 RXI handler (vector 53) | Should start with status-flag-clearing ops, then stores to RAM `0xF25C`/`0xF25E` |
| RVR transmission | `0x07C9F`, `0x07D1C`, `0x07DFA`, `0x07F6A`, `0x0803D`, `0x08133`, `0x08207` | Main-loop bit-tests of RAM `0xF3A2` | Each should read the byte, test one bit (0/2/3/5 seen), then call a shared subroutine — confirm via real decompiler what each target writes |
| RVR engine (MT) | `0x06520`–`0x06560` | SCI register init (BRR/SMR/SCR writes) | `SCI1 BRR=0xFF`, `SCI2 BRR=0xFF`, `SCI3 SCR=0xB0` |
| RVR transmission | `0x067E0`–`0x06820` | SCI register init | `SCI1 BRR=0x1F`, `SCI2 BRR=0x07`, `SCI3 SCR=0x70` |
| Evo5 stock | `0x06530`+ | SCI register init | Byte-identical to RVR engine ROM's init block (173-byte identical run) |
| All three ROMs | `0x021A` | ROM ID (4 bytes) | RVR engine: `21 00 00 11`; RVR trans: `21 45 10 05`; Evo5: `22 58 00 06` |

If the module disassembles these regions into something that doesn't match the expected
shape above, that's a real bug to report back, not a "looks plausible" judgment call.

---

## 7. Concrete next steps (suggested order)

1. Set up the Ghidra module project locally with Pulsar MCP / Ghidra MCP.
2. Pull in the three sources above (OZVR4, c4ashley/h8520, IDA SDK h8500) plus the two
   not-yet-obtained ones (codeberg h8-300, laboratoryb.org upstream) into the project folder.
3. Share the project folder / give me read access so I can do the rule-by-rule diff against
   the IDA opcode tables directly against your actual files rather than my cached copies.
4. I draft: H8/539 `.pspec`/`.cspec`/`.ldefs`, the peripheral register map from `ecurom.idc`,
   and a first-pass diff report of slaspec-vs-IDA-tables discrepancies.
5. You compile (`sleigh`) and load against one of the three ROMs; check the anchor points in
   §6.
6. Iterate: you report compile errors / disassembly that doesn't match an anchor point, I
   propose the specific slaspec fix, repeat.
7. Once disassembly is trustworthy at the anchor points, use Ghidra's decompiler + xrefs to
   properly trace: the four subroutines called from the `0xF3A2` bit-tests (what do they
   write?), and the full SCI1 RXI → main-loop data path, to get a real, verified answer on
   what the TCU communication protocol actually carries.
