# Import hand-named functions from an old (broken-SLEIGH) Ghidra XML export.
# @category MitsubishiECU
#
# Source: RVR_1998_x3 4g63t 21000011 md352553.hex.xml - a Ghidra XML PROGRAM
# export from an earlier disassembly session, done before the current SLEIGH
# fixes. Many functions were hand-named at the time to help diagnose decode
# problems. Function boundaries/addresses may have shifted since (the old
# SLEIGH was broken), so this script ONLY renames functions whose address
# matches EXACTLY between the old export and the current program, and ONLY
# if the current function is still auto-named (FUN_xxxxxxxx) - i.e. it will
# never overwrite a name you've already set by hand in this session.
#
# Everything else (no function at that address in the new disassembly,
# address falls inside a different function's body, current name is already
# custom) is logged to a "needs manual review" report instead of guessed at.
#
# Usage: edit XML_PATH below if the file moves, then run from Script Manager.

import re

XML_PATH = "C:\\Users\\j.brophy.CORKILLSYSTEMS\\github\\Ghidra-H8-Processor\\test\\rvr\\RVR_1998_x3 4g63t 21000011 md352553.hex.xml"

FUNC_RE = re.compile(
    r'<FUNCTION ENTRY_POINT="([0-9a-fA-F]+)" NAME="([^"]+)" LIBRARY_FUNCTION="n">'
)

def load_old_names(path):
    """Parse the old XML export, return list of (addr_int, name) for
    functions that were hand-named (i.e. NOT still FUN_xxxxxxxx)."""
    pairs = []
    with open(path, "r") as f:
        for line in f:
            m = FUNC_RE.search(line)
            if not m:
                continue
            addr_hex, name = m.group(1), m.group(2)
            if name.startswith("FUN_"):
                continue    # never hand-named to begin with, nothing to carry
            pairs.append((int(addr_hex, 16), name))
    return pairs


def main():
    print("=" * 70)
    print("Importing hand-named functions from old XML export")
    print("Source: %s" % XML_PATH)
    print("=" * 70)

    try:
        old_names = load_old_names(XML_PATH)
    except Exception as e:
        print("ERROR: could not read/parse XML: %s" % e)
        return

    print("Parsed %d hand-named functions from old export." % len(old_names))

    fm = currentProgram.getFunctionManager()

    renamed = []
    skipped_already_named = []
    skipped_no_function = []
    skipped_boundary_mismatch = []

    tx = currentProgram.startTransaction("Import old function names (exact-address matches)")
    try:
        for old_addr, old_name in old_names:
            try:
                target = toAddr(old_addr)
            except Exception:
                skipped_no_function.append((old_addr, old_name, "bad address"))
                continue

            fn = fm.getFunctionAt(target)
            if fn is None:
                # Check if the address falls INSIDE some other function's
                # body - that's a boundary mismatch, not a clean "no match".
                containing = fm.getFunctionContaining(target)
                if containing is not None:
                    skipped_boundary_mismatch.append(
                        (old_addr, old_name, containing.getName(),
                         containing.getEntryPoint().getOffset()))
                else:
                    skipped_no_function.append((old_addr, old_name, "no function at address"))
                continue

            current_name = fn.getName()
            if not current_name.startswith("FUN_"):
                skipped_already_named.append((old_addr, old_name, current_name))
                continue

            try:
                fn.setName(old_name, ghidra.program.model.symbol.SourceType.USER_DEFINED)
                renamed.append((old_addr, old_name))
            except Exception as e:
                skipped_no_function.append((old_addr, old_name, "rename failed: %s" % e))
    finally:
        currentProgram.endTransaction(tx, True)

    print("")
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print("Renamed (exact address match, was FUN_*):        %d" % len(renamed))
    print("Skipped - already custom-named in new disasm:     %d" % len(skipped_already_named))
    print("Skipped - address falls inside another function:  %d" % len(skipped_boundary_mismatch))
    print("Skipped - no function at that address at all:     %d" % len(skipped_no_function))
    print("=" * 70)

    if renamed:
        print("")
        print("--- Renamed ---")
        for addr, name in renamed:
            print("  0x%08X -> %s" % (addr, name))

    if skipped_already_named:
        print("")
        print("--- Skipped: new disassembly already has a custom name ---")
        print("(review manually - old name may be better/worse, your call)")
        for addr, old_name, current_name in skipped_already_named:
            print("  0x%08X   old='%s'   current='%s'" % (addr, old_name, current_name))

    if skipped_boundary_mismatch:
        print("")
        print("--- NEEDS MANUAL REVIEW: address now falls inside a different function ---")
        print("(function boundaries shifted between old/new disassembly)")
        for addr, old_name, containing_name, containing_addr in skipped_boundary_mismatch:
            print("  old 0x%08X '%s'  ->  now inside %s (starts 0x%08X)" %
                  (addr, old_name, containing_name, containing_addr))

    if skipped_no_function:
        print("")
        print("--- NEEDS MANUAL REVIEW: no function at this address in new disassembly ---")
        for addr, old_name, reason in skipped_no_function:
            print("  0x%08X   old='%s'   (%s)" % (addr, old_name, reason))

    print("")
    print("=" * 70)
    print("Done. %d renamed automatically; %d total need manual review." %
          (len(renamed), len(skipped_boundary_mismatch) + len(skipped_no_function)))
    print("=" * 70)


main()
