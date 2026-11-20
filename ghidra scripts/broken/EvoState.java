import ghidra.app.script.GhidraScript;
import ghidra.framework.model.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.address.*;
import java.util.*;
public class EvoState extends GhidraScript {
  public void run() throws Exception {
    DomainFile df = state.getProject().getProjectData().getRootFolder().getFile("22580006_EVO5_Stock.hex");
    Program evo = (Program) df.getReadOnlyDomainObject(this, DomainFile.DEFAULT_VERSION, monitor);
    try {
      println("lang="+evo.getLanguageID()+" compiler="+evo.getCompilerSpec().getCompilerSpecID());
      for (MemoryBlock b : evo.getMemory().getBlocks()) println("block "+b.getName()+" "+b.getStart()+"-"+b.getEnd()+" init="+b.isInitialized());
      ghidra.program.model.lang.Register dp = evo.getRegister("DP");
      if (dp!=null) { Address a = evo.getMinAddress(); println("DP default ctx at min: "+evo.getProgramContext().getValue(dp, evo.getFunctionManager().getFunctions(true).next().getEntryPoint(), false)); }
      // user labels in flash (>=0x10000), classified by prefix
      Map<String,Integer> pre = new TreeMap<>(); List<String> sample = new ArrayList<>(); int n=0;
      SymbolIterator it = evo.getSymbolTable().getAllSymbols(true);
      while (it.hasNext()) { Symbol s=it.next(); long o=s.getAddress().getOffset(); if (s.getSymbolType()!=SymbolType.LABEL || s.getSource()!=SourceType.USER_DEFINED) continue;
        if (o<0x10000L && o>=0xEE80L) continue; n++; String nm=s.getName(); String p=nm.length()>6?nm.substring(0,6):nm; pre.merge(p,1,Integer::sum);
        if (sample.size()<30 && !nm.startsWith("MUT_")) sample.add(Long.toHexString(o)+" "+nm+" ["+s.getAddress().getAddressSpace().getName()+"]"); }
      println("non-RAM user labels="+n);
      println("top prefixes: "+pre);
      for (String s : sample) println("  "+s);
      println("refs total="+evo.getReferenceManager().getReferenceCountFromAndTo ); 
    } catch (Throwable t) { println("ERR "+t); } finally { evo.release(this); }
  }
}