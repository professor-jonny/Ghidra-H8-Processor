Review 2: RVR XML axis/table address verification
====================================================================

Scope: verify and correct table/axis ADDRESSES ONLY in the RVR XML
(21000011_1997-2001_RVR_X3_Mt__4g63t_.xml) against the live
RVR_1998_x3 4g63t 21000011 md352553.hex ROM in Ghidra. Naming is out
of scope -- existing table/axis names are left as-is even when a fix
moves the address to a different real-world quantity than the name
implies. Purely a data-integrity pass.

Source list for this batch: the H8539F-TABLE-*-OVERLAP /
H8539F-AXIS-DATA-OVERLAP bookmark set (Ghidra bookmark export,
2026-08-01), covering table/data address collisions and axis/axis
collisions flagged during ROM scraping. After this batch: the ~94
"Unknown"-category scraper-derived TABLE_2D_*/TABLE_3D_* tables with
placeholder axis info (deliberately wrong axis, set only so data is
visible in EcuFlash -- see review.md item 20) get the same treatment.

Method (per entry):
1. Read raw ROM bytes at the flagged/candidate address(es).
2. Classify header shape against the confirmed scraper signatures
   (from h8539_ecu_master_setup.py Step 8b/8c, CHANGELOG.md):
   - 3D value table: 7-byte header `0x03 | pad | X-ptr(word) | Y-ptr(word) | nrows`
   - 2D value table: 4-byte header `0x02 | pad | axis-ptr(word)`
   - Scaling table: 6-byte header `[F0-F7] xx [E0-FE] xx 00 [02-90]`
