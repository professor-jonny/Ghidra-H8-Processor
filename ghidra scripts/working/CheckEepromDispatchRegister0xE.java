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

// Verifies whether eeprom_backup_table_write_dispatch's two register0x0e
// hits (noted but not individually checked in review15.md section 1 item 4)
// share the same link/unlk self-reassignment shape as
// init_copy_const_block_via_memcpy_banked (section 7/9), or differ --
// needed before assuming a fix built against the first function covers
// this one too.
public class CheckEepromDispatchRegister0xE extends GhidraScript {
    @Override
    public void run() throws Exception {
        Address addr = currentProgram.getAddressFactory().getAddress("000149f5");
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

        println("=== Decompiled C for " + f.getName() + " @ " + addr + " ===");
        println(res.getDecompiledFunction().getC());

        HighFunction hf = res.getHighFunction();
        if (hf == null) {
            println("No HighFunction returned");
            return;
        }

        println("");
        println("=== SP/FP (register offset 0xe / 0xc) touches, with def-chain ===");
        Iterator<PcodeOpAST> opIter = hf.getPcodeOps();
        while (opIter.hasNext()) {
            PcodeOpAST op = opIter.next();
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

        println("");
        println("=== CPUI_SEGMENTOP ops and their input def-chains ===");
        Iterator<PcodeOpAST> opIter2 = hf.getPcodeOps();
        int segCount = 0;
        while (opIter2.hasNext()) {
            PcodeOpAST op = opIter2.next();
            if (op.getOpcode() != PcodeOp.SEGMENTOP) continue;
            segCount++;
            println("SEGMENTOP @ " + op.getSeqnum() + " numInputs=" + op.getNumInputs());
            for (int i = 0; i < op.getNumInputs(); i++) {
                Varnode in = op.getInput(i);
                println("  input[" + i + "] = " + describeVarnode(in));
                if (in != null && !in.isConstant()) {
                    PcodeOp def = in.getDef();
                    if (def == null) {
                        println("    -> getDef() == null [untracked]");
                    } else {
                        println("    -> defined by " + def.getMnemonic() + " @ " + def.getSeqnum());
                    }
                }
            }
        }
        if (segCount == 0) {
            println("No CPUI_SEGMENTOP ops found in this function's pcode.");
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
