# H8/539F ECU - Master Setup Script
# @category MitsubishiECU
#
# Single master script for H8/539F ROM import and annotation.
# Run IMMEDIATELY after import, BEFORE clicking "Analyze".
#
# STEPS (each individually toggleable via prompts):
#
#   Step 1 - Validate base address + ROM ID check  (always runs)
#   Step 2 - Create on-chip RAM block       (0xEE80-0xFFFF)
#   Step 3 - Set CP/DP/TP context registers over ROM pages
#   Step 4 - Read reset vector, create entry function
#   Step 5 - Decompiler health check        (always runs, gates Step 6)
#   Step 6 - Auto-analysis
#   Step 7 - EcuFlash XML table labelling
#              - Prompts for XML file via file browser
#              - Verifies ROM ID matches XML before labelling
#              - Labels the TABLE HEADER address (xml_addr - header_size)
#                so labels align with code xrefs, not raw data bytes
#              - 1D scalars: labeled at their raw address (no header offset)
#              - If no XML chosen: offers ROM scraper as fallback
#   Step 8 - ROM header scraper (optional fallback or complement to XML)
#              - MUT table labels
#              - Scaling table detection (6-byte header pattern)
#              - 3D value table detection (0x03 + two RAM ptr words)
#              - 2D value table detection (0x02 + one RAM ptr word)
#              - All heuristics ported from mitsubishi-h8-539-rom-scraper
#
# IMPORT SETTINGS REQUIRED:
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
from ghidra.app.decompiler import DecompInterface, DecompileOptions
import os, xml.etree.ElementTree as ET

flat_api = FlatProgramAPI(currentProgram)
mem      = currentProgram.getMemory()
space    = currentProgram.getAddressFactory().getDefaultAddressSpace()
listing  = currentProgram.getListing()
symTable = currentProgram.getSymbolTable()

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

def safe_plate(a, text):
    """
    Append-only plate comment at Ghidra address 'a'.
    Never duplicates text, never clobbers existing comments.
    """
    try:
        from ghidra.program.model.listing import CodeUnit
        cu = listing.getCodeUnitAt(a)
        if cu is None:
            cu = listing.getCodeUnitContaining(a)
        if cu is None:
            return
        existing = cu.getComment(CodeUnit.PLATE_COMMENT)
        if existing and text in existing:
            return
        new_text = (existing + "\n" + text) if existing else text
        cu.setComment(CodeUnit.PLATE_COMMENT, new_text)
    except Exception as e:
        print("  WARNING plate comment @ %s: %s" % (a, e))

def safe_plate_offset(cpu_offset, text):
    """safe_plate variant taking a CPU-page-relative ROM offset."""
    safe_plate(addr(ROM_BASE + cpu_offset), text)

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

# ──────────────────────────────────────────────────────────────────
print("=" * 60)
print("H8/539F ECU Master Setup")
print("=" * 60)

# ──────────────────────────────────────────────────────────────────
# STEP 1 — Validate base address (mandatory)
# ──────────────────────────────────────────────────────────────────
if mem.getBlock(addr(ROM_BASE)) is None:
    abort("No memory block at 0x%08X.\n"
          "Re-import ROM as Raw Binary with base address 0x%08X." %
          (ROM_BASE, ROM_BASE))
print("[1] OK: ROM block found at 0x%08X" % ROM_BASE)

# ──────────────────────────────────────────────────────────────────
# STEP 2 — On-chip RAM block
# ──────────────────────────────────────────────────────────────────
do_ram = askYesNo("Step 2 - RAM Block",
    "Create on-chip RAM block (0xEE80-0xFFFF)?\n"
    "(Skip if already exists or re-running)")
if do_ram:
    tx = currentProgram.startTransaction("Create RAM block")
    try:
        ram_start = addr(0x0000EE80)
        if mem.getBlock(ram_start) is not None:
            print("[2] OK: RAM block already exists - skipped")
        else:
            blk = mem.createUninitializedBlock("RAM", ram_start, 0x1180, False)
            blk.setRead(True); blk.setWrite(True)
            blk.setExecute(False); blk.setVolatile(True)
            print("[2] OK: Created RAM block 0x0000EE80-0x0000FFFF")
    finally:
        currentProgram.endTransaction(tx, True)
else:
    print("[2] Skipped RAM block creation")

# ──────────────────────────────────────────────────────────────────
# STEP 3 — Context registers
# ──────────────────────────────────────────────────────────────────
do_ctx = askYesNo("Step 3 - Context Registers",
    "Set CP/DP/TP context registers over ROM pages?\n"
    "(Required for correct H8/539F disassembly)")
