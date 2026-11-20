package h8539f;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import ghidra.app.services.AbstractAnalyzer;
import ghidra.app.services.AnalysisPriority;
import ghidra.app.services.AnalyzerType;
import ghidra.app.util.importer.MessageLog;
import ghidra.framework.options.Options;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.address.AddressSetView;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.listing.Program;
import ghidra.program.model.scalar.Scalar;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolIterator;
import ghidra.program.model.symbol.SymbolTable;
import ghidra.program.model.symbol.SymbolType;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.program.model.symbol.ReferenceManager;
import ghidra.program.model.symbol.RefType;
import ghidra.program.model.symbol.SourceType;
import ghidra.util.exception.CancelledException;
import ghidra.util.task.TaskMonitor;

/**
 * Finds calibration table and axis accesses made through the ROM's table helper
 * functions and resolves them to real flash addresses.
 *
 * The helpers take a far pointer as two literal word pushes: the OFFSET is pushed
 * first and the BANK last (so the bank is the push nearest the pjsr). Ghidra cannot
 * see this as a data reference, so tables and axes have no xrefs. This analyzer reads
 * each call site, builds bank*0x10000+offset, and (optionally) adds a DATA reference
 * from the call site to the data.
 *
 * Address model (see CHANGELOG 2026-11-20): the flash is ONE image, visible at
 * 0x10000-0x2FFFF, and page 0's 0x0000-0x3FFF is an alias of 0x10000-0x13FFF. A bank 0
 * pointer below 0x4000 is therefore normalised to 0x10000+offset so every access to the
 * same byte lands on one canonical address. Bank 0 offsets at or above 0xEE80 are
 * RAM/registers, not tables, and are ignored.
 *
 * SAFETY / SCOPE (v1):
 *   - Only call sites whose two pushes are literal immediates are resolved. If any
 *     non-immediate push sits between the pair and the call, the site is counted as
 *     "runtime" and left alone (never guessed).
 *   - References are only written when the option "Write references" is enabled
 *     (default OFF). With it off the analyzer only bookmarks and logs, so a first run
 *     is a dry run.
 *   - It never creates, renames or retypes anything else.
 *   - Table-to-axis pairing is only a hint (bookmark text): the nearest earlier
 *     axis_lookup_interp call in the same function. 60 tables were ambiguous in the
 *     16 Nov review, so no reference is made from that hint.
 *   - Constant-offset indexed reads (@(disp:16,Rn) with DP set) are NOT handled yet.
 */
public class H8EcuTableAnalyzer extends AbstractAnalyzer {

    private static final String NAME = "H8 ECU Table Access Analyzer";
    private static final String DESCRIPTION =
        "Resolves bank/offset literal pushes passed to the table lookup helpers into real "
            + "flash addresses (mirror-aware) and bookmarks, optionally referencing, each table and axis.";

    // Default helper entry points (RVR 21000011, verified in the live program). They are
    // overridable analyzer options so a different ROM can point at its own helpers.
    private static final long DEF_TABLE_LOOKUP_INTERP = 0x14656L;     // 2D interpolated
    private static final long DEF_AXIS_LOOKUP_INTERP = 0x14735L;
    private static final long DEF_TABLE_LOOKUP_INDEXED = 0x14854L;
    private static final long DEF_TABLE_READ_INDEXED = 0x14880L;
    private static final long DEF_TABLE_3AXIS_INTERP_TRIPLE = 0x148a2L; // 3D interpolated

    private static final String OPT_H_2D = "Helper address: 2D table lookup";
    private static final String OPT_H_AXIS = "Helper address: axis lookup";
    private static final String OPT_H_IDX = "Helper address: indexed table lookup";
    private static final String OPT_H_RIDX = "Helper address: indexed table read";
    private static final String OPT_H_3D = "Helper address: 3D table lookup";

    private long tableLookupInterp = DEF_TABLE_LOOKUP_INTERP;
    private long axisLookupInterp = DEF_AXIS_LOOKUP_INTERP;
    private long tableLookupIndexed = DEF_TABLE_LOOKUP_INDEXED;
    private long tableReadIndexed = DEF_TABLE_READ_INDEXED;
    private long table3axisInterpTriple = DEF_TABLE_3AXIS_INTERP_TRIPLE;

    private static final long FLASH_START = H8MemoryMap.FLASH_START;
    private static final long FLASH_END = H8MemoryMap.FLASH_END;
    private static final long MIRROR_END = H8MemoryMap.MIRROR_END;   // page 0 alias of 0x10000-0x13FFF
    private static final long RAM_START = H8MemoryMap.RAM_START;

