METHODOLOGY / RECIPE (added 2026-07-22, distilled from what's actually
worked across sessions -- read this first, especially when starting the
same kind of investigation on a different ECU/ROM)
============================================================
Goal of this whole document: fully name and document every MUT RequestID,
dispatcher command byte, RAM flag, and physical output pin on this ECU so
the result can become a reusable, shareable signature applicable to other
Mitsubishi H8/500-family ECUs, not just this one ROM.

WHAT HAS RELIABLY WORKED:

1. Prefer tracing FORWARD FROM REAL HARDWARE over backward from assumed
   command semantics. Command-byte/RAM-flag chains (e.g.
   sci1_meta_cmd_dispatch_c0_ff's f510/f512/f516 bits) very often terminate
   in further internal RAM state machines with no confirmed physical
   meaning. Starting instead from confirmed hardware registers -- H8 port
   data registers P1DR-PCDR (0xfe80-0xfe97), SCI1/2/3 UART registers
   (0xfec0-0xfed5), timer registers (0xff2x+) -- and tracing BACKWARD to
   find their writers is far more likely to land on something with a real,
   nameable physical identity (a relay, a solenoid, a lamp). See the
   "PHYSICAL OUTPUT PIN TRACE" section below for the method that produced
   the first confirmed command-byte-to-physical-pin chain in this project.

2. ALWAYS confirm you have a function's true ENTRY POINT before commenting
   or labeling. search_byte_patterns matches raw bytes anywhere in the ROM,
   including mid-function -- it does NOT return function boundaries. Call
   get_function_by_address on every hit before treating it as "the
   function". Plate comments silently fail (or attach nowhere useful) if
   set on a non-entry address -- verify with a decompile/re-read after
   every batch_set_comments call, don't trust the tool's own success flag
   alone.

3. For any register/table you plan to describe as a bitmask, byte layout,
   or repeating structure: verify FINAL entries and conclusions via
   individual read_memory calls anchored on absolute addresses, not by
   eyeballing one long combined hex dump and counting bytes by hand. This
   project has already produced two separate miscounting errors doing it
   the fast way (a table entry-count error, and a specific bit-mask
   misread) -- both caught only because they were double-checked
   independently before being written down as fact. The slow way is worth
   it whenever a finding is about to be saved as an established fact
   rather than a rough lead.

4. Before accepting a plausible-looking hypothesis (e.g. "this graduated
   mode-select value looks like a PWM fan-speed driver"), check the ACTUAL
   register labels via list_globals for anything you're about to name as a
   guess. This project had a specific case where a well-reasoned-sounding
   fan-PWM hypothesis was completely wrong once the real register labels
   (SCI1/2/3 UART SMR/BRR/SCR) were checked -- the corrected finding is
   preserved alongside the original wrong one in the relevant plate comment
   so future readers don't rediscover the same dead end.

5. When re-deriving a decompiler's rendering of an addressing mode (banked/
   segmented EA forms in particular), trace the actual Sleigh grammar
   constructor (the .slaspec/.sinc pcode body) rather than reverse-
   engineering the intent from the decompiler's C-like output alone -- the
   decompiler's CONCAT/tracked_set folding is a useful cross-check but the
   grammar itself is the ground truth for what an instruction actually
   computes. See the DP=2 pointer table derivation below for a worked
   example (eaw_disp16 -> Rn_banked chain).

6. Label AND comment as you go, not as a final pass. Every RAM cell, ROM
   table, and function that gets a confirmed (or well-evidenced
   provisional) meaning should get: a descriptive name via rename_or_label/
   rename_function, and a plate comment stating what's confirmed, what's
   inferred, what's still open, and pointing back to the relevant section
   of this file. This is what actually accumulates into a reusable
   signature -- comments only in this markdown file, without corresponding
   Ghidra labels, don't transfer to a fresh project the same way.

7. When a hypothesis turns out wrong, CORRECT THE EXISTING PLATE COMMENT IN
   PLACE (don't just note the correction elsewhere) -- the whole point is
   that the next person (or the next session) reads the function and gets
   the corrected understanding immediately, not a stale wrong one plus a
   pointer to a correction buried in this file's chronological log.

8. Keep confidence levels explicit and honest in every write-up:
   CONFIRMED (independently re-derived from live disassembly/memory, ideally
   twice), LIKELY/well-evidenced (a real mechanism traced, but physical
   real-world identity inferred rather than proven), or OPEN/no writer
   found. Do not let a "LIKELY" finding get cited elsewhere as if it were
   CONFIRMED -- several sections below deliberately flag this distinction
   (e.g. the P1DR.5/ignition-output lead) precisely so it doesn't harden
   into an unearned fact over time.

WHAT HAS NOT WORKED / TO AVOID:
- Relying on external tooling's actuator/RequestID lists (EvoScan's UI,
  MUT-III's mutdata.mdb, MUT-II hand-programmer documentation) as a source
  of ground truth for THIS ROM. These reflect a generic/shared convention
  across many Mitsubishi ECUs and have already been shown to NOT match
  what this specific ROM's dispatcher actually implements (the DP=2 table
  finding). Use them only as naming inspiration once a real ROM mechanism
  is independently confirmed, never as a substitute for tracing the ROM
  itself.
- Chasing a RAM flag that turns out to be shared across 100+ xref sites
  (e.g. f20e, f502) to a single conclusive meaning in one sitting -- these
  are typically genuine shared engine-state words, not actuator-specific.
  Recognize the scale early (a bulk search_byte_patterns hit count is a
  fast signal) and either scope the trace narrowly (one specific
  consumer/writer pair) or note it as a low-priority/impractical thread
  rather than getting stuck.


0x2fad0 (indexed via adc_sensor_convert_single @0x171c3) and cross-
referencing every entry against Mitsubishi_MUTII_EFI.xml (the standard
Evo 4/5/6+ EFI EvoScan profile the RVR's own MUT profile was adapted
from, per logging.txt's PURPOSE section). Also cross-checked (2026-07-13)
against Mitsubishi_MUTII_EFI_GalantLegnum.xml (same-generation Galant/
Legnum EC5x EvoScan profile, ~40 items) -- smaller profile, but it named
two RequestIDs this table had BLANK, and raised a conflict worth flagging
on RequestID 0x00 (see rows below and the note after the table).

IMPORTANT CAVEAT: "Name (per EFI profile)" below is an INHERITED CLAIM,
not a verified fact. Several of the already-investigated entries in this
table turned out to be WRONG for this specific ROM (knock_flag, and the
Engine RPM claim at RequestID 0x21/F17B, both refuted -- see below and
review.md item 7). Every "NAMED (untraced)" row is a lead worth checking,
not a conclusion. Status column meanings:
  CONFIRMED        - address AND semantics independently verified live
  REFUTED          - address correct, semantic label proven wrong
  OPEN             - address known, writer/relationship not fully traced
  NAMED (untraced) - EFI profile claims a name, nobody has checked it yet
  BLANK (untraced) - no name anywhere (not even the stock EFI profile),
                     completely uninvestigated -- may be RVR/Tephra-mod-
                     specific, unused, or reserved

NOTE ON THE 2026-07-14 SWEEP: every BLANK/NAMED(untraced) row EXCEPT the
following was checked via get_bulk_xrefs and came back with ZERO hits (see
"PRE-EMPTIVE SWEEP" section near the end of this file for the full caveat --
zero hits means "not found by this cheap method," NOT "confirmed unused").
Rows with an actual finding from that sweep are individually annotated
in-line below with "POINTER (2026-07-14 sweep)" or "LIKELY SCRAPER ARTIFACT":
0x0F (F26E), 0x2A/0x2B (F971/F972), 0x4F (F270, see sweep section), 0x80-0x82
(F5C0/F5C1/F5C3). Every other BLANK/NAMED(untraced) row below was included
in the sweep's zero-hit set and remains exactly as uninvestigated as before
2026-07-14 -- the sweep did not narrow them down, it just confirmed the cheap
method doesn't see them.

| ReqID(hex) | Addr  | Name (per EFI profile)                          | Status |
|---|-------|----------------------| 00/01 | F0F7/F0F6 | LoadMUT2Byte (deprecated 2-byte load)         | NAMED (untraced) -- THIRD CONFLICTING CLAIM (2026-07-15): the same uploaded Mitsubishi_MUTII_EFI.xml that names this LoadMUT2Byte ALSO has a separate entry for ReqID 0x00 called "gmas" / "Airflow Rate gm/s" (Eval="x", no formula detail) -- an internal collision within the same XML file, not just a cross-file conflict. Combined with the GalantLegnum packed-switch-flags claim already noted, ReqID 0x00 now has THREE mutually incompatible claims across sources (LoadMUT2Byte, switch-flags byte, airflow-rate). Strongly suggests this ID has been repurposed differently across ROM revisions/mods rather than having one stable meaning -- do not trust any single claim without live tracing. |gs byte) before trusting either label. |
| 02/03 | F0FD/F0FC | RPMMUT2Byte (deprecated 2-byte RPM)           | NAMED (untraced) -- RPM-adjacent, set aside per user |
| 04/05 | F343/F363 | AirFlowMUT2Byte                               | OPEN -- item 6, non-contiguous hi/lo pair flagged |
| 06 | F361 | Timing Advance (TimingAdv)                          | NAMED (untraced) |
| 07 | F109 | Coolant Temp                                        | CONFIRMED (addr only, no writer) |
| 08 | EECA | ISC Correction (mode-shadow copy)                   | CONFIRMED (2026-07-15): written by isc_eeca_eecc_eece_correction_calc (0x27a81), which computes one ISC correction term and mode-selects which of EECA/EECC/EECE gets it, based on F0F8 bit4/bit0 + byte@0x2c7. EECA = default-mode target. See EECC row and plate comment on thi| 09 | F3FB | ISC Correction low byte (mode-shadow, default mode) | CONFIRMED (2026-07-15): F3FB is the LOW byte of the 16-bit word written at F3FA by isc_f3fa_f3fc_f3fe_correction_calc (0x27990) -- confirmed real, not a scraper artifact (see adc_sensor_convert_single @0x171c3: ReqID<=0xBF reads a SINGLE byte at the table-decoded address, so the 0x2fad0 table's entry for 0x09 must decode directly to 0xF3FB). Same mode-shadow idiom as EECA/EECC (0x08/0x0A) above -- F3FA/F3FB pair = default-mode ISC correction (F0F8 bit4==0). |                          | BLANK (untraced) |
| 0A | EECC | ISC Correction (mode-shadow copy, alt mode)         | CONFIRMED (2026-07-15): same writer/value as EECA (0x08) above -- isc_eeca_eecc_eece_correction_calc (0x27a81) selects EECC when F0F8 bit4=1, byte@0x2c7!=1. A third shadow (EECE, not a MUT ID in this table) covers the remaining mode. All three are the SAME computed correction value; MUT reading 0x08 vs 0x0A just pi| 0B | F3FD | ISC Correction low byte (mode-shadow, alt mode)     | CONFIRMED (2026-07-15): F3FD is the LOW byte of the 16-bit word written at F3FC by isc_f3fa_f3fc_f3fe_correction_calc (0x27990) -- same reasoning as F3FB/0x09 above. F3FC/F3FD pair = alt-mode ISC correction (F0F8 bit4==1, byte@0x2c7!=1). A third pair (F3FE/F3FF, not a MUT ID in this table) covers the remaining mode, mirroring EECE. |                           | BLANK (untraced) |
| 0C | EE99 | Fuel Trim Low (LTFT)                                | NAMED (untraced) |
| 0D | EE9B | Fuel Trim Mid (LTFT)                                | NAMED (untraced) |
| 0E | EE9D | Fuel Trim High (LTFT)                               | NAMED (untraced) |
| 0F | F26E | Oxygen Feedback Trim (STFT)                         | NAMED (untraced) -- POINTER (2026-07-14 sweep): written inside tcu_shift_torque_and_knock_mgmt (0x28fff, ~0x96b0-0x96d1), a clamped accumulator fed by F264/F262 (<<2, add/sub via sat_add_u16/sat_sub_u16 depending on F21C Also touched by a SEPARATE function (0x20782, renamed 2026-07-14 to
f26e_cluster_accumulator_unrelated_to_ihex, formerly misleadingly named
sci1_boot_ihex_data_byte_store), misleadingly named sci1_boot_ihex_data_byte_store) which reads/writes F26E directly at 0x207a0-0x207a4 as a simple 16-bit accumulator (`add:g.w R0,R1` then store back). Two distinct writers to the same address is unusual -- worth reconciling before trusting either as "the" Oxygen Feedback Trim writer. Does NOT look like classic STFT (short-term fuel trim) math (no O2-sensor-error-driven PI/PID pattern visible in either writer) -- treat the inherited label with suspicion. |
| 10 | F10F | Coolant Temp Scaled                                 | CONFIRMED (addr only, no writer) |
| 11 | F119 | MAF Air Temp Scaled| 12 | F111 | EGR Temperature                                     | NAMED (untraced) -- also claimed as "LC1 Wideband o2 e8 mod" (LC1WidebandO2) in the same source XML (2026-07-15), but that entry's own Notes say it requires wiring an external 0-5V sensor into the ECU -- a user hardware mod repurposing this cell on modified ROMs, not a competing claim about the stock ROM's meaning. EGRTemp remains the primary lead. |                                   | NAMED (untraced) |
| 13 | F11F | Oxygen Sensor                                       | CONFIRMED |
| 14 | F13B | Battery                                             | CONFIRMED |
| 15 | F12F | Barometer                                           | NAMED (untraced) |
| 16 | EED5 | ISC Steps                                           | CONFIRMED |
| 17 | F13D | Throttle Position (TPS)                             | CONFIRMED |
| 18 | F21D | --                                                  | BLANK (untraced) |
| 19 | F217 | --                                                  | BLANK (untraced) |
| 1A | F1DF | Air Flow Hz                                         | NAMED (untraced) |
| 1B | EE83 | ECU Load | 1C | F187 | ECULoad                                              | NAMED (untraced) -- source: uploaded Mitsubishi_MUTII_EFI.xml (2026-07-15), missed in the original 2026-07-13 build. Eval="5*x/8", clips at 160. |                                             | BLANK (untraced) |
| 1D | F18D | Airflow/Rev (AccelEnrich)                           | NAMED (untraced) |
| 1E | F20F | --                                                  | BLANK (untraced) |
| 1F | F189 | Load11Bit4                                          | NAMED (untraced) |
| 20 | F179 | --                                                  | BLANK (untraced) -- adjacent to 0x21, unlabeled |
| 21 | F17B | Engine RPM (per EFI profile)                        | REFUTED for this ROM -- confirmed to be engine-torque-derived scale value (engine_torque_pct_scale_calc), NOT RPM. See review.md item 7. |
| 22 | EED1 | --                                                  | BLANK (untraced) |
| 23 | F3F1 | --                                                  | BLANK (untraced) |
| 24 | F401 | Target Idle RPM                                     | CONFIRMED |
| 25 | F40B | --                                                  | BLANK (untraced) |
| 26 | F3A3 | Knock Sum                                           | CONFIRMED |
| 27 | EEC9 | Octane Level (OctaneFlag)                           | CONFIRMED |
| 28 | F291 | --                                                  | BLANK (untraced) |
| 29 | F970 | Injector Pulse Width                                | CONFIRMED |
| 2A | F971 | Injector Pulse Width low byte (word w/ F970)        | CONFIRMED (2026-07-15): resolved by reading fuel_pw_and_airvol_compute (0x29fba) directly instead of relying on xrefs. The function writes InjPulseWidth as a single 16-bit store at 0xf970 (@0x2a6c1) -- there is no separate byte-level write anywhere, confirming F971 is simply the low byte of the F970/F971 big-endian word, same idiom as F3FA/F3FB (0x08/0x09). injpw_airvol_reset_on_fuelcut (0x24680) corroborates: its fuel-cut reset zeroes F970 as one ushort store, never touching F971 independently. No separate signal here -- do not treat as distinct from F970. |
| 2B | F972 | Air Volume high byte (word w/ F973)                 | CONFIRMED (2026-07-15): resolved by reading fuel_pw_and_airvol_compute (0x29fba) directly. AirVol is written as a single 16-bit store at 0xf972 (@0x2a6d7) -- no separate byte-level write exists, so F972 (this ReqID) and F973 (ReqID 0x2C, already CONFIRMED as "Air Volume") are the high/low bytes of the SAME word, same idiom as F3FC/F3FD (0x0A/0x0B). injpw_airvol_reset_on_fuelcut (0x24680) corroborates: zeroes F972 as one ushort store. Resolves the prior open question about whether this is part of AirVol's word or a distinct 32-bit value -- it is the former; not a separate signal. |
| 2C | F973 | Air Volume                                          | CONFIRMED |
| 2D | F85F | --                                                  | BLANK (untraced) |
| 2E | F1E7 | --                                                  | BLANK (untraced) |
| 2F | F1E9 | Speed                                               | NAMED (untraced) |
| 30 | F15D | Knock Voltage                                       | CONFIRMED addr, writer NOT found (open, see below) |
| 31 | F297 | --                                                  | BLANK (untraced) |
| 32 | F2A5 | AFR Map (target AFR used by ECU)                    | NAMED (untraced) |
| 33 | F345 | --                                                  | BLANK (untraced) |
| 34 | F1FD | --                                                  | BLANK (untraced) |
| 35 | F2DB | --                                                  | BLANK (untraced) |
| 36 | EEEF | --                                                  | BLANK (untraced) |
| 37 | EEF3 | --                                                  | BLANK (untraced) |
| 38 | F15F | Boost (MAP)                                         | CONFIRMED |
| 39 | F161 | ADC channel #8 (physical sensor unidentified)       | CONFIRMED live (2026-07-15): adc_read_sequence_main (0x1556d) writes F160/F161 as a single 16-bit word via ADC channel #8 (`trap_hang(8)` call @0x5628, store @0x562c) -- distinct from the neighboring F15E/F15F word (channel #0xB, MAP/Boost, ReqID 0x38). Genuine, independent ADC-fed signal, not an artifact or shared cell. Physical sensor identity not yet determined -- channel #8 not cross-checked against the H8/539F ADC pin assignment or RVR harness pinout this session; that's the concrete next step. |
| 3A | F117 | Air Temperature                                     | CONFIRMED |
| 3B | F15B | -- (structurally dead, always reads 0)              | CONFIRMED DEAD (2026-07-15): F15A/F15B (16-bit word) has exactly TWO touches in the entire ROM, both inside gear_state_config_loader_f1fc (0x20f28): it calls zero_var_f15a() (0x156c2, a one-line `DAT_0001f15a = 0`) and then immediately reads the same word back to derive a 3-bit TCU gear-config index into F1FA. No other function anywhere writes F15A between the zero and the read (confirmed via search_byte_patterns "F1 5A" -- only 2 hits total, both these). The word is therefore always 0 when read, making the derived index always 0 -- structurally dead for MUT-reading purposes, same category as the confirmed-dead MUT_83/0xF0BB cell. Do not log this RequestID; flag as unimplemented/vestigial rather than a real sensor. |
| 3C | F123 | Oxygen Sensor #2                                    | CONFIRMED |
| 3D | F125 | --                                                  | BLANK (untraced) |
| 3E | F121 | Knock Sum 3E (legacy pre-1998 Knock Sum)            | NAMED (untraced) |
| 3F | F5BD | --                                                  | BLANK (untraced) |
| 40 | EED7 | Alt Maps (dev-mod placeholder, undocumented)        | NAMED (untraced) -- first entry of the EED7-EEE9 cluster, adjacent to Load1B |
| 41 | EED9 | Load 1Byte (Load1B)                                 | OPEN -- producer not found, see below |
| 42 | EEDB | --                                                  | BLANK (untraced) |
| 43 | EEDD | --                                                  | BLANK (untraced) |
| 44 | EEDF | MAT Scaled (Manifold Air Temp Scaled)               | NAMED (untraced) |
| 45 | EEE1 | MAP Scaled                                          | NAMED (untraced) |
| 46 | EEE3 | --                                                  | BLANK (untraced) |
| 47 | EEE5 | --                                                  | BLANK (untraced) |
| 48 | EEE7 | --                                                  | BLANK (untraced) |
| 49 | EEE9 | AC Relay Switch (bit flag)                          | NAMED (untraced) |
| 4A | F45D | Crank/IdlePos/PwrSteering/ACSwitch/Inhibitor (combined switch-flags byte) | NAMED (untraced) |
| 4B | F2A7 | --                                                  | BLANK (untraced) |
| 4C | EEAF | --                                                  | BLANK (untraced) |
| 4D | EEB1 | --                                                  | BLANK (untraced) |
| 4E | EEB3 | --                                                  | BLANK (untraced) |
| 4F | F270 | --                                                  | BLANK (untraced) |
| 50 | F27F | Fuel Trim InUse (LTFT)                              | NAMED (untraced) |
| 51 | F283 | --                                                  | BLANK (untraced) |
| 52 | F287 | --                                                  | BLANK (untraced) |
| 53 | F28B | --                                                  | BLANK (untraced) |
| 54 | F2DD | --                                                  | BLANK (untraced) |
| 55 | F2DF | --                                                  | BLANK (untraced) |
| 56 | F1C9 | --                                                  | BLANK (untraced) |
| 57 | F1CD | --                                                  | BLANK (untraced) |
| 58 | F5BF | --                                                  | BLANK (untraced) |
| 59 | F21F | --                                                  | BLANK (untraced) |
| 5A | F22B | --                                                  | BLANK (untraced) |
| 5B | F22D | --                                                  | BLANK (untraced) |
| 5C | F127 | --                                                  | BLANK (untraced) |
| 5D | F129 | --                                                  | BLANK (untraced) |
| 5E | F237 | --                                                  | BLANK (untraced) |
| 5F | F239 | --                                                  | BLANK (untraced) |
| 60 | EE8C | --                                                  | BLANK (untraced) |
| 61 | EE8E | --                                                  | BLANK (untraced) |
| 62 | EE90 | --                                                  | BLANK (untraced) |
| 63 | EE92 | --                                                  | BLANK (untraced) |
| 64 | EE94 | --                                                  | BLANK (untraced) |
| 65 | EE96 | --                                                  | BLANK (untraced) |
| 66 | F233 | --                                                  | BLANK (untraced) |
| 67 | F235 | --                                                  | BLANK (untraced) |
| 68 | EEF1 | --                                                  | BLANK (untraced) |
| 69 | EEF5 | --                                                  | BLANK (untraced) |
| 6A | F3A9 | knock_adc_processed                                 | CONFIRMED |
| 6B | F967 | knock_base                                          | CONFIRMED |
| 6C | F963 | knock_var                                           | CONFIRMED |
| 6D | F969 | knock_change                                        | CONFIRMED |
| 6E | F3B7 | knock_dynamics                                      | CONFIRMED |
| 6F | EFC3 | knock_flag                                          | REFUTED -- confirmed throttle-transient detector, nothing to do with knock |
| 70 | F4BD | --                                                  | BLANK (untraced) |
| 71 | F1FF | --                                                  | BLANK (untraced) |
| 72 | F201 | Knock_72 (bit flags for knock)                      | NAMED (untraced) |
| 73 | F14D | --                                                  | BLANK (untraced) |
| 74 | F151 | --                                                  | BLANK (untraced) |
| 75 | F405 | --                                                  | BLANK (untraced) |
| 76 | F40D | --                                                  | BLANK (untraced) |
| 77 | F49D | --                                                  | BLANK (untraced) |
| 78 | F49B | --                                                  | BLANK (untraced) |
| 79 | F2CF | Injector Latency                                    | NAMED (untraced) |
| 7A | EEA7 | --                                                  | BLANK (untraced) |
| 7B | EEBD | --                                                  | BLANK (untraced) |
| 7C | EEA9 | --                                                  | BLANK (untraced) |
| 7D | EEBF | --                                                  | BLANK (untraced) |
| 7E | EEAB | --                                                  | BLANK (untraced) |
| 7F | EEC1 | --                                                  | BLANK (untraced) |
| 80 | F5C0 | --                                                  | BLANK (untraced) -- POINTER (2026-07-14 sweep): written inside channel_dispatch_and_snapshot_update (0x19d80). CONFIRMED as a 16-bit word, gear-indexed snapshot (read via current_gear_state_index @0xF1FC into a ROM table at 0x20c-offset), part of a run of five 16-bit snapshot words: F5C0 (this one, gear-table value), F5C2 (from 0x21C), F5C4 (from 0x21E), F5C6 (from 0x206), and a status/flags word F5C8 (bits set/cleared based on F0E6/F0EA). The real structure here is 16-bit-word-spaced (F5C0/C2/C4/C6/C8), NOT byte-spaced -- this table's own 0x81/0x82 rows (F5C1/F5C3, odd byte offsets) don't align with any field boundary found and are likely scraper artifacts, not real distinct RequestID targets. |
| 81 | F5C1 | --                                                  | BLANK (untraced) -- LIKELY SCRAPER ARTIFACT (2026-07-14 sweep): see 0x80/F5C0 finding -- the real structure at this ROM location is 16-bit-word-spaced (F5C0/C2/C4/C6/C8), so F5C1 (odd byte offset) does not align with any real field boundary found. |
| 82 | F5C3 | --                                                  | BLANK (untraced) -- LIKELY SCRAPER ARTIFACT (2026-07-14 sweep): same as 0x81/F5C1 -- odd byte offset does not align with the confirmed 16-bit-word structure (F5C0/C2/C4/C6/C8). |
| 83 | F0BB | --                                                  | BLANK (untraced) |
| 84 | F495 | RadFans (Cooling Fan Duty Cycle)                    | NAMED (untraced) -- source: GalantLegnum profile (RequestID 0x84 not present in the base Evo profile) |
| 85 | F449 | --                                                  | BLANK (untraced) |
| 86 | F44D | Wastegate Duty Cycle (WGDC)                         | CONFIRMED |
| 87 | F163 | --                                                  | BLANK (untraced) |
| 88 | F167 | --                                                  | BLANK (untraced) |
| 89 | F169 | --                                                  | BLANK (untraced) |
| 8A | F13F | Load Error                                          | NAMED (untraced) |
| 8B | F4AD | WGDC Correction (WGDCCorr)                          | OPEN -- relationship to WGDC not determined, see below |
| 8C | F84F | --                                                  | BLANK (untraced) |
| 8D | EEFB | --                                                  | BLANK (untraced) |
| 8E | F4DF | --                                                  | BLANK (untraced) |
| 8F | F4DD | --                                                  | BLANK (untraced) |
| 90 | F4E5 | --                                                  | BLANK (untraced) |
| 91 | F4E7 | --                                                  | BLANK (untraced) |
| 92 | F4EB | --                                                  | BLANK (untraced) |
| 93 | F4DB | --                                                  | BLANK (untraced) |
| 94 | F0BB | --                                                  | BLANK (untraced) -- duplicate address of ReqID 0x83, worth checking if intentional |
| 95 | F0BB | --                                                  | BLANK (untraced) -- duplicate address of ReqID 0x83/0x94 |
| 9A | ??? | FuelPumpSpeed (Fuel Pump Hi/Low, dual-speed bit)     | NAMED (untraced) -- source: GalantLegnum profile. NOT in the base 150-entry 0x2fad0 table scraped for this file (table stops at 0x95) -- address unknown, needs its own lookup/derivation before this row can be trusted as belonging to the same RequestID scheme. |

Tally: 56 of 150 entries have SOME name attached (from CONFIRMED/REFUTED/
OPEN work or an EFI profile -- base Evo profile or the GalantLegnum
cross-check); of those, only 24 have actually been independently verified
(CONFIRMED/REFUTED/OPEN-with-partial-trace). That leaves 94 entries with
literally no name anywhere, and ~32 more that have an inherited EFI-profile
name but have never been checked against this ROM's live disassembly --
remember 0x21 (Engine RPM) and 0x6F (knock_flag) both looked equally
credible before they were actually traced and turned out wrong. Treat
every NAMED (untraced) row the same way: a lead, not a fact. This also
applies to the two new GalantLegnum-sourced rows (0x84 RadFans, 0x9A
FuelPumpSpeed) and the 0x00 conflict flag -- a second EFI profile agreeing
or disagreeing is a useful signal, not proof either way. Plus a 151st row
(0x9A) added below the table for a RequestID outside the original 0x00-0x95
scrape range -- its address is not yet known and needs separate lookup.

Priority follow-ups suggested by this table (clusters worth checking first,
since contiguous addresses tend to be a related family, as the knock
cluster and AirVol/InjPulseWidth pairs already showed):
- EED7-EEE9 (ReqID 0x40-0x49): Alt Maps, Load1B, 3 blank, MAT Scaled, MAP
  Scaled, 2 blank, AC Relay Switch -- mixed known/unknown cluster right
  next to the open Load1B question item 1 below.
- EE8C-EE96 (ReqID 0x60-0x65): six consecutive blanks, tight spacing --
  likely a per-cylinder or per-gear array, completely uninvestigated.
- EEA7-EEC1 (ReqID 0x7A-0x7F): six consecutive blanks, adjacent to Octane
  Level (EEC9) -- possibly part of the octane/knock retard pipeline.
- F4Dx-F4Ex-F84F (ReqID 0x8C-0x93): eight blanks near the WGDC/WGDCCorr
  family (F44D/F4AD) -- possibly a third WGDC-pipeline stage.
- ReqID 0x83/0x94/0x95 all resolve to the SAME address F0BB -- worth
  checking whether that's intentional (a status/flags byte read three
  ways) or a scraper/table artifact.

MUT Verification Status
========================
Extracted from test/rvr/logging.txt (session 10, 2026-07-03, written under
the OLD/buggy pre-MAP3-6 Sleigh grammar) and re-verified against the
CURRENT live disassembly/decompile during the 2026-07-12/13 sessions.

Source file test/rvr/logging.txt is safe to delete once this file and the
plate comments described in review.md item 6/7 have captured everything
needed from it.

RPM identity is tracked separately (see review.md item 7 / the isr_sci3_eri
lead) and is intentionally NOT included here -- this file covers everything
else that was re-verifiable independent of that open question.

CONFIRMED (address + semantics both verified against live disassembly)
------------------------------------------------------------------------
- TPS (0x17 -> RAM 0xF13D): writer adc_read_sequence_b (0x15689), channel 7,
  16-bit word at 0xF13C/F13D. ~20 consumers gated on throttle position
  confirm semantics, not just address.
- Battery (0x14 -> RAM 0xF13B): same function/pattern as TPS, channel 5,
  word at 0xF13A/F13B.
- AirTemp (0x3A -> RAM 0xF117), MAP/Boost (0x38 -> RAM 0xF15F): writer
  adc_read_sequence_main (0x1556d), even-word/odd-byte pattern.
- O2 Sensor (0x13 -> RAM 0xF11F): writer adc_read_sequence_main channel 3;
  consumer o2_closed_loop_fuel_trim_compute (0x237a0) reads it directly as
  narrowband O2 input to closed-loop fuel trim.
- O2 Sensor 2 (0x3C -> RAM 0xF123): writer adc_read_sequence_main channel 4;
  consumer o2_sensor2_threshold_flag_update_f226_bit13 (0x22f16) sets/clears
  bit13 of the F226 "lambda mode" register.
- Octane Level (0x27 -> RAM 0xEEC8/EEC9): this IS the "knock retard"
  mechanism on this ECU. Chain: knock sum (F3A2/F3A3) ->
  knock_event_counter_update_eec6 (0x251c4) -> octane_level_compute_from_
  knock_counter (0x252d3, writes EEC8/9). Separate init/override path:
  octane_level_init_or_force_from_gear_table (0x24e80), caller not yet
  found.
- TargetIdleRPM (0x24 -> RAM 0xF400/F401): writer idle_target_rpm_compute_
  f400 (0x2629b). Coolant-temp-indexed table, A/C flag (F0F8 bit0x20)
  selects table pair, floor clamp + A/C trim offset.
- AirVol (0x2C -> RAM 0xF972/F973) and InjPulseWidth (0x29 -> RAM
  0xF970/F971): both written by fuel_pw_and_airvol_compute (0x29fba).
  Secondary reset function injpw_airvol_reset_on_fuelcut (0x24680) zeroes
  both under a fuel-cut condition (F25A bit0x28).
- ISCSteps (0x16 -> RAM 0xEED4/EED5): writer isc_stepper_output_state_
  machine_eed4 (0x26f82), closed-loop idle stepper state machine.
- WGDC (0x86 -> RAM 0xF44C/F44D): writer chain wgdc_correction_integrator_
  update (0x18fe0) -> wgdc_output_clamp_f44c (0x19110). Relationship to
  WGDCCorr (0x8B -> F4AD) NOT yet determined -- see Open Items below.
- TCU Shift Torque Cmd Lo/Hi per gear (ROM 0x1328e/0x13296): gear-indexed
  ((gear&3)<<1), read into RAM 0xF39E/F3A0, used as a raw SCI3 protocol
  command byte to the TCU -- never used arithmetically. Small values (1-2)
  are expected, not a data error.
- Knock Sum (0x26 -> RAM 0xF3A3), Knock Voltage (0x30 -> RAM 0xF15D),
  knock_adc (0x6A -> F3A9), knock_var (0x6C -> F963, holds a DERIVED
  decision magnitude not raw variance), knock_base (0x6B -> F967, holds a
  snapshot of the PREVIOUS cycle's retard output F3AA), knock_change
  (0x6D -> F969, delta current/previous), knock_dynamics (0x6E -> F3B7,
  persistence counter, sets F200 bit0 under sustained knock).
  NOTE: 2026-07-12 re-verification of Knock Voltage's *write* side found
  the read location confirmed (inside tcu_shift_torque_and_knock_mgmt) but
  NO writer under bank prefixes 0x0-0x3 -- flagged in Ghidra, needs further
  investigation (possible bank prefix >3, computed/indirect write, or not
  runtime-written at all).
- Coolant Temp (0x07 -> RAM 0xF109) / CoolantTempScaled (0x10 -> RAM
  0xF10F): address arithmetic only, NOT independently traced. 2026-07-12
  re-check: no writer found under bank prefixes 0x0-0x1 either -- see the
  four-way conflict in Open Items below.

REFUTED / MISLABELED
------------------------------------------------------------------------
- knock_flag (0x6F -> RAM 0xEFC2/EFC3): NOT knock-related. CONFIRMED
  mislabel, re-verified 2026-07-12. Both writers (efc2_threshold_update
  @0x252f9, and a second writer inside tcu_rx_main_scheduler @0x2b676) are
  throttle-position-delta detectors (TPS-now vs TPS-previous, @0xF13C/
  F142) -- genuinely nothing to do with knock. Inherited from the stock
  Evo profile.

MAJOR STRUCTURAL FIX: knock + TCU shift torque is ONE function
------------------------------------------------------------------------
What was called "knock_process_main" (0x2933b) and "tcu_shift_torque_mgmt"
(0x28fff) were never two coordinating functions -- Ghidra had mis-split ONE
real function into four pieces across a 2-byte inline data literal
(0x186a @ ROM 0x29339-0x2933a) left unresolved since session 3. Fixed by
marking that literal as data and merging all four pieces into one function,
now named tcu_shift_torque_and_knock_mgmt (ROM 0x28fff-0x29c32). Fixing the
boundary surfaced its real caller: isr_sci3_eri (COMPUTED_CALL @ 0x169b1).

f3a8/f3aa/f3ac/f3ae/f3b0/f3b2 form a shared "Knock-to-TCU Torque
Coordination" register cluster, gated by RAM 0xf1f2 bit7
(gear_config_word_bit7_tcu_knock_coord), loaded per-gear via
current_gear_state_index (RAM 0xf1fc) from gear_config_table_f1f2 (ROM
0x272). Practical meaning: knock-informed torque-cut coordination with the
TCU is only enabled in certain gears. The specific ROM calibration table
addresses previously guessed for this cluster were REMOVED from the
MT-specific XML (never independently traced, several overlapped Warmup
Retard's real byte range) -- the RAM register finding survives, those
specific addresses do not.

Action needed (2026-07-13): the tcu_shift_torque_and_knock_mgmt boundary
fix (0x28fff-0x29c32) and its isr_sci3_eri caller xref should be
spot-checked against the current live listing before further work builds
on this -- see review.md item 6.

TUNING XML CLEANUP: speculative table block removed
------------------------------------------------------------------------
The MT-specific XML's "UNKNOWN / PARTIALLY IDENTIFIED TABLES" block (~60
tables) was built from data-shape pattern guessing without cross-checking
against tables already defined elsewhere in the file. Verification: (1)
byte-range overlap check found 3408 collisions concentrated in this block
(e.g. High Octane Ignition Map 1 fully contained four of the "unknown"
tables); (2) a 28-address Ghidra xref sample found zero addresses used as
an independently-addressed lookup table anywhere in the code. REMOVED the
entire block from 21000011_1997-2001_RVR_X3_Mt__4g63t_.xml; full text
preserved separately in logging_session10_removed_tables.xml for reference
only (not for re-inclusion without independent verification). Overlap
count after fix: 3408 -> 913 (remainder expected/benign: MT file
legitimately overriding base-file tables, shared axis arrays).

RETRACTED DEAD ENDS (do not re-investigate without new evidence)
------------------------------------------------------------------------
- isr_ram_tpu_crank @ RAM 0xF9BA: not real code, bytes undefined; suspected
  boot_ram_block_copy source (0x1F290) is just uninitialized RAM.
- isr_adi_adc @ ROM 0x163cc: resolved dead vector, calls a one-line no-op
  stub. Not the knock sampling path.
- 0x3898[chan] dispatch table: decoded as a generic ADC/DMA transfer
  descriptor state machine (init/start/poll/ready/done) underlying the
  already-known adc_read_sequence_main/b channel reads.
  NOTE (2026-07-12 re-check): no function and no xrefs currently exist at
  0x13898 (review.md item 3's flagged unresolved address table) -- NOT
  confirmed this is the same address as this "0x3898" shorthand; treat as
  independent until the dispatch-table structure is re-derived against the
  current live listing.
- isc_integrator_update (0x17dd3): the one speculative table address with
  any xref at all ("Lambda Fuel Trim vs O2 A", 0x11412) turned out to be
  read as a single scalar threshold byte, not a 42-element table lookup --
  does not rescue that table definition.

Open items (non-RPM)
------------------------------------------------------------------------
1. Load1B (0x41 -> RAM 0xEED8/EED9): producer not found. Two writers
   located are both RESET/init paths (startup_phase_reset_eed6_cluster,
   startup_phase_reset_eed6_eefa_bulk), not the per-cycle compute. Since
   Load1B is described as MAF/RPM-derived like AirVol, check whether
   fuel_pw_and_airvol_compute (0x29fba) produces it further down, or
   whether a sibling load-calc function exists.
   [UPDATE 2026-07-15] Still no producer found, but the trigger chain for
   startup_phase_reset_eed6_eefa_bulk is now fully traced and it is NOT
   startup-only: sci1_meta_cmd_dispatch_c0_ff command 0xFC (SCI1) sets
   @0xf516 bit7 -> eee0_eeee_diag_flags_reset_dispatch (0x282c1) reads that
   bit and calls startup_phase_reset_eed6_eefa_bulk on demand. So Load1B
   (and the whole EED6-EEFA cluster) can be force-reset live over SCI1, not
   just at boot. Does not resolve the producer question, but changes the
   read-safety picture slightly: if this dispatcher is ever reachable from
   the MUT/SCI3 path, a stray 0xFC-equivalent command would zero this
   whole cluster rather than just fail to answer a read. No evidence yet
   that it IS reachable from SCI3 (see dispatcher section above).
2. WGDC (0xF44C/F44D) vs WGDCCorr (0xF4AD) relationship not determined --
   likely two stages of one pipeline, not yet traced which is which.
3. Coolant Temp four-way address conflict: RVR_base.xml (F0C4/F0C8), MUT
   profile (F109/F10F), and a fourth independently-traced ADC path
   (F84E->F12E->F130->F29A, via coolant_temp_validity_and_scale, 0x2142c)
   all claim to be coolant temp; none overlap, none reconciled. Do not
   treat any as authoritative.
4. gear_config_table_f1f0 (ROM 0x262) and gear_config_table_f1f4 (ROM
   0x282) -- two of the three per-gear config words loaded alongside f1f2 --
   not yet decoded. Also unknown: which specific gear index/indices have
   f1f2 bit7 set in ROM table 0x272.
5. o2_downstream_clamp_by_type's exact transform not re-derived. f1fe
   bit3, f200 bit0, f0fe bit0 (force-zero/force-max conditions in the
   octane level chain) not decoded.
6. AirFlowMUT2Byte (RequestID 0x04/0x05 -> RAM 0xf343/0xf363): NOT
   contiguous, unlike other 2-byte pairs in the profile -- hi/lo byte
   stitching assumption unconfirmed, verify before trusting logged values.
7. General backlog: ~140 "Bad Instruction" bookmarks remain, clustered
   around 0x10000-0x10090, 0x14000-0x14e10, and scattered singles. The
   tcu_shift_torque_and_knock_mgmt fix came from investigating exactly one
   of these and found a real mis-split function with a hidden caller --
   treat "Bad Instruction adjacent to a zero-xref function" as a priority
   pattern when working this backlog.

SLEIGH DECODE BUG -- RESOLVED, historical note only
------------------------------------------------------------------------
logging.txt (written under the OLD pre-project-fix Sleigh grammar) recorded
six "Unable to resolve constructor" Bad Instruction sites (0x142a6, 0x142dc,
0x14349, 0x14379, 0x143a7, 0x1440a), all byte-for-byte identical at the
failing instruction (opcode bytes `A0 16`, Ghidra's partial-decode guess
read it as `tst.b R0`).

STATUS (2026-07-13, per user): this was a bug in the old grammar only. The
user has since updated the Sleigh implementation and confirms all such
decode bugs are gone in the current live Ghidra project. No action needed
here -- this is retained purely as a historical note explaining an old
logging.txt entry, not as an open item. If any "Unable to resolve
constructor" bookmarks are seen again in the live project, they should be
treated as new findings, not a recurrence of this one, and verified fresh
against the current .sinc files rather than assumed to be the same bug.

PRE-EMPTIVE SWEEP OF BLANK/NAMED-UNTRACED ADDRESSES (2026-07-14)
------------------------------------------------------------------------
Ran ghidra:get_bulk_xrefs across ~110 addresses covering every BLANK and
several NAMED(untraced) rows in the master table above, to surface any
address that's actually touched by live code -- a by one function, renamed 2026-07-14 to f26e_cluster_accumulator_unrelated_to_ihex
(formerly misleadingly named sci1_boot_ihex_data_byte_store)e relevant rows above
(F26E, F971/F972, F5C0/F5C1/F5C3). Also found in passing: RAM addresses
F270, F272, F274, F275, F276, F278, F27A, F27C, F27E, F281 are all touched
by one function currently misleadingly named sci1_boot_ihex_data_byte_store
(0x20782) -- despite the name, this function's body has nothing to do with
SCI1 or Intel-hex boot loading; it looks like an accumulator/threshold
tracker unrelated to its name. F270 is a BLANK MUT row (ReqID unlisted in
this sweep's scope but present in the table above) written here. Rename
candidate, not yet renamed -- caller (0x20747) is itself NOT inside any
currently-defined function, which is its own small gap worth a bookmark.

CAVEAT ON THIS SWEEP'S COVERAGE: the overwhelming majority (~95+ of ~110)
of addresses checked showed ZERO xrefs via get_bulk_xrefs. Per the
decompiler-reliability note earlier in this file and review.md's repeated
findings (Knock Voltage, Coolant Temp, several others), static xref
tracking on this ROM has a KNOWN BLIND SPOT for bank-prefixed/indirect RAM
access -- a zero-hit result here is NOT proof an address is unused, only
that it isn't referenced via a directly-encoded operand Ghidra's xref
engine caught. Do not mark any zero-hit BLANK row as "confirmed dead"
based on this sweep alone (contrast with the F0BB case in the "NEW
FINDING" section above, which WAS confirmed dead, but only after a raw
byte-pattern search across the whole ROM, filtered for false positives --
a much more expensive check than bulk xrefs, not repeated here for all
~95 zero-hit addresses due to volume). Treat every zero-hit row as
"not yet found by this cheap method," not "unused." The five findings
above (F26E, F971/F972 adjacency, F5C0 cluster, F270 cluster) are the
sweep's actual yield; everything else in the BLANK/NAMED-untraced rows
remains exactly as uninvestigated as before this pass.

## Note:

so some of the request id's could be actuator tests

Look at what's already in the file: the Mode5 (Actuator Tests) block uses RequestID values like 01, 02, 03, 04, 05, 06, 17, 1A — and those exact same byte values already exist in the Mode2 (Data List Items) block as sensor reads (e.g. 01 is part of LoadMUT2Byte's pair in Mode2, but is "Fuel Pump Relay" in Mode5; 17 is Throttle Position in Mode2, but "Ignition Timing Fix" in Mode5).

That's not a conflict — it's how the real MUT protocol works. EvoScan sends a Mode byte first (2 = data list read, 5 = actuator test, etc.), and the RequestID byte only means something within that mode. So the same byte 0x17 means "read throttle position" under Mode 2 and "force timing to 5° BTDC" under Mode 5 — two completely separate command families, almost certainly dispatched by different code paths in the ECU (Mode 2 → the adc_sensor_convert_single / MUT-table read path we've fully traced; Mode 5 → whatever handles the actual relay/solenoid/output commands).

A few implications:

The ~87 new BLANK entries added are all Mode 2 requests (data reads), so they go through the confirmed read-only dispatch chain — logging them shouldn't trigger anything physical. That's a different risk category from Mode 5.
The existing Mode5 rows' Notes are probably wrong/misleading. They currently carry the same "[RAM CONFIRMED via adc_sensor_convert_single + MUT Table @ 0x2fad0]" annotation as the Mode2 rows — but that's the Mode 2 read table, and there's no evidence anyone actually traced Mode 5's dispatch function to confirm it uses the same table or the same addresses. That looks like it was pasted across uncritically.

REAL COMMAND DISPATCHER FOUND (2026-07-14) -- separate from the MUT table entirely
------------------------------------------------------------------------
This resolves the open question directly above: the dispatcher IS separate,
and part of it IS live actuator control, not just a Mode 5 theory.

Traced upward from the SCI1 receive path (isr_sci1_eri -> ... ->
sci1_protocol_state_machine @0x287af -> sci1_dispatch_and_latch_response
@0x2882b -> sci1_meta_cmd_dispatch_c0_ff @0x28869). This last function is a
genuine COMMAND-BYTE dispatcher, and it is COMPLETELY SEPARATE from
adc_sensor_convert_single (0x171c3) and the 150-entry MUT table at ROM
0x2fad0 that this whole file has been built around. Two different
mechanisms, two different tables, confirmed by direct disassembly:

- Command byte < 0xC0 (0xbf boundary check at 0x28870): reads a WORD from a
  ROM pointer table at ROM 0x2530 -- `mov:g.w @(-0x530:16,R0),R1` with DP=2,
  R0 = command_byte<<1 -- then dereferences that pointer and returns a byte.
  This is a genuinely DIFFERENT table from 0x2fad0. Not yet mapped at all.
  This may be the real Mode-2-equivalent data-read path, or something else
  entirely -- UNKNOWN, not yet traced further per user instruction to stop
  here.

- Command byte 0xC0-0xFF: explicit CASE-BY-CASE handling, each case doing
  direct bit manipulation on what look like hardware/actuator control
  registers -- NOT reads from any lookup table. Concrete examples seen in
  the disassembly:
    0xC3 -> bset.w @0xf512:16, bit 6
    0xC4 -> sets bits in @0xf516:16 (or.w 0x140)
    0xD9 -> bset.w @0xf510:16, bit 0
    0xFA -> bset.w @0xf516:16, bit 2 (conditionally, then bit 5 or error)
    0xFB -> bset.w @0xf516:16, bit 6
    0xFC -> bset.w @0xf516:16, bit 7
    0xCA/0xCB/0xF3/0xF8/0xF9 and the 0xEC-0xEF, 0xFD-0xFF range: various
    reads/writes of @0xf50e, @0xf594, @0xf596, @0xf1fc (gear index), and a
    small 4-byte struct at ROM 0x232 indexed by (0xec-0xef minus 0xec).
  F516, F512, F510 are set/cleared bit-by-bit per command byte in a pattern
  that looks like direct control-flag manipulation (each command sets
  exactly one bit, no arithmetic/scaling) -- structurally consistent with
  actuator/relay/solenoid TRIGGER flags, not sensor data. NOT yet confirmed
  which physical actuator (if any) each bit maps to -- that would need
  tracing what reads F516/F512/F510 elsewhere and what hardware those
  reads control (timer/PWM channel enable, port bit, etc.) -- NOT DONE,
  stopping here per user instruction.

WHAT THIS MEANS FOR THIS FILE'S SCOPE: everything in this file (the
150-entry table at 0x2fad0, all CONFIRMED/OPEN/BLANK rows above) is
downstream of adc_sensor_convert_single, which this dispatcher never calls
for command bytes 0xC0-0xFF. In other words: the MUT table this whole file
tracks is READ-ONLY telemetry, structurally isolated from the actuator-like
command range found here. Reading/logging any RequestID in the table above
does NOT appear to risk triggering the 0xC0-0xFF actuator-style commands --
those are a different byte, dispatched by a different function, gated by a
different comparison. This is a reassuring structural finding for the
"is it safe to log all 150 entries" question, but it is NOT a substitute
for actually confirming what EvoScan sends on the wire for this specific
profile -- if the RVR MUT profile's Mode5/actuator-test block ever gets
used, it almost certainly routes through THIS dispatcher (0x28869), not
through adc_sensor_convert_single, and those rows' "[RAM CONFIRMED via
adc_sensor_convert_single...]" annotations (wherever they exist in the
tuning XML) are WRONG and should not be trusted -- flagged, not yet fixed.

NOT YET DONE (stopping here per user instruction, 2026-07-14):
- The <0xC0 ROM-0x2530 pointer table itself: unmapped, no entries decoded.
- Which physical hardware F516/F512/F510 bits 0-7 each control: unknown.
- Whether the RVR MUT profile's actual Mode5 RequestID values (01-06, 17,
  1A, etc. per the note above) correspond 1:1 with this dispatcher's
  0xC0-0xFF range, or with the <0xC0 pointer-table range, or with neither
  (e.g. mode byte routing could happen even earlier, upstream of this
  function) -- NOT confirmed. Do not assume a mapping between the "Mode 5"
  RequestID bytes documented elsewhere and the C0-FF command bytes seen
  here without further tracing.
