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
#   Step 4  - Read reset vector, create entry function
#   Step 4b - Interrupt vector table: mark as data, create ISR functions,
#             flag duplicate/out-of-range targets, flag ISRs with a
#             non-standard terminating instruction
#   Step 4c - prts/rts function-start scan (report only, fallback/backup
#             for h8539pattern.xml)
#   Step 5  - Decompiler health check       (always runs, gates Step 6)
#   Step 5c - EcuFlash XML table labelling + pre-analysis protection
#              - Prompts for XML file via file browser
#              - Verifies ROM ID matches XML before touching anything -
#                a mismatched/wrong-revision XML is rejected outright
#              - On a match: labels AND types table headers as data
#                immediately (xml_addr - header_size), so they're
#                protected before Step 6 auto-analysis ever runs
#              - 1D scalars: labeled/typed at their raw address
#   Step 5b - Pre-analysis data table protection (STRONGLY RECOMMENDED) -
#             types MUT/scaling/2D/3D table regions as data BEFORE
#             auto-analysis runs, so it can't decode through them as code
#   Step 6  - Auto-analysis
#   Step 6b - Post-analysis undefined-byte gap report (report only)
#   Step 6c - Disassembly error-bookmark triage: classifies "Bad Instruction"
#             bookmarks left after analysis as padding, out-of-bounds flow,
#             data mistakenly swept as code, or a genuine grammar gap, using
#             only generic xref/flow signals (not tied to any known table
#             byte-signature, unlike Step 5b/8 -- covers page 2 too)
#   Step 8 - ROM header scraper (complements Step 5c XML labels, or stands
#            alone if no XML was applied)
#              - MUT table labels
#              - Scaling table detection (6-byte header pattern)
#              - 3D value table detection (0x03 + two RAM ptr words)
#              - 2D value table detection (0x02 + one RAM ptr word)
#              - All heuristics ported from mitsubishi-h8-539-rom-scraper
#   Step 8d - Page 2 label-coverage marker (report only - flags the
#             ROM scraper's known page-2 blind spot)
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
        overlap = False
        if cu is None:
            cu = listing.getCodeUnitContaining(a)
            if cu is not None:
                # 'a' has no code unit of its own - it fell inside a code
                # unit that starts at a DIFFERENT address, meaning this
                # table's declared address overlaps another table's already-
                # typed data (e.g. a 1D scalar address landing inside a 2D
                # table's header bytes). Flag it rather than silently
                # merging two tables' comments at the wrong address - we
                # can't tell which XML entry is stale/correct from here.
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

