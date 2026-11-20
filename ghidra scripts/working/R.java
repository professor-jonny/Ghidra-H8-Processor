import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.*;
import ghidra.program.model.pcode.*;
import ghidra.program.model.lang.*;
import java.util.*;
public class R extends GhidraScript {
  long spOff;
  Map<Varnode,String> memo = new HashMap<Varnode,String>();
  Long cst(Varnode v){
    if (v.isConstant()) return v.getOffset();
    PcodeOp d = v.getDef();
    if (d != null && (d.getOpcode()==PcodeOp.INT_SEXT || d.getOpcode()==PcodeOp.COPY) && d.getInput(0).isConstant()) {
      long x = d.getInput(0).getOffset();
      if (d.getOpcode()==PcodeOp.INT_SEXT && d.getInput(0).getSize()==1) x = (byte)x;
      return x;
    }
    return null;
  }
  String ev(Varnode v, int depth){
    if (depth > 200) return "deep";
    PcodeOp d = v.getDef();
    if (d == null) return v.isRegister() && v.getOffset()==spOff ? "0" : "?in";
    int oc = d.getOpcode();
    if (oc == PcodeOp.INT_SUB || oc == PcodeOp.INT_ADD) {
      Long c = cst(d.getInput(1));
      String b = ev(d.getInput(0), depth+1);
      if (c == null) return "?c";
      if (b.startsWith("?") || b.contains("|")) return b + (oc==PcodeOp.INT_SUB?"-":"+") + c;
      long bv = Long.parseLong(b);
      return Long.toString(oc==PcodeOp.INT_SUB ? bv-c : bv+c);
    }
    if (oc == PcodeOp.INDIRECT) {
      String b = ev(d.getInput(0), depth+1);
      if (b.startsWith("?") || b.contains("|")) return b + "+ind";
      return Long.toString(Long.parseLong(b) + 4);
    }
    if (oc == PcodeOp.MULTIEQUAL) {
      StringBuilder sb = new StringBuilder();
      Set<String> s = new LinkedHashSet<String>();
      for (int i=0;i<d.getNumInputs();i++) s.add(ev(d.getInput(i), depth+1));
      for (String x : s) { if (sb.length()>0) sb.append("|"); sb.append(x); }
      return sb.toString();
    }
    if (oc == PcodeOp.COPY) return "COPY(" + d.getInput(0).toString(currentProgram.getLanguage()) + ")";
    return "?" + d.getMnemonic();
  }
  public void run() throws Exception {
    Language lang = currentProgram.getLanguage();
    spOff = lang.getRegister("SP").getAddress().getOffset();
    Function f = getFunctionAt(toAddr(0x14656));
    DecompInterface di = new DecompInterface();
    di.openProgram(currentProgram);
    di.setSimplificationStyle("firstpass");
    HighFunction hf = di.decompileFunction(f, 60, monitor).getHighFunction();
    List<PcodeOpAST> ops = new ArrayList<PcodeOpAST>();
    Iterator<PcodeOpAST> it = hf.getPcodeOps();
    while (it.hasNext()) ops.add(it.next());
    Collections.sort(ops, new Comparator<PcodeOpAST>() {
      public int compare(PcodeOpAST a, PcodeOpAST b) {
        int c = a.getSeqnum().getTarget().compareTo(b.getSeqnum().getTarget());
        return c != 0 ? c : Integer.compare(a.getSeqnum().getTime(), b.getSeqnum().getTime());
      }});
    println("SP value AFTER each SP write, relative to entry SP (INDIRECT modelled as +4)");
    for (PcodeOpAST op : ops) {
      Varnode o = op.getOutput();
      if (o == null || !o.isRegister() || o.getOffset() != spOff) continue;
      long a = op.getSeqnum().getTarget().getOffset();
      if (a < 0x146c0 || a > 0x14734) continue;
      println(String.format("  %s.%d %-10s SP=%s", op.getSeqnum().getTarget(), op.getSeqnum().getTime(), op.getMnemonic(), ev(o, 0)));
    }
  }
}