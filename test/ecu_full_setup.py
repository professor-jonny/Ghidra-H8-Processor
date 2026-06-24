# H8/539F ECU - Full Auto Setup
# @category MitsubishiECU
#
# Run this IMMEDIATELY after import, BEFORE clicking "Analyze".
# It will:
#   1. Validate the import base address
#   2. Create the on-chip RAM block
#   3. Set CP/DP/TP context registers over the full ROM
#   4. Read the reset vector and create the entry function
#   5. Test the decompiler - aborts with clear error if it fails
#   6. Run auto-analysis only if the decompiler is healthy
#   7. Apply ECU table labels from EcuFlash XML (if file exists)
#
# Import settings required:
#   Format:       Raw Binary
#   Language:     H8:BE:32:H8539F
#   Base Address: 0x00010000
#
# Edit XML_PATH below to point at your EcuFlash ROM definition XML.
# Set XML_PATH = "" to skip table labelling.

from java.math import BigInteger
from ghidra.program.flatapi import FlatProgramAPI
from ghidra.app.decompiler import DecompInterface, DecompileOptions
import os, xml.etree.ElementTree as ET

XML_PATH = r"C:\Users\j.brophy.CORKILLSYSTEMS\Downloads\21000011_1997-2001_RVR_X3_Mt__4g63t_.xml"

flat_api = FlatProgramAPI(currentProgram)
mem      = currentProgram.getMemory()
space    = currentProgram.getAddressFactory().getDefaultAddressSpace()

def addr(offset):
    return space.getAddress(offset & 0xFFFFFFFF)

def abort(msg):
    print("ABORT: " + msg)
    raise Exception(msg)

print("=" * 60)
print("H8/539F ECU Auto Setup")
print("=" * 60)

# ------------------------------------------------------------------
# 1. Validate base address
# ------------------------------------------------------------------
if mem.getBlock(addr(0x00010000)) is None:
    abort("No memory block at 0x00010000.\n"
          "Re-import ROM as Raw Binary with base address 0x00010000.")
print("OK: ROM block found at 0x00010000")

# ------------------------------------------------------------------
# 2. On-chip RAM block (0xEE80-0xFFFF)
# ------------------------------------------------------------------
tx = currentProgram.startTransaction("Create RAM block")
try:
    ram_start = addr(0x0000EE80)
    if mem.getBlock(ram_start) is not None:
        print("OK: RAM block already exists")
    else:
        blk = mem.createUninitializedBlock("RAM", ram_start, 0x1180, False)
        blk.setRead(True); blk.setWrite(True)
        blk.setExecute(False); blk.setVolatile(True)
        print("OK: Created RAM block 0x0000EE80-0x0000FFFF")
finally:
    currentProgram.endTransaction(tx, True)

# ------------------------------------------------------------------
# 3. Context registers (CP/DP/TP) over both ROM pages
# ------------------------------------------------------------------
tx = currentProgram.startTransaction("Set context registers")
try:
    ctx    = currentProgram.getProgramContext()
    cp_reg = ctx.getRegister("CP")
    dp_reg = ctx.getRegister("DP")
    tp_reg = ctx.getRegister("TP")
    if cp_reg:
        ctx.setValue(cp_reg, addr(0x00010000), addr(0x0001FFFF), BigInteger.valueOf(1))
        ctx.setValue(cp_reg, addr(0x00020000), addr(0x0002FFFF), BigInteger.valueOf(2))
        print("OK: CP=1 over page 1, CP=2 over page 2")
    if dp_reg:
        ctx.setValue(dp_reg, addr(0x00010000), addr(0x0002FFFF), BigInteger.valueOf(1))
        print("OK: DP=1 over full ROM")
    if tp_reg:
        ctx.setValue(tp_reg, addr(0x00010000), addr(0x0002FFFF), BigInteger.valueOf(0))
        print("OK: TP=0 over full ROM")
finally:
    currentProgram.endTransaction(tx, True)

