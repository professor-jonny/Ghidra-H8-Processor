# H8/539F ECU - XML Table Import + ROM Scraper
# @category MitsubishiECU
#
# Split out of h8539_ecu_master_setup_new3.py (2026-07-29) so table
# annotation runs as its OWN pass, separate from ROM setup/auto-analysis.
#
# RUN ORDER: run h8539_ecu_master_setup_new3.py FIRST (base setup +
# auto-analysis), THEN this script, THEN (optionally, any time after)
# h8539_export_tables_xml.py to write back out.
#
# WHY THIS RUNS AFTER AUTO-ANALYSIS, NOT BEFORE:
#   The original master script ran XML import before Step 6 auto-analysis
#   so table headers would be typed as data and "protected" from the
#   disassembler walking through them. A live gap-scan on a fresh,
#   un-annotated ROM (2026-07-29 session) showed that on this ROM/analyzer
#   combination, plain auto-analysis already does NOT wander into the
#   known table regions on its own -- so that protection isn't load-bearing
#   here, though Step 5b's fixed-offset MUT-table typing stays in the
#   setup script as cheap insurance against the previously-observed
#   runaway-function merge bug (see that script's Step 5b comment).
#
#   What actually needs protecting is the XML/scraper data itself: community
#   XMLs are known to carry wrong addresses (see review.md item 17's Idle
#   Stepper header-offset bug), and byte-pattern scraping can false-positive
#   on code that merely looks table-shaped (review.md item 3's 0x13898
#   case). verify_xml_table()'s VERIFIED/SUSPECT/REJECTED gate is the real
#   safeguard, and it gets BETTER evidence running after analysis: more
#   xrefs and instructions are defined by then, so is_likely_code() (the
#   function that catches "this address is actually real code, not a
#   table") has a fuller, truer picture of the program than it would
#   pre-analysis. Running this step post-analysis is therefore strictly
#   safer, not riskier, for the verification logic -- and it means a
#   REJECTED verdict here is checked against final, settled ROM state on
#   the FIRST pass, rather than needing a later rescue pass (see Step 9
#   below) to fix a verdict that was only ever a stale pre-analysis
#   snapshot.
#
# STEPS (each individually toggleable via prompts):
#
#   Step 5c - EcuFlash XML table labelling, with per-table VERIFIED/
#             SUSPECT/REJECTED cross-check against real ROM bytes
#              - Prompts for XML file via file browser
#              - Verifies ROM ID matches XML before touching anything -
#                a mismatched/wrong-revision XML is rejected outright
#              - On a match: labels AND types VERIFIED table headers as
#                data (xml_addr - header_size); SUSPECT tables are
#                reported only; REJECTED tables are left untyped and
#                flagged loudly
#              - 1D scalars: labeled/typed at their raw address (no
#                header to verify, always SUSPECT-tier by design)
#   Step 8  - ROM header scraper (complements Step 5c XML labels, or
#             stands alone if no XML was applied)
#              - MUT table labels
#              - Scaling table detection (6-byte header pattern)
#              - 3D value table detection (0x03 + two RAM ptr words)
#              - 2D value table detection (0x02 + one RAM ptr word)
#              - All heuristics ported from mitsubishi-h8-539-rom-scraper
#   Step 8d - Page 2 label-coverage marker (report only - flags the
#             ROM scraper's known page-2 blind spot)
#   Step 9  - Re-verify REJECTED XML tables against current state.
#             Demoted from "the fix for stale pre-analysis rejections" to
#             a defensive re-check: since Step 5c itself now always runs
#             post-analysis, a REJECTED verdict here is not a stale
#             snapshot, it's a genuine collision with real code AT THE
#             TIME OF THIS RUN. This step still earns its keep for the
#             case where you re-run this script later (new/different XML,
#             or manual fixes made in between runs) and want previously-
#             rejected entries re-checked against whatever's changed
#             since.
#
# IMPORT SETTINGS REQUIRED (same ROM setup as the master script):
#   Format:       Raw Binary
#   Language:     H8:BE:32:H8539F
#   Base Address: 0x00010000
#
# ADDRESS CONVENTION:
#   EcuFlash XML "address" = first DATA byte of the table.
#   ROM header precedes data:
#     2D table header = 4 bytes  -> header at xml_addr - 4
#     3D table header = 7 bytes  -> header at xml_addr - 7
#     1D scalar       = no header -> labeled at xml_addr directly
#   Code xrefs point at the header address - that is where we label.

from java.math import BigInteger
from ghidra.program.flatapi import FlatProgramAPI
import os, xml.etree.ElementTree as ET

flat_api = FlatProgramAPI(currentProgram)
mem      = currentProgram.getMemory()
space    = currentProgram.getAddressFactory().getDefaultAddressSpace()
listing  = currentProgram.getListing()
symTable = currentProgram.getSymbolTable()
bookmarkMgr = currentProgram.getBookmarkManager()

ROM_BASE  = 0x00010000
ROM_END   = 0x0002FFFF
ROM_SIZE  = 0x20000      # 128 KB (two 64 KB pages)

# MUT table is at a fixed CPU offset from ROM base
MUT_OFFSET  = 0x1FAD0
MUT_ADDR    = ROM_BASE + MUT_OFFSET
MUT_ENTRIES = 256

# RAM range for pointer validation
MEM_ADDR_MIN = 0xEE00
MEM_ADDR_MAX = 0xFEFF

# Header sizes by table type (bytes before data start)
HEADER_SIZE = {"2D": 4, "3D": 7}

PROGRAM_INFO_CATEGORY   = "H8539F Setup Script"
XML_APPLIED_KEY         = "Last XML Applied"
XML_APPLIED_ROMID_KEY   = "Last XML ROM ID Verified"
XML_TOUCHED_ADDRS_KEY   = "Last XML Touched Addresses"   # comma-separated hex offsets

# Tracks XML table-overlap regions already warned about, keyed by the
# containing code unit's start address (as a string), so safe_plate only
# reports each distinct overlap region ONCE - not once per table/entry
# that lands inside it. See safe_plate() below.
_warned_overlap_regions = set()

# ──────────────────────────────────────────────────────────────────
# Shared helpers
# ──────────────────────────────────────────────────────────────────

def addr(offset):
    return space.getAddress(offset & 0xFFFFFFFF)

def in_rom(offset):
    return ROM_BASE <= offset <= ROM_END

def in_ram(val):
    return MEM_ADDR_MIN <= val <= MEM_ADDR_MAX

def abort(msg):
    print("ABORT: " + msg)
    raise Exception(msg)

def rom_byte(cpu_offset):
    """Read one byte from ROM at a CPU-page-relative offset."""
    try:
        return flat_api.getByte(addr(ROM_BASE + cpu_offset)) & 0xFF
    except Exception:
        return 0

def rom_word(cpu_offset):
    """Read a big-endian word from ROM at a CPU-page-relative offset."""
    return (rom_byte(cpu_offset) << 8) | rom_byte(cpu_offset + 1)

def rom_bytes_at(ghidra_addr, length):
    """Read 'length' bytes starting at a Ghidra address."""
    result = []
    for i in range(length):
        try:
            result.append(flat_api.getByte(addr(ghidra_addr + i)) & 0xFF)
        except Exception:
            result.append(0)
    return result

def find_sentinel_data_len(start, max_len=0x1FF):
    """
    Scan forward from ROM offset 'start' for the 0xFF terminator byte that
    ends every 2D/3D value table's data run on this ROM (see review.md
    item 18 / the Post Start Enrichment - Lean Spool Trailing Time XML
    fixes). Shared module-level copy - used by the Step 8 scraper and
    verify_xml_table() so both passes agree on what "a real table ends
    here" means.

    Returns the data length INCLUDING the terminator byte, so that
    'header_start + header_len + data_len' lands on the next table's
    header. Returns None if no 0xFF turns up within max_len bytes.
    """
    for j in range(max_len):
        if rom_byte(start + j) == 0xFF:
            return j + 1
    return None

def header_shape_ok(header_offset, ttype):
    """
    Check whether the bytes at 'header_offset' look like a genuine 2D/3D
    table header on this ROM, independent of what any XML claims.

    Convention confirmed across many independently-traced tables (see
    review.md items 1/6/7/17): a real header is a mode byte (0x02 for 2D,
    0x03 for 3D) followed by 0x00, followed by one (2D) or two (3D) RAM
    pointers in the 0xF0xx-0xF7xx range (MEM_ADDR_MIN-MEM_ADDR_MAX).

    This is a POSITIVE-EVIDENCE check only - it does not know about the
    header-record convention some tables use (item 17), so a False result
    here is not proof the address is wrong, only that this particular
    signature isn't present. Combine with find_sentinel_data_len() before
    drawing any conclusion; never reject on this check alone.
    """
    if ttype == "2D":
        b = rom_bytes_at(ROM_BASE + header_offset, 4)
        if len(b) < 4:
            return False
        mode_ok = (b[0] == 0x02 and b[1] == 0x00)
        ptr = (b[2] << 8) | b[3]
        return mode_ok and in_ram(ptr)
    elif ttype == "3D":
        b = rom_bytes_at(ROM_BASE + header_offset, 7)
        if len(b) < 7:
            return False
        mode_ok = (b[0] == 0x03 and b[1] == 0x00)
        x_ptr = (b[2] << 8) | b[3]
        y_ptr = (b[4] << 8) | b[5]
        return mode_ok and in_ram(x_ptr) and in_ram(y_ptr)
    return False

