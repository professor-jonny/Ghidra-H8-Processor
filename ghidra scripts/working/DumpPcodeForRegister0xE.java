import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileOptions;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.pcode.HighFunction;
import ghidra.program.model.pcode.PcodeOpAST;
import ghidra.program.model.pcode.Varnode;
import ghidra.program.model.pcode.PcodeBlockBasic;
import java.util.Iterator;

// Dumps the raw pcode op graph (post decompiler simplification, via HighFunction)
// for init_copy_const_block_via_memcpy_banked, specifically looking for any
// Varnode in the "register" address space whose getHigh()/symbol resolution
// looks unusual, and for any PcodeOp related to PIECE/join construction near
// the function entry -- direct evidence for or against the translate.cc
// constructJoinAddress theory from review15.md section 6.
public class DumpPcodeForRegister0xE extends GhidraScript {
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

        println("=== Pcode ops for " + f.getName() + " @ " + addr + " ===");
        Iterator<PcodeOpAST> opIter = hf.getPcodeOps();
        int count = 0;
        while (opIter.hasNext() && count < 60) {
            PcodeOpAST op = opIter.next();
            StringBuilder sb = new StringBuilder();
            sb.append(op.getSeqnum()).append(": ");
            Varnode out = op.getOutput();
            if (out != null) {
                sb.append(describeVarnode(out)).append(" = ");
            }
            sb.append(op.getMnemonic()).append("(");
            for (int i = 0; i < op.getNumInputs(); i++) {
                if (i > 0) sb.append(", ");
                sb.append(describeVarnode(op.getInput(i)));
            }
            sb.append(")");
            println(sb.toString());
            count++;
        }

        println("");
        println("=== Varnodes touching the 'register' space at offset 0xe (SP) or 0xc (FP) ===");
        Iterator<PcodeOpAST> opIter2 = hf.getPcodeOps();
        while (opIter2.hasNext()) {
            PcodeOpAST op = opIter2.next();
            Varnode out = op.getOutput();
            if (out != null && isSpOrFp(out)) {
                println("OUTPUT " + describeVarnode(out) + " <- " + op.getMnemonic() + " @ " + op.getSeqnum());
            }
            for (int i = 0; i < op.getNumInputs(); i++) {
                Varnode in = op.getInput(i);
                if (isSpOrFp(in)) {
                    println("INPUT  " + describeVarnode(in) + " -> " + op.getMnemonic() + " @ " + op.getSeqnum());
                }
            }
        }
    }

    private boolean isSpOrFp(Varnode vn) {
        if (vn == null || !vn.isRegister()) return false;
        long off = vn.getAddress().getOffset();
        return off == 0xe || off == 0xc;
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