def type_header_as_data(header_addr, size):
    """
    Type 'size' bytes at header_addr as a byte array, clearing whatever was
    there first. Used to protect XML-declared table headers from
    auto-analysis BEFORE it runs, the same way Step 5b protects
    scraper-detected tables. Safe to call redundantly (idempotent).
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

# ROM signature banner - helps distinguish ROMs across multi-session notes.
# This is NOT the verified EcuFlash ROM ID (that needs an XML - see Step 7);
# it's just a quick raw-byte fingerprint so you can tell ROMs apart at a glance.
_sig_bytes = rom_bytes_at(ROM_BASE, 16)
_sig_hex   = ' '.join('%02X' % b for b in _sig_bytes)
print("[1] ROM signature (first 16 bytes @ 0x%08X): %s" % (ROM_BASE, _sig_hex))

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
# STEP 4b — Interrupt vector table: mark as data + create ISR functions
#
# The vector table's LOCATION (0x10000-0x1013F) and FORMAT (80 entries,
# each a 4-byte CP:PC pointer, same layout as the reset vector read in
# Step 4) are fixed by the H8/539F hardware itself, so this is safe to
# run on any H8/539F ROM. Only the actual handler ADDRESSES stored in
# the table are specific to this ROM's firmware - those are read live,
# not hardcoded.
#
# This fixes two things identified while analysing the RVR 21000011 ROM:
#   1. The vector table was sitting as undefined bytes instead of data
#      (README known limitation).
#   2. Several interrupt handlers (e.g. the ones ending in `rte`) had no
#      byte-pattern signature reliable enough to find via pattern search
#      (unlike `prts`/`prtd`, which got added to h8539pattern.xml) -
#      their entry addresses are already sitting right there in the
#      vector table, so no searching is needed at all.
# ──────────────────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────────
# Step 4a - Register-indirect jump/call site report (jmp @Rn / jsr @Rn)
#
# Report only. These are the classic "computed switch" idiom on this
# compiler: index -> shll.w (word-size table entries) -> mov.w
# @(disp16,Rn),Rn (table load) -> optional sub.w #imm,Rn (bias) ->
# jmp/jsr @Rn. The table base is a REGISTER, not a fixed address, so
# it can't be resolved the way the IVT can - some tables live in RAM
# (populated at runtime, nothing to recover statically) and some may
# be ROM constants. This step just lists every site and prints the
# preceding instructions so each can be reviewed by hand.
# ──────────────────────────────────────────────────────────────────
do_jmp_report = askYesNo("Step 4a - Register-indirect jump/call sites",
    "Scan for jmp @Rn / jsr @Rn (computed switch) sites and print\n"
    "their addresses + preceding instructions to the console?\n"
    "(Report only - does not modify the program)")
if do_jmp_report:
    JMP_JSR_PATTERNS = [
        (chr(0x11) + chr(0xD0 + r), "jmp", r) for r in range(8)
    ] + [
        (chr(0x11) + chr(0xF0 + r), "jsr", r) for r in range(8)
    ]
    listing = currentProgram.getListing()
    hits = []
    for pat, mnem, reg in JMP_JSR_PATTERNS:
        start = currentProgram.getMinAddress()
        while True:
            hit_arr = flat_api.findBytes(start, pat, 1)
            if hit_arr is None or len(hit_arr) == 0:
                break
            hit = hit_arr[0]
            hits.append((hit, mnem, reg))
            try:
                start = hit.add(1)
            except Exception:
                break
    hits.sort(key=lambda h: h[0].getOffset())
    print("=" * 70)
    print("Register-indirect jump/call sites (jmp @Rn / jsr @Rn): %d found" % len(hits))
    print("=" * 70)
    for hit_addr, mnem, reg in hits:
        fn = flat_api.getFunctionContaining(hit_addr)
        fn_name = fn.getName() if fn is not None else "(no function)"
        print("  0x%08X  %s @R%d   in %s" % (hit_addr.getOffset(), mnem, reg, fn_name))
        try:
            ctx_addr = hit_addr
            preceding = []
            for _ in range(6):
                prev = listing.getInstructionBefore(ctx_addr)
                if prev is None:
                    break
                preceding.append(prev)
                ctx_addr = prev.getAddress()
            for instr in reversed(preceding):
                print("      %08X: %s" % (instr.getAddress().getOffset(), instr.toString()))
            target_instr = listing.getInstructionAt(hit_addr)
            if target_instr is not None:
                print("      %08X: %s   <-- indirect jump/call" %
                      (hit_addr.getOffset(), target_instr.toString()))
        except Exception as e:
            print("      (could not print context: %s)" % e)
        print("")
    print("=" * 70)
    print("Review each site by hand. If the table base register is a ROM")
    print("constant (mov #addr,Rn shortly before), the table may be worth")
    print("marking as data manually. If it resolves into RAM, the table is")
    print("populated at runtime and there is nothing static to recover.")
    print("=" * 70)

VECTOR_TABLE_BASE    = 0x00010000
VECTOR_TABLE_ENTRIES = 80          # 0x140 bytes / 4 bytes per entry
VECTOR_ENTRY_SIZE    = 4

do_ivt = askYesNo("Step 4b - Interrupt Vector Table",
    "Mark the interrupt vector table (0x10000-0x1013F) as data and\n"
    "create functions at every unique handler address it points to?\n"
    "(Skip if already done)")
if do_ivt:
    tx = currentProgram.startTransaction("Interrupt vector table")
    try:
        from ghidra.program.model.data import DWordDataType
        seen        = {}
        created     = 0
        target_idxs = {}   # target -> list of vector indices pointing at it
        for idx in range(VECTOR_TABLE_ENTRIES):
            off     = idx * VECTOR_ENTRY_SIZE
            cp_word = flat_api.getShort(addr(VECTOR_TABLE_BASE + off)) & 0xFFFF
            pc_word = flat_api.getShort(addr(VECTOR_TABLE_BASE + off + 2)) & 0xFFFF
            v_cp    = cp_word & 0xFF
            target  = (v_cp << 16) | pc_word
            print("  IVT_%02d @ 0x%08X -> target 0x%08X" %
                  (idx, VECTOR_TABLE_BASE + off, target))

            # Mark this 4-byte slot as data so it stops showing as undefined
            try:
                v_addr = addr(VECTOR_TABLE_BASE + off)
                if listing.getInstructionAt(v_addr) is not None or \
                   listing.getDefinedDataAt(v_addr) is None:
                    listing.clearCodeUnits(v_addr, addr(VECTOR_TABLE_BASE + off + 3), False)
                    listing.createData(v_addr, DWordDataType())
            except Exception as e:
                print("  WARNING: could not mark vector slot %d as data: %s" % (idx, e))
            safe_label_offset(off, "IVT_%02d" % idx)
            safe_plate_offset(off,
                "Interrupt Vector Table Entry\n"
                "Index  : %d\n"
                "Target : 0x%08X" % (idx, target))

            if target == 0:
                continue    # unpopulated entry
            if not in_rom(target):
                print("  WARNING: IVT_%02d target 0x%08X is outside ROM "
                      "(0x%08X-0x%08X) - skipped" % (idx, target, ROM_BASE, ROM_END))
                continue
            target_idxs.setdefault(target, []).append(idx)
            if target in seen:
                continue    # already created a function for this handler
            seen[target] = idx

            t_addr = addr(target)
            if flat_api.getFunctionAt(t_addr) is not None:
                continue    # already a function (e.g. reset vector / entry)
            containing_fn = flat_api.getFunctionContaining(t_addr)
            if containing_fn is not None:
                # Target is INSIDE an existing function's body (e.g. a shared
                # fallthrough/branch target reused as a vector target) - do
                # NOT create a new function here, that would split/fragment
                # the real one and can produce duplicate-named functions.
                print("  NOTE: IVT_%02d target 0x%08X is inside existing "
                      "function %s (0x%08X) - not creating a separate "
                      "function, this is a shared branch target" %
                      (idx, target, containing_fn.getName(),
                       containing_fn.getEntryPoint().getOffset()))
                continue

            try:
                cp_reg = currentProgram.getProgramContext().getRegister("CP")
                if cp_reg:
                    currentProgram.getProgramContext().setValue(
                        cp_reg, t_addr, t_addr, BigInteger.valueOf(v_cp))
                flat_api.disassemble(t_addr)
                fn = flat_api.createFunction(t_addr, None)
                if fn is not None:
                    body_len = fn.getBody().getNumAddresses()
                    if body_len < 2:
                        # Degenerate function - target wasn't a real
                        # instruction boundary (e.g. off-by-one into
                        # another function/table). Undo it rather than
                        # leave a garbage 1-byte function behind.
                        print("  WARNING: IVT_%02d target 0x%08X produced a "
                              "degenerate %d-byte function - removing "
                              "(likely not a real handler entry)" %
                              (idx, target, body_len))
                        flat_api.removeFunctionAt(t_addr)
                    else:
                        created += 1
                        print("    -> created function at 0x%08X (%s)" %
                              (target, fn.getName()))
            except Exception as e:
                print("  WARNING: could not create function at 0x%08X (vector %d): %s" %
                      (target, idx, e))
        # ── Conflict check: which target is the "shared default stub"? ──
        # Heuristic: whichever target has the most vector indices pointing
        # at it is almost certainly the shared default/unhandled-interrupt
        # stub. Any OTHER target hit by 2+ distinct indices is unexpected
        # and worth a human look.
        if target_idxs:
            default_target = max(target_idxs, key=lambda t: len(target_idxs[t]))
        else:
            default_target = None
        for target, idxs in target_idxs.items():
            if target != default_target and len(idxs) > 1:
                print("  WARNING: IVT entries %s all point to 0x%08X - "
                      "duplicate target that is NOT the shared default stub "
                      "(0x%08X, hit by %d entries)" %
                      (idxs, target, default_target, len(target_idxs[default_target])))

        # ── ISR termination check ──
        # Every unique handler this table points to should end in a return
        # or halt instruction. Flag anything that doesn't - it usually means
        # the function boundary was mis-detected (fell through into the next
        # handler) or the ROM does something unusual worth a manual look.
        TERMINATORS = ("rte", "sleep", "rts", "prts", "prtd")
        bad_term = 0
        for target, idx in seen.items():
            t_addr = addr(target)
            fn = flat_api.getFunctionAt(t_addr)
            if fn is None:
                continue    # createFunction failed earlier - already warned
            last_instr = None
            for ins in listing.getInstructions(fn.getBody(), True):
                last_instr = ins
            if last_instr is None:
                print("  WARNING: ISR at 0x%08X (vector %d) has no instructions "
                      "in its body - check disassembly" % (target, idx))
                bad_term += 1
                continue
            mnem = last_instr.getMnemonicString().lower()
            if mnem not in TERMINATORS:
                print("  WARNING: ISR at 0x%08X (vector %d) ends in '%s', not a "
                      "recognised terminator %s" % (target, idx, mnem, TERMINATORS))
                bad_term += 1
        if bad_term:
            print("[4b] %d handler(s) flagged for non-standard termination - see warnings above" %
                  bad_term)

        print("[4b] OK: %d vector slots labeled, %d unique handler functions created" %
              (VECTOR_TABLE_ENTRIES, created))
    finally:
        currentProgram.endTransaction(tx, True)
else:
    print("[4b] Skipped interrupt vector table")

# ──────────────────────────────────────────────────────────────────
# STEP 4c — prts/rts function-start scan (report only)
#
# Automated version of the README's manual "Search Memory for 11 19 / 19"
# technique. This is a SAFE fallback/backup for h8539pattern.xml (which
# should catch most of these during auto-analysis) - it only PRINTS
# candidate addresses rather than creating functions, since a byte scan
# can't tell a real function boundary from a coincidental match inside
# data (e.g. the vector table/padding region already flagged in
# h8539pattern.xml's own comments).
# ──────────────────────────────────────────────────────────────────
do_prts_scan = askYesNo("Step 4c - prts/rts Function-Start Scan",
    "Scan the ROM for 'prts' (0x11 0x19) and 'rts' (0x19) bytes not\n"
    "already followed by a defined function, and print a report of\n"
    "candidate function-start addresses?\n\n"
    "Report only - does not create functions or modify the program.\n"
    "(Run AFTER Step 6 auto-analysis for the most useful results.)")
if do_prts_scan:
    print("[4c] Scanning ROM for prts/rts boundaries...")
    candidates = []
    i = 0
    while i < ROM_SIZE - 1:
        b0 = rom_byte(i)
        b1 = rom_byte(i + 1)
        if b0 == 0x11 and b1 == 0x19:
            next_off = i + 2      # prts, 2 bytes
        elif b0 == 0x19:
            next_off = i + 1      # rts, 1 byte
        else:
            next_off = None
        if next_off is not None and next_off < ROM_SIZE:
            next_addr = addr(ROM_BASE + next_off)
            if (flat_api.getFunctionAt(next_addr) is None and
                    listing.getInstructionAt(next_addr) is None):
                candidates.append(ROM_BASE + next_off)
        i += 1
    if candidates:
        print("[4c] %d candidate function-start address(es) not currently a "
              "function or disassembled instruction:" % len(candidates))
        for c in candidates[:200]:
            print("       0x%08X" % c)
        if len(candidates) > 200:
            print("       ... and %d more (truncated)" % (len(candidates) - 200))
        print("[4c] Review these manually before creating functions - some may be "
              "data (e.g. inside the vector table/padding region) rather than code.")
    else:
        print("[4c] OK: no un-analysed prts/rts boundaries found")
else:
    print("[4c] Skipped prts/rts scan")

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
        id_addr = int(id_addr_str, 16)   # this is already an absolute Ghidra
                                          # address (same convention as every
                                          # table "address" attribute elsewhere
                                          # in this file - do NOT add ROM_BASE)
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

# ──────────────────────────────────────────────────────────────────
# STEP 5c — EcuFlash XML table labelling + pre-analysis data protection
#
# Moved to run BEFORE auto-analysis (Step 6) so that a ROM-ID-VERIFIED
# XML's table headers get typed as data before the analyzer can decode
# through them - the same protection Step 5b already gives the
# byte-pattern scraper's tables, just driven by the real XML definitions
# where one is available and matches this ROM.
#
# The ROM-ID check is the safety net: a wrong/mismatched community XML
# is rejected before it touches a single byte, exactly as before - moving
# this step earlier does not weaken that check, it's the same gate, just
# running sooner.
# ──────────────────────────────────────────────────────────────────

def apply_xml(file_path, visited=None, id_verified=None):
    """
    Parse an EcuFlash XML, verify its ROM ID, then label table headers AND
    type them as data (protecting them from auto-analysis).

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
            print("  [ID] Load the correct XML for this ROM and re-run this step.")
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
            type_header_as_data(target_addr, 2)   # protect before analysis
            meta.append("Address        : 0x%05X  [scalar - no header]" % xml_addr_int)
            plate_text = "\n".join(meta)
            if symTable.getPrimarySymbol(target_addr) is not None:
                already_named += 1
            else:
                safe_label(target_addr, label_name)
                labeled_scalar += 1
            safe_plate(target_addr, plate_text)

        elif ttype in ("2D", "3D") or ttype is None:
            # ── 2D/3D: label + type at header address (xml_addr - header_size) ──
            hdr_size    = HEADER_SIZE.get(ttype, 4)
            header_int  = xml_addr_int - hdr_size
            header_addr = addr(header_int)

            if not in_rom(header_int):
                header_int  = xml_addr_int
                header_addr = addr(header_int)
                meta.append("NOTE: header offset (-%d) outside ROM; "
                             "labeled at data address." % hdr_size)
            else:
                type_header_as_data(header_addr, hdr_size)   # protect before analysis
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


