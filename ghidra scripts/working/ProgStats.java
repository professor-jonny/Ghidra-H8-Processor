import ghidra.app.script.GhidraScript;
import ghidra.program.model.symbol.*;
import ghidra.program.model.listing.*;
import java.util.*;
public class ProgStats extends GhidraScript {
  public void run() throws Exception {
    SymbolTable st = currentProgram.getSymbolTable();
    int fn=0, fnNamed=0, lbl=0, lblUser=0, mem=0;
    for (Function f : currentProgram.getFunctionManager().getFunctions(true)) { fn++; if (!f.getName().startsWith("FUN_")) fnNamed++; }
    SymbolIterator it = st.getAllSymbols(true);
    while (it.hasNext()) { Symbol s = it.next(); if (s.getSymbolType()==SymbolType.LABEL) { lbl++; if (s.getSource()==SourceType.USER_DEFINED) lblUser++; } }
    println("PROG="+currentProgram.getName()+" fns="+fn+" namedFns="+fnNamed+" labels="+lbl+" userLabels="+lblUser);
    int c=0; it = st.getAllSymbols(true);
    while (it.hasNext() && c<25) { Symbol s = it.next(); if (s.getSource()==SourceType.USER_DEFINED && s.getSymbolType()==SymbolType.LABEL && s.getAddress().getOffset()>=0x10000 && s.getAddress().getOffset()<0x30000) { println("  "+Long.toHexString(s.getAddress().getOffset())+" "+s.getName()); c++; } }
  }
}