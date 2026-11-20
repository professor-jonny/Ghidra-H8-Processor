import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import ghidra.app.decompiler.*;
import java.util.*;

public class RemoveBadDispatchRefs extends GhidraScript {
  public void run() throws Exception {
    AddressSpace sp = currentProgram.getAddressFactory().getDefaultAddressSpace();
    Address from = sp.getAddress(0x28b50);
    Set<Long> good = new HashSet<>(Arrays.asList(0x28b62L,0x28b89L,0x28ba8L,0x28c5a L,0x28c78L,0x28c83L,0x28cbaL,0x28cc8L));
    ReferenceManager rm = currentProgram.getReferenceManager();
    List<Reference> bad = new ArrayList<>();
    println("refs from 28b50 BEFORE removal:");
    for (Reference r : rm.getReferencesFrom(from)) {
      boolean g = good.contains(r.getToAddress().getOffset());
      println(String.format("  %s %s src=%s op=%d %s", r.getToAddress(), r.getReferenceType(), r.getSource(), r.getOperandIndex(), g ? "GOOD" : "BAD"));
      if (!g && r.getReferenceType() == RefType.COMPUTED_JUMP) bad.add(r);
    }
    println("bad candidates: " + bad.size());
    for (Reference r : bad) {
      int others = 0;
      for (Reference x : rm.getReferencesTo(r.getToAddress())) if (!x.getFromAddress().equals(from)) others++;
      CodeUnit cu = currentProgram.getListing().getCodeUnitAt(r.getToAddress());
      println(String.format("  %s other-refs-to=%d target=%s", r.getToAddress(), others, cu));
    }
    int tx = currentProgram.startTransaction("remove bad computed jump refs from 28b50");
    boolean ok = false;
    try { for (Reference r : bad) rm.delete(r); ok = true; }
    finally { currentProgram.endTransaction(tx, ok); }
    println("refs from 28b50 AFTER removal:");
    for (Reference r : rm.getReferencesFrom(from)) println("  " + r.getToAddress() + " " + r.getReferenceType() + " " + r.getSource());
    DecompInterface di = new DecompInterface(); di.openProgram(currentProgram);
    Function f = currentProgram.getFunctionManager().getFunctionContaining(from);
    DecompileResults res = di.decompileFunction(f, 60, monitor);
    String c = res.decompileCompleted() ? res.getDecompiledFunction().getC() : "FAILED";
    println("decompile lines=" + c.split("\n").length + " switch=" + c.contains("switch") + " cases=" + (c.split("case \\d+:", -1).length - 1));
    println("program changed=" + currentProgram.isChanged() + " (NOT saved)");
  }
}