if do_ctx:
    tx = currentProgram.startTransaction("Set context registers")
    try:
        ctx    = currentProgram.getProgramContext()
        cp_reg = ctx.getRegister("CP")
        dp_reg = ctx.getRegister("DP")
        tp_reg = ctx.getRegister("TP")
        if cp_reg:
            ctx.setValue(cp_reg, addr(0x00010000), addr(0x0001FFFF), BigInteger.valueOf(1))
            ctx.setValue(cp_reg, addr(0x00020000), addr(0x0002FFFF), BigInteger.valueOf(2))
            print("[3] OK: CP=1 over page 1, CP=2 over page 2")
        if dp_reg:
            ctx.setValue(dp_reg, addr(0x00010000), addr(0x0002FFFF), BigInteger.valueOf(1))
            print("[3] OK: DP=1 over full ROM")
        if tp_reg:
            ctx.setValue(tp_reg, addr(0x00010000), addr(0x0002FFFF), BigInteger.valueOf(0))
            print("[3] OK: TP=0 over full ROM")
    finally:
        currentProgram.endTransaction(tx, True)
else:
    print("[3] Skipped context registers")

# ──────────────────────────────────────────────────────────────────
# STEP 4 — Reset vector -> entry function
# ──────────────────────────────────────────────────────────────────
do_entry = askYesNo("Step 4 - Entry Function",
    "Read reset vector and create entry function?\n"
    "(Skip if already done)")
if do_entry:
    tx = currentProgram.startTransaction("Create entry function")
    try:
        cp_word    = flat_api.getShort(addr(ROM_BASE)) & 0xFFFF
        pc_word    = flat_api.getShort(addr(ROM_BASE + 2)) & 0xFFFF
        entry_cp   = cp_word & 0xFF
        entry_flat = (entry_cp << 16) | pc_word
        print("[4] Reset vector: CP=0x%02x PC=0x%04x -> 0x%08x" %
              (entry_cp, pc_word, entry_flat))
        if entry_cp == 0:
            abort("Reset vector CP=0 - ROM is at wrong base address.")
        ep     = addr(entry_flat)
        cp_reg = currentProgram.getProgramContext().getRegister("CP")
        if cp_reg:
            currentProgram.getProgramContext().setValue(
                cp_reg, ep, ep, BigInteger.valueOf(entry_cp))
        flat_api.disassemble(ep)
        flat_api.createFunction(ep, "entry")
        print("[4] OK: entry function created at 0x%08x" % entry_flat)
    finally:
        currentProgram.endTransaction(tx, True)
else:
    print("[4] Skipped entry function")

# ──────────────────────────────────────────────────────────────────
# STEP 5 — Decompiler health check (mandatory, gates Step 6)
# ──────────────────────────────────────────────────────────────────
print("")
print("[5] Checking decompiler...")
ifc  = DecompInterface()
opts = DecompileOptions()
opts.grabFromProgram(currentProgram)
ifc.setOptions(opts)
ok = ifc.openProgram(currentProgram)
ifc.dispose()
if not ok:
    abort("Decompiler openProgram() FAILED.\n"
          "Check h8.cspec, do a full Ghidra restart, delete and re-import the ROM.")
print("[5] OK: Decompiler is healthy")

# ──────────────────────────────────────────────────────────────────
# STEP 6 — Auto-analysis
# ──────────────────────────────────────────────────────────────────
do_analysis = askYesNo("Step 6 - Auto-Analysis",
    "Run auto-analysis now?\n"
    "(Can take 1-2 minutes. Skip if already analysed.)")
if do_analysis:
    print("[6] Running auto-analysis...")
    flat_api.analyzeAll(currentProgram)
    fc = currentProgram.getFunctionManager().getFunctionCount()
    print("[6] OK: Auto-analysis complete - %d functions found" % fc)
else:
    print("[6] Skipped auto-analysis")

print("")

