import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.scalar.Scalar;
import ghidra.program.model.symbol.*;
import ghidra.program.model.mem.Memory;
import java.util.*;

/**
 * Workaround for the class of bug documented in Ghidra core issue #817
 * ("Decompiler is not handling far pointers to stack/ram data correctly"):
 * Ghidra's decompiler never combines this ROM's bank+offset call arguments
 * into a recognized far pointer (confirmed, review.md item 26). Rather than
 * fix the decompiler's pointer algebra (which would need a real SLEIGH/pcode
 * callfixup or constresolve-style mechanism), this script makes the
 * connection permanent and visible in GHIDRA'S OWN REFERENCE DATABASE:
 * it adds an explicit memory reference from the instruction that pushes the
 * OFFSET immediate directly to the real, bank-adjusted target address.
 * This means get_xrefs_to, the Listing's own "XREF" display, and navigation
 * (double-click / follow reference) all work correctly at the resolved
 * address from now on, even though the decompiled C output itself still
 * shows two separate plain-integer arguments.
 *
 * Includes a validity filter (per review.md item 27's known false
 * positives) to skip resolutions that are clearly garbage rather than
 * silently creating wrong references:
 *   - bank must be in a small, plausible range (observed real banks: 1, 2)
 *   - resolved address must fall within a defined memory block
 */
public class FixBankOffsetReferences extends GhidraScript {
    @Override
    public void run() throws Exception {
        Listing listing = currentProgram.getListing();
        AddressFactory af = currentProgram.getAddressFactory();
        Memory mem = currentProgram.getMemory();
        ReferenceManager refMan = currentProgram.getReferenceManager();

        String[] targetAddrs = { "00014656", "00014854", "000148a2" };
        String[] targetNames = { "table_lookup_interp", "table_lookup_indexed", "table_3axis_interp_triple" };

        // Observed real banks across all 146 confirmed call sites (item 27): 1 and 2 only.
        Set<Long> plausibleBanks = new HashSet<>(Arrays.asList(1L, 2L));

        int totalFixed = 0;
        int totalSkippedBadBank = 0;
        int totalSkippedOutOfRange = 0;
        int totalSkippedUnresolved = 0;
        int totalAlreadyPresent = 0;

        for (int t = 0; t < targetAddrs.length; t++) {
            Address targetAddr = af.getAddress(targetAddrs[t]);
            Function target = getFunctionAt(targetAddr);
            if (target == null) { println(targetNames[t] + ": not found, skipping"); continue; }

            ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(targetAddr);
            List<Address> callSites = new ArrayList<>();
            while (refs.hasNext()) callSites.add(refs.next().getFromAddress());

            println("=== " + targetNames[t] + " (" + callSites.size() + " call sites) ===");

            for (Address callSite : callSites) {
                Function caller = listing.getFunctionContaining(callSite);
                String callerName = (caller != null) ? caller.getName() : "UNKNOWN";

                // Backward-scan, tracking BOTH the value and the instruction address that provided it
                Instruction cur = listing.getInstructionAt(callSite);
                List<Long> imms = new ArrayList<>();
                List<Address> immAddrs = new ArrayList<>();
                for (int i = 0; i < 8 && cur != null; i++) {
                    cur = cur.getPrevious();
                    if (cur == null) break;
                    String mn = cur.getMnemonicString();
                    if (mn.startsWith("mov")) {
                        Object[] opObjs = cur.getOpObjects(0);
                        if (opObjs != null && opObjs.length > 0 && opObjs[0] instanceof Scalar) {
                            long val = ((Scalar) opObjs[0]).getUnsignedValue();
                            imms.add(0, val);
                            immAddrs.add(0, cur.getAddress());
                        }
                    }
                    if (mn.equals("pjsr") || mn.equals("jsr") || mn.equals("bsr")) break;
                    if (imms.size() >= 2) break;
                }

                if (imms.size() < 2) {
                    totalSkippedUnresolved++;
                    continue;
                }

                long offset = imms.get(0);
                long bank = imms.get(1);
                Address offsetPushAddr = immAddrs.get(0);

                if (!plausibleBanks.contains(bank)) {
                    println("  " + callerName + " @ " + callSite +
                        " : SKIPPED (implausible bank=" + bank + ", offset=0x" +
                        Long.toHexString(offset) + ") -- likely a mis-grab, not creating a reference");
                    totalSkippedBadBank++;
                    continue;
                }

                long realAddr = bank * 0x10000L + offset;
                Address realAddress;
                try {
                    realAddress = af.getAddress(String.format("%08x", realAddr));
                } catch (Exception e) {
                    totalSkippedOutOfRange++;
                    continue;
                }

                if (!mem.contains(realAddress)) {
                    println("  " + callerName + " @ " + callSite +
                        " : SKIPPED (resolved 0x" + String.format("%08x", realAddr) +
                        " falls outside any defined memory block)");
                    totalSkippedOutOfRange++;
                    continue;
                }

                // Check if this exact reference already exists (idempotent re-run)
                boolean alreadyThere = false;
                for (Reference r : refMan.getReferencesFrom(offsetPushAddr)) {
                    if (r.getToAddress().equals(realAddress)) { alreadyThere = true; break; }
                }
                if (alreadyThere) {
                    totalAlreadyPresent++;
                    continue;
                }

                refMan.addMemoryReference(offsetPushAddr, realAddress, RefType.DATA, SourceType.USER_DEFINED, 0);
                println("  " + callerName + " @ " + callSite + " : reference added " +
                    offsetPushAddr + " -> " + realAddress);
                totalFixed++;
            }
        }

        println("");
        println("TOTAL new references added: " + totalFixed);
        println("TOTAL already present (skipped, idempotent): " + totalAlreadyPresent);
        println("TOTAL skipped (implausible bank, e.g. the known bank=252 mis-grabs): " + totalSkippedBadBank);
        println("TOTAL skipped (resolved address outside defined memory): " + totalSkippedOutOfRange);
        println("TOTAL skipped (could not resolve two immediates at all): " + totalSkippedUnresolved);
    }
}