    private static final int MAX_PUSH_WALK = 8;
    private static final int MAX_AXIS_WALK = 80;

    private static final String OPT_WRITE_REFS = "Write references";
    private static final String OPT_BOOKMARKS = "Add bookmarks";
    private static final String OPT_PTRARR = "Follow far-pointer arrays (map selectors)";
    private static final String OPT_STUBS = "Mark header-only table stubs";

    private boolean writeRefs = false;
    private boolean addBookmarks = true;
    private boolean followPtrArrays = false;
    private boolean markStubs = true;

    public H8EcuTableAnalyzer() {
        super(NAME, DESCRIPTION, AnalyzerType.FUNCTION_ANALYZER);
        // After function creation and the H8 stack analyzers, so call references exist.
        setPriority(AnalysisPriority.DATA_ANALYSIS.after());
        setDefaultEnablement(true);
    }

    @Override
    public boolean canAnalyze(Program program) {
        return program.getLanguage().getLanguageID().toString().toUpperCase().contains("H8539F");
    }

    @Override
    public void registerOptions(Options options, Program program) {
        options.registerOption(OPT_WRITE_REFS, writeRefs, null,
            "Add DATA references from each resolved call site to its table/axis. "
                + "Leave off for a dry run (bookmarks and log only).");
        options.registerOption(OPT_BOOKMARKS, addBookmarks, null,
            "Add a bookmark at each resolved call site.");
        options.registerOption(OPT_STUBS, markStubs, null,
            "Bookmark (H8Table/HeaderStub) and comment table descriptors that are immediately followed by another descriptor or a 0xFF terminator, so they are not mistaken for table data. Flash 0x10100-0x13FFF.");
        String helperHelp = " (hex, default is the Mitsubishi RVR 21000011 address; set to the matching helper in another ROM)";
        options.registerOption(OPT_H_2D, hex(DEF_TABLE_LOOKUP_INTERP), null, "Entry point of the 2D table lookup helper" + helperHelp);
        options.registerOption(OPT_H_AXIS, hex(DEF_AXIS_LOOKUP_INTERP), null, "Entry point of the axis lookup helper" + helperHelp);
        options.registerOption(OPT_H_IDX, hex(DEF_TABLE_LOOKUP_INDEXED), null, "Entry point of the indexed table lookup helper" + helperHelp);
        options.registerOption(OPT_H_RIDX, hex(DEF_TABLE_READ_INDEXED), null, "Entry point of the indexed table read helper" + helperHelp);
        options.registerOption(OPT_H_3D, hex(DEF_TABLE_3AXIS_INTERP_TRIPLE), null, "Entry point of the 3D table lookup helper" + helperHelp);
        options.registerOption(OPT_PTRARR, followPtrArrays, null,
            "Find arrays of 4-byte far pointers (bank 1/2 + offset) that point at table descriptors "
                + "(02 00 <ram> / 03 00 <ram> <ram>) and add DATA references from each slot, and from "
                + "every instruction that references a slot, to the table that slot selects. Code selects a map by "
                + "indexing such an array, so call sites never name the table directly. Off by default.");
    }

    @Override
    public void optionsChanged(Options options, Program program) {
        writeRefs = options.getBoolean(OPT_WRITE_REFS, writeRefs);
        addBookmarks = options.getBoolean(OPT_BOOKMARKS, addBookmarks);
        followPtrArrays = options.getBoolean(OPT_PTRARR, followPtrArrays);
        markStubs = options.getBoolean(OPT_STUBS, markStubs);
        tableLookupInterp = parseHex(options, OPT_H_2D, DEF_TABLE_LOOKUP_INTERP);
        axisLookupInterp = parseHex(options, OPT_H_AXIS, DEF_AXIS_LOOKUP_INTERP);
        tableLookupIndexed = parseHex(options, OPT_H_IDX, DEF_TABLE_LOOKUP_INDEXED);
        tableReadIndexed = parseHex(options, OPT_H_RIDX, DEF_TABLE_READ_INDEXED);
        table3axisInterpTriple = parseHex(options, OPT_H_3D, DEF_TABLE_3AXIS_INTERP_TRIPLE);
    }

    private static String hex(long v) {
        return String.format("0x%x", v);
    }

    private static long parseHex(Options options, String name, long def) {
        String s = options.getString(name, hex(def));
        try {
            String t = s.trim().toLowerCase();
            return t.startsWith("0x") ? Long.parseLong(t.substring(2), 16) : Long.parseLong(t, 16);
        }
        catch (NumberFormatException e) {
            return def;   // bad text: keep the default rather than guess
        }
    }

