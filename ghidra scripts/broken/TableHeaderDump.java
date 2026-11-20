import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.*;
import ghidra.program.model.mem.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;

public class TableHeaderDump extends GhidraScript {
  @Override
  public void run() throws Exception {
    println("changed=" + currentProgram.isChanged());
    BookmarkManager bm = currentProgram.getBookmarkManager();
    Map<String,Integer> cnt = new TreeMap<>();
    Map<String,List<String>> samp = new TreeMap<>();
    var it = bm.getBookmarksIterator();
    while (it.hasNext()) {
      Bookmark b = it.next();
      String k = b.getTypeString() + " / " + b.getCategory();
      cnt.merge(k, 1, Integer::sum);
      List<String> l = samp.computeIfAbsent(k, x -> new ArrayList<>());
      if (l.size() < 2) l.add(b.getAddress() + ": " + b.getComment());
    }
    println("bookmarks by type/category:");
    for (var e : cnt.entrySet()) println("  " + e.getValue() + "  " + e.getKey() + "   e.g. " + samp.get(e.getKey()));

    Set<Long> targets = new TreeSet<>();
    List<String> lines = Files.readAllLines(Paths.get(System.getProperty("user.home"), "ghidra_scripts", "table_call_sites.csv"));
    for (String ln : lines) {
      String[] p = ln.split(",");
      if (p.length >= 7 && p[0].equals("table_lookup_interp") && p[5].startsWith("0x")) targets.add(Long.decode(p[5]));
    }
    long[] sel = {0x1288a,0x12896,0x128a2,0x128ae,0x119b8,0x11bc0,0x1264a,0x127be,0x11cea,0x11880,0x11d62,0x11d6e,0x11d58,0x11d5a,0x120d2,0x12230,0x1238e};
    for (long s : sel) targets.add(s);
    println("unique table targets (interp call sites + selector entries): " + targets.size());
    Memory mem = currentProgram.getMemory();
    Map<Integer,Integer> b0 = new TreeMap<>(), b1 = new TreeMap<>();
    int ramPtr = 0, withBm = 0;
    for (long t : targets) {
      byte[] buf = new byte[12];
      Address a = toAddr(t);
      int got = 0;
      try { got = mem.getBytes(a, buf); } catch (Exception e) { }
      StringBuilder sb = new StringBuilder();
      for (int i = 0; i < got; i++) sb.append(String.format("%02x", buf[i] & 0xff)).append(i == 1 || i == 3 || i == 5 ? "." : "");
      int w2 = ((buf[2] & 0xff) << 8) | (buf[3] & 0xff);
      b0.merge(buf[0] & 0xff, 1, Integer::sum);
      b1.merge(buf[1] & 0xff, 1, Integer::sum);
      if (w2 >= 0xf000) ramPtr++;
      StringBuilder bms = new StringBuilder();
      for (Bookmark b : bm.getBookmarks(a)) { bms.append("[" + b.getCategory() + ": " + b.getComment() + "]"); }
      if (bms.length() > 0) withBm++;
      Data d = getDataAt(a);
      String dt = d == null ? "" : " data=" + d.getDataType().getName();
      Symbol sy = currentProgram.getSymbolTable().getPrimarySymbol(a);
      println(String.format("0x%05x %s%s %s %s", t, sb, dt, sy == null ? "" : sy.getName(), bms));
    }
    println("byte0 histogram: " + b0);
    println("byte1 histogram: " + b1);
    println("targets whose word at +2 is >= 0xf000 (RAM index-cell pointer?): " + ramPtr + " of " + targets.size() + "; with a bookmark on the address: " + withBm);
  }
}
