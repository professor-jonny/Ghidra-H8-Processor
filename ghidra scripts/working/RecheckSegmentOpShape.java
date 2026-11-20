import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileOptions;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.pcode.HighFunction;
import ghidra.program.model.pcode.HighVariable;
import ghidra.program.model.pcode.PcodeOp;
import ghidra.program.model.pcode.PcodeOpAST;
import ghidra.program.model.pcode.Varnode;
import java.util.Iterator;

// Fresh, current-build re-check of the exact pcode shape feeding SEGMENTOP,
// to see why ActionSegmentRegisterIdentity still isn't firing after the
// isSelfReferentialRegisterArithmetic fix. Does NOT rely on section 9's
// earlier dump -- re-captures live, right now, against the current build.
public class RecheckSegmentOpShape extends GhidraScript {
    @Override
    public void run() throws Exception {
        Address addr = currentProgram.getAddressFactory().getAddress("000149c8");
        Function f = getFunctionAt(addr);
        if (f == null) { println("Function not found"); return; }

        DecompInterface ifc = new DecompInterface();
        DecompileOptions opts = new DecompileOptions();
        ifc.setOptions(opts);
        ifc.openProgram(currentProgram);
        DecompileResults res = ifc.decompileFunction(f, 60, monitor);
        if (!res.decompileCompleted()) { println("Decompile failed: " + res.getErrorMessage()); return; }

        HighFunction hf = res.getHighFunction();
        println("=== All CPUI_SEGMENTOP ops in " + f.getName() + " ===");
        Iterator<PcodeOpAST> opIter = hf.getPcodeOps();
        int segCount = 0;
        while (opIter.hasNext()) {
            PcodeOpAST op = opIter.next();
            if (op.getOpcode() != PcodeOp.SEGMENTOP) continue;
            segCount++;
            println("SEGMENTOP @ " + op.getSeqnum() + " numInputs=" + op.getNumInputs());
            for (int i = 0; i < op.getNumInputs(); i++) {
                Varnode in = op.getInput(i);
                if (in == null) { println("  input[" + i + "] = null"); continue; }
                println("  input[" + i + "] = " + describe(in)
                        + "  isConstant=" + in.isConstant()
                        + "  spaceType=" + in.getAddress().getAddressSpace().getType()
                        + "  hasHigh=" + (in.getHigh() != null)
                        + "  hasSymbol=" + (in.getHigh() != null && in.getHigh().getSymbol() != null));
                PcodeOp def = in.getDef();
                if (def != null) {
                    println("    def op = " + def.getMnemonic() + "  numInputs=" + def.getNumInputs());
                    for (int j = 0; j < def.getNumInputs(); j++) {
                        Varnode din = def.getInput(j);
                        println("      def.input[" + j + "] = " + describe(din) + "  isConstant=" + (din != null && din.isConstant()));
                    }
                } else {
                    println("    def op = null (no definition -- free/input varnode)");
                }
            }
        }
        if (segCount == 0) println("No SEGMENTOP ops found at all.");
    }

    private String describe(Varnode vn) {
        if (vn == null) return "null";
        StringBuilder sb = new StringBuilder();
        sb.append(vn.getAddress().getAddressSpace().getName()).append(":");
        sb.append(String.format("0x%x", vn.getAddress().getOffset())).append(":").append(vn.getSize());
        if (vn.getHigh() != null && vn.getHigh().getName() != null) sb.append("[").append(vn.getHigh().getName()).append("]");
        return sb.toString();
    }
}