def is_likely_code(header_offset):
    """
    Positive-evidence check that a byte-pattern table-header candidate is
    actually sitting inside real code, not data -- catches false-positive
    matches on instruction bytes that happen to satisfy the header gate
    (mode byte + in-range pointer bytes can occur by coincidence inside a
    dense instruction stream).

    Two independent signals, either one is enough to call it code:
      1. Ghidra already has an instruction defined AT or CONTAINING this
         address -- i.e. the candidate header either starts an instruction,
         or sits inside the byte range of one that started earlier. The
         latter case matters because a false-positive header pattern (mode
         byte + a coincidentally in-range pointer) very often lands
         mid-instruction, not at its start; getCodeUnitAt() alone would
         miss that, since the instruction "belongs" to its own start
         address, not to every byte offset inside it.
      2. Ghidra has a jump/call-type reference INTO this address (XREF
         tagged (j)/(c) in the listing). Real table headers are only ever
         referenced as DATA (a pointer loaded into a register, an operand
         address) -- never landed on directly by a branch. A jump-type
         xref into a byte-pattern match is strong evidence the match is
         actually a byte inside (or the start of) a real instruction, not
         a table header.

    Running post-analysis (this script's whole reason for existing) gives
    this check MORE evidence than it would have pre-analysis: more
    instructions and xrefs are defined by the time this runs, so a
    positive result here is more trustworthy, not less, than it would
    have been in the original pre-Step-6 timing.
    """
    a = addr(ROM_BASE + header_offset)
    try:
        cu = listing.getCodeUnitAt(a)
        if cu is None:
            # Not an instruction/data-unit START address -- check whether
            # 'a' falls INSIDE an already-defined instruction that started
            # earlier (e.g. a multi-byte opcode whose operand bytes happen
            # to satisfy the header gate). getCodeUnitContaining() covers
            # this; getCodeUnitAt() alone would silently miss it.
            cu = listing.getCodeUnitContaining(a)
        if cu is not None and cu.getMnemonicString() and not cu.getMnemonicString().startswith("??"):
            from ghidra.program.model.listing import Instruction
            if isinstance(cu, Instruction):
                return True
    except Exception:
        pass

    try:
        refMgr = currentProgram.getReferenceManager()
        refs = refMgr.getReferencesTo(a)
        for ref in refs:
            rt = ref.getReferenceType()
            if rt.isJump() or rt.isCall():
                return True
    except Exception:
        pass

    return False

def find_next_header_boundary(start, max_len=0x1FF):
    """
    Scan forward from ROM offset 'start' for the next byte position that
    looks like a genuine table header (2D or 3D shape per header_shape_ok),
    and treat that as the end-of-data boundary for the CURRENT table.

    REPLACES find_sentinel_data_len() as the primary length source for
    tables that have real neighbor tables packed back-to-back with no
    0xFF terminator between them at all -- confirmed real case: Table D
    (0x11dc2, "Limp Home - TPS Table") is immediately followed by a real
    2D header (02 00 F0 C0) with NO terminator byte in between; a
    height-derived formula does not match its real 53-byte data length
    either (table_height=4 does not evenly divide 53), so neither "scan
    for 0xFF" nor "trust height * row_width" is a safe general rule.

    This is a POSITIVE stop condition (found real evidence of the next
    thing) rather than a coincidental one (found some 0xFF byte,
    somewhere). Still bounded by max_len so a table with no real neighbor
    within range doesn't scan arbitrarily far into unrelated code.

    Starts scanning at j=1, not j=0 -- every table is guaranteed to claim
    at least 1 byte of its own data before a "next header" match counts.
    Without this, a table whose very first data byte(s) coincidentally
    reproduce a valid header shape self-matches at offset 0 and reports
    zero-length data. Confirmed real case: the 2D table at 0x13212's
    first four data bytes are themselves "02 00 F0 C0" (an exact repeat
    of a valid 2D header) purely by coincidence of the calibration
    values; the real table is 6 bytes (ending where the genuine next
    header actually starts, at 0x1321C), not 0.

    Returns the data length up to (not including) the next header, or
    None if nothing that looks like a real header turns up within
    max_len -- in that case the caller should fall back to
    find_sentinel_data_len() (some tables ARE 0xFF-terminated, notably
    the ones ending a cluster right before reserved/filler flash) rather
    than assume a length.
    """
    for j in range(1, max_len):
        off = start + j
        if header_shape_ok(off, "2D") or header_shape_ok(off, "3D"):
            return j
    return None

def header_shape_fault(header_offset, ttype):
    """
    Positive-evidence check for a SPECIFIC, nameable header defect, as
    opposed to header_shape_ok()'s plain pass/fail. Distinguishes "mode
    byte is right but a pointer is out of range" (a concrete, likely-real
    fault worth a human look) from "nothing about these bytes resembles a
    header at all" (which header_shape_ok() already reports and which is
    handled by the ordinary SUSPECT/REJECTED paths).

    Returns None if no specific fault is identified (either the shape is
    fully OK, or it's wrong in a generic way with nothing concrete to
    name), otherwise a short string describing the fault.
    """
    if ttype == "2D":
        b = rom_bytes_at(ROM_BASE + header_offset, 4)
        if len(b) < 4:
            return None
        mode_ok = (b[0] == 0x02 and b[1] == 0x00)
        ptr = (b[2] << 8) | b[3]
        if mode_ok and not in_ram(ptr):
            return "mode byte OK (02 00) but axis pointer 0x%04X is outside RAM range (0x%04X-0x%04X)" % (
                ptr, MEM_ADDR_MIN, MEM_ADDR_MAX)
        return None
    elif ttype == "3D":
        b = rom_bytes_at(ROM_BASE + header_offset, 7)
        if len(b) < 7:
            return None
        mode_ok = (b[0] == 0x03 and b[1] == 0x00)
        x_ptr = (b[2] << 8) | b[3]
        y_ptr = (b[4] << 8) | b[5]
        if mode_ok:
            if not in_ram(x_ptr) and not in_ram(y_ptr):
                return "mode byte OK (03 00) but BOTH axis pointers (X=0x%04X, Y=0x%04X) are outside RAM range" % (
                    x_ptr, y_ptr)
            if not in_ram(x_ptr):
                return "mode byte OK (03 00) but X-axis pointer 0x%04X is outside RAM range (0x%04X-0x%04X)" % (
                    x_ptr, MEM_ADDR_MIN, MEM_ADDR_MAX)
            if not in_ram(y_ptr):
                return "mode byte OK (03 00) but Y-axis pointer 0x%04X is outside RAM range (0x%04X-0x%04X)" % (
                    y_ptr, MEM_ADDR_MIN, MEM_ADDR_MAX)
            if x_ptr == y_ptr:
                return "mode byte OK (03 00) but X-axis and Y-axis pointers are identical (0x%04X) - " \
                       "a 3D table needs two distinct axes" % x_ptr
        return None
    return None

def verify_xml_table(name, ttype, header_offset, data_offset):
    """
    Cross-check a single XML-declared table against independent ROM
    evidence before it's trusted. Returns one of:

      "VERIFIED" - header shape matches AND a sentinel terminator exists
                   within a sane range. Safe to type/protect automatically.
      "CHECK"    - a SPECIFIC, nameable defect was positively identified
                   (e.g. mode byte correct but a pointer falls outside
                   RAM range, or a 3D table's X/Y axis pointers are
                   identical). This is stronger and more actionable than
                   plain SUSPECT: something concrete is wrong and a human
                   should look at exactly that thing. Report only, don't
                   type.
      "SUSPECT"  - can't be positively corroborated, and no specific
                   fault could be named (1D scalars with no header to
                   check; header shape check fails in a generic way but a
                   sentinel still exists nearby, which can legitimately
                   happen for tables using the header-record indirection
                   convention from review.md item 17 - table_lookup_interp/
                   table_3axis_interp_triple callers pass a header-record
                   address that isn't the flat XML data address, so a
                   shape mismatch here is NOT strong evidence of a bad
                   XML entry, just inconclusive). Report only, don't type.
      "REJECTED" - header shape fails AND no sentinel terminator exists
                   nearby either, AND the address sits on real code (an
                   actual instruction or a jump/call target). This is
                   the code-collision case: the XML address is landing
                   somewhere the disassembler has already confirmed is
                   code, not data. Do not type; flag loudly for manual
                   review (bookmarked H8539F-TABLE-CODE-OVERLAP).
      "NO_TABLE" - header shape fails AND no sentinel terminator exists
                   nearby either, but the address is NOT on code -- just
                   bytes that don't conform to any known table standard
                   (1D/2D/3D). Same strong-negative-evidence signal as
                   REJECTED, but distinguished because the failure mode
                   is different: nothing recognizable is here at all,
                   rather than a code collision specifically. Do not
                   type; flag loudly for manual review (bookmarked
                   H8539F-TABLE-NO-TABLE).
    Deliberately conservative: only REJECTED and NO_TABLE block a table
    from ever being typed automatically. CHECK and SUSPECT are both
    report-only, never silently accepted and never silently discarded -- see
    review.md item 3's own design note ("agreement is corroboration,
    not automatic truth") and item 17's caution against blanket-applying
    one table's fix pattern to others without individual confirmation.
    CHECK exists purely to separate "something specific and identified
    is wrong" from SUSPECT's broader "can't corroborate either way" so a
    human reviewing the bookmark list knows which ones have an actual
    named lead to chase.

    Running post-analysis: a REJECTED verdict here means the address
    collided with real, settled disassembly/xrefs at the time this
    script ran -- not a snapshot that later needs a rescue pass.
    """
    if ttype not in ("2D", "3D"):
        # 1D scalars have no ROM header to corroborate against at all.
        return ("SUSPECT", "1D scalar - no header to verify")

    # header_offset/data_offset are bare CPU-relative ROM offsets here
    # (the caller converts full Ghidra addresses to offsets right before
    # calling this function), matching the convention every helper below
    # -- is_likely_code, header_shape_ok, find_sentinel_data_len -- expects
    # and adds ROM_BASE to internally. in_rom() itself checks a full
    # address range, so it needs ROM_BASE added back for this one check.
    if not in_rom(ROM_BASE + header_offset):
        return ("SUSPECT", "header offset outside ROM range")

    if is_likely_code(header_offset):
        return ("REJECTED", "address already contains a real instruction or has a "
                             "jump/call reference into it -- this is code, not a table "
                             "header (the XML address is very likely wrong)")

    shape_ok = header_shape_ok(header_offset, ttype)
    sentinel_len = find_sentinel_data_len(data_offset)
    fault = header_shape_fault(header_offset, ttype)

    if shape_ok and sentinel_len is not None:
        return ("VERIFIED", "header shape OK, data terminates at +%d" % sentinel_len)
    elif fault is not None:
        return ("CHECK", fault)
    elif not shape_ok and sentinel_len is None:
        return ("NO_TABLE", "no valid header shape AND no sentinel terminator found "
                             "within 0x1FF bytes - no table conforming to any known "
                             "standard (1D/2D/3D) was found at this address")
    elif shape_ok and sentinel_len is None:
        return ("SUSPECT", "header shape OK but no sentinel terminator found - "
                            "possibly a very large or unusual table")
    else:
        return ("SUSPECT", "sentinel terminator found but header shape doesn't match - "
                            "may use the header-record indirection convention "
                            "(review.md item 17), not necessarily a bad XML address")

