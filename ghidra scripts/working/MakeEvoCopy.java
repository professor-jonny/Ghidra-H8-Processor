import ghidra.app.script.GhidraScript;
import ghidra.framework.model.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.lang.Register;
import ghidra.program.model.address.*;
import ghidra.program.model.mem.*;
import java.util.*;
public class MakeEvoCopy extends GhidraScript {
  public void run() throws Exception {
    DomainFolder root = state.getProject().getProjectData().getRootFolder();
    DomainFile src = root.getFile("22580006_EVO5_Stock.hex");
    DomainFile cp = root.getFile("EVO5_dp0_work");
    if (cp == null) { cp = src.copyTo(root, monitor); cp.setName("EVO5_dp0_work"); }
    println("copy file: "+cp.getName());
    Program p = (Program) cp.getDomainObject(this, true, false, monitor);
    int tx = p.startTransaction("dp0+mirror");
    try {
      AddressSpace sp = p.getAddressFactory().getDefaultAddressSpace();
      Register dp = p.getProgramContext().getRegister("DP");
      p.getProgramContext().remove(sp.getAddress(0x10000L), sp.getAddress(0x2FFFFL), dp);
      if (p.getMemory().getBlock("page0_mirror")==null) {
        MemoryBlock mb = p.getMemory().createByteMappedBlock("page0_mirror", sp.getAddress(0L), sp.getAddress(0x10000L), 0x4000, false);
        mb.setRead(true); mb.setWrite(true); mb.setExecute(true);
      }
      // drop stale analysis refs into low memory created under DP=1
      ghidra.program.model.symbol.ReferenceManager rm = p.getReferenceManager(); int del=0;
      List<ghidra.program.model.symbol.Reference> d = new ArrayList<>();
      ghidra.program.model.symbol.ReferenceIterator it = rm.getReferenceIterator(p.getMinAddress());
      while (it.hasNext()) { ghidra.program.model.symbol.Reference r = it.next();
        if (r.getSource()==ghidra.program.model.symbol.SourceType.ANALYSIS && r.getReferenceType()==ghidra.program.model.symbol.RefType.DATA && r.getToAddress().getOffset()<0x30000L) d.add(r); }
      for (ghidra.program.model.symbol.Reference r : d) rm.delete(r);
      println("deleted stale analysis DATA refs: "+d.size());
      p.endTransaction(tx, true);
    } catch (Throwable t) { p.endTransaction(tx, false); println("ERR "+t); }
    p.save("dp0+mirror", monitor); p.release(this);
    println("saved");
  }
}