- Whether sci1_meta_cmd_dispatch_c0_ff is reachable from SCI3 (the TCU/MUT
  logging port used elsewhere in this file) at all, or only from SCI1 --
  the call chain traced above is entirely SCI1. If MUT logging in practice
  goes over SCI3, this dispatcher may not even be reachable that way -- not
  confirmed either way.

UPDATE 2026-07-15 -- dispatcher table fully decoded, two consumers found
------------------------------------------------------------------------
NOTE FIRST: none of this resolves a MUT table entry above. This dispatcher
remains structurally separate from the 0x2fad0 MUT table (see previous
section) -- Mode5 RequestID bytes are all <0x20, this command range is
0xC0-0xFF, no overlap found. Logged here as dispatcher/actuator-path
progress only.

- The 0xC0-0xD8 table (ROM 0x13740, labeled cmd_c0_d8_actuator_bit_table)
  is now fully read and decoded (20 entries). It's a clean one-bit-per-
  command sweep: idx byte selects @0xf512 (idx=1) or @0xf510 (idx=0) via a
  computed address, mask word sets one bit. Covers f512 bits 0-4,6 and
  f510 bits 0-13. C0-C2/C5/CC are stubbed (mask=0, unimplemented/reserved).
  CA/CB have real table entries but are unreachable (intercepted earlier,
  always error).
