import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.lang.PrototypeModel;
import ghidra.program.model.lang.PrototypeModel.FarPointerJoinSpec;
import java.util.List;

// Direct unit-level check of the new Java-side PrototypeModel.getFarPointerJoins()
// accessor added 2026-08-18. Prior confirmation this session was indirect
// (program opened without a cspec parse error; decompiler output still showed
// the fused pointer correctly) -- this script calls the new accessor directly
// and prints exactly what it decoded, closing that gap.
public class CheckFarPointerJoins extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] addrs = { "00014656", "00014854", "000148a2" };
        String[] names = { "table_lookup_interp", "table_lookup_indexed", "table_3axis_interp_triple" };

        for (int i = 0; i < addrs.length; i++) {
            Address addr = currentProgram.getAddressFactory().getAddress(addrs[i]);
            Function f = getFunctionAt(addr);
            if (f == null) {
                println(names[i] + " @ " + addrs[i] + ": FUNCTION NOT FOUND");
                continue;
            }

            PrototypeModel model = f.getCallingConvention();
            if (model == null) {
                // fall back to the program's default model, same as Ghidra does internally
                model = currentProgram.getCompilerSpec().getDefaultCallingConvention();
                println(names[i] + ": getCallingConvention() returned null, using default model \""
                    + model.getName() + "\" instead");
            }

            println("=== " + names[i] + " @ " + addrs[i] + " ===");
            println("  calling convention: " + model.getName());

            List<FarPointerJoinSpec> joins = model.getFarPointerJoins();
            if (joins.isEmpty()) {
                println("  getFarPointerJoins(): EMPTY -- no <farpointerjoin> declared on this model");
            }
            else {
                for (FarPointerJoinSpec spec : joins) {
                    println("  getFarPointerJoins(): hislot=" + spec.hislot + " joinsize=" + spec.joinsize);
                }
            }
            println("");
        }

        println("Done. Non-empty hislot/joinsize output above confirms the Java-side");
        println("<farpointerjoin> decode path (PrototypeModel.restoreXml -> farPointerJoins");
        println("field -> getFarPointerJoins() accessor) is working end-to-end, not just");
        println("'compiles' or 'program opens without error'.");
    }
}