    private static final class Kind {
        final long entry;
        final String label;
        final boolean isAxis;
        Kind(long entry, String label, boolean isAxis) {
            this.entry = entry;
            this.label = label;
            this.isAxis = isAxis;
        }
    }

    @Override
    public boolean added(Program program, AddressSetView set, TaskMonitor monitor, MessageLog log)
            throws CancelledException {

        Kind[] kinds = {
            new Kind(tableLookupInterp, "2D table", false),
            new Kind(table3axisInterpTriple, "3D table", false),
            new Kind(tableLookupIndexed, "indexed table", false),
            new Kind(tableReadIndexed, "indexed table read", false),
            new Kind(axisLookupInterp, "axis", true),
        };

        Listing listing = program.getListing();
        ReferenceManager refMgr = program.getReferenceManager();
        int resolved = 0, runtime = 0, outOfRange = 0, refsAdded = 0, sites = 0, helpersMissing = 0;

        for (Kind k : kinds) {
            monitor.checkCancelled();
            Address entry = toAddr(program, k.entry);
            if (entry == null || program.getFunctionManager().getFunctionAt(entry) == null) {
                helpersMissing++;
                log.appendMsg(NAME, String.format(
                    "helper at 0x%x (%s) not found as a function - skipped", k.entry, k.label));
                continue;
            }
            List<Address> callSites = new ArrayList<>();
            ReferenceIterator it = refMgr.getReferencesTo(entry);
            while (it.hasNext()) {
                Reference r = it.next();
                if (r.getReferenceType().isCall()) {
                    callSites.add(r.getFromAddress());
                }
            }
            for (Address from : callSites) {
                monitor.checkCancelled();
                sites++;
                Instruction call = listing.getInstructionAt(from);
                if (call == null) {
                    continue;
                }
                long[] pair = readPushPair(call);
                if (pair == null) {
                    runtime++;
                    continue;
                }
                long bank = pair[0];
                long offset = pair[1];
                long flat = canonical(bank, offset);
                if (flat < 0) {
                    outOfRange++;
                    continue;
                }
                Address target = toAddr(program, flat);
                if (target == null || !program.getMemory().contains(target)) {
                    outOfRange++;
                    continue;
                }
                resolved++;

                String note = String.format("%s @0x%x (bank %d, offset 0x%04x)",
                    k.label, flat, bank, offset);
                if (!k.isAxis) {
                    String axis = nearestAxis(program, call);
                    if (axis != null) {
                        note += "; nearest earlier axis call: " + axis;
                    }
                }
                if (addBookmarks) {
                    program.getBookmarkManager().setBookmark(from, "H8Table", k.isAxis ? "Axis" : "Table", note);
                }
                if (writeRefs && !hasRef(refMgr, from, target)) {
                    refMgr.addMemoryReference(from, target, RefType.DATA, SourceType.ANALYSIS, 0);
                    refsAdded++;
                }
            }
        }

        if (followPtrArrays) {
            int[] pa = followPointerArrays(program, monitor);
            log.appendMsg(NAME, String.format(
                "far-pointer arrays=%d slots=%d (table-start entries %d) slot refs added=%d code refs added=%d",
                pa[0], pa[1], pa[2], pa[3], pa[4]));
        }

        if (markStubs) {
            log.appendMsg(NAME, "header-only table stubs marked=" + markHeaderStubs(program, monitor));
        }

        log.appendMsg(NAME, String.format(
            "call sites=%d resolved=%d runtime(non-literal)=%d out-of-range=%d refs added=%d%s%s",
            sites, resolved, runtime, outOfRange, refsAdded,
            writeRefs ? "" : " (dry run: Write references is off)",
            helpersMissing > 0 ? " helpers missing=" + helpersMissing : ""));
        return true;
    }






    /** Bank/offset to one canonical flash address, or -1 if not a flash table pointer. */
    static long canonical(long bank, long offset) {
        long flat = (bank & 0xffL) * 0x10000L + (offset & 0xffffL);
        if (bank == 0) {
            if (offset < MIRROR_END + 1) {
                return FLASH_START + offset;   // page 0 alias of flash page 1
            }
            return -1;                         // missing area or RAM/registers
        }
        if (flat >= FLASH_START && flat <= FLASH_END) {
            return flat;
        }
        return -1;
    }

