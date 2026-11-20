// CheckHighVarIdentity.java
// review15.md follow-up: confirm whether the SEGMENTOP's register:0xe input
// varnode ("vn"/segInput, the post-INT_ADD SP value) and the upstream
// CAST-input register:0xe varnode ("upstream", the pre-arithmetic raw SP
// read) share the SAME HighVariable object after the eighth-rebuild
// ActionSegmentRegisterIdentity fix. If they do, both display names are
// governed by one shared HighVariable's Symbol (PrintLanguage::pushSymbolDetail,
// printlanguage.cc:239-263, which reads vn->getHigh()->getSymbol() directly,
// not an address/usepoint-bound scope query) -- confirming the "merge
// collapse" theory rather than a usepoint-collision theory.
//@category MCP

import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.pcode.HighFunction;
import ghidra.program.model.pcode.PcodeOpAST;
import ghidra.program.model.pcode.Varnode;
import ghidra.program.model.pcode.HighVariable;
import ghidra.program.model.pcode.PcodeOp;
import java.util.Iterator;

public class CheckHighVarIdentity extends GhidraScript {

    @Override
    public void run() throws Exception {
        Function f = getFunctionAt(toAddr(0x149c8));
        if (f == null) {
            println("Function not found at 0x149c8");
            return;
        }

        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);
        DecompileResults res = decomp.decompileFunction(f, 60, monitor);
        HighFunction hf = res.getHighFunction();
        if (hf == null) {
            println("No HighFunction (decompile failed): " + res.getErrorMessage());
            decomp.dispose();
            return;
        }

        Varnode segInput = null;
        Varnode upstream = null;

        Iterator<PcodeOpAST> it = hf.getPcodeOps();
        while (it.hasNext()) {
            PcodeOpAST op = it.next();
            if (op.getOpcode() == PcodeOp.SEGMENTOP) {
                for (int i = 0; i < op.getNumInputs(); i++) {
                    Varnode in = op.getInput(i);
                    if (in != null && in.isRegister() && in.getOffset() == 0xe) {
                        segInput = in;
                    }
                }
            }
            if (op.getOpcode() == PcodeOp.CAST) {
                Varnode in = op.getInput(0);
                if (in != null && in.isRegister() && in.getOffset() == 0xe) {
                    upstream = in;
                }
            }
        }

        println("=== HighVariable identity check ===");
        HighVariable hv1 = null;
        HighVariable hv2 = null;

        if (segInput == null) {
            println("segInput (SEGMENTOP's register:0xe input) NOT FOUND");
        } else {
            hv1 = segInput.getHigh();
            println("segInput varnode: " + segInput.toString());
            println("  HighVariable identityHashCode: " + (hv1 == null ? "null" : System.identityHashCode(hv1)));
            println("  Symbol: " + (hv1 == null || hv1.getSymbol() == null ? "null" : hv1.getSymbol().getName()));
        }

        if (upstream == null) {
            println("upstream (CAST's register:0xe input) NOT FOUND");
        } else {
            hv2 = upstream.getHigh();
            println("upstream varnode: " + upstream.toString());
            println("  HighVariable identityHashCode: " + (hv2 == null ? "null" : System.identityHashCode(hv2)));
            println("  Symbol: " + (hv2 == null || hv2.getSymbol() == null ? "null" : hv2.getSymbol().getName()));
        }

        if (segInput != null && upstream != null) {
            println("=== SAME HighVariable object? " + (hv1 == hv2) + " ===");
        }

        decomp.dispose();
    }
}