# ──────────────────────────────────────────────────────────────────
# ROM ID verification helper
# ──────────────────────────────────────────────────────────────────

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
        id_addr = int(id_addr_str, 16)   # this is a ROM file offset (no base added)
    except ValueError:
        return True, "Could not parse internalidaddress '%s' - skipping" % id_addr_str

    # id_hex_str is the expected hex string e.g. "21000011"
    # Strip spaces, convert to bytes
    id_hex_clean = id_hex_str.replace(' ', '')
    if len(id_hex_clean) % 2 != 0:
        id_hex_clean = '0' + id_hex_clean
    try:
        expected_bytes = [int(id_hex_clean[i:i+2], 16)
                          for i in range(0, len(id_hex_clean), 2)]
    except ValueError:
        return True, "Could not parse internalidhex '%s' - skipping" % id_hex_str

    # Read actual ROM bytes at the ID address
    # id_addr is a file offset; Ghidra address = ROM_BASE + id_addr
    ghidra_id_addr = ROM_BASE + id_addr
    actual_bytes = rom_bytes_at(ghidra_id_addr, len(expected_bytes))

    expected_hex = ' '.join('%02X' % b for b in expected_bytes)
    actual_hex   = ' '.join('%02X' % b for b in actual_bytes)

    detail = ("XML ID  : %s (at file offset 0x%05X / Ghidra 0x%08X)\n"
              "Expected: %s\n"
              "Actual  : %s" % (xml_id_str, id_addr, ghidra_id_addr,
                                expected_hex, actual_hex))

    if expected_bytes == actual_bytes:
        return True, detail
    else:
        return False, detail

# ──────────────────────────────────────────────────────────────────
# STEP 7 — EcuFlash XML table labelling
# ──────────────────────────────────────────────────────────────────

def apply_xml(file_path, visited=None, id_verified=None):
    """
    Parse an EcuFlash XML and label table headers in Ghidra.

    ROM ID VERIFICATION:
      Before labelling, reads <internalidaddress> + <internalidhex> from the
      XML and compares against actual ROM bytes. On mismatch: prints a clear
      warning and skips labelling for that file (does NOT abort the script).
      id_verified is a mutable list [True/False/None] shared across the
      include chain so the check only runs once at the top-level file.

    ADDRESS STRATEGY:
      2D/3D tables: label at (xml_addr - header_size) = true header address.
      1D scalars  : label at xml_addr directly (no ROM header exists).

    DEDUPLICATION:
      Existing labels survive re-runs - only plate comments are updated.

    INCLUDES:
      <include> entries are followed recursively (cycle-guarded).
    """
    if visited is None:
        visited = set()
    if id_verified is None:
        id_verified = [None]   # None=unchecked, True=ok, False=failed

    real_path = os.path.realpath(file_path)
    if real_path in visited:
        return (0, 0, 0, 0)
    visited.add(real_path)

    if not os.path.exists(file_path):
        print("  WARNING: XML not found: " + file_path)
        return (0, 0, 0, 0)

    try:
        root = ET.parse(file_path).getroot()
    except Exception as e:
        print("  WARNING: Could not parse XML: " + str(e))
        return (0, 0, 0, 0)

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
            print("  [ID] Load the correct XML for this ROM and re-run Step 7.")
            return (0, 0, 0, 0)

    # If a parent file already failed ID check, propagate the skip
    if id_verified[0] is False:
        return (0, 0, 0, 0)

    base_dir = os.path.dirname(file_path)

    # Follow <include> references first (base definitions before overrides)
    inc_h = inc_s = inc_a = inc_r = 0
    for inc in root.findall('include'):
        inc_name = (inc.text or "").strip()
        if not inc_name:
            continue
        if not inc_name.endswith('.xml'):
            inc_name += '.xml'
        inc_path = os.path.join(base_dir, inc_name)
        ih, is_, ia, ir = apply_xml(inc_path, visited, id_verified)
        inc_h += ih; inc_s += is_; inc_a += ia; inc_r += ir

    labeled_header = 0
    labeled_scalar = 0
    already_named  = 0
    skipped_range  = 0

    for table in root.findall('table'):
        name     = table.get('name')
        addr_str = table.get('address')
        ttype    = table.get('type')
        category = table.get('category') or ""
        scaling  = table.get('scaling') or ""
        swapxy   = table.get('swapxy') or ""
        flipy    = table.get('flipy') or ""
        level    = table.get('level') or ""

        # Skip axis sub-tables
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
            # ── 1D scalar: no ROM header, label at raw XML address ──
            target_addr = addr(xml_addr_int)
            meta.append("Address        : 0x%05X  [scalar - no header]" % xml_addr_int)
            plate_text = "\n".join(meta)
            if symTable.getPrimarySymbol(target_addr) is not None:
                already_named += 1
            else:
                safe_label(target_addr, label_name)
                labeled_scalar += 1
            safe_plate(target_addr, plate_text)

        elif ttype in ("2D", "3D") or ttype is None:
            # ── 2D/3D: label at header address (xml_addr - header_size) ──
            hdr_size    = HEADER_SIZE.get(ttype, 4)
            header_int  = xml_addr_int - hdr_size
            header_addr = addr(header_int)

            if not in_rom(header_int):
                header_int  = xml_addr_int
                header_addr = addr(header_int)
                meta.append("NOTE: header offset (-%d) outside ROM; "
                             "labeled at data address." % hdr_size)
            else:
                meta.append("Header address : 0x%05X  (code xrefs point here)" % header_int)
                meta.append("Data address   : 0x%05X  (XML address, %d bytes in)" %
                             (xml_addr_int, hdr_size))

            plate_text = "\n".join(meta)
            if symTable.getPrimarySymbol(header_addr) is not None:
                already_named += 1
            else:
                safe_label(header_addr, label_name)
                labeled_header += 1
            safe_plate(header_addr, plate_text)

        else:
            # Unknown type
            target_addr = addr(xml_addr_int)
            meta.append("Address        : 0x%05X" % xml_addr_int)
            meta.append("NOTE: unrecognised type '%s'" % ttype)
            plate_text = "\n".join(meta)
            if symTable.getPrimarySymbol(target_addr) is None:
                safe_label(target_addr, label_name)
            safe_plate(target_addr, plate_text)

    total_h = labeled_header + inc_h
    total_s = labeled_scalar + inc_s
    total_a = already_named  + inc_a
    total_r = skipped_range  + inc_r

    print("  %s -> header-labeled: %d  scalar-labeled: %d  "
          "plate-updated: %d  out-of-range: %d" %
          (os.path.basename(file_path),
           labeled_header, labeled_scalar, already_named, skipped_range))

    return (total_h, total_s, total_a, total_r)


