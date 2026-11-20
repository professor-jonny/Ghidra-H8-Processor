# sci1_colon_frame_dispatch jump table, spSegment emulation, flash_region_classify_table (condensed 2026-11-17)

Condensed from the 533-line original (`..\H8-review-archive\review9.md`, 2026-08-09 and follow-ups). The first-session premises "three callers are orphaned outside any function" and "DP is an unknown per-call-site value, which blocks recovery" were OVERTURNED by the file's own follow-up sessions and are not repeated below.

## 1. The jump table in sci1_colon_frame_dispatch (0x20664): characterised, static ceiling reached

- The code: `add:q.b #-1,R1; extu.b R1; shll.w R1` (index = (cmd-1)*2), then `mov:g.w @(-0x6d2:16,R1),R1` (the banked load at 0x206c3), `sub.w 0xda0,R1`, `jmp @R1` at 0x206cb.
- Three callers (0x20240, 0x20320, 0x2033d), all `bsr`, all inside `sci1_boot_cmd_dispatch` (entry 0x2016e). They looked orphaned only because that function's stored body had been truncated at 0x201be (a real `rts` reached by internal back-branches). FIXED: deleted and recreated with disassemble-first; body grew 80 -> 301 bytes (0x2016e-0x2036c) and now holds all three call sites plus the boot command dispatch (flash erase, IHEX colon frames, checksum, security-seed handshake). Plate comment added.
- Page registers: R0-R3 are based via DP, R4/R5 via EP, FP/SP via TP (file's own finding; applies to any banked-load work in this ROM). `sci1_boot_cmd_dispatch` writes EP only; DP is never written on this path.
- DP traced to reset: `ldc.b 0x0,DP` at 0x15182 (reset entry 0x1517c), once, before the bit-7 check that branches to the bootloader (`pjmp @0x20000`) or runtime (`pjsr @0x20a80`). No function on the bootloader path writes DP. So DP = 0 for all three callers.
- With DP = 0 the table read addresses are 0xfb2c (param 0), 0xf92e (param 1), 0xf930 (param 2). They lie in the declared RAM segment (0xee80-0xffff), which has no bytes in the static image (read_memory fails). Xrefs show only the one read at 0x206c3 and nothing writes them. Conclusion: the table contents are populated at runtime or by an external SCI1 programming host; static recovery cannot go further. (The "SCI1 host writes them" story is plausible, not proven.) Same class as the `sci1_boot_cmd_dispatch` RAM-pointer mechanism in `review8.md`.
- All static methods tried first were negative: xrefs and byte-pattern searches for 0xf92e, 0xfb2a, 0xfb2c, 0xda0 (the 0xda0 hits were unrelated calibration regions); disassembling a flat reading (0x2f92e) gave unrelated code.

## 2. Emulation findings (reusable)

- The built-in `emulate_function` tool fails on this H8 target ("Undefined register: ESP"); it seeds an x86 register unconditionally. Manual `EmulatorHelper` scripting works.
- `spSegment` is a deliberate pcodeop backing `<segmentop>` in `h8539f.pspec`, not a Sleigh bug: `spSegment(bankReg, offset) = (zext(bankReg) << 16) | zext(offset)`. It is used for every push/pop, banked EA, call/return and link/unlk. The stock emulator has no behaviour for it, so a `registerCallOtherCallback` handler is needed (one was written and verified on a single-instruction test and a 28-step run; the snippet was NOT saved as a script, so it must be re-derived or saved from the original file).
- `run_script_inline` failed with "class not found" in later sessions; the answer was computed by hand from the confirmed p-code instead.

## 3. flash_region_classify_table (0x20a14): decoded and typed, consumer NOT found

- 16 rows x 6 bytes = 96 bytes (0x20a14-0x20a73), FF-padded after. Row = `[00][hi][lo][00][hi][lo]`, two 24-bit fields (region_base, size_mask), low byte implied 0x00.
- Rows 9-16: 0x02c000, 0x028000, 0x024000, 0x020000, 0x01c000, 0x018000, 0x014000, 0x010000, i.e. the 0x4000-aligned flash sector boundaries across 0x10000-0x30000, with power-of-2-minus-1 masks for 16 KB regions. Rows 1-8 use a 0x200 stride over 0x013000-0x013e00 (near the fixed-point math library at 0x14000-0x1450b); purpose not identified.
- Applied `FlashRegionClassifyEntry[16]` (dry run confirmed an exact 96-byte fit), labelled `flash_region_classify_table`, decompiler pre-comment holds the decode.
- Consumer search came up empty: xrefs, byte patterns for 0x20a14, and `analyze_data_region` all return nothing. `sci1_boot_flash_addr_range_validate` (0x20461) is NOT the consumer (flat 32-bit range checks, no table walk). The code just before the table is `flash_vpp_pulse_handshake_echo_verify`'s own epilogue, not a table walker.

## Open

- Check `flash_erase_sectors` (0x2080c) and `flash_erase_sector_loop` (0x2093c) as consumers before calling `flash_region_classify_table` dead data.
- Purpose of rows 1-8 of the table.
- Save a working `spSegment` emulation callback as a script under `ghidra_scripts` if emulation is needed again.