def check_range_overlap(touched_ranges, start_offset, end_offset, header_offset=None):
    """
    Check whether [start_offset, end_offset] (inclusive, CPU-relative ROM
    offsets covering a table's header+data bytes) overlaps any range
    already recorded in touched_ranges from earlier in THIS SAME apply_xml
    run (including everything pulled in via <include>).

    This catches the case type_header_as_data() alone cannot: two
    different XML <table> entries whose header/data byte spans genuinely
    intersect (e.g. one table's header lands inside the tail of the
    previous table's data, or two headers partially overlap). Each
    type_header_as_data() call only clobbers whatever code-unit sat at
    ITS OWN address -- it has no visibility into a PRIOR XML table's
    range, so back-to-back XML entries with bad addresses can silently
    overwrite each other with no warning at all before this check existed.

    header_offset, if given, is the CURRENT table's own header offset.
    Any recorded range whose header offset is IDENTICAL to this one is
    skipped -- that's the same table being processed a second time in
    this run (e.g. reachable via two different <include> paths that the
    file-path-keyed visited-set in apply_xml doesn't dedupe), not a real
    collision between two distinct tables. Without this guard, a table
    revisited later in the run "collides" with its own earlier entry and
    gets falsely flagged OVERLAP against itself.

    Returns the first genuinely-distinct overlapping entry as
    (start, end, name, header_addr) if found, else None. Does not itself
    mutate touched_ranges -- the caller adds the new range after deciding
    how to handle any overlap.
    """
    for (o_start, o_end, o_name, o_header_addr) in touched_ranges:
        if header_offset is not None and o_start == header_offset:
            continue  # same table, revisited -- not a real collision
        if start_offset <= o_end and end_offset >= o_start:
            return (o_start, o_end, o_name, o_header_addr)
    return None

def resolve_header_address(xml_addr_int, ttype, hdr_size):
    """
    Figure out where a 2D/3D table's real header actually sits, since this
    ROM's XML uses TWO different addressing conventions and nothing in the
    XML itself says which one a given entry follows:

      Convention A ("address = header"): the XML address IS the header
      byte (mode + RAM pointer(s)) directly. Confirmed via live memory read
      on ordinary tables like "Knock Control Above Load" (address=12832 ->
      bytes at 0x12832 are 02 00 F0 C4, a valid header with zero offset)
      and "Max Total Upward WGDC Correction vs TPS" (address=12a72 -> bytes
      at 0x12a72 are 02 00 F0 C0). This appears to be the COMMON case.

      Convention B ("address = data, header is hdr_size bytes earlier"):
      the XML address is the DATA start, and the real header sits hdr_size
      bytes before it. This is the convention the script originally assumed
      unconditionally. It still matters for tables where xml_addr - hdr_size
      genuinely lands on a real header (verified independently below, not
      assumed) -- e.g. some tables using item 17's header-record style
      layout.

    Since header_shape_ok() is a real, independent positive-evidence check
    (mode byte + in-RAM pointer, verified against live ROM bytes, not
    guessed), the safe way to pick between the two conventions is to just
    try both candidate addresses and see which one actually looks like a
    real header on THIS ROM, rather than assuming one convention for every
    table in the file.

    Returns (header_int, convention_label) where convention_label is one of
    "header-at-xml-addr", "header-before-xml-addr", or "unresolved" (neither
    candidate passed header_shape_ok -- caller should fall back to the
    original xml_addr - hdr_size guess and let verify_xml_table's normal
    SUSPECT/REJECTED logic report the uncertainty as before).
    """
    candidate_a = xml_addr_int               # convention A: address IS the header
    candidate_b = xml_addr_int - hdr_size    # convention B: address is the data start

    if in_rom(candidate_a) and header_shape_ok(candidate_a - ROM_BASE, ttype):
        return (candidate_a, "header-at-xml-addr")
    if in_rom(candidate_b) and header_shape_ok(candidate_b - ROM_BASE, ttype):
        return (candidate_b, "header-before-xml-addr")
    return (candidate_b, "unresolved")   # preserve old default for the fallback path

def is_packed_micro_record(table_elem):
    """
    Detect EcuFlash <table> entries that are tagged type="2D"/"3D" but are
    NOT real axis-driven grids -- e.g. the "Case Number (Spec N)" and
    "Software Version" family, which are small fixed-width packed records
    (a few label/PN bytes) spaced only 4-25 bytes apart in ROM.

    The generic 2D/3D path assumes a real table: HEADER_SIZE bytes of RAM
    axis-pointer header, then a data grid sized from real axis element
    counts. For these packed micro-records there is no such header and no
    real axis - "Static X/Y Axis" children carry hardcoded string labels
    with no ROM address, and any real axis child has elements="1". Backing
    up HEADER_SIZE bytes from their XML address walks straight into the
    tail of the previous record (see review.md's Case Number (Spec 4)
    overlap finding), because consecutive records are packed far closer
    together than any genuine 3D table's axis data ever is.

    Returns True only when EVERY child <table> is either:
      - a Static X/Y Axis (no address attribute at all), or
      - a real axis with elements="1" (a single-row/column "axis", which
        isn't really an axis, just a scalar slot dressed up as one)
    i.e. there is no genuine multi-element ROM-addressed axis anywhere in
    this table, which is the actual defining feature of a real 2D/3D grid.
    Any table with a real axis (elements > 1, has a ROM address) returns
    False and is left on the normal HEADER_SIZE path untouched.
    """
    children = table_elem.findall('table')
    if not children:
        return False
    for child in children:
        child_type = child.get('type') or ""
        if 'Static' in child_type:
            continue
        addr_attr = child.get('address')
        try:
            elements = int(child.get('elements') or "0")
        except ValueError:
            elements = 0
        if addr_attr and elements > 1:
            return False
    return True

def safe_label(a, name, overwrite=False):
    """
    Create label at Ghidra address 'a'.
    Uses getPrimarySymbol() - returns None when no symbol exists.
    Skips silently if label already exists (unless overwrite=True).
    """
    try:
        primary = symTable.getPrimarySymbol(a)
        if primary is not None and not overwrite:
            return False
        flat_api.createLabel(a, name, True)
        return True
    except Exception as e:
        print("  WARNING label '%s' @ %s: %s" % (name, a, e))
        return False

def safe_label_offset(cpu_offset, name, overwrite=False):
    """safe_label variant that takes a CPU-page-relative ROM offset."""
    return safe_label(addr(ROM_BASE + cpu_offset), name, overwrite)

def safe_label_ram(ram_val, name):
    """Label a RAM address if it falls in the valid RAM range."""
    if not in_ram(ram_val):
        return
    a = addr(ram_val)
    blk = mem.getBlock(a)
    if blk is None:
        return
    safe_label(a, name)

def safe_plate(a, text, written_set=None):
    """
    Plate comment at Ghidra address 'a'.

    written_set (optional): a set shared across one whole XML-apply run
    (a top-level apply_xml() call plus everything it recurses into via
    <include>). On this address's FIRST touch within that run, any stale
    plate comment left over from a PREVIOUS run is fully overwritten -
    this is what stops re-imports from stacking old and new table text
    forever. On a SECOND+ touch within the SAME run (e.g. two XML tables
    genuinely overlapping the same code unit), behaviour falls back to
    the old append-and-dedupe logic so both entries stay visible for that
    one import.

    If written_set is None (legacy callers, e.g. step 8's scanners),
    behaves exactly as before: append-only, never clobbers.
    """
    try:
        from ghidra.program.model.listing import CodeUnit
        cu = listing.getCodeUnitAt(a)
        overlap = False
        if cu is None:
            cu = listing.getCodeUnitContaining(a)
            if cu is not None:
                overlap = True
        if cu is None:
            return
        if overlap:
            region_key = str(cu.getMinAddress())
            if region_key not in _warned_overlap_regions:
                _warned_overlap_regions.add(region_key)
                print("  WARNING: XML table overlap - region starting at %s "
                      "(%d bytes) has entries from more than one XML table "
                      "landing inside it (first seen via address %s). "
                      "Comments still attached, but verify the table "
                      "addresses against the XML/ROM - one is likely stale. "
                      "(further entries in this same region are not "
                      "re-reported individually)" %
                      (cu.getMinAddress(), cu.getLength(), a))
            text = "[OVERLAP - VERIFY ADDRESS] " + text

        key = str(cu.getMinAddress())
        if written_set is not None and key not in written_set:
            written_set.add(key)
            cu.setComment(CodeUnit.PLATE_COMMENT, text)
            return

        existing = cu.getComment(CodeUnit.PLATE_COMMENT)
        if existing and text in existing:
            return
        new_text = (existing + "\n" + text) if existing else text
        cu.setComment(CodeUnit.PLATE_COMMENT, new_text)
        if written_set is not None:
            written_set.add(key)
    except Exception as e:
        print("  WARNING plate comment @ %s: %s" % (a, e))

