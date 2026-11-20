import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.lang.PrototypeModel;
import ghidra.program.model.pcode.XmlEncode;

// Direct encode() round-trip check for the new PrototypeModel.encode()
// addition (2026-08-18). Prior work confirmed decode() works
// (CheckFarPointerJoins.java) and confirmed encode()'s mere PRESENCE doesn't
// break decode (program reopens/decompiles fine) -- but encode() itself has
// never been called and its actual output never inspected. This script does
// that: call encode() into a real XmlEncode buffer, print the resulting XML
// text, and visually/programmatically confirm <farpointerjoin> with the
// right hislot/joinsize attributes actually appears in it.
public class CheckFarPointerEncode extends GhidraScript {
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
                model = currentProgram.getCompilerSpec().getDefaultCallingConvention();
            }

            println("=== " + names[i] + " @ " + addrs[i] + " ===");

            XmlEncode encoder = new XmlEncode(true); // true = formatted/indented output
            // injectLibrary is only dereferenced if hasUponEntry/hasUponReturn is set;
            // none of these three functions use call-fixup injection, so null is safe here.
            model.encode(encoder, null);
            String xml = encoder.toString();

            println(xml);

            boolean hasElement = xml.contains("<farpointerjoin");
            boolean hasHislot = xml.contains("hislot=\"0\"");
            boolean hasJoinsize = xml.contains("joinsize=\"3\"");

            println("  <farpointerjoin> element present: " + hasElement);
            println("  hislot=\"0\" present:               " + hasHislot);
            println("  joinsize=\"3\" present:             " + hasJoinsize);
            println((hasElement && hasHislot && hasJoinsize)
                ? "  ROUND TRIP OK for " + names[i]
                : "  *** ROUND TRIP FAILED for " + names[i] + " ***");
            println("");
        }

        println("Done.");
    }
}