3. Confirm data curve is sane (monotonic-ish, terminates at/near a
   0xFF sentinel before the next real table's header starts).
4. Where possible, find the real caller (table_lookup_interp @0x14656 /
   axis_lookup_interp @0x14735 / table_lookup_indexed @0x14854 /
   table_read_indexed @0x14880) via literal-push byte search and
   disassembly, and confirm the literal pointer + bank-adjustment.
   CONFIRMED FORMULA (2026-08-01, verified against 3 independent call
   sites): callers push a 16-bit offset then an 8-bit bank immediately
   before the pjsr:
     mov:g.w #0xXXXX:16,@-SP   ; 16-bit offset
     mov:g.w #0xN:8,@-SP       ; bank N
     pjsr @0x14735/0x14656/0x14854/0x14880
     real_address = N * 0x10000 + 0xXXXX
   Byte encoding for the search: `BF 07 <hi> <lo>` = mov:g.w #imm:16,@-SP;
   `BF 06 <imm>` = mov:g.w #imm:8,@-SP (bank). Use search_byte_patterns
   on `BF 07 <hi> <lo>` (the offset half of the candidate real address)
   to find literal-push callers directly.
   IMPORTANT CAVEAT learned this pass: a 2D/3D value table's own header
   axis-ptr field is a RAM address (not a ROM pointer) -- it's the RAM
   cell an axis_lookup_interp call writes its interpolated
   {index,fraction} result into (the record's own first word, "value_ptr").
   Two different tables can legitimately share one axis_lookup_interp
   record via this RAM cell (e.g. Load/RPM globals reused by many 3D
   maps), OR the same RAM tag can turn up on multiple *unrelated*,
   independently-real ROM records (seen at least twice this pass) that
   just happen to reuse the same scratch RAM pair. Matching a table's
   axis-ptr RAM value against a scaling-table record's value_ptr is a
   *lead*, not proof -- always confirm with a literal-push caller trace
   (or get_xrefs_to on the table's own address, the 8/8 DATA-xref
   pattern from items 3/4/6) before writing an XML change.
5. Record verdict: CONFIRMED CORRECT / CONFIRMED WRONG (+ real
   address if found) / UNRESOLVED, with the evidence.
6. Only write XML changes for CONFIRMED items. Never guess.

Status key: OPEN / CONFIRMED / WRONG-FIXED / WRONG-UNRESOLVED

--------------------------------------------------------------------
Batch 1 -- H8539F-TABLE-*-OVERLAP / H8539F-AXIS-DATA-OVERLAP bookmarks
--------------------------------------------------------------------

1. Air Temperature Compensation (2D) -- XML addr 0002af74 lands on
   real code (`beq LAB_0002afbe`), not a table.
   STATUS: CONFIRMED WRONG (already resolved in review.md item 19,
   2026-07-30). Real table found independently at 0x11d7a via
   iat_axis_update (0x21396) -- confirmed live call to
   table_lookup_interp with #0x1d7a/mode=1. Header 02 00 F0D0 at
   11d7a, 7-byte monotonic curve (158,143,135,129,122,115,106),
   0xFF sentinel at 11d85, sits back-to-back with Post Start Enrich
   Trim vs Load (11d86), no gap/overlap. Axis at 2d4a6 (F0D0 F118
   0007 header) -> real 7-element breakpoints at 2d4ac
   (8,33,49,63,78,96,125). XML already updated per review.md:
   table address="11d7a", axis address="2d4ac". VERIFIED COMMENT:
   correct as-is, carry forward, no further action.

2. Accel Enrichment (2D) -- flagged suspect solely for overlapping
   'Low Octane Fuel Map 1' (00011cb1 vs 00011bc0).
   STATUS: CONFIRMED WRONG -- byte-verified live 2026-08-01.
   Read 11bc0 onward directly: real header 03 00 F0C0 F0C2 0E
   (mode=3, stride=14). Full data body traced byte-by-byte to its
   real 0xFF sentinel at 0x11ccb (261 bytes of real curve data,
   11bc8-11cca). 0x11cb1 (the flagged address) is offset 0x11 into
   this table's own live data (byte value 0x8d) -- NOT a second
   table, not a real overlap between two tables at all. The
   "OVERLAP" framing on this bookmark is itself the bug: there's one
   real table (11bc0) and one bad address (11cb1) landing inside it.
   Immediately following the real sentinel at 11ccb is a SEPARATE,
   genuinely real header at 0x11ccc: 02 00 F0C8 (mode=2, single-axis
   2D), monotonic curve visible (60,56,50,46,3c,33,23,20,17,0e,0a...).
   Confirmed live consumer of 0x11ccc: decel_fuel_cut_eval (0x222a6)
     222ce: mov:g.w #0x1ccc:16,@-SP   (table pointer)
     222d2: mov:g.w #0x1:8,@-SP       (EP bank = 1)
     222d5: pjsr @0x14656:24          (table_lookup_interp)
   Call chain: decel_fuel_cut_eval <- f25e_bit6_update_from_decel_fuel_cut
   <- main_control_loop_update (real, reachable, periodic).
   Separately confirmed: fueling_accel_enrichment_calc (0x21aa5, the
   function the "Accel Enrichment" name implies) contains ZERO calls
   to table_lookup_interp/axis_lookup_interp/table_lookup_indexed --
   pure fixed-point arithmetic via div_s32_s16_rounded/
   div_u32_u16_rounded/identity_passthrough_arg1. This table is
   definitely not consumed by anything resembling accel-enrichment
   logic.
   VERIFIED COMMENT for XML (address only, name left as-is per scope):
     "Accel Enrichment" address corrected 11cb1 -> 11ccc. Real header
     at 11ccc (mode=2), real single-axis 2D table, confirmed live
     caller decel_fuel_cut_eval via main_control_loop_update. NOTE:
     despite the address fix, this table's actual function is decel
     fuel cut related, not accel enrichment -- naming correction is
     out of scope for this pass but flagged for whoever next touches
     names.
   Axis: mode=2 header means single embedded axis, no separate
   axis_lookup_interp call seen at this call site -- TO CONFIRM: check
   whether table_lookup_interp internally reads an axis pointer from
   within the 0x11ccc record itself (would need decompiling
   table_lookup_interp @0x14656, not yet done this pass).

3. Boost Enhancement Enrich/Enlean (Anti-lag) Map (3D) -- flagged
   suspect solely for overlapping 'Warmup Retard' (000124ec vs
   000124f9).
   STATUS: CONFIRMED CORRECT (per review.md item 19, 2026-07-30).
   124ec = confirmed real record pointer, 8/8 xrefs. Real data 342
   bytes, 0xFF sentinel at 12649. XML address 124f3 = 124ec+7,
   matches the mode-3 (3D) convention. Warmup Retard's old address
   (124f9) was the bug, not this table -- see item 4 below.
   No XML change needed for this entry.

4. (from same overlap pair) Warmup Retard -- old XML address 124f9
   overlapped Boost Enhancement's own confirmed data.
   STATUS: WRONG-FIXED (per review.md item 19, 2026-07-30, already
   applied). 124f9 had ZERO xrefs, sat only 13 bytes into Boost
   Enhancement's real data -- not a separate table. False lead
   (11ccc) tried and retracted (wrong mode byte: Warmup Retard needs
   mode=3/Load+RPM per XML's own axis element counts, 11ccc's
   neighborhood didn't fit). Real table found at 0x1264a -- second
   mode-3 header immediately after Boost Enhancement's real end,
   header 03 14 F0C0 F0C2 12 (stride 0x12=18), distinct 342-byte
   curve (confirmed different values from Boost Enhancement's own,
   ruling out copy-paste duplication), own sentinel at 127a7.
   CONFIRMED via get_xrefs_to: exactly 8 DATA xrefs at 1264a
   (0x2da0c-0x2da28), same index-block confirmation signature used
   throughout this file. XML already corrected: address="12651"
   (1264a+7, mode-3 convention). Axis element counts (Load 19, RPM
   17) left unchanged -- note real data is 342 bytes/stride 18, not
   a clean 19x17=323, worth a follow-up check if EcuFlash renders a
   trailing gap. No further action needed for the table address
   itself.

5. Injector Battery Voltage Latency Compensation -- flagged suspect
   for overlapping 'Desired ISCV intial step position with AC
   off-Neutral' (000128a3 vs 000128a2).
   STATUS: CONFIRMED WRONG, XML entry removed (per review.md item 19,
   2026-07-30, RESOLUTION). Ghidra bookmark
   H8539F-TABLE-DATA-OVERLAP-CORRECTED at 0x128a2 carries a
   ROM-scraper plate comment confirming the real table at that
   address IS "Desired ISCV intial step position with AC
   off-Neutral" (4-byte header, data at 128a6, ending ~128d6). The
   claimed Injector Battery Voltage Latency Compensation range
   (128a3-128ad, XML addr 128a7) falls entirely inside that real
   table's own header+data -- there was never a second, independent
   table there. No code-verified table_lookup_interp/
   table_lookup_indexed/table_read_indexed call site was ever found
   for this table across 9 checked candidate callers (see review.md
   item 19 continuation). XML entry commented out permanently (not
   pending replacement -- none exists or should be sought).
   No further action needed.

6. Desired ISCV intial step position with AC off-Neutral (the other
   side of item 5's overlap) -- 000128a2.
   STATUS: CONFIRMED CORRECT (per review.md item 19). 8/8 xrefs
   confirm 128a2 is real. No XML change needed.

7. TABLE_2D_00011EE2 (2D) -- flagged suspect for overlapping 'Decel
   Fuel Cut Resume Enrich' (00011ee2 vs 00011f04).
   STATUS: CONFIRMED, applied per review.md item 20 (2026-07-31).
   This was one of the "3 remaining H8539F-TABLE-DATA-OVERLAP-
   CORRECTED bookmarks never written to XML" -- corrected to
   header+4-bytes per ROM-scraper plate comment, matching the
   established 2D convention (11EE2 -> 11EE6). Placeholder RPM axis
   left untouched deliberately (scaffolding, not a real axis claim --
   applies to all ~94 "Unknown" category tables, see Batch 2 below).
   XML already updated. No further action needed for THIS entry's
   own address; "Decel Fuel Cut Resume Enrich" (11f04) not
   independently re-checked this pass -- TO VERIFY.

8. TABLE_2D_0002D3C0 (2D) -- flagged suspect for overlapping 'TPS
   (axis of Max Total Upward WGDC Correction vs TPS)' at 0x2D3C8.
   STATUS: CONFIRMED, applied per review.md item 20 (2026-07-31).
   Corrected to header+4-bytes (2D3C0 -> 2D3C4) per ROM-scraper
   plate comment, same convention as item 7. XML already updated.
   'TPS (axis of Max Total Upward WGDC Correction vs TPS)' AXIS_TPS
   at 2d3c8 -- CHECKED 2026-08-01, see item 10 below: confirmed not a
   real axis (lands in the table's own data body), real candidate
   axis is 0x2d3fe but TABLE_2D_0002D3C0's own caller still unfound,
   so this entry's axis address is WRONG-UNRESOLVED, not yet fixable.

9. TABLE_2D_0002D668 (2D) -- flagged suspect for overlapping 'RPM
   (axis of Accel Enrichment)' at 0x2D68A.
   STATUS: CONFIRMED, applied per review.md item 20 (2026-07-31).
   Corrected to header+4-bytes (2D668 -> 2D66C) per ROM-scraper
   plate comment. XML already updated. 'RPM (axis of Accel
   Enrichment)' AXIS_RPM at 2d68a NOT independently re-checked this
   pass -- TO VERIFY. NOTE: "Accel Enrichment" name reappears here
   too (different address, 2d68a is an axis not the 11ccc table from
   item 2) -- another naming-vs-address mismatch candidate, out of
   scope for this pass per naming being excluded, flagged only.

10. AXIS_TPS mislabel note (from review.md item 20, found in passing).
    STATUS: WRONG-UNRESOLVED (byte-verified 2026-08-01, table's own
    caller not found -- see item 8 update below for the shared
    context). AXIS_TPS @ 0x2d3c2 is not a real axis record at all: it
    lands squarely inside TABLE_2D_0002D3C0's OWN header (bytes 2-3 of
    "02 00 F0C2", i.e. the table's axis-ptr field itself, not a
    separate structure). The item 8 overlap address (0x2d3c8) also
    isn't real -- it lands 4 bytes into the table's own data body.
    Real axis record with matching leading RAM tag (F0C2) confirmed to
    exist at 0x2d3fe (F0C2 F0BA 0007, 7 elements: 33,65,97,129,161,
    193,225) -- this is the SAME record independently confirmed live
    via literal-push caller in item 11 below (used by
    f0ba_f2d0_o2_mode7_8_correction_calc for O2 mode 7/8 correction,
    not TPS/AXIS_TPS's old tcu_shift_torque_and_knock_mgmt lead, and
    not "Max Total Upward WGDC Correction vs TPS" either). NOT FIXED:
    could not find any literal-push caller for TABLE_2D_0002D3C0
    itself (checked both header 0x2d3c0 and data-start 0x2d3c4 --
    zero xrefs, zero literal pushes). The table/axis RAM-tag match
    (F0C2) is suggestive but per the Method step 4 caveat above is not
    proof by itself, especially since a second, unrelated record also
    sharing a different RAM tag pair (F0C2/F0BA) was found nearby at
    0x2d356 (16 elements) -- this ROM reuses RAM scratch pairs across
    multiple independent records, so tag-matching alone can't
    disambiguate here. Likely reached via computed-pointer-array
    indirection (same category as Batch 2's expected difficulty).
    NEXT STEP: find TABLE_2D_0002D3C0's real caller via
    table_lookup_indexed/table_read_indexed indirection before
    touching this XML entry.
    2026-08-01 FOLLOW-UP: decompiled table_lookup_indexed (0x14854) --
    it takes an ARRAY BASE POINTER as a stack parameter (pushed by its
    caller, same literal-push convention as axis/table_lookup_interp)
    plus a global index variable (0x1f1fc, masked &7) to pick 1 of up
    to 8 pointer-array entries. Searched for a literal push of
    TABLE_2D_0002D3C0's address as an ARRAY BASE (not as a direct
    table pointer) -- same zero-result outcome (`BF 07 D3 C0` / `D3 C4`
    still not found anywhere, and this table has no 8-DATA-xref array
    pointing to it the way items 3/4/6/12's ignition maps do). Also
    tried get_xrefs_to on the array-base candidates for already-
    CONFIRMED tables (e.g. 0x2da0c, the Warmup Retard/Boost Enhancement
    array) and got zero hits even there -- meaning array-base pointers
    themselves are apparently never referenced via a discoverable
    static xref/literal-push anywhere in this ROM, even for tables we
    are certain are real and correctly wired. The array base must be
    computed/loaded through an addressing mode Ghidra's static xref
    engine doesn't track (e.g. PC-relative table-of-tables one level
    up, or register-indirect through a value set by yet another
    function). This is a structural limitation, not a search-pattern
    problem -- REMAINS BLOCKED. Confirmed one more useful negative:
    TABLE_2D_0002D3C0 is definitively NOT part of the
    knock_octane_dual_axis_table_blend_f2a8 call chain (see item 12
    follow-up below) -- that function's arrays (0x2d9ac/0x2d9cc/
    0x2d96c/0x2d98c) resolve to 0x11abc/0x11f74-adjacent ignition
    tables, nothing at 0x2d3c0/2d3c4. No further lead to chase without
    a fundamentally different technique (e.g. symbolic execution or
    manual trace of the ISR/dispatch table that ultimately reaches
    fuel-table consumers). Recommend deferring to a dedicated session
    focused on cracking the array-base addressing mode generally, since
    this will also block most of Batch 2's ~94 tables.

11. RPM (axis of 'Limp Home - TPS Table') -- flagged overlapping TPS
    axis of the same table at 0x2D3F8 (overlap addr 0x2D3EE).
    STATUS: WRONG-FIXED (2026-08-01, XML updated).
    Byte reads confirmed: RPM axis header IS correctly at 0x2d3ee
    (F0C0 F170 0005, 5 elements: 128,256,512,768,1024 raw) -- no
    change needed. TPS axis was wrong on both address and element
    count: XML claimed 2d3f8/5-elem, but 0x2d3f8 lands mid-data inside
    the RPM record's own body (2d3ee's data spans 2d3f4-2d3fd). Real
    TPS axis header is 6 bytes later at 0x2d3fe (F0C2 F0BA 0007), 7
    elements: 33,65,97,129,161,193,225.
    LIVE CALLER CONFIRMED via disassembly (search_byte_patterns on
    `BF 07 D3 EE` and `BF 07 D3 FE`, bank-adjustment formula from
    Method step 4): f0ba_f2d0_o2_mode7_8_correction_calc (0x242f5,
    called from engine_periodic_correction_master_dispatch, a real
    reachable periodic function) pushes literal 0xd3ee then 0xd3fe
    (bank=2 both times) into axis_lookup_interp (0x14735)
    back-to-back, immediately before table_lookup_interp(0x11dc2)
    (bank=1, offset 0x1dc2 -> 0x11dc2, matching the Limp Home table's
    own address neighborhood, 11dc9 = 11dc2+7 per 3D convention).
    NOTE: the live caller is O2 sensor mode 7/8 correction, not
    limp-home logic as named -- naming correction out of scope for
    this pass, flagged only.
    XML APPLIED (test/rvr/xml/ecuflash/new/
    21000011_1997-2001_RVR_X3_Mt__4g63t_bac.xml): TPS axis
    address="2d3f8" elements="5" -> address="2d3fe" elements="7".
    RPM axis address="2d334" -> address="2d3ee" (was already wrong in
    the working XML, not just stale from review.md's notes -- see
    audit comment in the XML for full detail). elements="5" unchanged.

12. RPM (axis of 'Boost Desired Engine Load # 1') -- flagged
    overlapping RPM axis of 'High Octane Ignition Map 1' at 0x2D332
    (overlap addr 0x2D334).
    STATUS: PARTIALLY RESOLVED -- real record found and live-confirmed,
    but NOT applied to XML pending a Load/RPM identity conflict.
    Neither 0x2d332 nor 0x2d334 is a real header -- both fall inside
    one real axis record's own data (element 0 and element 1
    respectively). Real header: 0x2d32c (F0C0 F170 0012, 18 elements,
    full data read and confirmed monotonic 0->2816 raw, sentinel/next
    header at 0x2d356).
    LIVE CALLERS CONFIRMED via disassembly (search_byte_patterns on
    `BF 07 D3 2C`): TWO callers found, both Idle Speed Control
    functions -- isc_f34e_f34a_correction_calc (0x25742) and
    isc_f374_correction_calc (0x25e8b) -- NOT "Boost Desired Engine
    Load # 1" or "High Octane Ignition Map 1" as the XML names claim.
    Naming mismatch flagged, out of scope per this file's stated
    scope.
    BLOCKER before writing XML: read High Octane Ignition Map 1's
    real header directly (0x11f74, confirmed via 8/8 DATA xrefs at
    0x2db6c-0x2db88, same signature as items 3/4/6 -- table address
    11f7b = 11f74+7 is ALREADY correct, no change needed there). That
    header is X-ptr=F0C0, Y-ptr=F0C2, and this file's own convention
    is X=Load/Y=RPM for 3D maps -- meaning F0C0 (0x2d32c's RAM output)
    may actually feed the LOAD axis here, not RPM as item 12's name
    assumes. Additionally "Boost Desired Engine Load # 1"'s XML
    element count (9) doesn't match 0x2d32c's 18 at all, suggesting it
    may need a different, not-yet-found record entirely rather than
    2d32c. Writing an RPM-axis fix here risks a wrong Load/RPM swap --
    NOT applied, deliberately held back per Method step 6 (never
    guess). NEXT STEP: trace which specific RAM cell (F0C0 or F0C2)
    the ISC functions above actually populate as *output* semantically
    (Load vs RPM), and separately locate "Boost Desired Engine Load #
    1"'s real 9-element axis record (currently unknown).
    2026-08-01 FOLLOW-UP: found the real caller chain for the ignition
    maps -- knock_octane_dual_axis_table_blend_f2a8 (0x233a0), reached
    via table_lookup_indexed's callers list. Its disassembly is clean
    (no decompiler ambiguity this time):
      axis_lookup_interp(0x2d2e0, bank=2)   -- RPM, 14 elements
      axis_lookup_interp(0x2d302, bank=2)   -- Load, 18 elements
      then btst 0x5,@0xf0f8 selects array base 0x2d9ac (set) or
      0x2d9cc (clear) -> table_lookup_indexed (Map "1" pair)
      then btst 0x7,@0xf1f2 (nested w/ 0xf0f8 bit5) selects
      0x2d96c or 0x2d98c -> table_lookup_indexed (Map "2" pair)
      result blended via table_read/interp (0x14599), written to F2A8.
    This RESOLVES the Load/RPM identity question from the note above:
    swapxy="true" on these table XML entries means the header's X-ptr
    (F0C0) maps to the XML's "RPM/Y Axis" entry and Y-ptr (F0C2) maps
    to "Load/X Axis" -- so F0C0=RPM is correct as item 12 originally
    assumed, my earlier worry about a Load/RPM swap was unfounded.
    HOWEVER this does NOT confirm 0x2d32c (item 12's original
    candidate) as the real RPM axis for these ignition maps -- the
    live-traced RPM axis actually used here is a DIFFERENT record,
    0x2d2e0 (14 elements: matches this file's own ROM notes at the
    top, "RPM axis @2d2b0: 500-7000 RPM (14 elem)"), and the Load axis
    is 0x2d302 (18 elements, data at 2d308, matches "Load axis @2d308:
    10-260% (18 elem)"). 0x2d32c (18 elements, confirmed via items 12's
    original work to be called only by isc_f34e_f34a_correction_calc
    and isc_f374_correction_calc) is NOT part of this call chain at
    all -- it's a genuinely separate, ISC-only axis unrelated to any
    currently-named ignition/boost XML table.
    NEW COMPLICATION: the pointer array pushed here (0x2d9ac, selected
    when octane-flag bit0xf0f8:5 is set) does NOT point to 0x11f74/
    11f7b (the address the XML currently uses for "High Octane
    Ignition Map 1", independently confirmed via its OWN 8/8 DATA-xref
    array at 0x2db6c-0x2db88). It points to 0x11abc instead -- read
    directly, all 8 entries identical (00 01 1A BC = bank 1, offset
    0x1abc). This means there are apparently TWO independently-real
    ROM tables that could each plausibly be "the" high-octane ignition
    map depending on which subsystem is traced: the one at 0x11f74
    currently in the XML, and this one at 0x11abc feeding the knock/
    octane blend. Untangling which is the EcuFlash-tunable table (or
    whether both legitimately coexist for different purposes -- e.g.
    one being an internal knock-correction sub-map, the other the
    primary displayed map) needs dedicated investigation, not
    inference. NOT resolved, NOT applied to XML. "Boost Desired Engine
    Load # 1"'s real 9-element axis is still completely unlocated --
    not found in this follow-up either. REMAINS PARTIALLY RESOLVED /
    BLOCKED. Genuinely useful confirmed sub-finding worth keeping
    regardless of the above: 0x2d2e0 (RPM, 14 elem) and 0x2d302 (Load,
    18 elem) are a real, live-confirmed axis pair for at least the
    octane-blend logic and match this file's own top-of-file ROM
    notes -- good candidates to check against Low Octane Ignition Map
    1/2 and the Boost Enhancement/Warmup Retard family in a future
    pass, since several of those currently reuse addresses (2d332/

    RESOLVED AND APPLIED (2026-08-01, later same session): found the DIRECT
    literal-push caller for "Boost Desired Engine Load # 1" itself, no tag-
    matching or indirection needed. Function at 0x191a0 pushes
    axis_lookup_interp(0xd5d6, bank=2) then IMMEDIATELY table_lookup_interp
    (0x2af8, bank=1) = 0x12af8 -- this exact table, direct adjacency, the
    same strength of evidence as item 11's fix. Real axis: 0x2d5d6 (F0C0
    F190 0009, 9 elements: 0,64,128,192,256,320,384,448,512 raw) -- element
    count already matched XML (9), only the address (2d334) was wrong.
    XML APPLIED: RPM axis address="2d334" -> address="2d5d6", elements
    unchanged.

    Separately, ALSO re-derived "High Octane Ignition Map 1"'s real axis
    pair with much stronger evidence than the earlier "matching tag" lead:
    isc_f34e_f34a_correction_calc (0x25742) pushes axis_lookup_interp
    (0xd32c)+axis_lookup_interp(0xd37c) [bank=2] back-to-back, immediately
    followed by table_lookup_indexed(0xdb6c) [bank=2] -> array base
    0x2db6c, which Ghidra's OWN xref engine independently confirms (8/8
    DATA xrefs) resolves to 0x11f74 (11f7b = 11f74+7, matches the existing,
    correct XML table address). This closes the loop cleanly: RPM axis =
    0x2d32c (18 elem, unchanged), Load axis = 0x2d37c (19 elem, unchanged,
    old address 2d382 was its data-start not header, same recurring bug).
    XML APPLIED to "High Octane Ignition Map 1" only.
    IMPORTANT, checked before extending this fix further: read the raw
    bytes of isc_f34e_f34a_correction_calc's OTHER array selection at this
    branch point (0x2db8c, the function's alternate path when the F0F8
    bit5 flag is clear) -- it resolves to 0x120d2 (-> 0x120d9, "High Octane
    Ignition Map 2"), NOT "Low Octane Ignition Map 1" (12237) as the
    High/Low-octane naming would suggest. So this specific F0F8 bit5 check
    is a Map1/Map2 selector, not a High/Low-octane selector -- "Low Octane
    Ignition Map 1"'s real axis is NOT confirmed by this chain and was
    deliberately left untouched (still on the old 2d382/2d332 placeholder).
    Also NOT touched, still needing individual verification before any fix:
    Boost Enhancement Enrich/Enlean (Anti-lag) Map (124f3, shares the old
    2d382/2d332 placeholder but its own caller wasn't traced this session),
    Warmup Retard (12651, RPM elements="17" in XML -- doesn't match 2d32c's
    18, so it definitely needs a DIFFERENT axis, not a copy of this fix),
    Max Wastegate Duty #1-4 (12a96/12aaa/12abe/12ad2, elements="16", also
    doesn't match, needs its own trace). Do not blanket-apply 2d32c/2d37c
    to any of these without the same per-table caller verification used
    above -- this file's own top-of-file ROM notes already list several
    same-tagged-family axes with different element counts (2d2b0/14,
    2d332-area/18, plus whatever the 16/17-element ones turn out to be),
    confirming this RAM tag family is reused by many distinct, differently-
    sized real records, not one universal axis.
    ALSO NOTE: the ~90 "Unknown"-category TABLE_2D_*/TABLE_3D_* scraper-
    derived entries elsewhere in this XML (Batch 2's placeholder tables)
    also default to the same 2d332/2d382 placeholder pair, each with an
    explicit inline comment marking it as deliberate and unresolved. None
    of those were touched either -- resolving them individually is Batch
    2's job, not a blanket find-and-replace, for the same reason as above.

    ARRAY-INDIRECTION SCRIPT COVERAGE CHECK (2026-08-02): after the
    review.md byte-signature sweep found 9 total functions sharing the
    bank/record calling convention (see review.md's 2026-08-02 update),
    checked which of the newly-found ones are actually candidates for the
    ResolveTableReadIndexedArrays.java-style array-indirection script (i.e.
    which ones read an 8-slot array of {pad,bank,hi,lo} POINTERS to resolve
    further, vs which just read raw calibration values directly with no
    further indirection to discover). Determined by shift-count in each
    function's own disassembly (shll.w before the array index add): *4
    stride (two shll.w) = 4-byte pointer array, candidate; *2 or *1 stride
    (one or zero shll.w) = raw value array, not a candidate at all --
    running the pointer-resolution script against those would misinterpret
    calibration data as bogus bank/offset pairs.
      table_3axis_interp_triple_wrapper (0x1497b): *4 stride, candidate.
      Wrote ResolveTable3AxisWrapperArrays.java (same technique, retargeted
      at 0x1497b), ran it: 0 call sites found in this ROM. Same negative-
      result situation as gear_indexed_table_lookup_f1fc (already recorded
      above) -- nothing to resolve, not a bug, just unused in this build.
      table_read_word_indexed_f1fc (0x14838): *2 stride, NOT a candidate --
      its array is 8 raw uint16 calibration values, no addresses to find.
      read_indexed_byte_f1fc (0x1481c): *1 stride (no shift), NOT a
      candidate -- 8 raw bytes, same reasoning.
    Net result: every function in the 9-member family that COULD benefit
    from this script has now either had it run (table_lookup_indexed,
    table_read_indexed: real results; table_3axis_interp_triple_wrapper,
    gear_indexed_table_lookup_f1fc: confirmed zero callers) or been
    confirmed structurally inapplicable (table_read_word_indexed_f1fc,
    read_indexed_byte_f1fc). table_lookup_interp/axis_lookup_interp/
    table_3axis_interp_triple are the remaining 3 -- these are the DIRECT
    (non-array) record consumers, a different case entirely (single
    literal-push resolution via search_byte_patterns, not array-walking);
    that's the technique used throughout Batch 1/2 above, not this script.
    2d382) that this session has now cast doubt on.

--------------------------------------------------------------------
Batch 2 -- ~94 "Unknown" category scraper-derived TABLE_2D_*/
TABLE_3D_* placeholder-axis tables (deliberately wrong/scaffolding
axis info, set only so EcuFlash renders the data -- see review.md
item 20). NOT YET STARTED. Same verification method applies, but
expect most axis addresses to require the "find the real reader"
approach (computed-pointer-array indirection, per review.md item 20's
unresolved High Octane Ignition Map 1 precedent) rather than a
literal call-site push, since item 20 already tried and failed the
literal-push approach across all 94 targets and all 22 known lookup
functions.

--------------------------------------------------------------------
SESSION HANDOFF (2026-08-01, continuation session) -- start here if
picking this up fresh. Everything below is ALSO logged in more detail
in review.md items 21-22; this is the condensed pointer + what to do next.
--------------------------------------------------------------------

WHAT HAPPENED THIS SESSION (separate track from Batch 1/2 above, but
directly useful to them):

1. RETURN-STORAGE AUDIT (review.md item 21). Found and fixed a real bug
   class: some dispatcher functions (table_lookup_interp @0x14656,
   table_3axis_interp_triple @0x148a2, table_lookup_indexed @0x14854) were
   declared `void` in Ghidra despite real callers capturing their return
   value -- the computed result was being silently discarded in every
   decompile. Fixed via:
     ghidra:set_function_prototype(function_address="<addr>",
       calling_convention="__stdcall_far_2arg",
       prototype="ushort <name>(byte ep_val, void *table)")
   CAVEAT: this call also reliably drops the `table` parameter's storage
   back to <UNASSIGNED> every time (pre-existing quirk, already documented
   in table_lookup_interp's own plate comment before this session touched
   anything -- NOT something this session broke). set_variable_storage
   cannot fix it either (tool says GUI or custom Pcode/HighVariable script
   required). STILL UNRESOLVED, real follow-up needed if param binding
   matters for further work.
   ~30 other functions checked, left alone (already correct -- see item 21
   for the full list so they're not re-checked from scratch).
   Two harder candidates flagged, NOT fixed: octane_trim_f262_f264_table_
   select's table_read_indexed usage (looks like a genuine multi-register
   return, extraout_R1+R2, needs its own investigation, do not naively
   ushort-ify table_read_indexed), and read_indexed_byte_f1fc (0x1481c, byte
   vs word return-width mismatch, noticed in passing).
   Follow-up grep sweep (bug signature: bare call immediately before
   `return;`) found 5 more superficial candidates, ALL verified as false
   alarms via real disassembly (not just decompile) -- egr_sequence_control,
   ign_advance_top_update/wgdc_correction_integrator_update,
   isc_openloop_stepper_scale_calc. No new bugs. Good confirmation the 3
   fixes were the real bugs, not the tip of an iceberg.

2. ARRAY-BASE INDIRECTION SCRIPT (review.md item 22) -- THE BIG ONE,
   directly unblocks this file's own Method step 4 caveat and item 10's
   "structural limitation, remains blocked" conclusion above. Diagnosis
   (credited to an external analysis document): Ghidra's static xref engine
   cannot and will never automatically discover table_lookup_indexed's
   array-base -> runtime-indexed-target relationship, because the real
   target address only exists after a runtime read of a global index
   variable (`array[*(0x1f1fc) & 7]`) -- there's no static address-of
   relationship to record. Fix: don't fight the limitation, encode the
   ROM's own convention directly via a Ghidra script that:
     - finds all real callers of table_lookup_indexed via
       get_function_callers (Ghidra DOES track the call itself fine --
       just not what happens inside)
     - backward-scans each call site for the pushed (offset, bank) pair
       (same method as the original table_lookup_interp extractor)
     - creates an explicit refMan.addMemoryReference(callSite,
       arrayBaseAddr, ...) -- the missing link
     - reads each array's 8 slots (4 bytes each: byte0=pad, byte1=bank,
       bytes2-3=offset) and adds a reference from each slot to its real
       resolved target
   Ran against all 14 real call sites (9 calling functions). 100% resolved
   cleanly. 5 cross-validated against already-known-correct tables
   (Warmup Retard 0x1264a, High Octane Ignition Map 2 0x120d2, Low/High
   Octane Fuel Map 1 0x11bc0/0x119b8, Desired ISCV step position 0x128a2).
   6 NEW table addresses surfaced: 0x128ae, 0x11880, 0x1288a, 0x12896,
   0x11cea, 0x1238e.
   XML CROSS-CHECK of those 6 (this file's actual job):
     - 0x128ae, 0x12896: ALREADY CORRECT in XML ("Desired ISCV intial step
       position with AC off-Drive", "Desired Idle RPM-Drive"). No action.
     - 0x11880: found as TABLE_2D_00011880, an "Unknown"-category Batch 2
       placeholder table. NEW LEAD for Batch 2 -- real caller now known
       (fueling_base_injection_calc via array 0x2da8c), gives a real
       subsystem identity even though axis still unresolved. PRIORITIZE
       this one in Batch 2 given the head start.
     - 0x1288a, 0x11cea, 0x1238e: NOT IN THE XML AT ALL (zero matches).
       Genuinely undocumented tables, not mis-addressed existing entries.
       Adding them is a bigger task than this file's address-only scope
       (needs type/axis/scaling from scratch). NOT attempted. Separate
       follow-up project, not folded into Batch 1/2.

IMMEDIATE NEXT STEPS (pick any):
  (a) Run the SAME array-base-indirection script technique against the
      OTHER indexed lookup functions in this ROM (table_read_indexed
      @0x14880, gear_indexed_table_lookup_f1fc @0x149a7, and any others
      sharing the same array-selector pattern) -- very likely to surface
      more real table addresses the same clean way, per review.md item 22's
      own method note. Not yet done.
  (b) Prioritize TABLE_2D_00011880 in the Batch 2 placeholder-axis project
      now that its real caller is known.
  (c) Continue Batch 2 generally (still NOT YET STARTED per this file's
      original bottom section) -- now with one more tool in the kit
      (the array-reference script) than when Batch 2 was originally scoped.
  (d) Investigate the 3 genuinely-undocumented tables (0x1288a, 0x11cea,
      0x1238e) as their own new-table-addition project.
  (e) Separately: the return-storage param-binding quirk (table_lookup_
      interp/table_3axis_interp_triple/table_lookup_indexed all losing
      their non-first parameter's storage on every set_function_prototype
      call) still needs a real fix -- would require either manual GUI work
      or a custom Pcode/HighVariable-level Ghidra script, per
      set_variable_storage's own tool response. Not attempted.

GOTCHAS TO REMEMBER (cross-session):
  - run_script_inline auto-wraps submitted code in its own class scaffold.
    Submit ONLY bare statements/method-body code, never a full "public class
    X extends GhidraScript" declaration, or the two wrappers nest and javac
    fails with "illegal start of expression" (see review.md item 19). Two
    dead orphan script files (TableExtract.java, TableExtractV2.java) exist
    from this mistake early on -- harmless, ignore the recurring stale
    compile-error preamble Ghidra prints because of them on every script
    run.
  - Always dry_run:true a new script before applying for real.
  - Bank-adjustment formula (confirmed across many independent call sites):
    real_address = bank*0x10000 + offset, from a push pair
    `mov:g.w #offset:16,@-SP` then `mov:g.w #bank:8,@-SP` immediately before
    the pjsr.
  - Array-slot format (confirmed across all 14 sites this session): 4 bytes
    per slot, byte0=pad/unused(0x00), byte1=bank, bytes2-3=offset (big-endian
    word).
  - Verification always needs TWO things before trusting a resolved
    address: byte-level plausibility (real header signature + sane data
    curve) AND either a get_xrefs_to 8/8 hit or a genuine live-traced caller
    -- neither alone is proof, per this file's own Method section above.

--------------------------------------------------------------------
13. ARRAY-BASE INDIRECTION SCRIPT extended to table_read_indexed (0x14880)
    (2026-08-01, follow-up session). Action item (a) from the handoff above.
    STATUS: DONE for table_read_indexed. gear_indexed_table_lookup_f1fc
    (0x149a7) checked too -- ZERO callers found in this ROM, nothing to run,
    recorded as a negative result rather than skipped.

    Script saved as a real file (not run_script_inline, to sidestep that
    tool's OSGi class-loading failures encountered this session -- see
    GOTCHA below) at:
      ghidra scripts/ResolveTableReadIndexedArrays.java (project copy)
      C:\Users\j.brophy.CORKILLSYSTEMS\ghidra_scripts\ (Ghidra's script path,
        copied there since run_ghidra_script does not search the project
        folder)
    Same technique as item 22 exactly, retargeted at table_read_indexed:
    get_function_callers -> backward-scan each call site for the
    (offset,bank) push pair -> addMemoryReference(callSite, arrayBase) ->
    read each array's 8 slots -> addMemoryReference(slot, resolvedTarget).
    Confirmed via decompile before running that table_read_indexed uses the
    identical array[global_index & 7] pattern as table_lookup_indexed
    (same 0x1f1fc index variable, same &7 mask).

    Dry-run first (clean), then applied for real. Both runs identical,
    10/10 call sites resolved, every array's 8 slots internally consistent
    (matches the pattern established on known-real tables). Full mapping:
      f286_knock_octane_secondary_trim_compute_via_table (0x240c4)
        -> array 0x2db0c -> table 0x11d5a
      f286_knock_octane_secondary_trim_compute_via_table (0x240f6)
        -> array 0x2daec -> table 0x11d58
      f286_knock_octane_secondary_trim_compute_via_table (0x24111)
        -> array 0x2daec -> table 0x11d58 (same array as the 0x240f6 site)
      table_select_scale_fanout_f1be_f1c2 (0x20ea1)
        -> array 0x2da8c -> table 0x11880 (matches item 22's
        fueling_base_injection_calc lead -- SECOND independent caller now
        resolving to the same array/table, strong cross-validation)
      octane_trim_f262_f264_table_select (0x23b6f, 0x23bb5)
        -> array 0x2daac -> table 0x11d62
      octane_trim_f262_f264_table_select (0x23b8b, 0x23bcf)
        -> array 0x2dacc -> table 0x11d6e
      isc_f420_correction_calc (0x27764)
        -> array 0x2d92c -> table 0x128a2 (matches already-confirmed-real
        Desired ISCV step position table -- cross-validation)
      isc_f41a_correction_calc (0x263db)
        -> array 0x2d8ec -> table 0x1288a (matches item 22's undocumented
        table lead -- SECOND independent cross-validation)

    Spot-verified live post-apply: get_xrefs_to(0x2da8c) now shows both
    table_select_scale_fanout_f1be_f1c2 (0x20ea1) and
    fueling_base_injection_calc (0x21a36, item 22's original find) pointing
    at the same array -- confirms the reference was actually written, not
    just printed.

    3 GENUINELY NEW table addresses surfaced (not seen in item 22's pass):
    0x11d5a, 0x11d58, 0x11d62, 0x11d6e (four addresses, two pairs sharing
    arrays). XML CROSS-CHECK NOT YET DONE this session -- next step, same
    as item 22's own follow-up pattern (check whether these already exist
    in the XML under existing names, or are undocumented like 0x1288a/
    0x11cea/0x1238e turned out to be).

    GOTCHA (new this session): run_script_inline failed twice with an OSGi
    "class could not be found" error (McpInline_<hash> not found by
    <bundle>) on both attempts, regardless of code content -- NOT the same
    failure mode as item 19's "illegal start of expression" (which was a
    genuine double-class-wrapper mistake). This looks like a Ghidra-side
    script-bundle/classloader issue rather than a code problem. WORKAROUND
    used: write the script as a real .java file via Pulsar's create-file,
    matching the public-class-per-filename convention already used by
    ReloadSleighLanguage.java in this project, then run it with
    run_ghidra_script (which requires the file to sit in Ghidra's own
    ghidra_scripts search path, not just the project's "ghidra scripts"
    folder -- copy it there first). This worked cleanly on the first try.
    Recommend this as the default approach going forward instead of
    run_script_inline, given two reproducible failures against zero
    successes this session.

    NEXT STEPS: (1) XML cross-check the 4 new addresses. (2) items (b)-(e)
    from the previous handoff are still open and unaffected by this entry.

    XML CROSS-CHECK FOLLOW-UP (2026-08-01, same session): the "4 genuinely
    new addresses" claim above does NOT hold up. Byte-verified: 0x11d5a,
    0x11d58, 0x11d62, 0x11d6e all land inside the unbroken data body of one
    already-known table, TABLE_2D_00011D4C (real header 02 00 F0C8 at
    0x11d4c, data runs uninterrupted through 0x11d79, next real header
    02 00 F0D0 at 0x11d7a is the already-confirmed Air Temperature
    Compensation, item 1). Same "OVERLAP framing is itself the bug" pattern
    as item 2. Did NOT add 4 new XML table entries -- would have repeated
    session 10's mistake. Instead annotated TABLE_2D_00011D4C's existing
    entry (in bac2.xml) with the caller-identity finding, and separately
    annotated TABLE_2D_00011880's entry with its now-doubly-confirmed
    fueling-subsystem caller identity. See bac2.xml inline comments for
    full detail. Lesson: 8/8 xref confirmation on an array proves the
    ARRAY is real, not that its resolved target is a novel table distinct
    from ones already in the XML -- always byte-check a "new" address
    against neighboring known headers before treating it as undocumented.

--------------------------------------------------------------------
14. HANDOFF ACTION ITEM (a) CLOSED -- no more array-base-indirection
    functions exist in this ROM (2026-08-01, follow-up session).
--------------------------------------------------------------------

STATUS: NEGATIVE RESULT, item (a) exhausted. Searched for additional
table_lookup_indexed/table_read_indexed-style array-base-indirection
targets to extend the resolver script to, using three independent
methods, all converging on the same answer:

1. NAME-BASED: searched all functions matching "indexed" (7 hits) and
   a user-supplied xref-count candidate list (~35 functions spanning
   axis_lookup_interp/table_lookup_interp callers, status-word table
   dispatchers, and ISC/O2/knock table selectors). Decompiled every
   candidate not already covered. All either (a) already-known single-
   table literal-push callers (axis_lookup_interp/table_lookup_interp
   with a baked-in address, no runtime array selection), (b) a
   different table type entirely (status-word RAM-pointer tables, not
   ROM value/axis tables), or (c) not table-related at all (scalar
   selects, status composites). table_select_scale_fanout_f1be_f1c2
   confirmed as an already-known table_read_indexed CALLER, not a new
   indirection function itself.

2. VARIABLE-BASED: grepped the exported .c for the f1fc global index
   variable directly (29 hits) to catch inlined/anonymous consumers a
   name search would miss. Found 3 new call sites (lines 10395, 23119,
   23172/23175) beyond the known functions -- all three read small
   fixed-size RAM structs (hardware register emulation / gear-config
   snapshot / EEPROM backup dispatch), not ROM table-pointer arrays.
   Confirmed false positives by reading surrounding context (timer
   register dispatch, EEPROM backup write, port state cluster).

3. STRUCTURAL (most reliable): grepped the full 28,064-line decompiled
   source for the actual computational fingerprint of the pattern --
   `& 7) * 4` / `& 7) * 2` (masked-index-into-4-or-2-byte-stride-array)
   and a bare `* 4)` array-slot multiply. RESULT: exactly 3 matches,
   all already known -- table_read_indexed (0x14880, 14 real callers),
   table_read_word_indexed_f1fc (0x14838, 0 callers), and
   gear_indexed_table_lookup_f1fc (0x149a7, 0 callers). Also checked
   the exact (byte,void*) two-arg signature shared by table_lookup_
   indexed/table_read_indexed/axis_lookup_interp -- only those three
   functions in the whole ROM share that shape.

CONCLUSION: the 4-byte bank+offset table-pointer array-selector idiom
this ROM uses (confirmed items 13/22) has exactly two live consumers,
table_lookup_indexed and table_read_indexed, both already fully
resolved. The two structurally-identical siblings
(gear_indexed_table_lookup_f1fc, table_read_word_indexed_f1fc) are
confirmed dead code paths (zero callers each). HANDOFF ACTION ITEM (a)
IS CLOSED -- no further indirection-script extension work exists to
do in this ROM. Confidence level here is higher than the earlier name-
based checks alone, since this was corroborated by a search over the
literal decompiled source rather than function-name pattern matching.

NEXT: proceeding to handoff action item (c), general Batch 2 pass over
the ~94 "Unknown"-category placeholder tables using the established
single-table literal-push method (Method step 4) now that indirection
is confirmed exhausted as an avenue for this specific ROM.

--------------------------------------------------------------------
Batch 2 -- individual items (started 2026-08-01, follow-up session)
--------------------------------------------------------------------

15. TABLE_2D_00011880 -- first Batch 2 table resolved, using the head
    start from item 22 (fueling_base_injection_calc lead, doubly
    cross-validated in item 13 via table_select_scale_fanout_f1be_f1c2).
    STATUS: CONFIRMED, XML APPLIED (test/rvr/xml/ecuflash/new/
    21000011_1997-2001_RVR_X3_Mt__4g63t_bac2.xml -- CORRECTED 2026-08-01:
    initially misapplied to the base _.xml file by mistake, caught and
    reverted, re-applied to the correct working copy _bac2.xml, which is
    the file items 13/22's caller-identity annotations already live in).
    Header confirmed live: 02 00 F0C0 at 0x11880 (mode=2), data
    50 50 57 FF at 0x11884 (header+4 convention, same recurring bug
    as Batch 1's items 1/2/7/8/9). NOTE (2026-08-02, item 16): the name-only
    suffix pass below applied "_Fueling" directly to TABLE_2D_00011880's own
    name in the live working XML (not bac2.xml, which does not exist in this
    checkout -- see item 16), separate from this address/axis fix. Full disassembly of
    fueling_base_injection_calc (0x21a0e) read directly (not just
    decompiled) to nail down which axis feeds this specific table,
    since the function contains three table lookups sharing one
    axis_lookup_interp call: axis_lookup_interp(0xd0f0, bank=2) at
    entry, then a btst-gated array select (0xda6c/0xda8c) into
    table_lookup_indexed (-> this table, 0x11880/11884), then two
    more literal table_lookup_interp calls (0x118a0, 0x11894 --
    Batch 2 neighbors, not yet independently verified). Per Method
    step 4, all three share the single axis_lookup_interp result.
    Axis header confirmed at 0x2d0f0: F0C0 F170 0010 (16 elements),
    X-ptr F0C0 matches the table's own axis-ptr field exactly. Data
    is a clean 16-element linear ramp (0x80..0x480 in steps of 0x80).
    XML APPLIED: address 11880 -> 11884, axis RPM address 2d332(18)
    -> 2d0f0(16). Old 2d332 placeholder confirmed unrelated (Batch 1
    items 9/10/12 already established 2d332 as a different ISC-only
    axis family).
    FOLLOW-UP LEAD: the same function also literal-pushes 0x118a0 and
    0x11894 as direct table_lookup_interp targets, sharing this same
    axis (0x2d0f0). Both are also Batch 2 "Unknown" placeholders
    (TABLE_2D_0001186C's neighbor and TABLE_2D_00011894 itself) --
    strong candidates for the next items in this pass, already having
    a confirmed caller and axis without further search needed.

--------------------------------------------------------------------
16. NAME-SUFFIX PASS over remaining Batch 2 placeholders using
    FindBatch2Callers.java / DumpBatch2Headers.java (2026-08-02).
--------------------------------------------------------------------

    STATUS: DONE for this pass. Note upfront: the working XML in this
    checkout is test/rvr/xml/ecuflash/new/21000011_1997-2001_RVR_X3_Mt__4g63t_.xml
    directly -- "bac2.xml" as referenced by earlier entries above does not
    exist in this checkout, so all name-suffix edits below were applied to
    that file. Most of the ~94 Batch 2 entries already carry a caller-derived
    "_Subsystem" name suffix from earlier sessions (e.g. _ISC, _Fueling,
    _Knock, _CompositeCorr, _TCU); this pass targeted only the ones that
    were still missing a suffix despite a confirmed caller existing.

    Ran both scripts (dry_run first, both clean, no writes needed since both
    are read-only dumps/scans):
      DumpBatch2Headers.java -- confirmed all Batch 2 headers still read as
        expected (mode=2/3 table headers for ROM addresses; the three 2D
        axis-record addresses in the list, 2D3C4/2D5F0/2D66C, correctly read
        as garbage mode bytes when interpreted as table headers, consistent
        with items 8/10/11's established finding that those are axis
        records, not table records).
      FindBatch2Callers.java -- literal-push scan across the whole program
        for each Batch 2 address's (bank,offset) pair.

    Cross-referenced FindBatch2Callers' output against the current XML name
    attributes. Found 17 entries with a confirmed literal-push caller but no
    suffix yet applied, plus 1 more (TABLE_2D_00011880) whose caller was
    already known from item 15/22 via array-indirection (not a literal push,
    so FindBatch2Callers correctly reports "NO CALLER FOUND" for it -- that
    script only catches the direct-call convention, not the array-indexed
    one). Applied name-only suffixes for all 18, address/axis untouched:

      11880 -> _Fueling   (fueling_base_injection_calc via array 0x2da8c,
                            cross-validated twice, items 13/15/22 -- indirect
                            caller, not caught by this pass's literal-push
                            scan, added from prior findings instead)
      12DE4 -> _ISC       (isc_condition_eval)
      12EA2 -> _EGR       (egr_duty_target_calc)
      12EAE -> _EGR       (egr_duty_target_calc)
      12EBC -> _ISC       (isc_f402_composite_correction_calc)
      12ECE -> _ThresholdSelect  (tiered_threshold_table_select)
      12EDC -> _ThresholdSelect  (tiered_threshold_table_select)
      12EEA -> _ThresholdSelect  (tiered_threshold_table_select)
      12EF8 -> _ThresholdSelect  (tiered_threshold_table_select)
      12F06 -> _TCU       (tcu_dtc_status_check_dispatch)
      12F14 -> _TCU       (tcu_dtc_status_check_dispatch)
      1313E -> _TCU       (tcu_shift_solenoid_table_init)
      131A0 -> _ISC       (isc_openloop_target_calc | isc_openloop_stepper_scale_calc)
      131A8 -> _ISC       (isc_openloop_target_calc | isc_integrator_update)
      131B0 -> _ISC       (isc_integrator_update)
      131D4 -> _DualChannel  (f276_f27a_dual_channel_compute_via_table)
      131E0 -> _DualChannel  (f276_f27a_dual_channel_compute_via_table)
      13212 -> _TCU       (tcu_torque_converter_slip_calc)

    Everything else FindBatch2Callers reported "NO CALLER FOUND" for
    (1186C, 11D20, 11EA0, 11F6C, 12AE6, 12D00, 12DF2, 12E4A, 1314C, 13154,
    1315C, 13168, 13174, 1317C, 13188, 13190, 13198, 131B8, 131C0, 131CC,
    131EC, 131F6, 13202, 1320A, 1321C, 13236, 13250, 1325E, 1326C, 1327A,
    2D3C0, 2D5EC, 2D668, 2D796, 10D73) was left with no suffix, per Method
    step 6 -- never guess a subsystem without a confirmed caller. These
    remain candidates for the array-indirection technique or a fresh
    literal-push search if new call sites are discovered later, same as
    the still-open items above (10D73/1186C/etc. genuinely have no direct
    or indirect caller found by any method run so far).

    NEXT STEP: none of the remaining "NO CALLER FOUND" addresses are
    resolvable by literal-push or the existing array-indirection scripts
    (per item 14's exhaustive negative-result conclusion -- there is no
    third indirection function left to extend to). Any further progress on
    those would need a different technique entirely (e.g. manual trace of
    dispatch tables, per item 10's closing note), not a rerun of these two
    scripts.

--------------------------------------------------------------------
17. AXIS PASS over the newly-named Batch 2 tables using FindBatch2Axes.java
    (new script, 2026-08-02).
--------------------------------------------------------------------

    STATUS: DONE for this pass, 23 of 24 candidate leads applied (one 3D
    entry -- 12DF2/12E4A were never candidates; see below).

    METHOD: wrote FindBatch2Axes.java, which reuses FindBatch2Callers'
    push-pair/pjsr event tracking but, for each Batch 2 table address with a
    known caller, looks at the immediately-PRECEDING push-pair+pjsr event in
    the same function. If that preceding event's pjsr target is
    axis_lookup_interp (0x14735), its pushed (bank,offset) is the candidate
    axis -- this is exactly the manual pattern established in items 11/15
    (axis_lookup_interp call sits right before the table's own
    table_lookup_interp/table_lookup_indexed call). Ran dry_run (script is
    read-only, no writes), copied to both the project's ghidra scripts/
    folder and Ghidra's own ghidra_scripts search path per the item 13
    gotcha.

    Produced a verdict per address: AXIS_LOOKUP_INTERP MATCH (usable lead),
    "preceding event is ANOTHER TABLE call" (this table is chained after
    another table's axis, not paired with its own -- e.g. many of the
    _CompositeCorr/_CompositeCalc/_ISC entries turned out to share axes with
    a sibling table rather than having their own dedicated axis_lookup_interp
    call), "NO PRECEDING PUSH-EVENT" (table call is the first in its
    function), or "NO CALLER FOUND" (inherited from the caller pass).

    24 addresses came back AXIS_LOOKUP_INTERP MATCH. Per Method step 4, a
    caller/axis match is a LEAD, not proof -- read all 20 unique candidate
    axis addresses' first 6 header bytes via ghidra:read_memory before
    touching the XML. All 20 read back a plausible axis-record shape (two
    2-byte RAM tags + a 2-byte element count in the 4-17 range, no garbage),
    consistent with the established axis-header convention. One, 0x2d356,
    matches the 16-element record already flagged as real-but-unassigned
    back in item 10 -- good independent cross-validation.

    Applied 23 of the 24 (11880 was already resolved via item 15/22's
    array-indirection route, so it's not re-logged here) as address+element
    corrections to the live XML, replacing the RPM/2d332/18 placeholder.
    18 are 2D tables with a single axis, fully resolved:

      11DEC -> 2d260 (7 elem)     11E4A -> 2d130 (8 elem)
      11E6A -> 2d440 (11 elem)    11F64 -> 2d2aa (14 elem)
      127FC -> 2d490 (8 elem)     12824 -> 2d274 (9 elem)
      1284E -> 2d180 (6 elem)     12858 -> 2d29c (4 elem)
      12950 -> 2d1fa (5 elem)     12CD2 -> 2d548 (17 elem)
      12D70 -> 2d09a (16 elem)    12DD6 -> 2d116 (10 elem)
      12DE4 -> 2d5ee (9 elem)     12EA2 -> 2d620 (8 elem)
      12EF8 -> 2d636 (10 elem)    12F14 -> 2d636 (10 elem)
      1313E -> 2d66a (10 elem)    13212 -> 2d636 (10 elem)

    6 are 3D tables where only the Y-axis was found this pass (X-axis still
    needs a second, further-back push-event search the script doesn't do
    yet -- flagged inline as unresolved, X-axis left on the 2d332
    placeholder rather than guessed):

      127A8(Y) -> 2d75a (7 elem)   12B06(Y) -> 2d50c (15 elem)
      12B94(Y) -> 2d356 (16 elem)  131A0(Y) -> 2d7b0 (10 elem)
      131A8(Y) -> 2d7b0 (10 elem)  131B0(Y) -> 2d7b0 (10 elem)

    Left untouched (no axis_lookup_interp match, per Method step 6 -- never
    guess): every "NO CALLER FOUND" address from item 16, plus all the
    "ANOTHER TABLE call" verdicts (11834, 11E86, 11E94, 11EC8, 11ED6, 11EE2,
    11F16/30/3C/4A/5C, 127D8, 12860, 12CBC, 12EAE, 131D4/131E0) and all the
    "NO PRECEDING PUSH-EVENT"/"inconclusive" verdicts (11D4C, 128D2, 128DE,
    128EA, 12926, 1297A, 12986, 12CE8, 12CF4, 12EBC, 12ECE/EDC/EEA, 12F06).
    These remain candidates for a follow-up pass that walks further back
    than one event, or that handles chained-table axis sharing explicitly.

    NEXT STEP: extend FindBatch2Axes.java to look two events back (not just
    one) for the 6 still-open 3D X-axes, and to follow the "ANOTHER TABLE
    call" chain (i.e. when the preceding event is itself a table call, walk
    back one more step from there) for the composite/ISC entries that share
    an axis with a sibling table rather than owning one directly.

--------------------------------------------------------------------
18. DIRECT-XREF CHECK on everything still "NO CALLER FOUND" (2026-08-02).
--------------------------------------------------------------------

    STATUS: DONE. 1 of 35 resolved (1186C); the other 34 confirmed to have
    zero code references by any method, not just a gap in the push-pair
    scanner.

    METHOD: ran ghidra:get_bulk_xrefs directly against all 34 remaining
    "NO CALLER FOUND" addresses (from item 16) plus 10D73, in one batch call
    -- this checks Ghidra's own reference database rather than re-scanning
    instructions, so it can catch patterns the literal-push scanner's
    specific mov/pjsr pattern-match doesn't cover (e.g. data-only refs,
    refs planted by a prior script run).

    33 addresses came back with zero xrefs of any kind -- confirms these
    are genuinely unreferenced by anything Ghidra's analysis has found, not
    just missed by the literal-push convention specifically. Consistent
    with the item 14 "exhaustive negative result" conclusion.

    1186C came back with 8 DATA xrefs from 0x2da6c-0x2da88 (4 bytes apart --
    a pointer array, same signature ResolveTableReadIndexedArrays.java
    plants). Read the array: all 8 slots hold the identical value 0x1186c
    (deliberate uniform array, not an index dispatch). Checked this array
    against ResolveTableReadIndexedArrays.java's known 10 call sites (fresh
    dry_run) -- not among them, so this is a genuinely new, 11th indirection
    array, previously undiscovered by any prior pass.

    Wrote a one-off script (FindArrayCaller.java, same push-pair/pjsr event
    tracking as FindBatch2Callers/Axes, pointed at just 0x2da6c) to find
    what pushes this array's address. Found it at 0x21a2a, inside
    fueling_base_injection_calc -- the SAME function that already owns
    11880/11894/118A0 (item 15/22). The push sequence there is:
    axis_lookup_interp(0x2d0f0) -> push 0x2da6c -> push 0x2da8c -> single
    pjsr to table_lookup_indexed. No pjsr occurs between the two array
    pushes, meaning that ONE call takes both array-base arguments (a
    dual-table blend/interpolation), and 0x2da8c is the already-known array
    resolving to 11880. So 1186C shares the exact same axis (0x2d0f0) as
    its three siblings.

    Verified axis 0x2d0f0's header byte-for-byte: F0C0 F170 0010 (16
    elements), a plausible axis-record shape. Applied to XML: renamed
    TABLE_2D_0001186C -> TABLE_2D_0001186C_Fueling, axis address/elements
    added (2d0f0 / 16, replacing the RPM/2d332/18 placeholder), full
    derivation logged inline.

    This raises an open question worth flagging for the next session: since
    table_lookup_indexed apparently takes two array arguments per call, the
    other ~9 already-resolved indirection arrays from
    ResolveTableReadIndexedArrays.java's output (item 13/14/22) may each
    have an unnoticed SIBLING array immediately preceding them in the same
    push sequence, the same way 0x2da6c precedes 0x2da8c. None of those
    call sites were re-examined for a second array this session -- only
    fueling_base_injection_calc's two known call sites (0x21a33/0x20ea1
    per item 13/15) were involved here, and only because 1186C's xref check
    happened to surface the sibling push at 0x21a2a. Worth a systematic
    "check one push-event earlier, is it also an array-base with no pjsr
    between them" pass across all 10 known table_read_indexed/
    table_lookup_indexed call sites -- may surface more previously-invisible
    tables the same way.

--------------------------------------------------------------------
19. FixBankOffsetReferences_v2.java -- ROM-agnostic rewrite of the manual
    bank+offset reference-creation workaround (2026-08-02), validated and run
    for real against the RVR ROM.
--------------------------------------------------------------------

    CONTEXT: item 22's original array-reference script (and item 27's
    AnnotateBankOffsetCallSites.java, both this-ROM sessions) used a
    backward-immediate-scan to resolve bank*0x10000+offset for every real
    caller of table_lookup_interp/table_lookup_indexed/table_3axis_interp_triple,
    working around the Ghidra #817-class decompiler bug (confirmed applies here,
    item 26) that never fuses the two visible call arguments into a real far
    pointer. PJ wrote FixBankOffsetReferences_v2.java to generalize this
    technique so it isn't tied to this specific ROM's addresses/bank layout.

    GENERALIZATION CHANGES from the original this-ROM-specific script:
      - Target functions resolved by NAME via the symbol table at runtime,
        not hardcoded addresses -- works on any binary where the callees are
        labeled, regardless of where they land.
      - Bank plausibility filter changed from a hardcoded {1,2} allowlist to
        pure memory-containment (mem.contains) -- a ROM with a different bank
        range no longer gets legitimate call sites silently rejected.
      - Added a FUNCTION-BOUNDARY check: the backward scan can never cross
        into the caller's own caller. Alone, this reproduces item 27's known
        table_3axis_interp_triple_wrapper false-positive rejection without
        needing to know that function's identity in advance.
      - Added an ADJACENCY check, refined twice during validation (see below).

    VALIDATION METHOD: ran dry_run against the live RVR program (146 total
    call sites across the 3 targets, matching item 27's count exactly) and
    diffed against item 22's independently-derived ground-truth array list
    and item 27's known-false-positive list.

    ROUND 1 (naive adjacency -- any non-qualifying-mov instruction breaks the
    pattern): 137/146 added, 9 skipped. Cross-checked against item 22's 4
    ground-truth isc_f34e_f34a_correction_calc arrays (0x2dbac/0x2da0c/
    0x2db8c/0x2dbcc) -- all 4 matched exactly, confirming the core logic
    sound. But of the 9 skips, only 3 were item 27's known bad rows
    (isc_f438_correction_calc, egr_duty_target_calc's bank=252 sites,
    table_3axis_interp_triple_wrapper). The other 6 needed individual
    disassembly review.

    DISASSEMBLY REVIEW OF THE UNEXPECTED SKIPS:
      - table_lookup_indexed's own internal call to table_lookup_interp
        @0x14874: NOT a real miss. Disassembly shows this call is fed by
        "mov R0,@-SP" / "mov R1,@-SP" -- REGISTER pushes (the runtime
        array-slot values from table_lookup_indexed's own indexing logic,
        per item 22), not immediate literals. Item 27's script had actually
        flagged this as a "GOOD CONFIRMATION" (resolved to a plausible-looking
        address) but that confidence was misplaced -- it was coincidentally
        grabbing unrelated nearby immediates (the "&7" mask constant etc.),
        not this call's real (runtime-computed) arguments. v2 correctly
        rejects it; the OLD script's "success" here was itself a latent bug,
        now caught.
      - The remaining 3 real misses (f2ea_f2ee_composite_correction_calc
        @0x24907, fueling_base_injection_calc @0x21a5a,
        f2e0_f2ec_composite_correction_calc @0x24792) were confirmed via
        direct disassembly to be GENUINE valid call sites with correct
        immediate pushes, broken only by a harmless interleaved
        "mov:f.w Rn,@(-N:8,FP)" frame-spill instruction between the second
        push and the pjsr -- a real compiler pattern, not a decode error.
        The naive adjacency rule was too strict.

    ROUND 2 (fixed adjacency): distinguished "any instruction" from
    "an instruction that pushes onto @-SP". Frame spills, register moves,
    and other non-stack-affecting instructions are now treated as
    transparent filler; only a genuine rival push to @-SP (immediate or
    register) breaks adjacency, since that's the only thing that could
    actually displace what "top of stack" means for the call. Re-ran
    dry_run: all 3 previously-missed genuine sites now resolve correctly
    (0x24907->0x11f30, 0x21a5a->0x11894, 0x24792->0x11e86), zero regressions
    on the previously-working 137, and the 3 true false positives plus the
    0x14874 register-push case remain correctly rejected.

    FINAL RESULT: 142/146 call sites resolved and applied for real (not just
    dry-run) -- MORE accurate than item 27's original 146-applied/0-flagged
    result, since item 27 never caught the 0x14874 latent bug and this
    version does. The 4 correctly-unresolved sites: table_lookup_indexed's
    own internal call (runtime register args, no static immediate exists to
    record), the 2 known bank=252 mis-grab sites (isc_f438_correction_calc,
    egr_duty_target_calc's first call), and table_3axis_interp_triple_wrapper
    (genuinely arg-less passthrough). None of these 4 have a real static
    bank+offset immediate pair to record, so leaving them unresolved is
    correct, not a gap.

    Script saved at "ghidra scripts/FixBankOffsetReferences_v2.java" (project
    copy) and C:\Users\j.brophy.CORKILLSYSTEMS\ghidra_scripts\ (Ghidra's
    search path, per the usual copy-before-running gotcha).

    STATUS: reference-database fix APPLIED (real run, not dry_run) to the
    live RVR program. This is complementary to, not a replacement for,
    item 24/25's decompiler param-storage fix -- per item 26, the decompiler-
    display layer and the reference-database layer are independent; this
    script only fixes the latter (get_xrefs_to / Listing XREF / navigation),
    not the #817-class decompiler pointer-fusion bug itself (which remains
    unfixed and un-fixable without a segmentop/constresolve-style mechanism).

--------------------------------------------------------------------
20. XML sweep using item 19's new/fixed references (2026-08-02).
--------------------------------------------------------------------

    STATUS: 2 XML entries corrected, 1 family of negative results confirmed
    and logged (not fixed -- no axis exists to find here).

    FIX 1 -- TABLE_2D_00011880_Fueling axis element was STALE despite its
    own inline comment claiming item 15 already resolved it: comment said
    "Address/axis already resolved per review.md item 22 / review2.md item
    15" but the actual <table name="RPM"> line still read address="2d332"
    elements="18" (the old, unrelated ISC-only placeholder, per items
    9/10/12). Re-verified via disassembly: axis_lookup_interp(0xd0f0,
    bank=2) @0x21a19 in fueling_base_injection_calc, immediately preceding
    this table's own call. Corrected to address="2d0f0" elements="16" to
    match what was already documented as true but never actually applied to
    the XML. Lesson: an inline comment claiming a fix was applied is not
    proof it was -- always re-check the actual attribute value, not just the
    comment text next to it.

    FIX 2 -- TABLE_2D_00011894_Fueling had NO axis annotation at all, still
    on the stale 2d332/18 placeholder. This table's call site
    (fueling_base_injection_calc @0x21a5a) was one of the 3 real call sites
    FixBankOffsetReferences_v2.java's adjacency-fix round resolved today
    (item 19). Direct disassembly confirms it shares the exact same
    axis_lookup_interp(0xd0f0, bank=2) @0x21a19 call as its sibling 0x11880
    above -- consistent with Method step 4's axis-sharing rule and
    review2.md item 15's own follow-up note anticipating this. Corrected to
    address="2d0f0" elements="16".

    NEGATIVE RESULT (logged, not a fix) -- the _CompositeCorr family in
    f2ea_f2ee_composite_correction_calc (0x11f16, 0x11f30, 0x11f3c, 0x11f5c)
    and f2e0_f2ec_composite_correction_calc (0x11e86, 0x11e7a, 0x11e94,
    0x11f22, plus 0x11f16 again) all still sit on the stale 2d332/18
    placeholder. Checked both functions' FULL disassembly directly (not just
    decompile) looking for a preceding axis_lookup_interp call, per the same
    method that resolved 0x11880/0x11894 above -- NEITHER function contains
    any axis_lookup_interp (0x14735) call anywhere in its body. Each
    table_lookup_interp call here is fed by a single scalar read from RAM
    (@0xf28e, @0xf20e-derived flags, or plain register arithmetic), not an
    axis-record lookup. Per Method step 6 (never guess), the 2d332
    placeholder stays as-is for all of these -- there is no discoverable
    real axis via the literal-push method for this table family. Would need
    a fundamentally different technique (manual trace of the RAM value's own
    producer elsewhere in the ROM, or accepting these tables may not use a
    real breakpoint-axis at all) to resolve further. Not attempted this
    session.

    METHOD NOTE: this sweep was possible specifically because item 19's
    FixBankOffsetReferences_v2.java resolved 3 previously-unresolved call
    sites (round 2's adjacency fix) that happened to land on/near existing
    Batch 2 XML entries -- a useful side effect of generalizing the script
    beyond its original scope.

--------------------------------------------------------------------
18. SCRAPER BUG FOUND AND FIXED: phantom 2D tables from unclaimed
    scaling-table byte ranges (2026-08-02).
--------------------------------------------------------------------

Four Batch 2 "Unknown" entries (TABLE_2D_0002D3C0, _0002D5EC, _0002D668,
_0002D796) were all false positives from the same root cause, found while
chasing an axis conflict for TABLE_2D_00012DE4 (see item 17's D5EE entry).

ROOT CAUSE: h8539_import_tables_xml.py's Step 8 runs multiple independent
byte-scanning passes over the same ROM region -- Pass 2 finds scaling/axis
tables (6-byte header: out_ptr, in_ptr, 0x00, count, then count*2 bytes of
data), Pass 3 finds 2D/3D value tables (4- or 7-byte header starting with
a mode byte 0x02/0x03). Neither pass tracked which byte ranges the other
had already claimed. In all four cases, a real axis record's OWN trailing
data word happened to equal 0x0200 -- which Pass 3's 2D-table gate reads
as mode=0x02, pad=0x00, then the following 2 bytes as an axis pointer
that (by further coincidence) fell in-range. Confirmed for all four by
reading the preceding axis record in full and showing its data run ends
exactly at the "table header" address Pass 3 had flagged.

This is a physical byte-ownership bug, not a "logical reference" bug --
it has nothing to do with multiple value tables legitimately sharing one
real axis (that's normal and unaffected; axis_ptr is a RAM address read
from a value table's own header, not a ROM byte-range claim).

FIX APPLIED to h8539_import_tables_xml.py: added a `claimed_ranges` list
+ `in_claimed_range()` helper. Pass 2 now records (start, end_exclusive)
for every scaling table it accepts; Pass 3's 2D and 3D header-shape gates
now both additionally require `not in_claimed_range(i)`. Since Pass 2
runs before Pass 3 in the same script execution, this prevents Pass 3
from ever re-claiming a byte range Pass 2 already consumed. Verified the
scaling-table gate's byte pattern (F0-F7, E0-FE, 0x00, 2-0x90) does match
the real axis record shape confirmed live in Ghidra, so Pass 2 should
already have been claiming these ranges -- this fix closes the gap.

All four phantom XML entries deleted with corrected reasoning (see their
individual delete-comments in the XML). Next full re-scrape should not
regenerate them.

--------------------------------------------------------------------
19. Two more overlap flags resolved from fresh scraper run (2026-08-02,
    post claimed_ranges fix): pre-existing (non-Batch-2) tables.
--------------------------------------------------------------------

Fresh scraper output confirmed the claimed_ranges fix worked (D3C0/D5EC/
D668/D796 no longer appear as phantom H8539F-TABLE entries). It also
surfaced two NEW H8539F-AXIS-DATA-OVERLAP flags, both on established
(non-Batch-2) tables, not Batch 2 placeholders:

- Boost Limit: axis was 2d100 (mid-data of 2d0f0's own record, same
  false-positive shape as the deleted phantoms). Table's own header
  (11cea) expects axis-ptr F0C4; only real F0C4-tagged 10-element axis
  in range is 2d080. Fixed 2d100 -> 2d080, element count unchanged (10).

- Post Start Enrich Trim vs Load: axis was 2d35e (mid-data of 2d356's
  own record). Table's own header (11d86) expects axis-ptr F0C0; two
  F0C0-tagged 14-element candidates exist (2d2aa, already claimed by
  item 17's TABLE_2D_00011F64_HysteresisTimer; 2d2e0, unclaimed). Used
  2d2e0. Fixed 2d35e -> 2d2e0, element count unchanged (14).

Both fixes are TAG-MATCHED, not caller-confirmed (no literal-push caller
found for either table) -- weaker evidence than item 17's caller-traced
fixes, flagged as such in the XML comments. Worth revisiting if a caller
ever surfaces.

--------------------------------------------------------------------
20. FindBatch2Callers.java UNDERCOUNTING BUG FOUND (2026-08-02):
    functions calling MULTIPLE Batch 2 tables only had their LAST call
    site's table matched. Two genuinely missing tables found and added.
--------------------------------------------------------------------

While spot-checking a "NO CALLER FOUND" address (0001313E's neighbors)
by reading tcu_shift_solenoid_table_init's full disassembly by hand
(not just script output), found the function calls table_lookup_interp
13 times total, but FindBatch2Callers.java's original run only reported
ONE match for this function (0001313E). The other 12 calls include:
- 5 already-known tables (Knock Sensor Filter Maps 1-5) -- good sanity
  check, confirms the technique works.
- 2 addresses (131C4, 131FA) that had NO XML entry at all -- true gaps,
  not axis-resolution issues. Both confirmed real via live get_xrefs_to
  (6 and 5 DATA xrefs respectively, all from this one function) and live
  header bytes: 03 00 F0C0 F0C2 0B/0A FF -- real 3D headers, height=11/10,
  but the byte immediately after height is the 0xFF sentinel, meaning
  ZERO data rows in this ROM. Real but empty/degenerate tables, not
  detection errors.

ADDED to XML: TABLE_3D_000131C4_TCU, TABLE_3D_000131FA_TCU, both with
full caller/xref evidence, both flagged as legitimately empty (height
field is real, data is zero rows).

IMPLICATION: any OTHER function that calls table_lookup_interp/indexed
multiple times for DIFFERENT Batch 2 addresses may have the same
undercounting problem in the original FindBatch2Callers.java output.
The remaining ~28 "NO CALLER FOUND" Batch 2 addresses have NOT been
re-checked against this specific failure mode yet -- worth a targeted
follow-up pass (e.g. rerun the caller search collecting ALL matches per
function, not just the last one, before concluding an address has no
caller). Not fixed this session; flagged for next pass.

--------------------------------------------------------------------
21. Whole-program caller scan vs XML (FindAllTableCallsVsXmlV2.java,
    2026-08-02): 3 more genuinely missing tables found and added.
--------------------------------------------------------------------

Built a proper version of item 20's ad-hoc discovery: a script that scans
the ENTIRE program (not a pre-built candidate list) for every literal-push
call to table_lookup_interp/indexed/read_indexed, then diffs against every
address in the live XML file (read directly, not hand-transcribed, to
avoid copy errors). Checked addr, addr+4, addr-4 against the XML to allow
for the header-vs-header+4 addressing convention seen throughout this
project. 151 total calls found; 6 flagged as genuinely missing after
filtering array-base addresses (17 of those, informational only, not
table candidates -- input to table_lookup_indexed/read_indexed, already
handled by items 13/22).

Of the 6: 3 were false positives from the diff script's own limitation
(only checked +/-4, but this ROM's 3D tables use a 7-byte header, so
Barometric Pressure Compensation, Limp Home - TPS Table, and the entry
at 12992 were already present at +7 offsets I hadn't accounted for).

GENUINELY MISSING, ADDED:
- Open Loop Load # 2 (11d38): sibling to existing "Open Loop Load # 1"
  (11d24), confirmed via f21c_bit8_hysteresis_from_table_variant which
  branches between the two on f0f8 bit5, both sharing axis 2d09a/2d0a0.
  Standard header convention.
- Idle Stepper Lookup Table (12992, data at 12999): confirmed via
  idle_stepper_table_lookup_wrapper, a clean dual-axis 3D lookup
  (2d4ba: 8-elem Engine Temp, 2d4d0: 27-elem RPM). Standard convention,
  matches bookmark name exactly.
- TABLE_2D_000132F8 (132f8): confirmed via calc_f110_f10e_via_table,
  called twice. UNUSUAL header shape -- "02 28 F0CC..." not the normal
  "02 00 ptr ptr" convention (second byte 0x28=40 isn't the usual zero
  pad). Axis candidate (0x1339e, bank=1) is also unusual -- a ROM CODE
  address, not the normal 0x2Dxxx RAM axis region, and its own "header"
  bytes don't fit the standard axis shape either (implausible count
  0xA1=161). Added the table entry with caller/address confirmed solid,
  but NO axis assigned and the format flagged as not-fully-understood --
  a genuinely open question for a future pass, not guessed at.

Also noted 0x1334e6 shares the same unusual "02 28" header shape as
132F8 (found during the same scan, in calc_f118_via_table) -- consistent
with this being a real, distinct header format used by a small family of
tables in the 0x132xx-0x134xx region, not a one-off anomaly. Not yet
added to the XML -- same open-question status as 132F8, flagged here for
whoever picks this up next.

--------------------------------------------------------------------
22. 1D scalar table search attempted, inconclusive -- stopped
    (2026-08-02).
--------------------------------------------------------------------

Tried to find missing 1D scalar tables (no ROM header exists for these,
per h8539_import_tables_xml.py's own design -- Step 8 only scans for
2D/3D headers, 1D entries are only ever labeled from an existing XML,
never discovered fresh from bytes). Two script attempts:

1. Find1DScalarCandidates.java: any address in 0x10800-0x10FFF with a
   real xref, not within 4 bytes of a known XML address. Result: 613
   candidates -- useless, this range is dense with internal RAM-style
   control-flow reads/writes on ROM-resident small values, not a sparse
   set of real calibration constants the way 2D/3D table headers are.

2. Find1DScalarCandidatesV2.java: tightened to single-xref addresses
   with a direct ROM-to-register load instruction pattern. Result: 0
   candidates -- either the regex pattern doesn't match this ISA's
   actual mnemonic/operand syntax closely enough, or there genuinely
   isn't a clean middle ground between "613 hits" and "0 hits" for this
   kind of scan.

CONCLUSION: 1D scalars have no reliable structural signature the way
2D/3D headers or axis records do, and this ROM's control-flow code
reads/writes far too many small values in this address range for a
generic reference-count heuristic to separate real calibration
constants from internal state. Stopped here -- not a productive avenue
without a much more targeted heuristic (e.g. cross-referencing against
EcuFlash's own known parameter list for this ROM family, if one exists,
rather than blind ROM-region scanning).