- Two real downstream consumers found via xrefs to f516 (f510/f512 have
  NO reader anywhere yet found):
  - f516_request_latch_f09a_calib_select (0x27e1a, renamed from
    eeea_bit7_f09a_update): consumes f516 bits 2/5/6/8 (set by dispatcher
    commands C3/C4/FA/FB), confirms they're one-shot request flags -
    latches via @0xeeea bit7 and selects output register f09a between two
    calibration values (f050 vs f052).
  - f516_hibits_f520_f0f2_mode_select (0x28700, renamed from
    f520_f0f2_f0f4_mode_select): consumes f516 bits 11/12/13/15 into a
    mode value written to f520/f0f2/f0f4 -- but NO WRITER for these bits
    has been found anywhere, including in the dispatcher's own table.
    Likely another command range/dispatcher uses the same computed-
    address trick and lands on these bits -- NOT YET LOCATED.
- Per-gear tables read by the dispatcher's 0xEC-0xEF/0xFE-0xFF range are
  now dumped and labeled: ROM 0x232 (gear_indexed_4byte_struct_ec_ef,
  4 bytes/gear, byte0 constant across gears, byte3 gear-unique) and ROM
  0x252 (gear_indexed_word_table_fe_ff, 2 bytes/gear, mostly a repeated
  value with two gear indices differing). Both look like calibration
  constants, not flags -- physical meaning still undetermined.