# ──────────────────────────────────────────────────────────────────
# STEP 8 — ROM scraper
# Ported from mitsubishi-h8-539-rom-scraper-main/index.js
# Detects: MUT table, scaling tables, 3D value tables, 2D value tables
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
                "Target : RAM:0x%04X" % (i, i, val))
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
                # Sanity: first 3 data words
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
                    safe_label_offset(i, lbl)
                    safe_plate_offset(i,
                        "Scaling Table\n"
                        "Out ptr : RAM:0x%04X\n"
                        "In ptr  : RAM:0x%04X\n"
                        "Entries : %d (%d bytes)" %
                        (out_ptr, in_ptr, count, count * 2))
                    safe_label_ram(out_ptr, "SCALING_OUT_%04X" % out_ptr)
                    safe_label_ram(in_ptr,  "SCALING_IN_%04X"  % in_ptr)
                    scaling_count += 1
            i += 1
    finally:
        currentProgram.endTransaction(tx, True)
    print("[8b] OK: %d scaling tables found" % scaling_count)

    # ── Pass 3 & 4: 3D and 2D value tables ───────────────────────
    print("[8c] Scanning for 2D/3D value tables...")
    tbl3d = 0
    tbl2d = 0
    tx = currentProgram.startTransaction("Value table labels")
    try:
        i = 0
        while i < MUT_OFFSET - 6:
            b = [rom_byte(i + j) for j in range(7)]

            # ── 3D ───────────────────────────────────────────────
            if (b[0] == 0x03 and
                    in_range(b[2], 0xE0, 0xFE) and
                    in_range(b[4], 0xE0, 0xFE)):
                bogus = False
                prev = rom_word(i + 7)
                for j in range(0, 6, 2):
                    nv = rom_word(i + 7 + j)
                    if abs(nv - prev) > 0x4000:
                        bogus = True
                        break
                    prev = nv
                if not bogus:
                    # Measure data length
                    prev = rom_word(i + 7)
                    data_len = 2
                    for j in range(0, 0x1FF, 2):
                        nv = rom_word(i + 7 + j)
                        if abs(nv - prev) > 0x4000:
                            data_len = j if j > 0 else 2
                            break
                        prev = nv
                    table_height = b[6] - 1
                    if table_height >= 1:
                        x_ptr = (b[2] << 8) | b[3]
                        y_ptr = (b[4] << 8) | b[5]
                        lbl   = "TABLE_3D_%08X" % (ROM_BASE + i)
                        ghidra_a = addr(ROM_BASE + i)
                        if symTable.getPrimarySymbol(ghidra_a) is None:
                            safe_label_offset(i, lbl)
                        safe_plate_offset(i,
                            "ROM Scraper: 3D Value Table\n"
                            "Header  : 7 bytes\n"
                            "Height  : %d rows\n"
                            "Data    : %d bytes\n"
                            "X axis  : RAM:0x%04X\n"
                            "Y axis  : RAM:0x%04X\n"
                            "Data @  : 0x%08X" %
                            (table_height, data_len,
                             x_ptr, y_ptr, ROM_BASE + i + 7))
                        safe_label_ram(x_ptr, "AXIS_X_%04X" % x_ptr)
                        safe_label_ram(y_ptr, "AXIS_Y_%04X" % y_ptr)
                        tbl3d += 1
                        i += 7 + data_len
                        continue

            # ── 2D ───────────────────────────────────────────────
            elif (b[0] == 0x02 and
                  in_range(b[2], 0xE0, 0xFE)):
                bogus = False
                prev = rom_word(i + 4)
                for j in range(0, 6, 2):
                    nv = rom_word(i + 4 + j)
                    if abs(nv - prev) > 0x4000:
                        bogus = True
                        break
                    prev = nv
                if not bogus:
                    prev = rom_word(i + 4)
                    data_len = 2
                    for j in range(0, 0x1FF, 2):
                        nv = rom_word(i + 4 + j)
                        if abs(nv - prev) > 0x4000:
                            data_len = j if j > 0 else 2
                            break
                        prev = nv
                    axis_ptr = (b[2] << 8) | b[3]
                    lbl      = "TABLE_2D_%08X" % (ROM_BASE + i)
                    ghidra_a = addr(ROM_BASE + i)
                    if symTable.getPrimarySymbol(ghidra_a) is None:
                        safe_label_offset(i, lbl)
                    safe_plate_offset(i,
                        "ROM Scraper: 2D Value Table\n"
                        "Header  : 4 bytes\n"
                        "Data    : %d bytes\n"
                        "Axis    : RAM:0x%04X\n"
                        "Data @  : 0x%08X" %
                        (data_len, axis_ptr, ROM_BASE + i + 4))
                    safe_label_ram(axis_ptr, "AXIS_%04X" % axis_ptr)
                    tbl2d += 1
                    i += 4 + data_len
                    continue

            i += 1
    finally:
        currentProgram.endTransaction(tx, True)
    print("[8c] OK: %d 3D tables, %d 2D tables found (%d total)" %
          (tbl3d, tbl2d, tbl3d + tbl2d))
    return mut_count, scaling_count, tbl3d, tbl2d


