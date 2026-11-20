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

// Dumps EVERY pcode op in the function whose output OR any input is a
// register-space varnode at offset 0xe (SP), with full seqnum/address info,
// to see whether the varnode ASRI links (SEGMENTOP input[2]) is the SAME
// SSA instance as whatever feeds the "sVar1 = (short)register0x0e + -2"
// print line, or a genuinely different one. (review15.md section 21+
// follow-up: linkSymbolAtUsepoint fired and returned a real symbol, but
// register0x0e still printed on the sVar1 line -- need to know if that's
// because two different varnode instances are involved.)
public class DumpAllSPInstances extends GhidraScript {
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
        println("=== All pcode ops touching register offset 0xe in " + f.getName() + " ===");
        Iterator<PcodeOpAST> opIter = hf.getPcodeOps();
        while (opIter.hasNext()) {
            PcodeOpAST op = opIter.next();
            boolean relevant = false;
            Varnode out = op.getOutput();
            if (out != null && isRegE(out)) relevant = true;
            for (int i = 0; i < op.getNumInputs() && !relevant; i++) {
                Varnode in = op.getInput(i);
                if (in != null && isRegE(in)) relevant = true;
            }
            if (!relevant) continue;

            StringBuilder sb = new StringBuilder();
            sb.append(op.getSeqnum()).append(" [uniq=").append(op.getSeqnum().getTime()).append("] ");
            sb.append(op.getMnemonic()).append(" out=").append(describe(out));
            for (int i = 0; i < op.getNumInputs(); i++) {
                sb.append(" in[").append(i).append("]=").append(describe(op.getInput(i)));
            }
            println(sb.toString());
        }

        println("");
        println("=== Decompiled C, for cross-reference ===");
        println(res.getDecompiledFunction().getC());

        ifc.dispose();
    }

    private boolean isRegE(Varnode vn) {
        if (vn == null) return false;
        if (!vn.getAddress().getAddressSpace().getName().toLowerCase().contains("register")) return false;
        return vn.getAddress().getOffset() == 0xe;
    }

    private String describe(Varnode vn) {
        if (vn == null) return "null";
        StringBuilder sb = new StringBuilder();
        sb.append(vn.getAddress().getAddressSpace().getName()).append(":");
        sb.append(String.format("0x%x", vn.getAddress().getOffset())).append(":").append(vn.getSize());
        HighVariable hv = vn.getHigh();
        sb.append("[").append(hv != null ? hv.getName() : "null-high").append("]");
        sb.append("(def=").append(vn.getDef() != null ? vn.getDef().getSeqnum().toString() : "none").append(")");
        return sb.toString();
    }
}
