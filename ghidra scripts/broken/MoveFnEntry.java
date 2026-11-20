import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.data.*;
import ghidra.app.cmd.function.CreateFunctionCmd;
import ghidra.app.decompiler.*;
import java.util.*;

public class MoveFnEntry extends GhidraScript {
  public void run() throws Exception {
    AddressSpace sp = currentProgram.getAddressFactory().getDefaultAddressSpace();
    Listing lst = currentProgram.getListing();
    FunctionManager fm = currentProgram.getFunctionManager();
    Address a1 = sp.getAddress(0x20461), a2 = sp.getAddress(0x20462);
    Function old = fm.getFunctionAt(a1);
    if (old == null) { println("no function at 20461, abort"); return; }
    if (fm.getFunctionAt(a2) != null) { println("function already at 20462, abort"); return; }
    String name = old.getName();
    String cc = old.getCallingConventionName();
    DataType ret = old.getReturn().getDataType();
    boolean custom = old.hasCustomVariableStorage();
    Parameter[] ps = old.getParameters();
    println("old fn: " + name + " body " + old.getBody().getMinAddress() + ".." + old.getBody().getMaxAddress() + " cc=" + cc + " ret=" + ret.getName() + " customStorage=" + custom + " params=" + ps.length);
    for (Parameter p : ps) println("  param " + p.getName() + " " + p.getDataType().getName() + " " + p.getVariableStorage());
    int[] kinds = {CodeUnit.PLATE_COMMENT, CodeUnit.PRE_COMMENT, CodeUnit.EOL_COMMENT, CodeUnit.POST_COMMENT, CodeUnit.REPEATABLE_COMMENT};
    String[] cm = new String[kinds.length];
    for (int k = 0; k < kinds.length; k++) { cm[k] = lst.getComment(kinds[k], a1); if (cm[k] != null) println("comment[" + k + "] @20461: " + cm[k].replace("\n", " | ")); }
    String fcomment = old.getComment();
    String frep = old.getRepeatableComment();
    println("function comment: " + fcomment + " / repeatable: " + frep);
    List<Parameter> keep = new ArrayList<Parameter>();
    for (Parameter p : ps) keep.add(new ParameterImpl(p.getName(), p.getDataType(), p.getVariableStorage(), currentProgram));
    int tx = currentProgram.startTransaction("move function entry 20461 -> 20462");
    boolean ok = false;
    try {
      fm.removeFunction(a1);
      CreateFunctionCmd cmd = new CreateFunctionCmd(name, a2, null, SourceType.USER_DEFINED);
      if (!cmd.applyTo(currentProgram)) throw new RuntimeException("create failed: " + cmd.getStatusMsg());
      Function nf = fm.getFunctionAt(a2);
      if (nf == null) throw new RuntimeException("no function after create");
      if (cc != null) { try { nf.setCallingConvention(cc); } catch (Exception e) { println("cc not set: " + e); } }
      if (custom || !keep.isEmpty()) {
        nf.updateFunction(cc, new ReturnParameterImpl(ret, currentProgram), keep,
            custom ? FunctionUpdateType.CUSTOM_STORAGE : FunctionUpdateType.DYNAMIC_STORAGE_ALL_PARAMS, true, SourceType.USER_DEFINED);
      }
      for (int k = 0; k < kinds.length; k++) {
        if (cm[k] != null) { lst.setComment(a2, kinds[k], cm[k]); lst.setComment(a1, kinds[k], null); }
      }
      if (fcomment != null) nf.setComment(fcomment);
      if (frep != null) nf.setRepeatableComment(frep);
      ok = true;
    } finally { currentProgram.endTransaction(tx, ok); }
    Function nf = fm.getFunctionAt(a2);
    println("new fn: " + nf + " body " + (nf == null ? "" : nf.getBody().getMinAddress() + ".." + nf.getBody().getMaxAddress()));
    if (nf != null) {
      println("sig: " + nf.getPrototypeString(true, true));
      for (Reference r : getReferencesTo(a2)) println("  caller ref " + r.getFromAddress() + " " + r.getReferenceType());
      DecompInterface di = new DecompInterface(); di.openProgram(currentProgram);
      DecompileResults res = di.decompileFunction(nf, 60, monitor);
      println("decompile ok=" + res.decompileCompleted());
      if (res.decompileCompleted()) println(res.getDecompiledFunction().getC());
    }
    println("symbols @20461: " + Arrays.toString(currentProgram.getSymbolTable().getSymbols(a1)));
    println("program changed=" + currentProgram.isChanged() + " (NOT saved)");
  }
}