- Plate comments updated on all three functions (0x28869, 0x27e1a,
  0x28700) with the above.

- FC's real target found: @0xf516 bit7 is consumed by
  eee0_eeee_diag_flags_reset_dispatch (0x282c1), which on-demand calls
  startup_phase_reset_eed6_eefa_bulk (0x28413) - the same bulk-reset
  function already known as one of Load1B's two writers (see item 1
  above). This means command 0xFC is a LIVE trigger for that reset, not
  just a startup path -- promoted to a concrete finding, see item 1's
  2026-07-15 update. Same function also clears f516 bit1, setter unknown.

STILL NOT DONE: writer for f516 bits 1/12/13/15; any reader for f510/
f512; physical hardware meaning of any bit; the <0xC0 pointer table;
SCI1-vs-SCI3 reachability (now higher priority given the 0xFC live-reset
finding).

RESOLVED 2026-07-15: f516 bit11's writer found -
f588_duty_gate_f516_bit11_set (0x28b62, renamed from FUN_00028b62),
confirmed clean in disassembly (`bset.w @0xf516:16, 0xb`). It's a
computed-jump branch target living inside sci1_periodic_phase_dispatch_f526
(0x28b2f, renamed from FUN_00028b2f, called from sci1_protocol_state_machine
0x287af) - gated on a duty/period counter (f588 vs f58c) and sets bit11
when it elapses, also advancing a phase counter f526 conditionally on
@0xf102 bit5. A sibling branch, f528_f52e_zero_f526_advance_alt_branch
(0x28b89), handles the opposite f102-bit5 case and zeroes f528/f52a/f52c/
f52e instead. So bit11 is NOT set by the SCI1 command dispatcher at all -
it's set by an independent periodic phase-sequencer. This is consistent
with f516_hibits_f520_f0f2_mode_select treating bit11 as a "disable/off"
mode signal.
CAVEAT: sci1_periodic_phase_dispatch_f526 (0x28b2f) itself has real
decompiler trouble (Bad Instruction warnings, likely an unresolved jump
table mis-splitting the function) - flagged as a Bad-Instruction-bookmark
candidate, not yet properly re-split. The two bit11-related branch targets
decompile cleanly and are trustworthy; the parent's case 0/2/6 paths are
not, and its case 7 (which calls into fueling/lambda functions) is
unrelated background-task content, not confirmed reliable either.
Bits 1/12/13/15 remain open - not resolved by this finding.

