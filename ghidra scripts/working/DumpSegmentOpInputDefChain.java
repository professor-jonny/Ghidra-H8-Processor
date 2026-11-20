import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileOptions;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.pcode.HighFunction;
import ghidra.program.model.pcode.PcodeOp;
import ghidra.program.model.pcode.PcodeOpAST;
import ghidra.program.model.pcode.Varnode;
import java.util.Iterator;

// Tests the specific claim from the second posted GitHub comment on issue #817:
// that walking Varnode.getDef() backward from a CPUI_SEGMENTOP op's own inputs
// terminates immediately as an untracked input/parameter, even when the real
// disassembly shows the register was assigned a few instructions earlier via a
// plain move. Walks every CPUI_SEGMENTOP op found in the target function and
// reports, for each input, whether getDef() resolves to a real defining op or
// returns null (the "untracked input" case the comment describes).
public class DumpSegmentOpInputDefChain extends GhidraScript {
    @Override
    public void run() throws Exception {
        Address addr = currentProgram.getAddressFactory().getAddress("000149c8");
        Function f = getFunctionAt(addr);
        if (f == null) {
            println("Function not found at " + addr);
            return;
        }

        DecompInterface ifc = new DecompInterface();
        DecompileOptions opts = new DecompileOptions();
        ifc.setOptions(opts);
        ifc.openProgram(currentProgram);

        DecompileResults res = ifc.decompileFunction(f, 60, monitor);
        if (!res.decompileCompleted()) {
            println("Decompile failed: " + res.getErrorMessage());
            return;
        }

        HighFunction hf = res.getHighFunction();
        if (hf == null) {
            println("No HighFunction returned");
            return;
        }

        println("=== Searching for CPUI_SEGMENTOP ops in " + f.getName() + " ===");
        Iterator<PcodeOpAST> opIter = hf.getPcodeOps();
        int segCount = 0;
        while (opIter.hasNext()) {
            PcodeOpAST op = opIter.next();
            if (op.getOpcode() != PcodeOp.SEGMENTOP) continue;
            segCount++;
            println("");
            println("SEGMENTOP @ " + op.getSeqnum() + " numInputs=" + op.getNumInputs());
            for (int i = 0; i < op.getNumInputs(); i++) {
                Varnode in = op.getInput(i);
                println("  input[" + i + "] = " + describeVarnode(in));
                walkDefChain(in, 1);
            }
        }
        if (segCount == 0) {
            println("No CPUI_SEGMENTOP ops found in this function's pcode --");
            println("(the CALLOTHER may not have been converted, or ActionSegmentize did not fire).");
        }
    }

    private void walkDefChain(Varnode vn, int depth) {
        String indent = "    ".repeat(depth);
        if (vn == null) {
            println(indent + "-> null varnode");
            return;
        }
        if (vn.isConstant()) {
            println(indent + "-> constant, no def (expected terminal)");
            return;
        }
        PcodeOp def = vn.getDef();
        if (def == null) {
            println(indent + "-> getDef() == null  [UNTRACKED INPUT/PARAMETER -- matches the claimed symptom]");
            println(indent + "   isInput=" + vn.isInput() + " isFree=" + vn.isFree() + " isRegister=" + vn.isRegister());
            return;
        }
        println(indent + "-> defined by " + def.getMnemonic() + " @ " + def.getSeqnum()
                + "  (inputs: " + def.getNumInputs() + ")");
        if (def.getNumInputs() > 0) {
            Varnode upstream = def.getInput(0);
            println(indent + "   upstream input[0] = " + describeVarnode(upstream));
        }
    }

    private String describeVarnode(Varnode vn) {
        if (vn == null) return "null";
        StringBuilder sb = new StringBuilder();
        sb.append(vn.getAddress().getAddressSpace().getName());
        sb.append(":");
        sb.append(String.format("0x%x", vn.getAddress().getOffset()));
        sb.append(":").append(vn.getSize());
        if (vn.getHigh() != null && vn.getHigh().getName() != null) {
            sb.append("[").append(vn.getHigh().getName()).append("]");
        }
        return sb.toString();
    }
}
