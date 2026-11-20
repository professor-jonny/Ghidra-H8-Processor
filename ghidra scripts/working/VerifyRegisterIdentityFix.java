import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileOptions;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;

// Post-fix verification: re-decompile init_copy_const_block_via_memcpy_banked
// against the new build (containing ActionSegmentRegisterIdentity) and check
// whether the register0x0e artifact is gone.
public class VerifyRegisterIdentityFix extends GhidraScript {
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

        String c = res.getDecompiledFunction().getC();
        println("=== Decompiled C for " + f.getName() + " ===");
        println(c);
        println("");
        println("=== register0x0e present? " + c.contains("register0x0e") + " ===");
    }
}
