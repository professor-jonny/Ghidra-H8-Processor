# Changelog

All notable changes to the Ghidra H8/500 Processor Module are recorded here.

---

## [Unreleased]

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