def safe_plate_offset(cpu_offset, text, written_set=None):
    """safe_plate variant taking a CPU-page-relative ROM offset."""
    safe_plate(addr(ROM_BASE + cpu_offset), text, written_set)

def safe_bookmark(a, category, text):
    """
    Set/replace a NOTE bookmark at address 'a'. Ghidra's BookmarkManager
    already de-dupes by (address, type, category) internally - calling
    this again on the same address+category just updates the comment
    text in place rather than creating a duplicate, so it's safe to call
    on every re-run without accumulating bookmarks.
    """
    try:
        from ghidra.program.model.listing import BookmarkType
        bookmarkMgr.setBookmark(a, BookmarkType.NOTE, category, text)
    except Exception as e:
        print("  WARNING bookmark @ %s: %s" % (a, e))

def safe_eol(cpu_offset, text):
    """Set EOL comment at a CPU-page-relative ROM offset."""
    try:
        flat_api.setEOLComment(addr(ROM_BASE + cpu_offset), text)
    except Exception:
        pass

def sanitise_name(name):
    """Make a valid Ghidra label from a human-readable table name."""
    result = ""
    for ch in name:
        if ch.isalnum() or ch == '_':
            result += ch
        elif ch in (' ', '-', '/'):
            result += '_'
    while '__' in result:
        result = result.replace('__', '_')
    return result.strip('_')

def type_header_as_data(header_addr, size):
    """
    Type 'size' bytes at header_addr as a byte array, clearing whatever was
    there first.

    Running post-analysis, this clear-then-type is a CORRECTION, not
    prevention: it may be undoing whatever auto-analysis guessed at this
    address (an instruction, undefined bytes, or a partial data unit).
    verify_xml_table()'s is_likely_code() check runs BEFORE this is ever
    called (a REJECTED verdict stops apply_xml from reaching this line at
    all), so by the time this executes the address has already been
    positively confirmed as data, not live code -- clearCodeUnits() here
    is operating on bytes already judged safe to retype, not gambling on
    unknown territory. Safe to call redundantly (idempotent).
    """
    try:
        from ghidra.program.model.data import ByteDataType, ArrayDataType
        end_addr = header_addr.add(size - 1)
        if listing.getInstructionAt(header_addr) is None and \
           listing.getDefinedDataAt(header_addr) is not None and \
           listing.getDefinedDataAt(header_addr).getLength() == size:
            return False   # already correctly typed, nothing to do
        listing.clearCodeUnits(header_addr, end_addr, False)
        listing.createData(header_addr, ArrayDataType(ByteDataType(), size, 1))
        return True
    except Exception as e:
        print("  WARNING: could not type 0x%08X (%d bytes) as data: %s" %
              (header_addr.getOffset(), size, e))
        return False

def verify_rom_id(xml_root):
    """
    Read <internalidaddress> and <internalidhex> from the XML romid block,
    then compare against actual ROM bytes.

    Returns (True, details_str) on match or if romid fields are absent.
    Returns (False, details_str) on mismatch - caller should warn/skip.
    """
    romid = xml_root.find('romid')
    if romid is None:
        return True, "No <romid> block in XML - skipping ID check"

    id_addr_str = romid.findtext('internalidaddress', '').strip()
    id_hex_str  = romid.findtext('internalidhex', '').strip()
    xml_id_str  = romid.findtext('xmlid', '').strip()

    if not id_addr_str or not id_hex_str:
        return True, "No internalidaddress/internalidhex in XML - skipping ID check"

    try:
        id_addr = int(id_addr_str, 16)   # already an absolute Ghidra address
    except ValueError:
        return True, "Could not parse internalidaddress '%s' - skipping" % id_addr_str

    id_hex_clean = id_hex_str.replace(' ', '')
    if len(id_hex_clean) % 2 != 0:
        id_hex_clean = '0' + id_hex_clean
    try:
        expected_bytes = [int(id_hex_clean[i:i+2], 16)
                          for i in range(0, len(id_hex_clean), 2)]
    except ValueError:
        return True, "Could not parse internalidhex '%s' - skipping" % id_hex_str

    ghidra_id_addr = id_addr
    actual_bytes = rom_bytes_at(ghidra_id_addr, len(expected_bytes))

    expected_hex = ' '.join('%02X' % b for b in expected_bytes)
    actual_hex   = ' '.join('%02X' % b for b in actual_bytes)

    detail = ("XML ID  : %s (at Ghidra address 0x%08X)\n"
              "Expected: %s\n"
              "Actual  : %s" % (xml_id_str, ghidra_id_addr,
                                expected_hex, actual_hex))

    if expected_bytes == actual_bytes:
        return True, detail
    else:
        return False, detail

def get_last_xml_applied():
    opts = currentProgram.getOptions(PROGRAM_INFO_CATEGORY)
    path = opts.getString(XML_APPLIED_KEY, None)
    ok   = opts.getBoolean(XML_APPLIED_ROMID_KEY, False)
    return path, ok

def set_last_xml_applied(path, id_ok):
    opts = currentProgram.getOptions(PROGRAM_INFO_CATEGORY)
    opts.setString(XML_APPLIED_KEY, path)
    opts.setBoolean(XML_APPLIED_ROMID_KEY, id_ok)

def get_last_xml_touched_addrs():
    """Returns a list of int CPU offsets touched by the last apply_xml run."""
    opts = currentProgram.getOptions(PROGRAM_INFO_CATEGORY)
    raw = opts.getString(XML_TOUCHED_ADDRS_KEY, "")
    if not raw:
        return []
    out = []
    for tok in raw.split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            out.append(int(tok, 16))
        except ValueError:
            pass
    return out

def set_last_xml_touched_addrs(offsets):
    opts = currentProgram.getOptions(PROGRAM_INFO_CATEGORY)
    opts.setString(XML_TOUCHED_ADDRS_KEY, ",".join("%X" % o for o in sorted(set(offsets))))

def clear_xml_labels(offsets, clear_scraped=False):
    """
    Undo what apply_xml did at each of the given CPU-offset addresses:
    remove the label/symbol, remove the plate comment, remove the
    H8539F-TABLE bookmark and any status-specific bookmark (CHECK,
    OVERLAP, OVERLAP-BAD, BAD, REJECTED, REJECTED-CORRECTED), and clear
    the code unit back to undefined so the next import can re-type it
    cleanly.

    If clear_scraped is True, ALSO remove any ROM-scraper artifacts at
    these same addresses: the H8539F-SCRAPED-TABLE bookmark, and any
    scraper-named symbol (TABLE_2D_*/TABLE_3D_*/SCALING_TABLE_*) that
    may be sitting there as a secondary/duplicate symbol left over from
    before the XML-vs-scraper address-unit bug was fixed. When False
    (the default), scraper-named symbols/bookmarks are left untouched -
    this only unwinds what the XML step itself did.

    Does NOT touch anything not in the offsets list -- this only unwinds
    exactly what a previous XML run recorded as touched (plus, optionally,
    whatever the scraper duplicated on top of those same addresses).
    """
    from ghidra.program.model.listing import CodeUnit
    from ghidra.program.model.listing import BookmarkType
    removed_labels    = 0
    removed_plates    = 0
    removed_bookmarks = 0
    cleared_data      = 0
    errors            = 0
    SCRAPER_PREFIXES = ("TABLE_2D_", "TABLE_3D_", "SCALING_TABLE_")
    for off in offsets:
        try:
            a = addr(off)

            for sym in list(symTable.getSymbols(a)):
                nm = sym.getName()
                if any(nm.startswith(p) for p in SCRAPER_PREFIXES) and not clear_scraped:
                    continue
                symTable.removeSymbolSpecial(sym)
                removed_labels += 1

            if listing.getComment(CodeUnit.PLATE_COMMENT, a) is not None:
                listing.setComment(a, CodeUnit.PLATE_COMMENT, None)
                removed_plates += 1

            xml_bm = bookmarkMgr.getBookmark(a, BookmarkType.NOTE, "H8539F-TABLE")
            if xml_bm is not None:
                bookmarkMgr.removeBookmark(xml_bm)
                removed_bookmarks += 1

            for status_cat in ("H8539F-TABLE-SUSPECT", "H8539F-TABLE-DATA-OVERLAP",
                                "H8539F-TABLE-DATA-OVERLAP-SUSPECT",
                                "H8539F-TABLE-CODE-OVERLAP", "H8539F-TABLE-CODE-OVERLAP-CORRECTED",
                                "H8539F-TABLE-NO-TABLE", "H8539F-TABLE-NO-TABLE-CORRECTED",
                                "H8539F-TABLE-SUSPECT-CORRECTED", "H8539F-TABLE-DATA-OVERLAP-CORRECTED",
                                "H8539F-TABLE-DATA-OVERLAP-SUSPECT-CORRECTED"):
                status_bm = bookmarkMgr.getBookmark(a, BookmarkType.NOTE, status_cat)
                if status_bm is not None:
                    bookmarkMgr.removeBookmark(status_bm)
                    removed_bookmarks += 1

            if clear_scraped:
                scraped_bm = bookmarkMgr.getBookmark(a, BookmarkType.NOTE, "H8539F-SCRAPED-TABLE")
                if scraped_bm is not None:
                    bookmarkMgr.removeBookmark(scraped_bm)
                    removed_bookmarks += 1

                rescued_bm = bookmarkMgr.getBookmark(a, BookmarkType.NOTE, "H8539F-TABLE-RESCUED")
                if rescued_bm is not None:
                    bookmarkMgr.removeBookmark(rescued_bm)
                    removed_bookmarks += 1

            cu = listing.getCodeUnitAt(a)
            if cu is not None:
                cu_len = cu.getLength()
                end_a = a.add(cu_len - 1) if cu_len > 1 else a
                listing.clearCodeUnits(a, end_a, False)
                cleared_data += 1
        except Exception as e:
            errors += 1
            print("  WARNING: could not clear 0x%08X: %s" % (off, e))
    print("  [clear-xml] removed labels: %d  removed plates: %d  "
          "removed bookmarks: %d  cleared data units: %d  errors: %d%s" %
          (removed_labels, removed_plates, removed_bookmarks, cleared_data, errors,
           "  (scraper artifacts included)" if clear_scraped else ""))

