// Scans the WHOLE program for every literal-push call to table_lookup_interp
// (0x14656), table_lookup_indexed (0x14854), and table_read_indexed (0x14880),
// collecting EVERY table address any function calls -- not scoped to a
// pre-existing candidate list. Cross-checks the result against every address
// currently present in the XML export. Reports any called address that has
// NO corresponding XML entry -- i.e. a genuinely missing table, the failure
// mode found manually in tcu_shift_solenoid_table_init (review2.md item 20).
// @category H8539F

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.listing.Function;
import ghidra.program.model.scalar.Scalar;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

public class FindAllTableCallsVsXml extends GhidraScript {

    static final long TABLE_LOOKUP_INTERP = 0x14656L;
    static final long TABLE_LOOKUP_INDEXED = 0x14854L;
    static final long TABLE_READ_INDEXED = 0x14880L;

    static class PushEvent {
        int offset;
        int bank;
        Address bankPushAddr;
        Function fn;
        long pjsrTarget = -1;
    }

    @Override
    public void run() throws Exception {
        String[] xmlAddrsHex = new String[] {
            "10aaf","11dc9","2d3f8","2d3ee","11cd0","2d418","11f08","2d42e","128f6",
            "2d3fe","12902","1290e","1291a","1292a","2d11c","11e3e","2d446","11d7a",
            "2d4ac","11d86","2d2e0","11d9c","11daa","11db8","11e7e","120d9","2d382",
            "2d332","12395","12832","2d2e6","12840","12808","2d27a","12816","127b0",
            "127be","127e4","2d28c","127ee","2d086","127cc","2d490","10ae4","128c6",
            "12938","2d4c0","12944","1295e","2d536","1296c","109e4","109e6","10dfb",
            "10dfd","12a72","2d3c8","119bf","2d308","2d2b0","11bc7","118bb","11ac3",
            "128a7","2d260","11cb5","2d68a","11d24","2d0a0","11cfc","11d0c","108a4",
            "10808","11804","2d21e","1181a","11847","2d210","2d24e","1080c","10810",
            "11f7b","12237","12651","10886","10872","11cee","2d080","10888","10ad4",
            "128a2","128ae","128ba","1288e","12896","10b6c","11aa2","12f22","12f8e",
            "12ffa","13066","130d2","10e0a","12a80","2d59c","12a96","2d334","12aaa",
            "12abe","12ad2","10e02","10894","114fe","12f84","11f26","2d2d2","124f3",
            "12af8","10df0","10df2","10208","1021a","10233","10237","1023b","1023f",
            "10243","10247","1024b","1024f","10232","10236","1023a","1023e","10242",
            "10246","1024a","1024e","10d73","11834","1186c","2d0f0","11880","11894",
            "118a0","11d20","11d4c","11dec","11e4a","2d130","11e6a","2d440","11e86",
            "11e94","11ea0","11ec8","11ed6","11ee6","11f16","11f30","11f3c","11f4a",
            "11f5c","11f64","2d2aa","11f6c","127a8","2d75a","127d8","127fc","12824",
            "2d274","1284e","2d180","12858","2d29c","12860","1286c","128d2","128de",
            "128ea","12926","12950","2d1fa","1297a","12986","12ae6","12b06","2d50c",
            "12b94","2d356","12cbc","12cd2","2d548","12ce8","12cf4","12d00","12d70",
            "2d09a","12dd6","2d116","12de4","2d5ee","12df2","12e4a","12ea2","2d620",
            "12eae","12ebc","12ece","12edc","12eea","12ef8","2d636","12f06","12f14",
            "1313e","2d66a","1314c","13154","1315c","13168","13174","1317c","13188",
            "13190","13198","131a0","2d7b0","131a8","131b0","131b8","131c0","131c4",
            "131cc","131d4","131e0","131ec","131f6","131fa","13202","1320a","13212",
            "1321c","13236","13250","1325e","1326c","1327a"
        };
        Set<Integer> xmlAddrs = new HashSet<>();
        for (String s : xmlAddrsHex) {
            xmlAddrs.add(Integer.parseInt(s, 16));
        }

        List<PushEvent> allEvents = new ArrayList<>();
        InstructionIterator it = currentProgram.getListing().getInstructions(true);
        Integer pendingOffset = null;

        while (it.hasNext()) {
            Instruction insn = it.next();
            String mnem = insn.getMnemonicString();
            String rep = insn.toString();

            if (mnem.startsWith("mov") && rep.contains("@-SP")) {
                Scalar sc = null;
                try { sc = insn.getScalar(0); } catch (Exception e) {}
                if (sc != null) {
                    long val = sc.getUnsignedValue();
                    if (rep.contains(":16")) {
                        pendingOffset = (int) val;
                    } else if (rep.contains(":8") && pendingOffset != null) {
                        int bank = (int) val;
                        Function f = getFunctionContaining(insn.getAddress());
                        if (f != null) {
                            PushEvent ev = new PushEvent();
                            ev.offset = pendingOffset;
                            ev.bank = bank;
                            ev.bankPushAddr = insn.getAddress();
                            ev.fn = f;
                            allEvents.add(ev);
                        }
                        pendingOffset = null;
                    }
                }
            } else if (mnem.equalsIgnoreCase("pjsr")) {
                if (!allEvents.isEmpty()) {
                    PushEvent last = allEvents.get(allEvents.size() - 1);
                    if (last.pjsrTarget == -1) {
                        try {
                            Address[] flows = insn.getFlows();
                            if (flows != null && flows.length > 0) {
                                last.pjsrTarget = flows[0].getOffset();
                            }
                        } catch (Exception e) {}
                    }
                }
            }
        }

        Set<Integer> missingFromXml = new HashSet<>();
        StringBuilder detail = new StringBuilder();
        int matchedCalls = 0;

        for (PushEvent ev : allEvents) {
            if (ev.pjsrTarget == TABLE_LOOKUP_INTERP ||
                ev.pjsrTarget == TABLE_LOOKUP_INDEXED ||
                ev.pjsrTarget == TABLE_READ_INDEXED) {
                int fullAddr = (ev.bank << 16) | ev.offset;
                matchedCalls++;
                if (!xmlAddrs.contains(fullAddr)) {
                    missingFromXml.add(fullAddr);
                    detail.append(String.format("%06X @ %s (in %s) [pjsr=%06X]\n",
                        fullAddr, ev.bankPushAddr, ev.fn.getName(), ev.pjsrTarget));
                }
            }
        }

        println("Total table_lookup_interp/indexed/read_indexed calls found: " + matchedCalls);
        println("Distinct addresses called but MISSING from XML: " + missingFromXml.size());
        println("");
        println(detail.toString());
    }
}