    /**
     * Walks back from the call over literal word pushes. The push nearest the call is the
     * bank, the one before it the offset. Returns {bank, offset}, or null if a
     * non-literal push, a flow change, or the walk limit is hit first.
     */
    private static long[] readPushPair(Instruction call) {
        long[] vals = new long[2];
        int found = 0;
        Instruction cur = call.getPrevious();
        for (int step = 0; cur != null && step < MAX_PUSH_WALK; step++, cur = cur.getPrevious()) {
            if (cur.getFlowType().isCall() || cur.getFlowType().isJump()
                    || cur.getFlowType().isTerminal()) {
                return null;
            }
            String s = cur.toString();
            if (s.endsWith(",@-SP")) {
                Scalar sc = cur.getScalar(0);
                if (sc == null) {
                    return null;                // pushes a register or memory value
                }
                vals[found++] = sc.getUnsignedValue();
                if (found == 2) {
                    // vals[0] = nearest = bank, vals[1] = offset
                    return new long[] { vals[0], vals[1] };
                }
            }
        }
        return null;
    }

    private String nearestAxis(Program program, Instruction tableCall) {
        Function fn = program.getFunctionManager().getFunctionContaining(tableCall.getAddress());
        if (fn == null) {
            return null;
        }
        Address axisEntry = toAddr(program, axisLookupInterp);
        Instruction cur = tableCall.getPrevious();
        for (int step = 0; cur != null && step < MAX_AXIS_WALK; step++, cur = cur.getPrevious()) {
            if (cur.getAddress().compareTo(fn.getEntryPoint()) < 0) {
                break;
            }
            if (!cur.getFlowType().isCall()) {
                continue;
            }
            boolean toAxis = false;
            for (Reference r : cur.getReferencesFrom()) {
                if (r.getToAddress().equals(axisEntry)) {
                    toAxis = true;
                }
            }
            if (!toAxis) {
                continue;
            }
            long[] pair = readPushPair(cur);
            if (pair == null) {
                return null;
            }
            long flat = canonical(pair[0], pair[1]);
            return flat < 0 ? null : String.format("0x%x", flat);
        }
        return null;
    }

    private static long readBE(ghidra.program.model.mem.Memory mem, Address a, int n) {
        if (a == null) {
            return -1;
        }
        try {
            long v = 0;
            for (int i = 0; i < n; i++) {
                v = (v << 8) | (mem.getByte(a.add(i)) & 0xffL);
            }
            return v;
        }
        catch (Exception e) {
            return -1;
        }
    }

    /** Table descriptor: 02 00 <ram ptr> (2D), 03 00 <ram ptr> <ram ptr> <cols> (3D) or 03 14 <ram ptr> <ram ptr> <cols> (indexed 3D, e.g. ignition maps). */
    private boolean looksLikeTable(Program program, long flat) {
        Address a = toAddr(program, flat);
        ghidra.program.model.mem.Memory mem = program.getMemory();
        long b0 = readBE(mem, a, 1);
        long b1 = a == null ? -1 : readBE(mem, a.add(1), 1);
        long p = a == null ? -1 : readBE(mem, a.add(2), 2);
        return ((b0 == 2 && b1 == 0) || (b0 == 3 && (b1 == 0 || b1 == 0x14))) && p >= RAM_START;
    }

    /** Descriptor incl. the 02 28 variant; returns header length (4 for 2D, 7 for 3D) or 0. */
    private int headerLen(Program program, long flat) {
        Address a = toAddr(program, flat);
        if (a == null) {
            return 0;
        }
        ghidra.program.model.mem.Memory mem = program.getMemory();
        long b0 = readBE(mem, a, 1);
        long b1 = readBE(mem, a.add(1), 1);
        long p = readBE(mem, a.add(2), 2);
        if (p < RAM_START || p >= 0xff00) {
            return 0;
        }
        if (b0 == 2 && (b1 == 0 || b1 == 0x28)) {
            return 4;
        }
        if (b0 == 3 && (b1 == 0 || b1 == 0x14)) {
            long q = readBE(mem, a.add(4), 2);
            return (q >= RAM_START && q < 0xff00) ? 7 : 0;
        }
        return 0;
    }