# ──────────────────────────────────────────────────────────────────
# apply_xml -- parse an EcuFlash XML, verify its ROM ID, then label
# table headers AND type VERIFIED ones as data.
# ──────────────────────────────────────────────────────────────────

def apply_xml(file_path, visited=None, id_verified=None, touched_offsets=None, written_addrs=None, touched_ranges=None):
    """
    Parse an EcuFlash XML, verify its ROM ID, then label table headers AND
    type VERIFIED ones as data.

    ROM ID VERIFICATION:
      Before touching anything, reads <internalidaddress> + <internalidhex>
      from the XML and compares against actual ROM bytes. On mismatch:
      prints a clear warning and skips entirely for that file (does NOT
      abort the script). id_verified is a mutable list [True/False/None]
      shared across the include chain so the check only runs once at the
      top-level file.

    ADDRESS STRATEGY:
      2D/3D tables: header/type at (xml_addr - header_size) = true header address.
      1D scalars  : header/type at xml_addr directly (no ROM header exists).

    DEDUPLICATION:
      Existing labels survive re-runs - only plate comments are updated.
      Already-correctly-typed data regions are left alone.

    INCLUDES:
      <include> entries are followed recursively (cycle-guarded).
    """
    if visited is None:
        visited = set()
    if id_verified is None:
        id_verified = [None]   # None=unchecked, True=ok, False=failed
    if touched_offsets is None:
        touched_offsets = []   # shared list, collects every offset apply_xml labels/types
    if written_addrs is None:
        written_addrs = set()  # shared across this whole run (+ includes); see safe_plate()
    if touched_ranges is None:
        touched_ranges = []    # shared across this whole run (+ includes); list of
                                # (start_offset, end_offset, name, header_addr) tuples
                                # for every 2D/3D table's header+data byte span touched
                                # so far, used to detect two XML tables overlapping the
                                # same ROM bytes. See check_range_overlap() below.

    real_path = os.path.realpath(file_path)
    if real_path in visited:
        return (0, 0, 0, 0, 0, 0, 0, 0)
    visited.add(real_path)

    if not os.path.exists(file_path):
        print("  WARNING: XML not found: " + file_path)
        return (0, 0, 0, 0, 0, 0, 0, 0)

    try:
        root = ET.parse(file_path).getroot()
    except Exception as e:
        print("  WARNING: Could not parse XML: " + str(e))
        return (0, 0, 0, 0, 0, 0, 0, 0)

    # ── ROM ID check (only on the top-level file, not includes) ────
    if id_verified[0] is None:
        ok, detail = verify_rom_id(root)
        id_verified[0] = ok
        if ok:
            print("  [ID] ROM ID verified OK")
            print("  [ID] " + detail.replace("\n", "\n  [ID] "))
        else:
            print("  [ID] WARNING: ROM ID MISMATCH - skipping XML labels for this file")
            print("  [ID] " + detail.replace("\n", "\n  [ID] "))
            print("  [ID] Load the correct XML for this ROM and re-run this step.")
            return (0, 0, 0, 0, 0, 0, 0, 0)

    if id_verified[0] is False:
        return (0, 0, 0, 0, 0, 0, 0, 0)

    base_dir = os.path.dirname(file_path)

    inc_h = inc_s = inc_a = inc_r = inc_v = inc_x = inc_c = inc_nt = 0
    for inc in root.findall('include'):
        inc_name = (inc.text or "").strip()
        if not inc_name:
            continue
        if not inc_name.endswith('.xml'):
            inc_name += '.xml'
        inc_path = os.path.join(base_dir, inc_name)
        ih, is_, ia, ir, iv, ix, ic, itbl = apply_xml(inc_path, visited, id_verified, touched_offsets, written_addrs, touched_ranges)
        inc_h += ih; inc_s += is_; inc_a += ia; inc_r += ir; inc_v += iv; inc_x += ix; inc_c += ic; inc_nt += itbl

    labeled_header = 0
    labeled_scalar = 0
    already_named  = 0
    skipped_range  = 0
    suspect_count  = 0
    rejected_count = 0
    no_table_count = 0
    check_count    = 0

    for table in root.findall('table'):
        name     = table.get('name')
        addr_str = table.get('address')
        ttype    = table.get('type')
        category = table.get('category') or ""
        scaling  = table.get('scaling') or ""
        swapxy   = table.get('swapxy') or ""
        flipy    = table.get('flipy') or ""
        level    = table.get('level') or ""

        if ttype and ('Axis' in ttype or 'axis' in ttype):
            continue
        if not name or not addr_str:
            continue

        try:
            xml_addr_int = int(addr_str, 16)
        except ValueError:
            continue

        if not in_rom(xml_addr_int):
            skipped_range += 1
            continue

        meta = ["EcuFlash Table : %s" % name]
        if category: meta.append("Category       : %s" % category)
        if ttype:    meta.append("Type           : %s" % ttype)
        if scaling:  meta.append("Scaling        : %s" % scaling)
        if swapxy:   meta.append("Swap XY        : %s" % swapxy)
        if flipy:    meta.append("Flip Y         : %s" % flipy)
        if level:    meta.append("Level          : %s" % level)

        label_name = sanitise_name(name)

        if ttype == "1D":
            target_addr = addr(xml_addr_int)
            type_header_as_data(target_addr, 2)
            touched_offsets.append(xml_addr_int)
            meta.append("Address        : 0x%05X  [scalar - no header]" % xml_addr_int)
            plate_text = "\n".join(meta)
            if symTable.getPrimarySymbol(target_addr) is not None:
                already_named += 1
            else:
                safe_label(target_addr, label_name)
                labeled_scalar += 1
            safe_plate(target_addr, plate_text, written_addrs)
            safe_bookmark(target_addr, "H8539F-TABLE", "%s (1D scalar)" % name)

        elif ttype in ("2D", "3D") and is_packed_micro_record(table):
            target_addr = addr(xml_addr_int)
            type_header_as_data(target_addr, 2)
            touched_offsets.append(xml_addr_int)
            meta.append("Address        : 0x%05X  [packed micro-record - no header]" % xml_addr_int)
            plate_text = "\n".join(meta)
            if symTable.getPrimarySymbol(target_addr) is not None:
                already_named += 1
            else:
                safe_label(target_addr, label_name)
                labeled_scalar += 1
            safe_plate(target_addr, plate_text, written_addrs)
            safe_bookmark(target_addr, "H8539F-TABLE", "%s (packed micro-record, %s)" % (name, ttype))

        elif ttype in ("2D", "3D") or ttype is None:
            hdr_size = HEADER_SIZE.get(ttype, 4)
            header_int, hdr_convention = resolve_header_address(xml_addr_int, ttype, hdr_size)
            header_addr = addr(header_int)

            if not in_rom(header_int):
                header_int  = xml_addr_int
                header_addr = addr(header_int)
                meta.append("NOTE: header offset (-%d) outside ROM; "
                             "labeled at data address." % hdr_size)
                verify_status, verify_detail = "SUSPECT", "computed header address fell outside ROM"
            else:
                if hdr_convention != "unresolved":
                    meta.append("Header convention : %s" % hdr_convention)
                verify_status, verify_detail = verify_xml_table(
                    name, ttype, header_int - ROM_BASE, xml_addr_int - ROM_BASE)

            meta.append("Verify status  : %s (%s)" % (verify_status, verify_detail))

            if verify_status in ("REJECTED", "NO_TABLE"):
                if verify_status == "REJECTED":
                    rejected_count += 1
                else:
                    no_table_count += 1
                print("  [XML-VERIFY] %s: '%s' (%s) at header 0x%05X -- %s" %
                      (verify_status, name, ttype, header_int, verify_detail))
                print("               NOT typed/protected. Check this XML entry's "
                      "address by hand before trusting it.")
                actual_bytes = rom_bytes_at(header_int, hdr_size)
                actual_hex = ' '.join('%02X' % bb for bb in actual_bytes)
                meta.append("FAULT          : %s" % verify_detail)
                meta.append("Bytes found    : %s  (expected mode byte %s + in-range RAM ptr)" %
                            (actual_hex, "02" if ttype == "2D" else "03" if ttype == "3D" else "?"))
                meta.append("NOTE: left untyped -- if the ROM scraper independently finds a "
                             "real table at/near this address, it will append the corrected "
                             "data below rather than replacing this note.")
                plate_text = "\n".join(meta)
                safe_plate(header_addr, plate_text, written_addrs)
                if verify_status == "REJECTED":
                    safe_bookmark(header_addr, "H8539F-TABLE-CODE-OVERLAP",
                                  "%s (%s) -- XML address lands on real code, not a table" % (name, ttype))
                else:
                    safe_bookmark(header_addr, "H8539F-TABLE-NO-TABLE",
                                  "%s (%s) -- no table conforming to any known standard "
                                  "(1D/2D/3D) found at this address" % (name, ttype))
                continue

            if verify_status == "CHECK":
                check_count += 1
                print("  [XML-VERIFY] CHECK: '%s' (%s) at header 0x%05X -- %s" %
                      (name, ttype, header_int, verify_detail))

            if verify_status == "SUSPECT":
                suspect_count += 1
                print("  [XML-VERIFY] SUSPECT: '%s' (%s) at header 0x%05X -- %s" %
                      (name, ttype, header_int, verify_detail))

            # ── Overlap check, BEFORE typing: does this table's header+data
            # span intersect a range some EARLIER table in this same run
            # already claimed? See check_range_overlap()'s docstring for
            # why type_header_as_data() alone can't catch this.
            overlap_hit = False
            was_check = False
            if in_rom(header_int):
                # data length unknown yet for a rough span estimate -- use
                # the sentinel/next-header scan the same way verify_xml_table
                # did, falling back to just the header bytes if neither finds
                # a length (still enough to catch a header-into-header collision).
                data_offset = xml_addr_int - ROM_BASE
                span_len = find_next_header_boundary(data_offset)
                if span_len is None:
                    span_len = find_sentinel_data_len(data_offset)
                if span_len is None:
                    span_len = 0
                span_start = header_int - ROM_BASE
                span_end = data_offset + span_len - 1
                span_end = max(span_end, span_start + hdr_size - 1)

                overlap = check_range_overlap(touched_ranges, span_start, span_end, header_offset=span_start)
                if overlap is not None:
                    overlap_hit = True
                    o_start, o_end, o_name, o_header_addr = overlap
                    # Compound severity: a table that ALREADY had a concrete
                    # fault (CHECK) and ALSO collides with another table is
                    # worse than either problem alone -- bookmark it BAD
                    # rather than the plain OVERLAP tier. A table that was
                    # otherwise clean (VERIFIED/SUSPECT) and only becomes
                    # suspect BECAUSE of the collision gets the lighter
                    # OVERLAP tier instead.
                    was_check = (verify_status == "CHECK")
                    if verify_status != "CHECK":
                        verify_status = "SUSPECT"
                        suspect_count += 1
                    overlap_note = ("OVERLAP: this table's byte range (0x%05X-0x%05X) overlaps "
                                     "'%s' (already claimed 0x%05X-0x%05X earlier in this same "
                                     "XML import). Both tables are now suspect -- verify both "
                                     "addresses by hand." %
                                     (ROM_BASE + span_start, ROM_BASE + span_end,
                                      o_name, ROM_BASE + o_start, ROM_BASE + o_end))
                    meta.append(overlap_note)
                    print("  [XML-VERIFY] OVERLAP: '%s' (%s) at header 0x%05X overlaps earlier "
                          "table '%s' at 0x%05X -- marking BOTH suspect" %
                          (name, ttype, header_int, o_name, ROM_BASE + o_start))

                    # The collision itself is always documented on both
                    # sides with the same OVERLAP-BAD marker, regardless of
                    # severity tier -- this is "these two addresses fight
                    # over the same bytes," independent of how bad either
                    # table's own verdict was going in.
                    safe_bookmark(header_addr, "H8539F-TABLE-DATA-OVERLAP-SUSPECT",
                                  "%s (%s) -- overlaps '%s' at 0x%05X, XML addresses need manual review" %
                                  (name, ttype, o_name, ROM_BASE + o_start))
                    # Retroactively re-flag the earlier table too -- it's
                    # equally compromised by this collision, not just the
                    # later one that happened to be processed second.
                    safe_bookmark(o_header_addr, "H8539F-TABLE-DATA-OVERLAP-SUSPECT",
                                  "%s -- overlaps '%s' at 0x%05X (found when the later table was "
                                  "processed), XML addresses need manual review" %
                                  (o_name, name, header_int))
                    try:
                        from ghidra.program.model.listing import CodeUnit as _CU_overlap
                        o_cu = listing.getCodeUnitAt(o_header_addr)
                        if o_cu is not None:
                            o_existing = o_cu.getComment(_CU_overlap.PLATE_COMMENT) or ""
                            o_note = ("OVERLAP: '%s' at 0x%05X was found to overlap this table's "
                                      "range (0x%05X-0x%05X) later in the same import -- both "
                                      "tables are now suspect, verify both addresses by hand." %
                                      (name, header_int, ROM_BASE + o_start, ROM_BASE + o_end))
                            if o_note not in o_existing:
                                o_cu.setComment(_CU_overlap.PLATE_COMMENT,
                                                 (o_existing + "\n" + o_note) if o_existing else o_note)
                    except Exception as e:
                        print("  WARNING: could not amend earlier table's plate @ %s: %s" % (o_header_addr, e))

                touched_ranges.append((span_start, span_end, name, header_addr))

                type_header_as_data(header_addr, hdr_size)
                touched_offsets.append(header_int)
                if hdr_convention == "header-at-xml-addr":
                    real_data_int = xml_addr_int + hdr_size
                else:
                    real_data_int = xml_addr_int
                meta.append("Header address : 0x%05X  (code xrefs point here)" % header_int)
                meta.append("Data address   : 0x%05X  (%d bytes after header)" %
                             (real_data_int, hdr_size))

            plate_text = "\n".join(meta)
            if symTable.getPrimarySymbol(header_addr) is not None:
                already_named += 1
            else:
                safe_label(header_addr, label_name)
                labeled_header += 1
            safe_plate(header_addr, plate_text, written_addrs)

            # Status-specific bookmark category, on top of the collision
            # marker (H8539F-TABLE-DATA-OVERLAP-SUSPECT) already set above if this
            # table collided with another. Every category is filterable on
            # its own in the Bookmarks window: SUSPECT (a specific, named
            # defect); DATA-OVERLAP-SUSPECT (a SUSPECT-tier defect compounded
            # by a collision -- the worst case); DATA-OVERLAP (otherwise-clean
            # table only made suspect because it collided with another);
            # TABLE (the plain VERIFIED/no-fault case, or a generic suspect
            # verdict with no specific fault and no collision).
            if overlap_hit and was_check:
                safe_bookmark(header_addr, "H8539F-TABLE-DATA-OVERLAP-SUSPECT",
                              "%s (%s) -- SUSPECT-tier defect compounded by an address overlap "
                              "with '%s'; see H8539F-TABLE-SUSPECT and H8539F-TABLE-DATA-OVERLAP-SUSPECT "
                              "for the individual faults" % (name, ttype, o_name))
            elif overlap_hit:
                safe_bookmark(header_addr, "H8539F-TABLE-DATA-OVERLAP",
                              "%s (%s) -- marked suspect solely due to overlapping '%s'" %
                              (name, ttype, o_name))
            elif verify_status == "CHECK":
                safe_bookmark(header_addr, "H8539F-TABLE-SUSPECT",
                              "%s (%s) -- %s" % (name, ttype, verify_detail))
            else:
                safe_bookmark(header_addr, "H8539F-TABLE", "%s (%s)" % (name, ttype or "2D/3D"))

        else:
            target_addr = addr(xml_addr_int)
            touched_offsets.append(xml_addr_int)
            meta.append("Address        : 0x%05X" % xml_addr_int)
            meta.append("NOTE: unrecognised type '%s'" % ttype)
            plate_text = "\n".join(meta)
            if symTable.getPrimarySymbol(target_addr) is None:
                safe_label(target_addr, label_name)
            safe_plate(target_addr, plate_text, written_addrs)
            safe_bookmark(target_addr, "H8539F-TABLE", "%s (unrecognised type '%s')" % (name, ttype))

    total_h = labeled_header + inc_h
    total_s = labeled_scalar + inc_s
    total_a = already_named  + inc_a
    total_r = skipped_range  + inc_r
    total_v = suspect_count  + inc_v
    total_x = rejected_count + inc_x
    total_c = check_count    + inc_c
    total_nt = no_table_count + inc_nt

    print("  %s -> header-labeled: %d  scalar-labeled: %d  "
          "plate-updated: %d  out-of-range: %d  suspect: %d  check: %d  rejected: %d  no-table: %d" %
          (os.path.basename(file_path),
           labeled_header, labeled_scalar, already_named, skipped_range,
           suspect_count, check_count, rejected_count, no_table_count))
    if rejected_count:
        print("  [XML-VERIFY] %d table(s) in %s landed on real CODE and left "
              "UNTYPED -- see [XML-VERIFY] lines above for details." %
              (rejected_count, os.path.basename(file_path)))
    if no_table_count:
        print("  [XML-VERIFY] %d table(s) in %s found NO conforming table (1D/2D/3D) "
              "and left UNTYPED -- see [XML-VERIFY] lines above for details." %
              (no_table_count, os.path.basename(file_path)))
    if check_count:
        print("  [XML-VERIFY] %d table(s) in %s flagged CHECK -- a specific, "
              "nameable header defect was found; see [XML-VERIFY] CHECK lines above." %
              (check_count, os.path.basename(file_path)))

    return (total_h, total_s, total_a, total_r, total_v, total_x, total_c, total_nt)