MUT BLANK/UNTRACED SWEEP, ROUND 2 (2026-07-15 session, in progress)
------------------------------------------------------------------
Goal: work through the ~150 BLANK/NAMED-untraced rows, and separately
identify which confirmed cells are true MUT "requests" (sensor/computed
values a scan tool reads) vs "actuators" (values that drive/target real
hardware output - stepper, duty cycle, solenoid).

APPROACH: individual per-address get_bulk_xrefs on BLANK cells mostly
returns zero hits (same indirect/bank-prefixed blind spot documented
throughout this file) - re-confirmed on EEEF/EEF3/F161/F15B this session,
no new information there. Switched to searching from the PRODUCER side
instead: enumerated all *_calc/*_duty_*/*_target_* functions
(ghidra:search_functions name_pattern "calc") and cross-checked their
write addresses against the master table, since a MUT-readable cell is
written by some real function even when static xrefs to the address
itself come back empty.

CONFIRMED THIS ROUND:
- ReqID 0x08 (EECA) and 0x0A (EECC): see updated table rows above.
  Both are mode-shadow copies of the same ISC correction value from
  isc_eeca_eecc_eece_correction_calc (0x27a81). Plate comment added.

PATTERN IDENTIFIED (useful for future BLANK entries): a recurring
"mode-select shadow copy" idiom - a single computed correction/target
value gets written to one of 2-3 candidate RAM cells depending on
F0F8 bit4, F0F8 bit0, and byte@0x2c7. Seen in both
isc_eeca_eecc_eece_correction_calc (EECA/EECC/EECE) and a second,
not-yet-fully-logged instance in the F3FA/F3FC/F3FE ISC pipeline
(isc_f3fa_f3fc_f3fe_correction_calc, 0x27990, same F0F8/0x2c7 gating).
If a BLANK row's address sits 2-4 bytes from a CONFIRMED cell AND that
CONFIRMED cell's writer contains F0F8-bit/0x2c7-style mode branching,
check the sibling addresses in that same writer function before
concluding "no writer found."

ACTUATOR-SIDE CONTEXT GATHERED (not MUT table entries, but useful
reference for the requests-vs-actuators question):
- F4AC (canister purge duty cycle): confirmed via canister_purge_duty_calc_f4ac
  (0x19560) - genuine PWM-style duty output, lookup-table + threshold-select
  driven. Not itself a MUT ID.
- F448 (EGR duty target): confirmed via egr_duty_target_calc (0x186fa) ->
  egr_target_f448_update (0x18650) caller. Not itself a MUT ID.
- F402 (ISC stepper target, feeds the EECA/EECC/F3FA-family mode-shadow
  copies above): confirmed via isc_f402_stepper_target_calc (0x2725d) -
  lookup-table base + F42A + F43A correction terms, saturated. Not itself
  a MUT ID but sits directly upstream of ones that are.
These three establish the general actuator-driver shape (lookup table ->
correction terms -> saturate -> store) to help classify further BLANK
entries as request-vs-actuator once traced.

RESOLVED (2026-07-15, same session): F3FB (0x09) and F3FD (0x0B) checked
against the F3FA/F3FC/F3FE mode-shadow triplet flagged above. Confirmed
these are REAL low-byte reads, not scraper artifacts -- different outcome
than the F5C0 cluster's 0x81/0x82 rows. Reasoning: adc_sensor_convert_single
(0x171c3), the actual MUT byte-fetch routine, does `mov:g.b @R1+,R0` +
`extu.b` for ReqID<=0xBF -- i.e. reads exactly ONE byte at whatever address
the 0x2fad0 table decodes to for that ID, no width ambiguity. Since
isc_f3fa_f3fc_f3fe_correction_calc only ever writes 16-bit words (mov:g.w)
at F3FA/F3FC/F3FE, and this chip is big-endian, F3FB/F3FD landing exactly
on the LOW byte of the F3FA/F3FC words (respectively) means the 0x2fad0
table's own entries for ReqID 0x09/0x0B genuinely point there -- not a
coincidence, not a mis-scrape. Table updated to CONFIRMED for both rows.
Lesson for future adjacency checks: word-store + odd-offset-ReqID is NOT
automatically an artifact -- rows have so far always come back zero-hit on static xref.

RESOLVED (2026-07-15, same session): F971 (0x2A) and F972 (0x2B), flagged as
POINTER/candidate leads in the 2026-07-14 sweep, are now fully CONFIRMED --
see updated table rows above. Read fuel_pw_and_airvol_compute (0x29fba) and
injpw_airvol_reset_on_fuelcut (0x24680) directly rather than relying on bulk
xrefs. Both confirm InjPulseWidth (F970/F971) and AirVol (F972/F973) are each
a single 16-bit big-endian word with no independent byte-level writer --
F971 is just F970's low byte, F972 is just F973's high byte. Same
mode-shadow-adjacent-word idiom as F3FA/F3FB and F3FC/F3FD, now confirmed a
third time on an unrelated writer function. This closes out the F970-F973
cluster entirely (all four ReqIDs now CONFIRMED) and reinforces the standing
approach note: for BLANK rows adjacent to a CONFIRMED word-value cell,
decompiling the writer function directly resolves the row far faster than
repeated bulk-xref attempts, which are a known dead end for this ROM's
indirect/bank-prefixed addressing.

EEEF/EEF3 CHECKED, STILL BLANK (2026-07-15, same session): both are the odd
low-bytes of the EEEE/EEF2 words zeroed in bulk by
startup_phase_reset_eed6_eefa_bulk (0x28413) -- but that's a reset path only
(itself flagged old-XML/not-yet-re-verified), not a steady-state producer.
Raw byte-pattern search for "EE EE" turned up two candidate hits inside
tcu_gear_ratio_calc (0x2cac4) and eeprom_backup_table_write_dispatch
(0x149f5); both fully decompiled and neither actually references 0xEEEE
anywhere in the body -- false positives from coincidental instruction
encoding, same failure mode as the earlier F0BB/F0BA false hits. No
steady-state writer found for EEEF/EEF3 this round. Remain BLANK.

F161/F15B RESOLVED (2026-07-15, same session): both moved out of BLANK via
adc_read_sequence_main (0x1556d) and gear_state_config_loader_f1fc
(0x20f28) -- see updated table rows above.
  - F161 (0x39): genuine live ADC channel #8 signal (F160/F161 word),
    independent of the neighboring MAP/Boost channel. Physical sensor
    identity still open.
  - F15B (0x3B): CONFIRMED DEAD. F15A/F15B is zeroed then immediately
    read back in the same function with no other writer anywhere in the
    ROM, so it always reads 0. Same class of finding as the MUT_83/0xF0BB
    dead cell from the 2026-07-13 session -- do not log this RequestID.