    /** A descriptor directly followed by another descriptor or a 0xFF terminator has no data: it is a stub, not a table. */
    private int markHeaderStubs(Program program, TaskMonitor monitor) throws CancelledException {
        int n = 0;
        ghidra.program.model.mem.Memory mem = program.getMemory();
        for (long f = 0x10100; f < 0x14000; f++) {
            if ((f & 0xfff) == 0) {
                monitor.checkCancelled();
            }
            int hl = headerLen(program, f);
            if (hl == 0) {
                continue;
            }
            long d = f + hl;
            Address da = toAddr(program, d);
            if (da == null) {
                continue;
            }
            if (headerLen(program, d) == 0 && readBE(mem, da, 1) != 0xff) {
                f += hl - 1;
                continue;
            }
            Address a = toAddr(program, f);
            try {
                program.getBookmarkManager().setBookmark(a, "H8Table", "HeaderStub",
                    "table descriptor with no data (followed by another descriptor or 0xFF)");
                if (program.getListing().getComment(ghidra.program.model.listing.CodeUnit.EOL_COMMENT, a) == null) {
                    program.getListing().setComment(a, ghidra.program.model.listing.CodeUnit.EOL_COMMENT,
                        "header-only stub, no table data");
                }
                n++;
            }
            catch (Exception e) {
                // ignore addresses that cannot take a bookmark/comment
            }
            f += hl - 1;
        }
        return n;
    }
    /**
     * Map-selector arrays: runs of 4-byte far pointers (bank word 1 or 2, then offset) in flash,
     * mostly pointing at table descriptors. Code indexes into the array to pick a map, so the call
     * site never names the table. Adds a DATA reference from each slot to its table, and from each
     * instruction that references the array to every distinct table in it.
     * Result: {arrays, slots, table-start slots, slot refs added, code refs added}.
     */
    private int[] followPointerArrays(Program program, TaskMonitor monitor) throws CancelledException {
        ghidra.program.model.mem.Memory mem = program.getMemory();
        Listing listing = program.getListing();
        ReferenceManager rm = program.getReferenceManager();
        int arrays = 0, slots = 0, tableSlots = 0, slotRefs = 0, codeRefs = 0;
        long off = FLASH_START;
        while (off < FLASH_END - 3) {
            monitor.checkCancelled();
            Address start = toAddr(program, off);
            if (start == null || !mem.contains(start) || listing.getInstructionAt(start) != null) {
                off += 2;
                continue;
            }
            int len = 0, starts = 0;
            java.util.Set<Long> targets = new java.util.TreeSet<>();
            while (true) {
                long slot = off + 4L * len;
                if (slot + 3 > FLASH_END) {
                    break;
                }
                long v = readBE(mem, toAddr(program, slot), 4);
                long hi = v >>> 16;
                if (v < 0 || (hi != 1 && hi != 2) || v < FLASH_START + 0x100 || v >= FLASH_END - 0xf) {
                    break;
                }
                targets.add(v);
                if (looksLikeTable(program, v)) {
                    starts++;
                }
                len++;
            }
            if (len < 4 || starts * 10 < len * 4) {
                off += 2;
                continue;
            }
            arrays++;
            slots += len;
            tableSlots += starts;
            if (addBookmarks) {
                program.getBookmarkManager().setBookmark(start, "H8Table", "PtrArray",
                    String.format("far-pointer array: %d slots, %d distinct tables", len, targets.size()));
            }
            if (program.getSymbolTable().getPrimarySymbol(start) == null) {
                try {
                    program.getSymbolTable().createLabel(start, String.format("ptr_array_%05x", off),
                        SourceType.ANALYSIS);
                }
                catch (Exception e) {
                    // label is cosmetic
                }
            }

            for (int i = 0; i < len; i++) {
                Address slotAddr = toAddr(program, off + 4L * i);
                Address tgt = toAddr(program, readBE(mem, slotAddr, 4));
                if (tgt != null && !hasRef(rm, slotAddr, tgt)) {
                    rm.addMemoryReference(slotAddr, tgt, RefType.DATA, SourceType.ANALYSIS, 0);
                    slotRefs++;
                }
                ReferenceIterator it = rm.getReferencesTo(slotAddr);
                while (it.hasNext()) {
                    Reference r = it.next();
                    Instruction in = listing.getInstructionAt(r.getFromAddress());
                    if (in == null) {
                        continue;
                    }
                    // the instruction names this slot (e.g. #0xcefe = start of a group), so it
                    // selects the table that slot points at - not every table in the array
                    if (tgt != null && !hasRef(rm, r.getFromAddress(), tgt)) {
                        rm.addMemoryReference(r.getFromAddress(), tgt, RefType.DATA, SourceType.ANALYSIS, 0);
                        codeRefs++;
                    }
                }
            }
            off += 4L * len;
        }
        return new int[] { arrays, slots, tableSlots, slotRefs, codeRefs };
    }

    private static boolean hasRef(ReferenceManager refMgr, Address from, Address to) {
        for (Reference r : refMgr.getReferencesFrom(from)) {
            if (r.getToAddress().equals(to)) {
                return true;
            }
        }
        return false;
    }

    private static Address toAddr(Program program, long flat) {
        try {
            return program.getAddressFactory().getDefaultAddressSpace().getAddress(flat);
        }
        catch (Exception e) {
            return null;
        }
    }
}