# ──────────────────────────────────────────────────────────────────
def run_rom_scraper():
    """
    Full ROM scraper ported from the JS reference implementation.

    Pass 1 - MUT table (fixed offset 0x1FAD0):
      256 entries x 2 bytes, each a RAM pointer to a diagnostic variable.

    Pass 2 - Scaling tables (6-byte header):
      [F0-F7] xx [E0-FE] xx 00 [02-90]
      output RAM ptr | input RAM ptr | 0x00 | entry count
      Followed by count*2 bytes of 16-bit scaling data.
      Sanity: first 3 data words must not differ by > 0x1000.

    Pass 3 - 3D value tables (7-byte header):
      0x03 | padding | X-axis RAM ptr (word) | Y-axis RAM ptr (word) | nrows
      Sanity: first 3 data words must not differ by > 0x4000.

    Pass 4 - 2D value tables (4-byte header):
      0x02 | padding | axis RAM ptr (word)
      Sanity: first 3 data words must not differ by > 0x4000.

    All passes use getPrimarySymbol() for existence checks (no hasNext bug).
    """

    def in_range(val, lo, hi):
        return lo <= val <= hi

    xml_touched = set(get_last_xml_touched_addrs())
    xml_skip_scaling = 0
    xml_skip_3d = 0
    xml_skip_2d = 0
    written_addrs = set()

    # ── Pass 1: MUT table ─────────────────────────────────────────
    print("[8a] MUT table at ROM offset 0x%05X (Ghidra 0x%08X)..." %
          (MUT_OFFSET, MUT_ADDR))
    mut_count = 0
    tx = currentProgram.startTransaction("MUT table labels")
    try:
        for i in range(MUT_ENTRIES):
            off = MUT_OFFSET + i * 2
            val = rom_word(off)
            entry_lbl = "MUT_%02X_entry" % i
            safe_label_offset(off, entry_lbl)
            safe_plate_offset(off,
                "MUT Table Entry\n"
                "Index  : 0x%02X (%d)\n"
                "Target : RAM:0x%04X" % (i, i, val), written_addrs)
            safe_label_ram(val, "MUT_%02X" % i)
            mut_count += 1
    finally:
        currentProgram.endTransaction(tx, True)
    print("[8a] OK: %d MUT entries labeled" % mut_count)

    # ── Pass 2: Scaling tables ────────────────────────────────────
    print("[8b] Scanning for scaling tables (0x%08X - 0x%08X)..." %
          (ROM_BASE, MUT_ADDR))
    scaling_count = 0
    tx = currentProgram.startTransaction("Scaling table labels")
    try:
        i = 0
        while i < MUT_OFFSET - 5:
            b = [rom_byte(i + j) for j in range(6)]
            if (in_range(b[0], 0xF0, 0xF7) and
                    in_range(b[2], 0xE0, 0xFE) and
                    b[4] == 0x00 and
                    in_range(b[5], 0x02, 0x90)):
                bogus = False
                prev = rom_word(i + 6)
                for j in range(0, 6, 2):
                    nv = rom_word(i + 6 + j)
                    if abs(nv - prev) > 0x1000:
                        bogus = True
                        break
                    prev = nv
                if not bogus:
                    out_ptr = (b[0] << 8) | b[1]
                    in_ptr  = (b[2] << 8) | b[3]
                    count   = b[5]
                    lbl     = "SCALING_TABLE_%08X" % (ROM_BASE + i)
                    if (ROM_BASE + i) in xml_touched:
                        xml_skip_scaling += 1
                    else:
                        type_header_as_data(addr(ROM_BASE + i), 6 + count * 2)
                        safe_label_offset(i, lbl)
                        safe_plate_offset(i,
                            "Scaling Table\n"
                            "Out ptr : RAM:0x%04X\n"
                            "In ptr  : RAM:0x%04X\n"
                            "Entries : %d (%d bytes)" %
                            (out_ptr, in_ptr, count, count * 2), written_addrs)
                        safe_bookmark(addr(ROM_BASE + i), "H8539F-SCRAPED-TABLE",
                                      "%s (Scaling)" % lbl)
                    safe_label_ram(out_ptr, "SCALING_OUT_%04X" % out_ptr)
                    safe_label_ram(in_ptr,  "SCALING_IN_%04X"  % in_ptr)
                    scaling_count += 1
            i += 1
    finally:
        currentProgram.endTransaction(tx, True)
    print("[8b] OK: %d scaling tables found (%d already covered by XML, skipped)" %
          (scaling_count, xml_skip_scaling))

    def append_scraper_correction(ghidra_a, correction_text):
        """
        If this address carries ANY flagged-status bookmark this script
        applies (REJECTED, CHECK, OVERLAP, OVERLAP-BAD, BAD), the scraper
        independently found a real table here despite that XML entry
        being flagged. Append the corrected data to that SAME plate
        comment (rather than writing a separate scraper plate), rename the
        bookmark to <category>-CORRECTED so it's clear at a glance this
        address has both a documented fault AND a scraper-confirmed fix,
        and return True so the caller skips its normal fresh-plate/
        bookmark path for this address. Returns False if none of those
        categories were present (ordinary scraper path).

        Deliberately generous: ANY flagged tier (CHECK, OVERLAP,
        OVERLAP-BAD, BAD, not just REJECTED) gets full re-derivation --
        those are exactly the addresses where an independent scraper read
        is most useful, since they're already flagged as untrustworthy.
        """
        from ghidra.program.model.listing import BookmarkType, CodeUnit
        correctable_categories = ("H8539F-TABLE-CODE-OVERLAP", "H8539F-TABLE-NO-TABLE", "H8539F-TABLE-SUSPECT",
                                   "H8539F-TABLE-DATA-OVERLAP", "H8539F-TABLE-DATA-OVERLAP-SUSPECT")
        existing = None
        existing_category = None
        for cat in correctable_categories:
            bm = bookmarkMgr.getBookmark(ghidra_a, BookmarkType.NOTE, cat)
            if bm is not None:
                existing = bm
                existing_category = cat
                break
        if existing is None:
            return False
        try:
            cu = listing.getCodeUnitAt(ghidra_a)
            if cu is not None:
                old_text = cu.getComment(CodeUnit.PLATE_COMMENT) or ""
                new_text = old_text + "\n\n[ROM SCRAPER CORRECTION]\n" + correction_text
                cu.setComment(CodeUnit.PLATE_COMMENT, new_text)
        except Exception as e:
            print("  WARNING: could not append scraper correction @ %s: %s" % (ghidra_a, e))
        bookmarkMgr.removeBookmark(existing)
        safe_bookmark(ghidra_a, existing_category + "-CORRECTED",
                      "XML address was flagged (%s), but ROM scraper independently "
                      "confirmed a real table here -- see plate comment for corrected data." %
                      existing_category)
        return True

    # ── Pass 3 & 4: 3D and 2D value tables ───────────────────────
    print("[8c] Scanning for 2D/3D value tables...")
    tbl3d = 0
    tbl2d = 0
    corrected_count = 0
    tx = currentProgram.startTransaction("Value table labels")
    try:
        i = 0
        while i < MUT_OFFSET - 6:
            b = [rom_byte(i + j) for j in range(7)]

            if (header_shape_ok(i, "3D") and
                    not is_likely_code(i)):
                data_len = find_next_header_boundary(i + 7)
                if data_len is None:
                    data_len = find_sentinel_data_len(i + 7)
                if data_len is not None:
                    table_height = b[6] - 1
                    if table_height >= 1:
                        x_ptr = (b[2] << 8) | b[3]
                        y_ptr = (b[4] << 8) | b[5]
                        lbl   = "TABLE_3D_%08X" % (ROM_BASE + i)
                        ghidra_a = addr(ROM_BASE + i)
                        correction_text = (
                            "Corrected 3D Value Table\n"
                            "Header  : 7 bytes\n"
                            "Height  : %d rows\n"
                            "Data    : %d bytes\n"
                            "X axis  : RAM:0x%04X\n"
                            "Y axis  : RAM:0x%04X\n"
                            "Data @  : 0x%08X" %
                            (table_height, data_len, x_ptr, y_ptr, ROM_BASE + i + 7))
                        if append_scraper_correction(ghidra_a, correction_text):
                            corrected_count += 1
                        elif (ROM_BASE + i) in xml_touched:
                            xml_skip_3d += 1
                        else:
                            if symTable.getPrimarySymbol(ghidra_a) is None:
                                safe_label_offset(i, lbl)
                            safe_plate_offset(i,
                                "ROM Scraper: 3D Value Table\n" + correction_text,
                                written_addrs)
                            safe_bookmark(ghidra_a, "H8539F-SCRAPED-TABLE",
                                          "%s (3D)" % lbl)
                        safe_label_ram(x_ptr, "AXIS_X_%04X" % x_ptr)
                        safe_label_ram(y_ptr, "AXIS_Y_%04X" % y_ptr)
                        tbl3d += 1
                        i += 7 + data_len
                        continue

            elif (header_shape_ok(i, "2D") and
                  not is_likely_code(i)):
                data_len = find_next_header_boundary(i + 4)
                if data_len is None:
                    data_len = find_sentinel_data_len(i + 4)
                if data_len is not None:
                    axis_ptr = (b[2] << 8) | b[3]
                    lbl      = "TABLE_2D_%08X" % (ROM_BASE + i)
                    ghidra_a = addr(ROM_BASE + i)
                    correction_text = (
                        "Corrected 2D Value Table\n"
                        "Header  : 4 bytes\n"
                        "Data    : %d bytes\n"
                        "Axis    : RAM:0x%04X\n"
                        "Data @  : 0x%08X" %
                        (data_len, axis_ptr, ROM_BASE + i + 4))
                    if append_scraper_correction(ghidra_a, correction_text):
                        corrected_count += 1
                    elif (ROM_BASE + i) in xml_touched:
                        xml_skip_2d += 1
                    else:
                        if symTable.getPrimarySymbol(ghidra_a) is None:
                            safe_label_offset(i, lbl)
                        safe_plate_offset(i,
                            "ROM Scraper: 2D Value Table\n" + correction_text,
                            written_addrs)
                        safe_bookmark(ghidra_a, "H8539F-SCRAPED-TABLE",
                                      "%s (2D)" % lbl)
                    safe_label_ram(axis_ptr, "AXIS_%04X" % axis_ptr)
                    tbl2d += 1
                    i += 4 + data_len
                    continue

            i += 1
    finally:
        currentProgram.endTransaction(tx, True)
    print("[8c] OK: %d 3D tables, %d 2D tables found (%d total)" %
          (tbl3d, tbl2d, tbl3d + tbl2d))
    print("[8c] %d 3D + %d 2D already covered by XML, skipped re-labeling" %
          (xml_skip_3d, xml_skip_2d))
    if corrected_count:
        print("[8c] %d previously-flagged XML table(s) (REJECTED/CHECK/OVERLAP/"
              "OVERLAP-BAD/BAD) corrected by the scraper -- bookmark renamed to "
              "<category>-CORRECTED, corrected data appended to the original "
              "fault plate comment." % corrected_count)
    return mut_count, scaling_count, tbl3d, tbl2d