PROGRAM_INFO_CATEGORY = "H8539F Setup Script"
XML_APPLIED_KEY        = "Last XML Applied"
XML_APPLIED_ROMID_KEY  = "Last XML ROM ID Verified"

def get_last_xml_applied():
    opts = currentProgram.getOptions(PROGRAM_INFO_CATEGORY)
    path = opts.getString(XML_APPLIED_KEY, None)
    ok   = opts.getBoolean(XML_APPLIED_ROMID_KEY, False)
    return path, ok

def set_last_xml_applied(path, id_ok):
    opts = currentProgram.getOptions(PROGRAM_INFO_CATEGORY)
    opts.setString(XML_APPLIED_KEY, path)
    opts.setBoolean(XML_APPLIED_ROMID_KEY, id_ok)

do_xml = askYesNo("Step 5c - XML Table Labels + Protection",
    "Apply EcuFlash XML table labels BEFORE auto-analysis?\n\n"
    "The ROM ID will be verified against the XML first - a mismatched\n"
    "XML is rejected and nothing is touched.\n\n"
    "On a match, table headers are labeled AND typed as data immediately,\n"
    "protecting them from auto-analysis the same way Step 5b protects\n"
    "scraper-detected tables.\n\n"
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
            _id_verified = [None]   # captures verify_rom_id's real result
            h, s, a, r = apply_xml(xml_path, id_verified=_id_verified)
            print("[5c] Total -> header-labeled: %d  scalar-labeled: %d  "
                  "plate-updated: %d  out-of-range: %d" % (h, s, a, r))
            id_ok = bool(_id_verified[0])
            set_last_xml_applied(xml_path, id_ok)
        finally:
            currentProgram.endTransaction(tx, True)
    else:
        print("[5c] No XML file selected")
else:
    print("[5c] Skipped XML table labels")

# ──────────────────────────────────────────────────────────────────
# STEP 5b — Pre-analysis data table protection
#
# ROOT CAUSE FIX for auto-analysis decoding into data tables:
# The ROM header scraper (Step 8) only LABELS table regions - it never
# actually types the bytes as Data. Combined with the scraper running
# AFTER auto-analysis (Step 6), this meant Step 6 had zero knowledge that
# MUT/scaling/2D/3D tables existed and would happily disassemble straight
# through them as instructions. Once it decodes garbage inside a table and
# keeps falling through, Ghidra's flow-following can glue huge, unrelated
# stretches of the ROM into one runaway function (observed: a single
# function body spanning 0x20640-0x2FFFF after auto-analysis).
#
# This step runs the SAME byte-pattern detection as Step 8, but only
# TYPES the matched regions as Data (byte/word arrays) - no labels, no
# plate comments (those still happen properly, with EcuFlash names and
# context, at Step 8). Once bytes are typed as Data, the disassembler
# will not walk through them, so auto-analysis can't merge them into code.
# ──────────────────────────────────────────────────────────────────

def protect_data_regions_early():
    from ghidra.program.model.data import ByteDataType, WordDataType, ArrayDataType

    def mark_range_as_data(cpu_offset, length, elem_type, elem_size):
        try:
            a     = addr(ROM_BASE + cpu_offset)
            end_a = addr(ROM_BASE + cpu_offset + length - 1)
            listing.clearCodeUnits(a, end_a, False)
            count = length // elem_size
            if count <= 0:
                return False
            arr = ArrayDataType(elem_type, count, elem_size)
            listing.createData(a, arr)
            print("  DATA 0x%08X - 0x%08X  (%d bytes, %s x%d)" %
                  (ROM_BASE + cpu_offset, ROM_BASE + cpu_offset + length - 1,
                   length, elem_type.getName(), count))
            return True
        except Exception as e:
            print("  WARNING: could not mark 0x%08X-0x%08X as data: %s" %
                  (ROM_BASE + cpu_offset, ROM_BASE + cpu_offset + length - 1, e))
            return False

    def in_range(val, lo, hi):
        return lo <= val <= hi

    marked = 0

    # ── MUT table: fixed offset, always safe to mark upfront ──
    if mark_range_as_data(MUT_OFFSET, MUT_ENTRIES * 2, WordDataType(), 2):
        marked += 1

    # ── Scan for scaling / 2D / 3D tables (same detection as Step 8) ──
    i = 0
    while i < MUT_OFFSET - 6:
        b = [rom_byte(i + j) for j in range(7)]

        # Scaling table (6-byte header)
        if (in_range(b[0], 0xF0, 0xF7) and in_range(b[2], 0xE0, 0xFE) and
                b[4] == 0x00 and in_range(b[5], 0x02, 0x90)):
            bogus = False
            prev = rom_word(i + 6)
            for j in range(0, 6, 2):
                nv = rom_word(i + 6 + j)
                if abs(nv - prev) > 0x1000:
                    bogus = True
                    break
                prev = nv
            if not bogus:
                total_len = 6 + b[5] * 2
                if mark_range_as_data(i, total_len, ByteDataType(), 1):
                    marked += 1
                i += total_len
                continue

        # 3D value table (7-byte header)
        if b[0] == 0x03 and in_range(b[2], 0xE0, 0xFE) and in_range(b[4], 0xE0, 0xFE):
            bogus = False
            prev = rom_word(i + 7)
            for j in range(0, 6, 2):
                nv = rom_word(i + 7 + j)
                if abs(nv - prev) > 0x4000:
                    bogus = True
                    break
                prev = nv
            if not bogus:
                prev = rom_word(i + 7)
                data_len = 2
                for j in range(0, 0x1FF, 2):
                    nv = rom_word(i + 7 + j)
                    if abs(nv - prev) > 0x4000:
                        data_len = j if j > 0 else 2
                        break
                    prev = nv
                if b[6] - 1 >= 1:
                    total_len = 7 + data_len
                    if mark_range_as_data(i, total_len, ByteDataType(), 1):
                        marked += 1
                    i += total_len
                    continue

        # 2D value table (4-byte header)
        if b[0] == 0x02 and in_range(b[2], 0xE0, 0xFE):
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
                total_len = 4 + data_len
                if mark_range_as_data(i, total_len, ByteDataType(), 1):
                    marked += 1
                i += total_len
                continue

        i += 1

    return marked


do_protect = askYesNo("Step 5b - Pre-Analysis Data Protection",
    "Type MUT/scaling/2D/3D table regions as DATA before auto-analysis runs?\n\n"
    "STRONGLY RECOMMENDED. Without this, auto-analysis has no way to know\n"
    "these tables exist and can decode straight through them as code,\n"
    "sometimes merging huge unrelated stretches of the ROM into a single\n"
    "runaway function.\n\n"
    "This only types bytes as data - labels/plate comments still happen\n"
    "properly later at Step 8.")
if do_protect:
    tx = currentProgram.startTransaction("Pre-analysis data protection")
    try:
        n_marked = protect_data_regions_early()
        print("[5b] OK: %d table region(s) typed as data before analysis" % n_marked)
    finally:
        currentProgram.endTransaction(tx, True)
else:
    print("[5b] Skipped pre-analysis data protection - auto-analysis may decode into tables")

# ──────────────────────────────────────────────────────────────────
# STEP 6 — Auto-analysis
# ──────────────────────────────────────────────────────────────────
do_analysis = askYesNo("Step 6 - Auto-Analysis",
    "Run auto-analysis now?\n"
    "(Can take 1-2 minutes. Skip if already analysed.)")
if do_analysis:
    print("[6] Running auto-analysis...")
    fc_before = currentProgram.getFunctionManager().getFunctionCount()

    # analyzeAll() must not be invoked from the Swing/EDT thread
    # (AutoAnalysisManager.scheduleWorker throws UnsupportedOperationException
    # if it is), so push the actual call onto a plain background thread.
    import threading
    _analysis_error = [None]
    def _run_analysis():
        try:
            flat_api.analyzeAll(currentProgram)
        except Exception as e:
            _analysis_error[0] = e
    _t = threading.Thread(target=_run_analysis)
    _t.start()
    _t.join()
    if _analysis_error[0] is not None:
        abort("Auto-analysis failed: %s" % _analysis_error[0])

    fc_after = currentProgram.getFunctionManager().getFunctionCount()
    print("[6] OK: Auto-analysis complete - %d functions found (%+d new since before this step)" %
          (fc_after, fc_after - fc_before))
else:
    print("[6] Skipped auto-analysis")

# ──────────────────────────────────────────────────────────────────
# STEP 6b — Post-analysis gap report
#
# Scans the whole ROM for contiguous runs of undefined bytes and prints
# them, so gaps left by auto-analysis (and not covered by Step 4c's
# candidates) are visible immediately instead of requiring a manual hunt.
# Report only - byte-by-byte over 128KB, so it can take a little while.
# ──────────────────────────────────────────────────────────────────
GAP_MIN_LENGTH = 16   # ignore runs shorter than this (alignment padding etc.)

do_gap_report = askYesNo("Step 6b - Post-Analysis Gap Report",
    "Scan the ROM for contiguous undefined-byte regions (>= %d bytes)\n"
    "left after auto-analysis and print them?\n\n"
    "Report only - does not modify the program. Scans the full 128KB\n"
    "ROM byte-by-byte, so it can take a little while." % GAP_MIN_LENGTH)
if do_gap_report:
    print("[6b] Scanning for undefined-byte gaps...")
    gaps = []
    run_start = None
    for off in range(ROM_SIZE):
        a = addr(ROM_BASE + off)
        is_undef = listing.getUndefinedDataAt(a) is not None
        if is_undef:
            if run_start is None:
                run_start = off
        else:
            if run_start is not None:
                length = off - run_start
                if length >= GAP_MIN_LENGTH:
                    gaps.append((run_start, length))
                run_start = None
    if run_start is not None:
        length = ROM_SIZE - run_start
        if length >= GAP_MIN_LENGTH:
            gaps.append((run_start, length))

    if gaps:
        print("[6b] %d undefined-byte gap(s) >= %d bytes found:" %
              (len(gaps), GAP_MIN_LENGTH))
        for start_off, length in gaps[:200]:
            print("       0x%08X - 0x%08X  (%d bytes)" %
                  (ROM_BASE + start_off, ROM_BASE + start_off + length - 1, length))
        if len(gaps) > 200:
            print("       ... and %d more (truncated)" % (len(gaps) - 200))
    else:
        print("[6b] OK: no undefined-byte gaps >= %d bytes found" % GAP_MIN_LENGTH)
else:
    print("[6b] Skipped gap report")

# ──────────────────────────────────────────────────────────────────
# STEP 6c — Post-analysis error-bookmark triage (universal, any ROM)
#
# Complements Step 5b: 5b prevents auto-analysis from decoding into the
# THREE KNOWN table byte-signatures (scaling/2D/3D), and only scans page 1
# (0x0-MUT_OFFSET). This step runs AFTER analysis and classifies whatever
# "Bad Instruction" bookmarks are left -- including page 2, and including
# table formats that don't match any of the three known signatures --
# using only generic Ghidra signals (xref types, function ownership,
# repeated-byte runs), so nothing here is specific to this ROM or to the
# three known EcuFlash table shapes.
#
# For each error bookmark:
#   1. Repeated-byte run (unprogrammed flash padding)    -> mark as data
#   2. Flow target outside defined memory                 -> flag, don't chase
#   3. No real flow (call/jump/branch) xref, and either
#      a data (read/write) xref or no owning function     -> mark as data
#   4. Otherwise (real flow context, still won't decode)  -> flag for manual/
#      Claude review; NOTHING is auto-written for this case, since it may
#      be a genuine SLEIGH grammar gap (verify against ana.cpp before
#      writing a constructor).
# ──────────────────────────────────────────────────────────────────
REPEAT_RUN_THRESHOLD = 8   # bytes

def is_repeated_byte_run(start_addr, min_run):
    try:
        first = flat_api.getByte(start_addr) & 0xFF
        count = 1
        a = start_addr.add(1)
        while count < min_run + 8 and mem.contains(a) and (flat_api.getByte(a) & 0xFF) == first:
            count += 1
            a = a.add(1)
        return count >= min_run
    except Exception:
        return False

def has_flow_ref_at(a):
    refMgr = currentProgram.getReferenceManager()
    for r in refMgr.getReferencesTo(a):
        if r.getReferenceType().isFlow():
            return True
    return False

def has_data_ref_at(a):
    from ghidra.program.model.symbol import RefType
    refMgr = currentProgram.getReferenceManager()
    for r in refMgr.getReferencesTo(a):
        rt = r.getReferenceType()
        if rt.isData() or rt == RefType.READ or rt == RefType.WRITE or rt == RefType.READ_WRITE:
            return True
    return False

def triage_disassembly_errors():
    from ghidra.program.model.listing import BookmarkType
    bm = currentProgram.getBookmarkManager()
    error_addrs = [b.getAddress() for b in bm.getBookmarksIterator(BookmarkType.ERROR)]
    print("[6c] Found %d disassembly-error bookmark(s)." % len(error_addrs))

    padding_count = 0
    oob_count     = 0
    data_count    = 0
    gap_count     = 0

    for a in error_addrs:
        if is_repeated_byte_run(a, REPEAT_RUN_THRESHOLD):
            try:
                listing.clearCodeUnits(a, a, False)
            except Exception:
                pass
            bm.setBookmark(a, BookmarkType.NOTE, "H8539F-AUTO-DATA",
                "AUTO: repeated-byte padding run")
            padding_count += 1
            print("  0x%08X -> padding (repeated-byte run)" % a.getOffset())
            continue

        if not mem.contains(a):
            bm.setBookmark(a, BookmarkType.NOTE, "H8539F-OOB",
                "AUTO: flow target outside defined memory - not chased")
            oob_count += 1
            print("  0x%08X -> out-of-bounds flow target" % a.getOffset())
            continue

        has_flow = has_flow_ref_at(a)
        if not has_flow:
            prev_instr = listing.getInstructionBefore(a)
            if prev_instr is not None and has_flow_ref_at(prev_instr.getMinAddress()):
                has_flow = True

        has_data = has_data_ref_at(a)
        owner    = listing.getFunctionContaining(a)

        if not has_flow and (has_data or owner is None):
            try:
                listing.clearCodeUnits(a, a, False)
            except Exception:
                pass
            bm.setBookmark(a, BookmarkType.NOTE, "H8539F-AUTO-DATA",
                "AUTO: no flow xrefs, data-pattern (dataRef=%s, owner=%s)" %
                (has_data, owner is not None))
            data_count += 1
            print("  0x%08X -> data pattern (dataRef=%s, owner=%s)" %
                  (a.getOffset(), has_data, owner is not None))
            continue

        bm.setBookmark(a, BookmarkType.NOTE, "H8539F-GAP",
            "REVIEW: real flow context but constructor failed to resolve - "
            "check against ana.cpp before writing a fix")
        gap_count += 1
        print("  0x%08X -> GENUINE GAP - needs manual/Claude review" % a.getOffset())

    print("[6c] Padding runs reclassified as data: %d" % padding_count)
    print("[6c] Out-of-bounds flow targets flagged: %d" % oob_count)
    print("[6c] Data-pattern regions reclassified:  %d" % data_count)
    print("[6c] Genuine grammar-gap candidates:     %d" % gap_count)
    print("[6c] Gap candidates bookmarked 'H8539F-GAP' for manual review - "
          "nothing auto-written for these.")
    return padding_count, oob_count, data_count, gap_count


do_triage = askYesNo("Step 6c - Disassembly Error Triage",
    "Classify every disassembly-error bookmark left after auto-analysis?\n\n"
    "Universal, xref-based triage (NOT limited to the three known EcuFlash\n"
    "table byte-signatures Step 5b/8 look for, and covers page 2 too):\n"
    "  - repeated-byte padding runs          -> marked as data\n"
    "  - flow that walked off defined memory -> flagged, not chased\n"
    "  - regions with only read/write xrefs\n"
    "    and no owning function              -> marked as data\n"
    "  - everything else (real flow context,\n"
    "    still won't decode)                 -> bookmarked 'H8539F-GAP'\n"
    "    for manual/Claude review - nothing is auto-written for these,\n"
    "    since they may be genuine grammar gaps.\n\n"
    "Recommended to re-run auto-analysis afterward if any regions were\n"
    "reclassified as data.")
if do_triage:
    tx = currentProgram.startTransaction("Disassembly error triage")
    try:
        triage_disassembly_errors()
    finally:
        currentProgram.endTransaction(tx, True)
else:
    print("[6c] Skipped disassembly error triage")

print("")

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
# Run Step 8
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
#
# Not a fix - the ROM scraper (Step 8) only scans 0x0..MUT_OFFSET, i.e.
# page 1 (README known limitation: embedded tables inline in page 2 code,
# 0x20000+, aren't reached). This just reports how much of page 2 has any
# labels at all, as a quick sanity check / reminder that page 2 needs a
# manual pass or a future scraper extension.
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
print("H8/539F Master Setup complete!")
print("=" * 60)
