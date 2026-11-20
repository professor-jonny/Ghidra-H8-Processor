// Read-only. Prints the decompiler's own stack-pointer arithmetic around the calls of one function,
// using the "firstpass" simplification style (before simplification, with the extrapop step applied).
// Question it answers: where does the decompiler's SP rise by 4 per call (the uStack0000/0002/0004 stores)?
// Run on the copy (RVR ...hex.1) from Script Manager, then send the console output.
// Change FUNC to look at another function.
//@category H8
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.*;
import ghidra.program.model.pcode.*;
import ghidra.program.model.lang.*;
import java.util.*;

public class SpAtCalls extends GhidraScript {
    static final String FUNC = "subsystem_unconditional_init_chain";

    @Override
    public void run() throws Exception {
        Language lang = currentProgram.getLanguage();
        Register sp = lang.getRegister("SP");
        long spOff = sp.getAddress().getOffset();
        println("program: " + currentProgram.getDomainFile().getPathname() + " version " + currentProgram.getDomainFile().getVersion());
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        di.setSimplificationStyle("firstpass");
        for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
            if (!f.getName().equals(FUNC)) continue;
            println("function " + f.getName() + " @" + f.getEntryPoint() + " conv=" + f.getCallingConventionName() + " purge=" + f.getStackPurgeSize());
            int n = 0;
            for (Instruction in : currentProgram.getListing().getInstructions(f.getBody(), true)) {
                println("   " + in.getAddress() + " " + in);
                if (++n >= 10) break;
            }
            DecompileResults dr = di.decompileFunction(f, 60, monitor);
            HighFunction hf = dr.getHighFunction();
            if (hf == null) { println("no high function: " + dr.getErrorMessage()); return; }
            List<PcodeOpAST> ops = new ArrayList<PcodeOpAST>();
            Iterator<PcodeOpAST> it = hf.getPcodeOps();
            while (it.hasNext()) ops.add(it.next());
            Collections.sort(ops, new Comparator<PcodeOpAST>() {
                public int compare(PcodeOpAST a, PcodeOpAST b) {
                    int c = a.getSeqnum().getTarget().compareTo(b.getSeqnum().getTarget());
                    return c != 0 ? c : Integer.compare(a.getSeqnum().getTime(), b.getSeqnum().getTime());
                }
            });
            println("=== firstpass ops (" + ops.size() + "); showing SP writes, STOREs and CALLs");
            int shown = 0;
            for (PcodeOpAST op : ops) {
                Varnode o = op.getOutput();
                boolean spWrite = o != null && o.isRegister() && o.getOffset() == spOff;
                int oc = op.getOpcode();
                if (!(spWrite || oc == PcodeOp.CALL || oc == PcodeOp.STORE)) continue;
                StringBuilder sb = new StringBuilder(String.format("%s.%d %-8s", op.getSeqnum().getTarget(), op.getSeqnum().getTime(), op.getMnemonic()));
                if (o != null) sb.append(" out=").append(o.toString(lang));
                for (int i = 0; i < op.getNumInputs(); i++) sb.append(" in").append(i).append("=").append(op.getInput(i).toString(lang));
                println("  " + sb);
                if (++shown >= 90) { println("  ..."); break; }
            }
        }
    }
}
