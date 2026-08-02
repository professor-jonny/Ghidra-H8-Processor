// Scans the 0x10800-0x10FFF ROM region (where known 1D scalar tables cluster
// densely per the bookmark list) for every address with at least one real
// xref/reference, then cross-checks against the XML file directly. Reports
// candidates NOT present in the XML at all. This is a narrow, targeted
// search for missing 1D scalars (which have no header signature to scan
// for structurally, unlike 2D/3D tables) -- see review2.md item 21 for the
// broader table_lookup_interp scan this complements.
// @category H8539F

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.program.model.listing.Function;

import java.io.BufferedReader;
import java.io.FileReader;
import java.util.HashSet;
import java.util.Set;
import java.util.TreeMap;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class Find1DScalarCandidates extends GhidraScript {

    @Override
    public void run() throws Exception {
        String xmlPath = "C:\\Users\\j.brophy.CORKILLSYSTEMS\\github\\Ghidra-H8-Processor\\test\\rvr\\xml\\ecuflash\\new\\21000011_1997-2001_RVR_X3_Mt__4g63t_.xml";
        Set<Integer> xmlAddrs = new HashSet<>();
        Pattern p = Pattern.compile("address=\"([0-9A-Fa-f]+)\"");
        try (BufferedReader r = new BufferedReader(new FileReader(xmlPath))) {
            String line;
            while ((line = r.readLine()) != null) {
                Matcher m = p.matcher(line);
                while (m.find()) {
                    try { xmlAddrs.add(Integer.parseInt(m.group(1), 16)); } catch (Exception e) {}
                }
            }
        }
        println("Parsed " + xmlAddrs.size() + " distinct XML addresses.");

        int start = 0x10800;
        int end = 0x10FFF;
        TreeMap<Integer, String> candidates = new TreeMap<>();

        for (int a = start; a <= end; a++) {
            Address addr = toAddr(a);
            ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(addr);
            if (refs.hasNext()) {
                // Skip if this address or a neighbor within 4 bytes is already in XML
                // (avoids re-flagging known tables' internal bytes).
                boolean nearXml = false;
                for (int d = -4; d <= 4; d++) {
                    if (xmlAddrs.contains(a + d)) { nearXml = true; break; }
                }
                if (nearXml) continue;

                StringBuilder callers = new StringBuilder();
                int count = 0;
                while (refs.hasNext() && count < 5) {
                    Reference ref = refs.next();
                    Address from = ref.getFromAddress();
                    Function f = getFunctionContaining(from);
                    String fname = f != null ? f.getName() : "???";
                    callers.append(fname).append("@").append(from).append(" ");
                    count++;
                }
                candidates.put(a, callers.toString());
            }
        }

        println("Candidates with real xrefs, NOT within 4 bytes of any XML address: " + candidates.size());
        println("");
        for (java.util.Map.Entry<Integer, String> e : candidates.entrySet()) {
            println(String.format("%06X : %s", e.getKey(), e.getValue()));
        }
    }
}
