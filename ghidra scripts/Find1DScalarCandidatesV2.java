// V2: same idea as Find1DScalarCandidates but filters much harder to reduce
// noise. A real 1D scalar table is typically read via a literal ROM address
// pushed directly before a simple load (mov.b/mov.w from an absolute ROM
// address), NOT accessed via the RAM-variable read/write patterns that
// dominate this ROM's control-flow code. This version:
//   1) Only considers addresses with a SINGLE code xref (real 1D constants
//      are typically read once, at one call site, unlike RAM state flags
//      which are touched from dozens of places).
//   2) Requires the referencing instruction to be a direct "mov...,Rn" load
//      FROM the candidate address (not a store TO it, not a bit-test/branch).
//   3. Widens the "already near an XML entry" exclusion to +/-8 bytes.
// @category H8539F

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;

import java.io.BufferedReader;
import java.io.FileReader;
import java.util.HashSet;
import java.util.Set;
import java.util.TreeMap;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class Find1DScalarCandidatesV2 extends GhidraScript {

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

            int refCount = 0;
            Reference onlyRef = null;
            while (refs.hasNext()) {
                onlyRef = refs.next();
                refCount++;
                if (refCount > 1) break;
            }
            if (refCount != 1) continue; // want exactly one xref -- real constants read once

            Address from = onlyRef.getFromAddress();
            Instruction insn = getInstructionAt(from);
            if (insn == null) continue;
            String mnem = insn.getMnemonicString();
            String rep = insn.toString();

            // Only interested in a direct load-from-ROM pattern, not RAM
            // read-modify-write, bit-test, or branch/compare instructions.
            if (!mnem.toLowerCase().startsWith("mov")) continue;
            if (rep.contains("@-SP") || rep.contains("@SP")) continue; // stack push, not a scalar load
            // The candidate address should appear on the SOURCE side (right
            // of comma is dest in this disassembly style: "mov ...,Rn" or
            // "mov ...,@addr" -- for a genuine constant load we want the ROM
            // address on the left/source side, going INTO a register).
            if (!rep.matches(".*0x" + Integer.toHexString(a) + ".*,[Rr]\\d.*")) continue;

            boolean nearXml = false;
            for (int d = -8; d <= 8; d++) {
                if (xmlAddrs.contains(a + d)) { nearXml = true; break; }
            }
            if (nearXml) continue;

            Function f = getFunctionContaining(from);
            String fname = f != null ? f.getName() : "???";
            candidates.put(a, fname + "@" + from + "  [" + rep.trim() + "]");
        }

        println("Filtered candidates (single xref, direct ROM->register load, not near XML): " + candidates.size());
        println("");
        for (java.util.Map.Entry<Integer, String> e : candidates.entrySet()) {
            println(String.format("%06X : %s", e.getKey(), e.getValue()));
        }
    }
}