# ------------------------------------------------------------------
# 4. Reset vector -> entry function
# ------------------------------------------------------------------
tx = currentProgram.startTransaction("Create entry function")
try:
    cp_word    = flat_api.getShort(addr(0x00010000)) & 0xFFFF
    pc_word    = flat_api.getShort(addr(0x00010002)) & 0xFFFF
    entry_cp   = cp_word & 0xFF
    entry_flat = (entry_cp << 16) | pc_word
    print("Reset vector: CP=0x%02x PC=0x%04x -> ram:0x%08x" % (entry_cp, pc_word, entry_flat))
    if entry_cp == 0:
        abort("Reset vector CP=0 - ROM is at wrong base address.\n"
              "Re-import with base 0x00010000.")
    ep = addr(entry_flat)
    cp_reg = currentProgram.getProgramContext().getRegister("CP")
    if cp_reg:
        currentProgram.getProgramContext().setValue(cp_reg, ep, ep, BigInteger.valueOf(entry_cp))
    flat_api.disassemble(ep)
    flat_api.createFunction(ep, "entry")
    print("OK: entry function created at ram:0x%08x" % entry_flat)
finally:
    currentProgram.endTransaction(tx, True)

# ------------------------------------------------------------------
# 5. Decompiler check - MUST pass before analysis
# ------------------------------------------------------------------
print("")
print("Checking decompiler...")
ifc  = DecompInterface()
opts = DecompileOptions()
opts.grabFromProgram(currentProgram)
ifc.setOptions(opts)
ok = ifc.openProgram(currentProgram)
ifc.dispose()

if not ok:
    abort("Decompiler openProgram() FAILED (marshalling error).\n"
          "Check h8.cspec is correctly installed in the Ghidra processors dir,\n"
          "do a full Ghidra restart, delete and re-import the ROM,\n"
          "then re-run this script.\n"
          "DO NOT run auto-analysis until this check passes.")

print("OK: Decompiler is healthy!")
print("")

# ------------------------------------------------------------------
# 6. Auto-analysis
# ------------------------------------------------------------------
print("Running auto-analysis (this may take a minute)...")
flat_api.analyzeAll(currentProgram)
fc = currentProgram.getFunctionManager().getFunctionCount()
print("OK: Auto-analysis complete - %d functions found" % fc)
print("")

# ------------------------------------------------------------------
# 7. EcuFlash XML table labels (optional)
# ------------------------------------------------------------------
def apply_xml(file_path):
    if not file_path or not os.path.exists(file_path):
        print("NOTE: EcuFlash XML not found - skipping table labels")
        print("      Set XML_PATH at the top of this script to enable.")
        return 0
    try:
        root = ET.parse(file_path).getroot()
    except Exception as e:
        print("WARNING: Could not parse XML: " + str(e))
        return 0
    # Follow <include> references
    base_dir = os.path.dirname(file_path)
    for inc in root.findall('include'):
        inc_name = inc.text.strip()
        if not inc_name.endswith('.xml'):
            inc_name += '.xml'
        inc_path = os.path.join(base_dir, inc_name)
        if os.path.exists(inc_path):
            apply_xml(inc_path)
    # Apply table labels
    count = 0
    for table in root.findall('table'):
        name     = table.get('name')
        addr_str = table.get('address')
        if not name or not addr_str:
            continue
        try:
            xml_addr = int(addr_str, 16)
            if 0x10000 <= xml_addr <= 0x2FFFF:
                t    = space.getAddress(xml_addr)
                safe = name.replace(" ","_").replace("(","").replace(")","").replace("-","_")
                if not flat_api.getSymbolAt(t):
                    flat_api.createLabel(t, safe, True)
                    count += 1
                else:
                    flat_api.setPlateComment(t, "EcuFlash Table: " + name)
        except ValueError:
            pass
    print("OK: %d EcuFlash table labels from %s" % (count, os.path.basename(file_path)))
    return count

tx = currentProgram.startTransaction("EcuFlash labels")
try:
    apply_xml(XML_PATH)
finally:
    currentProgram.endTransaction(tx, True)

print("")
print("=" * 60)
print("Setup complete!")
print("=" * 60)