# ──────────────────────────────────────────────────────────────────
print("=" * 60)
print("H8/539F XML Table Import + ROM Scraper")
print("=" * 60)
print("Run this AFTER h8539_ecu_master_setup_new3.py (base setup + auto-analysis).")
print("")

if mem.getBlock(addr(ROM_BASE)) is None:
    abort("No memory block at 0x%08X. Run the master setup script first." % ROM_BASE)

# ── Offer to clear a previously-applied XML before importing a new one ──
_prev_path, _prev_ok = get_last_xml_applied()

from ghidra.program.model.listing import BookmarkType as _BookmarkType2
_ARTIFACT_CATEGORIES = ("H8539F-TABLE", "H8539F-SCRAPED-TABLE", "H8539F-TABLE-RESCUED",
                         "H8539F-TABLE-SUSPECT", "H8539F-TABLE-DATA-OVERLAP", "H8539F-TABLE-DATA-OVERLAP-SUSPECT",
                         "H8539F-TABLE-CODE-OVERLAP", "H8539F-TABLE-CODE-OVERLAP-CORRECTED",
                         "H8539F-TABLE-NO-TABLE", "H8539F-TABLE-NO-TABLE-CORRECTED",
                         "H8539F-TABLE-SUSPECT-CORRECTED", "H8539F-TABLE-DATA-OVERLAP-CORRECTED",
                         "H8539F-TABLE-DATA-OVERLAP-SUSPECT-CORRECTED")
