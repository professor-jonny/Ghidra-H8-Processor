## h8539pattern.xml — verified anchors and known caveats

Verified against `h8539f-branch.sinc` (source of truth) and confirmed present in the
RVR_1998_x3 test ROM via raw byte-pattern search.

### Anchors currently in h8539pattern.xml (all confirmed correct)
| Anchor bytes | Instruction | Notes |
|---|---|---|
| `0x17 ..` | `link FP,#s8` | FP-frame prologue, 8-bit displacement |
| `0x1F ..` | `link FP,#s16` | FP-frame prologue, 16-bit displacement |
| `0x12 ..` | `stm (regs),@-SP` | register-save prologue |
| `0x11 0x19` | `prts` | far return — the workhorse anchor, ~530+ hits, fires `funcstart after=data` |
| `0x11 0x14 ..` | `prtd #s8` | far return, 8-bit disp |
| `0x11 0x1C .. ..` | `prtd #s16` | far return, 16-bit disp (2-byte immediate, not 1) |

### Deliberately NOT anchored
- **`0x19` (`rts`) alone.** Single-byte anchor, extremely high false-positive rate
  against arbitrary code/data bytes. Only safe to use as a manual/report-only search,
  never as a `funcstart` trigger. Checked this ROM specifically: `unlk` (`0x0F`)
  immediately followed by bare `rts` (`0x0F 0x19`) — **zero occurrences**. This
  compiler always uses the far-return convention (`prtd`/`prts`), even after an
  FP-frame teardown, so there was nothing to gain from an `unlk+rts` anchor either.
- **`0x0F` (`unlk`) alone or `0x0F 0x11 0x19` (`unlk`+`prts`).** Real and common
  (172 hits in the RVR test ROM) but fully redundant with the existing `0x1119`
  anchor — doesn't catch anything `prts` alone doesn't already catch. Not worth
  adding.

### Known limitation even when correctly wired
`Function Start Search` in Ghidra only scans bytes that are still **undefined** at
the moment it runs its one pass. If the disassembler/non-return analyzer sequence
temporarily walks *through* a `prts` before recognizing it as non-returning, the
bytes just after it can end up disassembled-but-orphaned (valid instructions, no
owning function, zero xrefs) rather than staying undefined — and the pattern search
will silently skip them, pattern file working correctly or not.

Symptom: a handful of addresses that sit right after a `prts`/`stm`/`link FP` don't
get a function created even on a fresh auto-analysis, e.g. (from the RVR test ROM,
pre-fix): `0x15A6C, 0x16128, 0x164F8, 0x1677C, 0x167C5, 0x16F53, 0x17136, 0x1A146,
0x1A2D0, 0x208C6, 0x20910, 0x20992`.

Confirmed root cause: two bugs stacked on top of each other, both now fixed.
1. `patternconstraints.xml` never wired `h8539pattern.xml` to the
   `H8:BE:32:H8539F` language ID (it only pointed `H8:BE:16:H8520Max` at the older
   `patterns.xml`).
2. Both files lived in `h8/data/languages/`. Ghidra's pattern loader
   (`ghidra.app.analyzers.Patterns`, used by `FunctionStartAnalyzer`) only scans a
   hard-coded `data/patterns/` subdirectory of each module root
   (`DATA_PATTERNS_SUBDIR = "data/patterns"`) — confirmed against every stock
   processor module (x86, ARM, PowerPC all keep `patternconstraints.xml` under
   `data/patterns/`, never `data/languages/`). Because of this, `Function Start
   Search` never registered as an applicable analyzer for `H8:BE:32:H8539F` at
   all — it wasn't just failing silently, it was completely absent from the
   Analysis Options analyzer list, with no log entry (unlike e.g. `FidAnalyzer`,
   which explicitly logs "No FID Libraries apply for language ..." when it
   doesn't apply — the pattern analyzer logged nothing because it never even
   attempted to load for this language).

All three pattern files (`patternconstraints.xml`, `h8539pattern.xml`,
`patterns.xml`) now live in `h8/data/patterns/`, matching stock Ghidra module
layout. Fixed 2026 — see git history.

**If addresses like this still turn up after moving the files + module reinstall +
re-analysis**, re-check with `create_function` (dry run) on the address first — if
it succeeds cleanly with a sane body size, it's the orphaned-instruction gap
described above, not a pattern-file problem, and the fix is a manual
`createFunction()` cleanup pass rather than another pattern-file edit.

### Reference: full prologue/epilogue byte notes
See `PATTERNS.TXT` (uploaded reference) for the full FP-frame prologue/epilogue
sequence this pattern file is derived from. All opcode bytes in it were re-verified
against `h8539f-branch.sinc` on 2026-07-09 and are accurate.
