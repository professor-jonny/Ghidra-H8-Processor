import ghidra.app.script.GhidraScript;
import ghidra.program.model.symbol.*;
import ghidra.program.model.listing.*;
import java.util.*;
public class ProgStats2 extends GhidraScript {
  public void run() throws Exception {
    SymbolTable st = currentProgram.getSymbolTable();
    int fn=0, fnNamed=0, lbl=0, lblUser=0, tblNamed=0;
    for (Function f : currentProgram.getFunctionManager().getFunctions(true)) { fn++; if (!f.getName().startsWith("FUN_")) fnNamed++; }
    SymbolIterator it = st.getAllSymbols(true);
    List<String> ex = new ArrayList<>();
    while (it.hasNext()) { Symbol s = it.next(); if (s.getSymbolType()==SymbolType.LABEL) { lbl++; if (s.getSource()==SourceType.USER_DEFINED) { lblUser++; long o=s.getAddress().getOffset(); if (o>=0x10000 && o<0x30000 && ex.size()<30) ex.add(Long.toHexString(o)+" "+s.getName()); } } }
    println("PROG="+currentProgram.getName()+" lang="+currentProgram.getLanguageID()+" fns="+fn+" namedFns="+fnNamed+" labels="+lbl+" userLabels="+lblUser+" blocks="+currentProgram.getMemory().getBlocks().length);
    for (String e : ex) println("  "+e);
  }
}