_found_artifact_offsets = []
_it2 = bookmarkMgr.getBookmarksIterator(_BookmarkType2.NOTE)
while _it2.hasNext():
    _bm2 = _it2.next()
    if _bm2.getCategory() in _ARTIFACT_CATEGORIES:
        _found_artifact_offsets.append(_bm2.getAddress().getOffset())

if _prev_path or _found_artifact_offsets:
    if not _prev_path:
        _prev_path = "(unknown - no tracked path, but artifacts found on program)"
    _prev_offsets = get_last_xml_touched_addrs()

    if _found_artifact_offsets:
        _prev_offsets = list(set(_prev_offsets) | set(_found_artifact_offsets))

    do_clear_xml = askYesNo("Clear previous XML import?",
        "An XML was already applied in a previous run:\n\n"
        "  File    : %s\n"
        "  ID OK   : %s\n"
        "  Tracked addresses from that run: %d\n\n"
        "If the XML file itself has changed (e.g. duplicate/incorrect\n"
        "table entries were fixed), the old labels/plates/data-typing at\n"
        "those addresses should be cleared BEFORE importing the new XML,\n"
        "otherwise stale entries can be left behind.\n\n"
        "Clear now?" % (_prev_path, _prev_ok, len(_prev_offsets)))
    if do_clear_xml:
        if _prev_offsets:
            do_clear_scraped = askYesNo("Also clear ROM-scraper bookmarks?",
                "Also remove any ROM-scraper artifacts (H8539F-SCRAPED-TABLE\n"
                "bookmarks, and TABLE_2D_*/TABLE_3D_*/SCALING_TABLE_* labels)\n"
                "sitting at these same addresses?\n\n"
                "Use this if the scraper has previously created duplicate\n"
                "bookmarks/labels on top of XML-labeled tables (this happened\n"
                "before the XML-vs-scraper address-unit bug was fixed - if\n"
                "you've never seen duplicates, you can say No here and this\n"
                "step is a no-op).")
            tx_clear = currentProgram.startTransaction("Clear previous XML labels")
            try:
                clear_xml_labels(_prev_offsets, clear_scraped=do_clear_scraped)
            finally:
                currentProgram.endTransaction(tx_clear, True)
            set_last_xml_touched_addrs([])
        else:
            print("  [clear-xml] No tracked addresses from a prior run "
                  "(older run predates address tracking) -- nothing to clear "
                  "automatically. Re-importing will still refresh plates/labels "
                  "for addresses in the new XML, but stale entries only present "
                  "in the OLD XML won't be removed.")
    else:
        print("  [clear-xml] Skipped -- leaving previous XML labels in place.")

# ──────────────────────────────────────────────────────────────────
# STEP 5c — EcuFlash XML table labelling + verification
# ──────────────────────────────────────────────────────────────────

do_xml = askYesNo("Step 5c - XML Table Labels",
    "Apply EcuFlash XML table labels?\n\n"
    "The ROM ID will be verified against the XML first - a mismatched\n"
    "XML is rejected and nothing is touched.\n\n"
    "On a match, each table is cross-checked against real ROM bytes:\n"
    "VERIFIED tables are labeled AND typed as data; SUSPECT tables are\n"
    "reported only; REJECTED tables (addresses that collide with real\n"
    "code) are left untyped and flagged loudly.\n\n"
    "You will be prompted to select the XML file.")

if do_xml:
    prev_path, prev_ok = get_last_xml_applied()
    if prev_path:
        print("[5c] NOTE: XML labels were already applied in a previous run:")
        print("       File    : %s" % prev_path)
        print("       ID OK   : %s" % prev_ok)
        print("       Proceeding will re-verify the ROM ID and refresh labels/plates.")
    xml_file = askFile("Select EcuFlash ROM Definition XML", "Open")
    if xml_file is not None:
        xml_path = xml_file.getAbsolutePath()
        print("[5c] Applying XML labels from: " + xml_path)
        tx = currentProgram.startTransaction("EcuFlash XML labels")
        try:
            _id_verified   = [None]
            _touched       = []
            _touched_ranges = []
            h, s, a, r, v, x, c, nt = apply_xml(xml_path, id_verified=_id_verified, touched_offsets=_touched,
                                                 touched_ranges=_touched_ranges)
            print("[5c] Total -> header-labeled: %d  scalar-labeled: %d  "
                  "plate-updated: %d  out-of-range: %d  suspect: %d  suspect-defect: %d  "
                  "code-overlap: %d  no-table: %d" %
                  (h, s, a, r, v, c, x, nt))
            if x:
                print("[5c] %d table(s) flagged CODE-OVERLAP and left UNTYPED. "
                      "Review the [XML-VERIFY] REJECTED lines above -- these table "
                      "addresses land on real code/instructions, not table data, "
                      "and are very likely wrong in this XML." % x)
            if nt:
                print("[5c] %d table(s) flagged NO-TABLE and left UNTYPED. "
                      "Review the [XML-VERIFY] NO_TABLE lines above -- no header shape "
                      "or sentinel pattern conforming to any known standard (1D/2D/3D) "
                      "was found at these addresses." % nt)
            if c:
                print("[5c] %d table(s) flagged SUSPECT -- a specific header defect (bad "
                      "pointer, identical axes, or an overlap with another table) was "
                      "positively identified. Review the [XML-VERIFY] CHECK/OVERLAP lines "
                      "above and the H8539F-TABLE-DATA-OVERLAP-SUSPECT bookmarks." % c)
            id_ok = bool(_id_verified[0])
            set_last_xml_applied(xml_path, id_ok)
            set_last_xml_touched_addrs(_touched)
        finally:
            currentProgram.endTransaction(tx, True)
    else:
        print("[5c] No XML file selected")
else:
    print("[5c] Skipped XML table labels")

# ──────────────────────────────────────────────────────────────────
# STEP 8 — ROM scraper
# ──────────────────────────────────────────────────────────────────

do_scraper = askYesNo("Step 8 - ROM Scraper",
    "Run the ROM header scraper?\n\n"
    "Detects MUT table, scaling tables, 2D/3D value tables by byte\n"
    "pattern scan. Complements the Step 5c XML labels (if any were\n"
    "applied) and catches tables the XML doesn't cover.\n"
    "(MUT table, scaling tables, 2D/3D value tables by byte pattern)")
if do_scraper:
    run_rom_scraper()
else:
    print("[8] Skipped ROM scraper")

# ──────────────────────────────────────────────────────────────────
# STEP 8d — Page 2 coverage marker
# ──────────────────────────────────────────────────────────────────
PAGE2_START = 0x00020000
page2_symbol_count = 0
sym_iter = symTable.getSymbolIterator(addr(PAGE2_START), True)
for s in sym_iter:
    if s.getAddress().getOffset() > ROM_END:
        break
    page2_symbol_count += 1
print("[8d] Page 2 (0x%08X-0x%08X) has %d labeled symbol(s). The ROM scraper "
      "(Step 8) only scans page 1 (0x0-0x%05X) - this is the known blind spot "
      "from the README. Low counts here likely mean page-2 tables are still "
      "unlabeled." % (PAGE2_START, ROM_END, page2_symbol_count, MUT_OFFSET))


# ──────────────────────────────────────────────────────────────────
print("")
print("=" * 60)
print("H8/539F XML Import + Scraper complete!")
print("You can now run h8539_export_tables_xml.py to write these labels back out.")
print("=" * 60)
