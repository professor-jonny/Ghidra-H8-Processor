import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.mem.*;
import java.util.*;

public class BankProbe4 extends GhidraScript {
  void dump(long a) throws Exception {
    Address ad = toAddr(a);
    byte[] b = new byte[8];
    currentProgram.getMemory().getBytes(ad, b);
    StringBuilder sb = new StringBuilder();
    for (byte x : b) sb.append(String.format("%02x ", x));
    Symbol[] ss = currentProgram.getSymbolTable().getSymbols(ad);
    StringBuilder sy = new StringBuilder();
    for (Symbol s : ss) sy.append(s.getName()).append(" ");
    ReferenceIterator ri = currentProgram.getReferenceManager().getReferencesTo(ad);
    List<String> refs = new ArrayList<>();
    while (ri.hasNext()) { Reference r = ri.next(); refs.add(r.getFromAddress() + "(" + r.getReferenceType() + ")"); }
    println(String.format("0x%x bytes=%s symbols=[%s] refsTo=%s", a, sb, sy, refs));
  }
  public void run() throws Exception {
    dump(0x2c1L);
    dump(0x102c1L);
    // Symbols named cal_* by page
    int p0 = 0, p1 = 0, p2 = 0, other = 0, total = 0;
    SymbolIterator si = currentProgram.getSymbolTable().getAllSymbols(true);
    while (si.hasNext()) {
      Symbol s = si.next();
      if (!s.getName().startsWith("cal_")) continue;
      total++;
      long off = s.getAddress().getOffset();
      if (off < 0x10000) p0++; else if (off < 0x20000) p1++; else if (off < 0x30000) p2++; else other++;
    }
    println("cal_* symbols: total=" + total + " page0=" + p0 + " page1=" + p1 + " page2=" + p2 + " other=" + other);
    // Memory blocks
    for (MemoryBlock mb : currentProgram.getMemory().getBlocks())
      println("block " + mb.getName() + " " + mb.getStart() + "-" + mb.getEnd() + " init=" + mb.isInitialized());
  }
}