This is a good illustration of the approach note above generalizing
beyond *_calc/*_duty/*_target functions: the adc_read_sequence_*
functions are the actual ADC-channel producer layer underneath most of
the F1xx sensor block and are worth checking directly for any remaining
BLANK row in that address range before assuming "no producer exists."
[NOTE: lines 601/675-687 in this file had corrupted/duplicated text from
an earlier same-session edit collision (stray "olved jump..." fragment
and a truncated "deBits..." line) - found and repaired 2026-07-15 while
processing the uploaded XML files below. If anything in the
sci1_periodic_phase_dispatch_f526 section above looks inconsistent with
review.md's copy of the same finding, review.md is the fallback source
of truth - it was not affected by this corruption.]

EFI/TCU MUT PROFILE CROSS-CHECK, ROUND 2 (2026-07-15, user-uploaded XML)
--------------------------------------------------------------------------
User uploaded Mitsubishi_MUTII_EFI.xml (107 entries) and
Mitsubishi_MUTII_TCU.xml (13 entries) directly. Diffed both against the
current master table above.

EFI FILE FINDINGS:
- ReqID 0x1C (F187) was BLANK in the table but this XML clearly names it
  "ECULoad" (Eval="5*x/8", clips at 160) - missed in the original
  2026-07-13 build. Table updated to NAMED (untraced).
- ReqID 0x00 now has a THIRD conflicting claim: this same XML has an
  internal collision between "LoadMUT2Byte" and "gmas"/"Airflow Rate
  gm/s" at the same RequestID - not just a cross-file conflict with the
  GalantLegnum switch-flags claim already on record. Table row updated
  with all three claims listed; do not trust any one without live
  tracing.
- ReqID 0x12 (F111, EGRTemp) has a secondary claim "LC1WidebandO2" in
  the same XML, but its own Notes describe it as requiring an external
  0-5V sensor wired in by the user - a hardware-mod repurposing, not a
  genuine claim about the stock ROM. EGRTemp remains the primary lead,
  noted but not treated as a real conflict.
- FC = "Clear EFI Diagnostic Codes" in this file. CORROBORATES the
  2026-07-15 SCI1 command-dispatcher finding (review.md item 7,
  "UPDATE 2026-07-15" paragraph) that command 0xFC triggers
  startup_phase_reset_eed6_eefa_bulk via eee0_eeee_diag_flags_reset_dispatch
  - the disassembly-only trace inferred "bulk reset trigger" structurally;
  this XML confirms the semantic meaning independently (diagnostic code
  clear). Worth citing in that review.md item if revisited.
- Everything else in the file (0x21/0x29/0x38/0x3C/0x4A multi-name
  entries) is expected EvoScan-side formula/bit-label reuse of a single
  byte for several derived display values, or external accessory pseudo-
  IDs (ZTX/LC1/WDB/DLPIO8 - Zeitronix, Innovate LM-1/LC-1, wideband, and
  digital-logger-pod hardware, NOT real ECU MUT RequestIDs at all) - not
  genuine conflicts, no table changes needed for those.
- No other currently-BLANK row in the table matched anything in this
  file - the 0x1C miss above appears to be the only gap from the
  original build.

TCU FILE FINDINGS (NEW SCOPE - not previously covered anywhere in this
file or review.md):
- This ROM/vehicle has a SEPARATE MUT RequestID scheme for the TCU
  (transmission control) side, entirely distinct from the EFI table
  above and not yet cross-checked against any live TCU-side disassembly
  in this project. 13 entries: AT_ID1/2/3 (00/01/03, identification
  bytes), AT_Temp (86, transmission temp), AT_Park/AT_Reverse (B4,
  packed bit flags), AT_Neutral/AT_Drive (B3, packed bits),
  AT_Low/AT_2nd/AT_3rd/AT_OutputShaftSpeedPulse/AT_InputShaftSpeedPulse
  (A8, packed bits), AT_Brake (AA, packed bit), AT_ClearDTC (FC).
- CORRECTION (2026-07-15, per user): on this vehicle the TCU is a
  SEPARATE PROCESSOR living inside the same PCM housing as the EFI ECU,
  with its OWN MUT table - not a second logical channel on the same H8
  reachable from this program's SCI1/SCI3 dispatcher. There is likely
  NOTHING in common between the EFI-side RequestID scheme documented
  throughout this file and the TCU-side scheme in the uploaded XML.
  Retracts the "shared physical serial link" / "reachable from the same
  SCI1/SCI3 family" speculation below - that assumption was wrong.
- AT_ClearDTC also happening to use command FC is very likely COINCIDENCE
  (or a shared EvoScan/diagnostic convention across unrelated Mitsubishi
  ECUs) rather than evidence of a shared command dispatcher - do NOT cite
  this as corroboration for the EFI-side eee0_eeee_diag_flags_reset_dispatch
  finding. That finding stands on its own EFI-side evidence only.
- This table has NOT been cross-referenced against anything - there is no
  live TCU-processor ROM open in this project at all (this program is the
  EFI/PCM-side H8/539F ROM only). The tcu_* functions already traced in
  this project (tcu_shift_torque_and_knock_mgmt, tcu_periodic_dispatch,
  tcu_shift_ratio_buffer_update, tcu_torque_converter_slip_calc, etc.) are
  logic running on the EFI-side H8 that COMMUNICATES WITH the separate TCU
  processor (e.g. via the SCI1/SCI3 links documented in review.md item 7)
  - they are NOT the TCU processor's own code, and have no relationship to
  this RequestID scheme.
- NEXT STEP if pursued: this project would need the TCU processor's own
  ROM dump/disassembly (a different physical chip, not covered by the
  currently-open RVR_1998_x3 program) before any of these 13 IDs could be
  traced to real addresses. Not started - out of scope for this project's
  current Ghidra program unless/until a TCU ROM is obtained.

NOT YET DONE: the bulk of the ~150 BLANK/NAMED-untraced rows remain
untraced. Next step agreed with user: continue working the *_calc/
*_duty_*/*_target_*/*_stepper_* function list against the table, and
prioritize clusters adjacent to CONFIRMED cells (per the F5C0 and
F970-F973 precedents) over isolated BLANK rows, since isolated BLANK
rows have so far always come back zero-hit on static xref.

PRODUCER-SIDE SWEEP, ROUND 3 (2026-07-22 session)
------------------------------------------------------------------
Continued the *_calc function-list approach from Round 2.

EE8C-EE96 cluster (ReqID 0x60-0x65): addresses independently RE-CONFIRMED --
these already carry live Ghidra data labels MUT_60_entry..MUT_65_entry at
ROM 0x2fb90 (6-entry, 2-byte-stride table), so the master table's scrape was
correct. ONE writer found: inj_channel_state_init (0x21f00, renamed from
FUN_00021f1a in an earlier pass -- same function, Ghidra just resolved a
mid-body address to it) unconditionally sets all six to neutral value 0x8080,
no gating conditions. No runtime/per-cycle updater found despite checking
every *inj*- and *cyl*-named function (fueling_inj_pw_calc, which DOES show
a genuine 4-way per-cylinder repeating write pattern at F186/188/18A/18C +
F190/192/194/196 -- confirming this ROM does use per-cylinder arrays
elsewhere, just not reachable from this specific search for THIS cluster).
Plate comment added to inj_channel_state_init documenting all of this.
Remains OPEN: if these 6 values move during live logging, a real runtime
writer exists via indirect addressing not yet located; if they never move,
likely an unused/init-only feature.

F84F/EEFB/F4DF/F4DD/F4E5/F4E7/F4EB/F4DB cluster (ReqID 0x8C-0x93): addresses
RE-CONFIRMED via live Ghidra data labels MUT_8C_entry..MUT_93_entry at ROM
0x2fbe8 (8-entry, 2-byte-stride table, immediately following WGDCCorr/0x8B
and preceding the F0BB dead-cell run at 0x94/0x95). Disassembly comment
added at 0x2fbe8 documenting this. Checked three nearby *_calc functions as
candidate producers -- all ruled out, none write any of the 8 target
addresses:
  - o2_heater_duty_f4da_calc (0x19bbc): confirmed real O2 heater PWM duty
    writer (F4DA only), plate comment added.
  - isc_f4d6_gated_offset_calc (0x259df): computed offset, no direct RAM
    store in this function body, plate comment added.
  - f4de_f4e2_octane_correction_calc (0x265c9): confirmed writer of F4DE/
    F4E0/F4E2 (a related-but-distinct triplet, F4E0 not previously
    documented as part of this write group), plate comment added.
No producer found for any of the 8 cluster addresses. All three ROM-level
findings above should be considered solid/current; the producer question
for this cluster remains genuinely open.

DP=2 POINTER TABLE (<0xC0 dispatcher branch) -- RESOLVED (2026-07-22 session)
------------------------------------------------------------------
Followed up on review.md item "c" (resolve the <0xC0 pointer table in
sci1_meta_cmd_dispatch_c0_ff @0x28869, gating whether Mode5 RequestIDs
01-06/17/1A map onto it).

MECHANISM CONFIRMED (grammar-level, not guesswork this time): the relevant
instruction is `mov:g.w @(-0x530:16,R0),R1` at 0x2887e, preceded by
`ldc.b 0x2,DP` at 0x2887b. This EA form compiles via h8539f.slaspec's
eaw_disp16 constructor, which uses Rn_banked (NOT raw Rn) as its base:
  Rn_banked "R0" (Rn=0): local addr:4 = (zext(DP) << 16) | zext(R0); export addr;
  eaw_disp16: tmp = (Rn_banked + disp16); export *:2 tmp;
So the effective address is ((DP<<16)|R0) + disp16, evaluated as a full
24-bit quantity (banking happens BEFORE the disp16 add, confirmed by
decompile_function's own constant-folded output under tracked_set:
`((param_4 << 1) | 0x20000) - 0x530`, where 0x20000 = DP(2)<<16). This
matches the space="ram" default_memory_blocks layout, which per
list_segments has a SEPARATE lowercase "ram" block spanning 0x10000-0x2ffff
(the ROM image itself, loaded at base 0x10000) alongside the real chip
"RAM" block at 0xee80-0xffff. DP=2 banked addresses land in the ROM/"ram"
block, not chip RAM -- consistent with this being a ROM-resident pointer
table, not a runtime-computed one.

For cmd_byte=0x01 (Fuel Pump Relay, one of the 8 disputed Mode5 rows):
  addr = ((2<<16) | (0x01<<1)) - 0x530 = 0x020002 - 0x530 = 0x1FAD2

LIVE ROM CHECK: read_memory/inspect_memory_content at 0x1fad2, and swept the
entire plausible table span for cmd_byte 0x00-0xBF (0x1FAD0-0x1FC4E, 384
bytes) plus generous padding on both sides (0x1F800-0x1FC90, ~1200 bytes
total) -- ALL 0xFF. This is unprogrammed/blank flash, not a decode error
(0x1fad2 itself IS a valid, in-range address inside the ram:0x10000-0x2ffff
block -- reads succeed and return real backing bytes, they're just all
0xFF, unlike a truly out-of-range address which fails outright as
confirmed by contrast-testing 0x2530 directly, which errors with "Unable
to read bytes").

CONCLUSION: on THIS ROM image (RVR_1998_x3 4g63t 21000011 md352553.hex),
the DP=2 pointer table that would service SCI1 command bytes <0xC0 is
entirely blank. Every command byte in that range that reaches the table
read will dereference 0xFFFF -> attempt a byte read at ROM 0xFFFFFF-ish
(FF as page, i.e., effectively an invalid/wrapped access) -- this branch
is a dead/unimplemented code path on this specific ROM revision, not a
live actuator-command mechanism. Confirms (rather than merely leaves open)
that RequestIDs 01-06/17/1A do NOT map onto anything live via this route
either. Combined with the earlier finding that they also don't fall in the
0xC0-0xFF table-driven range, there is now no remaining live-code candidate
mechanism for those 8 RequestIDs on this ROM -- they should be treated as
inherited-but-unimplemented on this specific calibration, not merely
"unverified." mut_verification_status.md's Mode5 XML fix (below) can be
updated accordingly if desired, though "(UNVERIFIED)" vs "(UNIMPLEMENTED ON
THIS ROM)" is a wording choice, not a new investigative step -- the
open item is effectively closed absent a different ROM revision to compare
against (a different .hex file/calibration might have this table
programmed; not checked, out of scope for this ROM).

Reachability check: sci1_meta_cmd_dispatch_c0_ff has exactly one caller,
sci1_dispatch_and_latch_response (0x2882b), consistent with the existing
plate comment -- this is a static-reachability check, not proof the <0xC0
branch never executes in the field, but combined with the blank table it
would return garbage/0xFF if it ever did fire.

REACHABILITY CONFIRMATION + MODE5 ACTUATOR ID SUMMARY (2026-07-22, same
session, follow-up to the DP=2 table finding above)
------------------------------------------------------------------
Re-verified the caller chain end-to-end rather than trusting the prior
write-up on faith:

- sci1_dispatch_and_latch_response (0x2882b) calls sci1_meta_cmd_dispatch_c0_ff
  UNCONDITIONALLY on command-byte value -- gated only by flags f522 bit6=1/
  bit5=0, never by the byte's range. Confirmed via decompile_function, not
  assumption.
- The command byte itself is read from RAM 0xf534. get_bulk_xrefs on 0xf534
  returns zero (known banked-access blind spot), but search_byte_patterns
  found it referenced at 0x16759 (sci1_rx_frame_accumulator). That function
  computes `((DAT_0001f584 << 1) | 0x10000) - 0xacc`, which equals exactly
  0xf534 when the running index f584 is 0. f584 is an incrementing 0-10
  index into an 11-byte accumulator filled from DAT_0001fecd (the live
  SCI1 UART receive-data register) as bytes arrive on the wire.
  CONCLUSION: 0xf534 is byte 0 of the real SCI1 receive-frame buffer --
  i.e. it's genuinely the first byte of whatever a connected tool sends
  over the wire, completely unfiltered before reaching the dispatcher.
  This means the blank DP=2 table found above is a real, reachable dead
  end for any tool that ever sends a command byte <0xC0 -- not a
  hypothetical/unreachable code path.
- Spot-checked the 0xC0-0xD8 actuator bit table at ROM 0x13740 directly
  against raw bytes (read_memory, 80 bytes from 0x13740): confirmed byte0=1/
  byte2-3=0x0000 (stub/mask=0) for entries C0-C4, then a clean descending
  one-bit sweep (0x10,0x08,0x04,0x02,0x01) starting at entry C5, exactly
  matching the existing plate comment with no discrepancy found.

FINAL ANSWER, Mode5 (Actuator Test) RequestIDs, this ROM
(RVR_1998_x3 4g63t 21000011 md352553.hex):

| ReqID | Name (per XML profile, UNCONFIRMED on this ROM) |
|-------|--------------------------------------------------|
| 0x01  | Fuel Pump Relay                                   |
| 0x02  | EGR Solenoid                                      |
| 0x03  | Purge Control Solenoid                            |
| 0x04  | A/C Relay                                         |
| 0x05  | Condenser Fan Hi/Lo (exact split unclear)         |
| 0x06  | Condenser Fan Hi/Lo (exact split unclear) or 6th distinct actuator |
| 0x17  | Ignition Timing Fix                               |
| 0x1A  | ISC Step Fix                                      |

STATUS: none of these 8 IDs correspond to anything live on THIS ROM.
Exhaustive check of both candidate mechanisms came back negative:
  (1) 0xC0-0xFF table-driven dispatcher: fully decoded, real bit-toggle
      logic exists here, but for different command byte VALUES (0xC0+),
      not 0x01-0x1A. No overlap.
  (2) <0xC0 DP=2 pointer table: mechanism now fully resolved (see above),
      and the entire table span is unprogrammed 0xFF on this ROM image.
Names above are inherited from a generic Mitsubishi MUT-II EFI profile
template, not confirmed by anything this ROM's own code does. Do not
transmit any of these 8 commands to a real vehicle expecting a specific
effect -- best current evidence is they do nothing (or return garbage) on
this specific calibration.

OPEN, NOT YET DONE: whether a different ROM revision (e.g.
"RVR_1998_x3 4g63t 21000012 md352554.hex" or the w4a51 AT calibration,
both present in test/rvr/roms/) has this same DP=2 table actually
programmed. Not checked -- out of scope unless revisited.

PHYSICAL OUTPUT PIN TRACE (2026-07-22, "work backward from real hardware
outputs" session)
------------------------------------------------------------------
Different approach from the sci1_meta_cmd_dispatch_c0_ff RAM-flag chain:
instead of starting from command bytes, started from the H8's real port
data registers (P1DR-PCDR, ROM 0xfe80-0xfe97, confirmed via list_globals)
and traced backward to find genuine physical-output-driving code, since the
f510/f512/f516 flag chains kept terminating in further RAM state machines
with no confirmed hardware meaning (and one earlier hypothesis this
session -- that f516's high bits drove a PWM dual-speed fan -- was
CHECKED AND REFUTED: fec0-fed5 are SCI1/2/3 UART registers per
list_globals, not a timer/PWM peripheral; see the corrected plate comment
at 0x28700).

FOUND: mirror_status_f0e6_to_ports (ROM 0x156ce, now labeled) is a genuine
RAM-flag-to-port-pin mirror -- 8 bits of RAM 0xf0e6 map directly onto real
P1DR/P2DR/P4DR/P6DR/PCDR pins, several gated by per-variant ROM config
bytes at 0x102e4-0x102ee. RAM 0xf0e6 itself has been labeled
output_relay_flags_f0e6. Full bit map:

  bit0 (0x01) -> P1DR.4, direct
  bit1 (0x02) -> P2DR.7, gated by ROM byte 0x102ee
  bit2 (0x04) -> P4DR.7, gated by ROM byte 0x102ed (polarity flips on its bit3)
  bit3 (0x08) -> PCDR.3, direct, INVERTED (bit clear = pin set)
  bit4 (0x10) -> P4DR.4, gated by ROM byte 0x102e4==1
  bit5 (0x20) -> PCDR.6, same gate as bit4
  bit6 (0x40) -> PCDR.7, direct
  bit7 (0x80) -> P1DR.5, gated by ROM byte 0x102e6==0
  bit13(0x2000)-> P6DR.2, INVERTED, gated by f1f6 bit3

ONE bit's writer fully traced: bit3, via knock_octane_f0e6_bit3_gate_dispatch
(ROM 0x284a3). Sets/clears based on an RPM threshold, the EED6/EED8/EEDA
per-cylinder cluster (same cluster used by the warmup/calibration-select
system under f516_request_latch_f09a_calib_select), and a call into
knock_octane_pattern_match_state_machine (ROM 0x28557) -- a bit-pattern
state machine over the EED0-EEE8 array family driving internal timers
f51a/f51c/f51e/f04a, structurally consistent with misfire/sustained-knock
pattern detection. HYPOTHESIS (not confirmed against real hardware): PCDR
bit3 is a check-engine/MIL lamp driver or a knock-condition dash warning
output. This is circumstantial -- flag as unconfirmed if cited elsewhere.

The other 8 bits (0/1/2/4/5/6/7/13) are NOT yet traced beyond a one-shot
unconditional set of bit1 at cold-init (engine_state_f498_init, 0x17302 --
not diagnostically useful). ~20 more xref sites to f0e6 exist in the ROM,
untraced: 0x17341/173d5/173db/174c9/174cf/1861d/18623/187ba/187c2/18bb1/
18bbb/18dbf/18dc5/18ddd/19359/1935f/19377/197ce/197d8/19806/19891/19904/
1998f/19e4c/27c94 -- these are the natural next targets, since they're the
best current lead for identifying genuine actuator names (fuel pump relay,
A/C clutch relay, radiator fan, etc.) against real physical pins rather
than unconfirmed RAM-flag semantics. Also worth doing the same "start from
port registers, trace backward" sweep for P3DR/P5DR/P7DR/P8DR/P9DR/PADR/
PBDR, which haven't been checked yet at all this session.

NOTE ON SCOPE: this thread grew out of trying to identify more MUT
actuator-test names beyond the 8 (Fuel Pump Relay/EGR/Purge/AC Relay/
Condenser Fan Hi-Lo/Ignition Timing Fix/ISC Step Fix) already found
unmapped-on-this-ROM in the DP=2 pointer table finding above. It has NOT
yet produced a confirmed mapping back to any MUT/EvoScan-style RequestID
or actuator name -- it's a parallel, independent hardware-level
investigation, not (yet) a resolution of the original Mode5 RequestID
question. The two threads may or may not converge; worth keeping in mind
if resuming either one.

SESSION CORRECTIONS + FIRST CONFIRMED SCI1-DISPATCHER-TO-PHYSICAL-PIN CHAIN
(2026-07-22, continuation of "PHYSICAL OUTPUT PIN TRACE" above)
------------------------------------------------------------------
Two corrections to prior work in this same session, both caught and fixed
before propagating further -- noting the process here since it's a useful
lesson for future signature-naming work: eyeballing a long combined
read_memory hex dump for a repeating-structure table is error-prone.
Individual per-entry read_memory calls anchored on absolute address are
slower but far more reliable; use that method when precision matters (e.g.
finalizing a table's entry count or a specific bit assignment).

CORRECTION 1: cmd_c0_d8_actuator_bit_table (ROM 0x13740) is 25 entries
(cmd 0xC0-0xD8 inclusive), not 20 as the original plate comment said.
Confirmed the table's true end: bytes immediately after the 0xD8 entry
(0x137a0+4) break the 4-byte-entry pattern entirely.

CORRECTION 2: f516_hibits_f520_f0f2_mode_select (0x28700) does NOT drive a
PWM dual-speed radiator/condenser fan, despite its graduated f0f2 mode
values initially looking exactly like a plausible fan-speed selector. The
consuming peripheral registers (0xfec0-0xfed5) are confirmed via
list_globals to be SCI1/2/3 UART SMR/BRR/SCR/TDR/SSR/RDR registers, not a
timer/PWM channel -- this is UART baud-rate/serial-config switching, most
likely a slow-init-handshake vs fast-K-line-comms speed change typical of
MUT/ISO-style diagnostic protocols. Plate comment at 0x28700 corrected in
place so this dead end isn't picked up as a lead again.

NEW FINDING: first confirmed end-to-end chain from a sci1_meta_cmd_dispatch_c0_ff
command byte all the way to a real physical output pin:
  cmd 0xD8 -> sets f510 bit1 (cmd_c0_d8_actuator_bit_table entry 24,
    00 ff 00 02, triple-confirmed via independent read_memory calls)
  -> read by engine_mode_f20e_f510_check (0x174a1): true unless
    (f20e bit4 SET AND f510 bit1 CLEAR)
  -> consumed by ign_advance_f0e6_bit7_update (0x173c0), gated on ROM
    config byte 0x102e6==0
  -> sets/clears output_relay_flags_f0e6 (0xf0e6) bit7
  -> mirrored by mirror_status_f0e6_to_ports (0x156ce) onto P1DR bit5
    (physical pin 0xfe82), same 0x102e6==0 gate
This is the FIRST bit in the whole sci1_meta_cmd_dispatch_c0_ff table with
a fully traced path to a real port pin. Confidence on the CHAIN itself is
high (every link independently verified against live disassembly/memory).
Confidence on WHAT PHYSICAL COMPONENT P1DR.5 actually drives is LOW -
f20e is an extremely widely-shared engine-mode flag word (170+ xref sites,
not practically fully traceable), so the physical identity is only a weak
inference (ignition-confirm/coil-adjacent, given the function's inherited
name "ign_advance_f0e6_bit7_update" and f20e's general "engine
running/ignition active" flavor) - NOT a confirmed component name. Do
not treat "P1DR.5 = ignition output" as established; it's a lead only.

Also worth noting: cmd 0xD8's table entry (0x0002) breaks what was
otherwise a perfectly clean descending-by-half bit sweep across D4-D8
(0x0040, 0x0020, 0x0010, 0x0008, then D8 should be 0x0004 by the pattern
but is actually 0x0002) - unexplained irregularity, possibly a deliberately
skipped/reserved bit2, not yet investigated further.

REMAINING WORK for full f510/f512/f516 physical-pin identification (the
"completely name everything" goal): systematically trace every other bit's
reader the same way bit1 was just traced here - i.e. for each bit,
find its RAM consumer function, then follow that consumer's output until
it either reaches a real port register (P1DR-PCDR, confirmed labeled) or a
clearly-general/shared system (like f20e or f502) where further tracing
isn't practical. The ~20 untraced output_relay_flags_f0e6 (0xf0e6) writer
xref sites listed in the "PHYSICAL OUTPUT PIN TRACE" section above remain
the best next targets, plus doing the same "start from port register,
trace backward" sweep for P3DR/P5DR/P7DR/P8DR/P9DR/PADR/PBDR which haven't
been touched at all yet.

EGR + PURGE SOLENOID FINDINGS (2026-07-22, continuation of port-backward
trace)
------------------------------------------------------------------
Continued the f0e6 writer sweep. Three more bits identified, two with
high confidence and coherent, self-consistent gating logic:

- f0e6 bit1 -> P2DR.7 (0xfe83) = EGR solenoid control. Writer:
  egr_f0e6_bit1_update (0x18600), gate: egr_activity_condition_check
  (0x18628), RPM-windowed (disabled at engine-off and at high RPM with a
  decaying counter active). NOT reachable from sci1_meta_cmd_dispatch_c0_ff
  -- purely internal engine-state driven. Same ROM gate byte (0x102ee)
  used by both writer and port-mirror side.

- f0e6 bits4+5 (mask 0x30) -> P4DR.4 (0xfe87) + PCDR.6 (0xfe97) = EGR
  valve position/sequence drive (two-bit, likely open/close or step
  direction). Writer: egr_f0e6_valve_bits_update (0x18b63), fed by RAM
  0xf490 (an EGR valve-state word maintained by a larger EGR state machine
  -- egr_sequence_control @ 0x187cf, egr_mode_dispatch @ 0x187a0 which
  selects between 3 hardware EGR variants on ROM byte 0x102e4: 0=none,
  1=this sequence drive, 2=egr_position_target_f494_calc, a different
  position-target strategy not yet traced). NOT reachable from the SCI1
  dispatcher either -- also purely internal.

- f0e6 bit2 -> P4DR.7 (0xfe87) = canister PURGE solenoid control. Writer:
  purge_f0e6_bit2_update (0x18db0), gate: purge_enable_check (0x18dca),
  RPM/coolant-temp hysteresis-band gated (classic purge-control pattern).
  ***THIS ONE IS REACHABLE FROM THE SCI1 DISPATCHER*** -- purge_enable_check
  has a force-override path: when f20e bit4 is SET and f510 bit8 is SET,
  purge is forced active regardless of the normal hysteresis. f510 bit8
  is set by sci1_meta_cmd_dispatch_c0_ff command byte 0xD1 (table entry
  17, 00 ff 01 00 at ROM 0x13784, confirmed via read_memory). Full chain:
    cmd 0xD1 -> f510 bit8 -> purge_enable_check override
    -> output_relay_flags_f0e6 bit2 -> P4DR.7 (physical pin)
  This is the STRONGEST candidate found in the whole investigation for a
  genuine, externally-triggerable MUT/EvoScan-style actuator command on
  this ROM -- recommend prioritizing this for real-hardware verification
  if that becomes possible. Exact real-world f20e-bit4 trigger condition
  not fully pinned down (f20e is the same widely-shared 170+-xref flag
  word noted elsewhere as impractical to fully trace), but the mechanism
  itself, cmd byte through to the physical pin, is fully confirmed live.

RUNNING TALLY of output_relay_flags_f0e6 bits identified so far:
  bit0: ISC/knock-condition-gated, NOT SCI1-reachable (P1DR.4)
  bit1: EGR solenoid, NOT SCI1-reachable (P2DR.7)
  bit2: PURGE solenoid, SCI1-REACHABLE via cmd 0xD1 (P4DR.7)  <-- best lead
  bit3: TWO writers (see below), NOT SCI1-reachable (PCDR.3)
  bit4+5: EGR valve position/sequence (two-bit), NOT SCI1-reachable
        (P4DR.4 + PCDR.6)
  bit6: writer not yet traced (PCDR.7)
  bit7: SCI1-REACHABLE via cmd 0xD8 (f510 bit1), physical meaning LOW
        CONFIDENCE (P1DR.5, weakly inferred ignition-adjacent)
  bit13: writer not yet traced (P6DR.2) -- but see f510 bit13/0x2000
        read by o2_upstream_enable_check below, a possible lead
Remaining genuinely untraced: bit6 (PCDR.7), bit13 (P6DR.2).

XREF SWEEP, ROUND 4 (2026-07-22 session, continuation): worked through the
remaining ~12 untraced f0e6 xref sites listed above. Most resolved to
functions already covered by name (get_function_by_address confirmed each
address before treating it as new, per this file's own methodology note):
0x17341 -> inside engine_state_f498_init (already known, cold-init bit1
set). 0x1861d -> inside egr_f0e6_bit1_update (already known). 0x19e4c ->
inside channel_dispatch_and_snapshot_update (already known F5C0 snapshot
function; decompiled directly this round to confirm it only READS f0e6
bit0 into F5C8, adds no new writer).

bit0 CONFIRMED: writer is isc_f0e6_bit0_update (0x174c0, already named from
an earlier pass but not yet decompiled/closed out). Full body is a clean
two-way branch on knock_condition_eval() -- sets bit0 if knock condition
true, clears it otherwise. No SCI1/dispatcher involvement. NOT
SCI1-reachable.

bit3 has a SECOND writer, not previously documented: warmup_state_f594_f0e6_init
(0x27c86) unconditionally ORs in bit3 (`DAT_0001f0e6 = DAT_0001f0e6 | 8`) as
part of a 3-line warmup-state init (also sets F09A from a ROM constant and
F594=0x41). This is separate from and additional to the already-known
conditional writer knock_octane_f0e6_bit3_gate_dispatch (0x284a3, RPM/knock-
pattern gated). Two writers to the same bit -- one unconditional warmup-set,
one conditional runtime gate -- is a real, not-yet-reconciled finding; the
bit3->MIL/warning-lamp hypothesis should be treated as even less certain
until the warmup-init interaction is understood (does warmup unconditionally
turn the lamp/output ON, later governed by the runtime gate?). Neither
writer is SCI1-reachable.

NEW MULTI-BIT FIELD FOUND (separate from the tracked bit0-7/13 set):
o2_sensor_control_dispatch (0x19720) writes f0e6 bits 8-11 (mask 0xf0ff,
i.e. `uVar2 | (f0e6 & 0xf0ff)`) based on O2 sensor upstream/downstream
enable-check results (o2_upstream_enable_check @0x197f4,
o2_downstream_enable_check @0x198f2). This nibble is NOT part of the
port-pin bit0-7/13 set documented above (no entry in
mirror_status_f0e6_to_ports' bit map for bits 8-11) -- likely an internal
O2-control-mode field, not a physical-pin flag. Not yet further traced;
noting for completeness since it came up in the same xref sweep.

Also of note: o2_upstream_enable_check (0x197f4) reads f510 bit13 (0x2000)
as part of its override-gating logic (`(f20e & 0x10)==0 || (f510 &
0x2000)==0`), alongside its read of f0e6 bit8/9. This is the same f510
word the SCI1 dispatcher writes bits into for the purge (bit8) and P1DR.5
(bit1) chains above -- worth checking whether anything in
sci1_meta_cmd_dispatch_c0_ff's table sets bit13, which would make O2
sensor override SCI1-reachable too. NOT YET CHECKED.

STILL OPEN, next targets: bit6 (PCDR.7) and bit13 (P6DR.2) writers
remain untraced -- no candidate xref site from the original ~20-site list
turned out to touch them; a fresh xref/byte-pattern sweep specifically
for these two bits (rather than relying on the original generic f0e6
xref list, which turned out to be dominated by already-covered
functions) is the concrete next step.

XREF SWEEP, ROUND 5 (2026-07-22 session, continuation): re-ran the F0E6
byte-pattern search fresh (broader than the original ~20-site list -- 28
hits total this time, including 3 new addresses: 0x156d1 (inside
mirror_status_f0e6_to_ports itself, expected), 0x28538/0x2853e (inside
knock_octane_f0e6_bit3_gate_dispatch, already known). Checked every
remaining unresolved address via get_function_by_address before treating
as new, per this file's own methodology note.

BIT6 NOW FULLY RESOLVED. Writer is f0e6_bit6_update (0x19350, already
labeled from an earlier pass but not yet decompiled/closed out) -- clean
two-way branch on ign_advance_rpm_zone_enable_check() (0x19364), same
shape as bit0/bit7's writers. That check function is an RPM-zone
hysteresis gate (ROM lookup tables 0xd6e/0xd70/0xd72 selected by f43e
state, load-based override via f186) with a CONFIRMED SCI1 override path:
it also reads f510 bit7 (0x80) alongside f20e bit4, bypassing the normal
RPM/load check when both are set. f510 bit7 is set by
sci1_meta_cmd_dispatch_c0_ff command byte 0xD2 (table entry 18, ROM
0x13788, confirmed via direct read_memory: bytes `00 ff 00 82` -- byte0=0
selects f510, mask 0x0082 sets bits 1 AND 7 simultaneously). This also
resolves the "D8 sweep irregularity" flagged earlier in this file and in
review.md: cmd 0xD2's two-bit mask (0x0082) is not an anomaly in the D-row
sweep pattern -- it deliberately triggers two independent override checks
at once (bit7 for this ign_advance_rpm_zone_enable_check chain, bit1 for a
still-unfound separate consumer, NOT to be confused with the different
"bit1" already traced via cmd 0xD8/engine_mode_f20e_f510_check, which is a
different f510 bit1 reference entirely despite the coincidental naming --
re-verify carefully if revisited).

This is a THIRD confirmed SCI1-reachable actuator chain on this ROM (after
cmd 0xD1's purge-solenoid override and cmd 0xD8's P1DR.5/f0e6-bit7 chain):
  cmd 0xD2 -> f510 bit7 -> ign_advance_rpm_zone_enable_check override
  -> output_relay_flags_f0e6 bit6 -> PCDR.7 (physical pin)
Physical real-world component identity is still NOT confirmed (same
low-confidence "ignition-adjacent" inference as the bit7/P1DR.5 chain,
based on naming continuity with ign_advance_f0e6_bit7_update rather than
independent hardware verification) -- treat as a lead, not a fact.

BIT13 REMAINS GENUINELY OPEN (as an f0e6 output-pin writer). Exhaustive:
all 28 hits from the fresh F0E6 byte-pattern sweep are now accounted for
(either the port-mirror function itself, or one of the already-documented
bit0/1/2/3/4+5/6/7 writers/gates). None write f0e6 bit13 (mask 0x2000).
This is consistent with this ROM's known static-analysis blind spot for
bank-prefixed/indirect RAM writes (same class of gap documented elsewhere
in this file for Knock Voltage, Coolant Temp, and others) -- f0e6 bit13's
writer, if a dedicated one exists, is not reachable via a directly-encoded
literal-address instruction. f1f6 bit3 (which gates whether f0e6 bit13 is
mirrored to P6DR.2 at all, per mirror_status_f0e6_to_ports) was checked as
an adjacent lead (search_byte_patterns "F1 F6", 9 hits) but NOT further
traced this round -- a plausible next step.

CORRECTION to the previous round's note (2026-07-22, same session,
verified via direct read_memory rather than left as a flagged assumption):
f510 bit13 (the DIFFERENT bit13, on a different RAM word, read by
o2_upstream_enable_check as part of its O2-sensor-override gate) IS
SCI1-reachable after all. sci1_meta_cmd_dispatch_c0_ff's 0xC0-0xD8 table
entry for cmd 0xCD, at ROM 0x13770 (confirmed via read_memory: bytes
`00 ff 20 00`), targets f510 (byte0=0) with mask 0x2000 = bit13. This
directly matches the bit o2_upstream_enable_check (0x197f4) reads as part
of its `(f20e & 0x10)==0 || (f510 & 0x2000)==0` override-gating condition.
So the O2 sensor upstream-enable override chain (cmd 0xCD -> f510 bit13 ->
o2_upstream_enable_check override -> o2_sensor_control_dispatch's f0e6
bits8-11 field) is a FOURTH confirmed SCI1-reachable chain on this ROM,
alongside cmd 0xD1 (purge), 0xD8 (P1DR.5/f0e6 bit7), and 0xD2 (PCDR.7/f0e6
bit6). Unlike the other three, this one does not terminate in a physical
port pin (f0e6 bits8-11 are an internal O2-control-mode field per the
earlier finding, not part of mirror_status_f0e6_to_ports' bit map) -- so
its real-world effect, if any, is forcing the ECU's O2 sensor read/control
logic into an override mode rather than toggling a discrete relay/solenoid.
Physical significance not yet assessed; flagging as a genuine new lead,
not yet fully characterized.

RUNNING TALLY, UPDATED (2026-07-22, end of session): f0e6 bits 0/1/2/3
(x2 writers)/4+5/6/7 all have confirmed writers; only bit13 remains
untraced. Three of those chains (bit2/purge, bit7/P1DR.5, bit6/PCDR.7)
are confirmed SCI1-reachable via cmd 0xD1/0xD8/0xD2 respectively. A
fourth SCI1-reachable chain (cmd 0xCD -> f510 bit13 -> O2 sensor override)
exists but does not terminate in f0e6/a physical pin -- tracked
separately, not folded into the f0e6 tally.


master list for actually logging the car, built from this file's earlier
rounds. It already correctly reflects most of the CONFIRMED/OPEN/BLANK
rows above, including the full 2026-07-14 Unk_0xNN sweep.

BUG FOUND AND FIXED (2026-07-22): its Mode5 (Actuator Tests) block had 8
rows (RequestID 01/02/03/04/05/06/17/1A -- Fuel Pump Relay, EGR Solenoid,
Purge Control Solenoid, A/C Relay, Condenser Fan Hi/Lo, Ignition Timing Fix,
ISC Step Fix) each annotated "[RAM CONFIRMED ...]" pointing at the MODE 2
address for that same RequestID number -- e.g. RequestID 0x17 here claimed
RAM 0xf13d, which is actually TPS's real, independently-confirmed Mode2
address, not anything actuator-related. This was a paste-across error: the
Mode2 annotation template got copied onto Mode5 rows without updating the
underlying mechanism.

What's actually confirmed on the actuator side (see review.md item 7 /
"REAL COMMAND DISPATCHER FOUND" section above for the original trace,
extended this session by a full decompile of sci1_meta_cmd_dispatch_c0_ff,
0x28869): a genuine, live actuator/relay dispatcher exists, handling SCI1
command bytes 0xC0-0xFF with direct bit manipulation on RAM F510/F512/F516,
gear-indexed reads via F1FC into ROM tables at 0x232/0x252, and real H8
hardware timer register names (T2CRH, TMDRA) appearing in the disassembly.
Actuator-test functionality 100% EXISTS in this ROM -- not in question.

What remains UNRESOLVED: whether RequestIDs 01-06/17/1A (the 8 disputed
rows) map onto this 0xC0-0xFF dispatcher at all. They structurally do NOT
(all 8 values are <0x20, nowhere near the 0xC0-0xFF range), so either (a) a
different, not-yet-found mechanism handles them, or (b) these specific
RequestIDs don't correspond to anything real on this ECU and were inherited
from generic EvoScan/Evo tooling convention without verification. A second
candidate mechanism was explored: the SAME dispatcher function also handles
command bytes <0xC0 via a DP=2-banked pointer table (raw instruction:
`ldc.b 0x2,DP` + `mov:g.w @(-0x530:16,R0)`). This table was NOT resolved --
this project has no verified DP-bank-to-physical-address mapping for the
H8/539F SLEIGH implementation (confirmed via h8539f-sleigh-grammar notes),
and a manual resolution attempt this session (assuming DP=2 maps linearly
to a fixed offset) was unverified guesswork, not a confirmed finding -- it
should NOT be trusted or built upon without independently deriving the real
DP-bank semantics first, ideally with input from someone who knows this
specific H8 variant's banking hardware.

FIX APPLIED: the 8 Mode5 rows had their false "[RAM CONFIRMED]" claims
removed, Display names marked "(UNVERIFIED)", and Notes rewritten to
explain exactly which real Mode2 address was mistakenly borrowed for each,
plus a block comment above <Mode5> explaining the full situation (real
dispatcher exists and is solid; these specific RequestIDs don't provably
connect to it; do not transmit any of these 8 commands to a real vehicle
without independent verification, since an unverified ACTUATOR command --
unlike a read-only Mode2 item -- could trigger unintended hardware action).

NEXT STEP if pursued: either (a) get a real DP-bank mapping (from hardware
docs or someone familiar with this H8 variant) and properly resolve the
<0xC0 pointer table, or (b) determine some other way whether these 8
RequestIDs correspond to anything real on this ECU at all.