# ──────────────────────────────────────────────────────────────────
# Run Steps 7 and 8
# ──────────────────────────────────────────────────────────────────

do_xml = askYesNo("Step 7 - XML Table Labels",
    "Apply EcuFlash XML table labels?\n\n"
    "The ROM ID will be verified against the XML before labelling.\n"
    "Tables are labeled at their HEADER address\n"
    "(xml_addr - 4 for 2D, xml_addr - 7 for 3D).\n\n"
    "You will be prompted to select the XML file.")

if do_xml:
    xml_file = askFile("Select EcuFlash ROM Definition XML", "Open")
    if xml_file is not None:
        xml_path = xml_file.getAbsolutePath()
        print("[7] Applying XML labels from: " + xml_path)
        tx = currentProgram.startTransaction("EcuFlash XML labels")
        try:
            h, s, a, r = apply_xml(xml_path)
            print("[7] Total -> header-labeled: %d  scalar-labeled: %d  "
                  "plate-updated: %d  out-of-range: %d" % (h, s, a, r))
        finally:
            currentProgram.endTransaction(tx, True)

        do_scraper_also = askYesNo("Step 8 - ROM Scraper (Optional)",
            "Also run the ROM header scraper?\n\n"
            "Detects MUT table, scaling tables, 2D/3D value tables\n"
            "by byte pattern scan. Complements XML labels and catches\n"
            "tables the XML does not cover.")
        if do_scraper_also:
            run_rom_scraper()
        else:
            print("[8] Skipped ROM scraper")
    else:
        print("[7] No XML file selected")
        do_scraper_fallback = askYesNo("Step 8 - ROM Scraper",
            "No XML selected.\n\n"
            "Run the ROM scraper instead?\n"
            "(MUT table, scaling tables, 2D/3D value tables by byte pattern)")
        if do_scraper_fallback:
            run_rom_scraper()
        else:
            print("[8] Skipped ROM scraper")
else:
    print("[7] Skipped XML table labels")
    do_scraper_standalone = askYesNo("Step 8 - ROM Scraper",
        "Run the ROM scraper?\n"
        "(MUT table, scaling tables, 2D/3D value tables by byte pattern)")
    if do_scraper_standalone:
        run_rom_scraper()
    else:
        print("[8] Skipped ROM scraper")

# ──────────────────────────────────────────────────────────────────
print("")
print("=" * 60)
print("H8/539F Master Setup complete!")
print("=" * 60)
