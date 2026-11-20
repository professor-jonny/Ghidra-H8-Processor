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
public class H8TableAnalyzer extends AbstractAnalyzer {

    private static final String NAME = "H8 Table Access Analyzer";
    private static final String DESCRIPTION =
        "Resolves bank/offset literal pushes passed to the table lookup helpers into real "
            + "flash addresses (mirror-aware) and bookmarks, optionally referencing, each table and axis.";

    // Helper entry points in RVR 21000011 (verified in the live program).
    private static final long TABLE_LOOKUP_INTERP = 0x14656L;     // 2D interpolated
    private static final long AXIS_LOOKUP_INTERP = 0x14735L;
    private static final long TABLE_LOOKUP_INDEXED = 0x14854L;
    private static final long TABLE_READ_INDEXED = 0x14880L;
    private static final long TABLE_3AXIS_INTERP_TRIPLE = 0x148a2L; // 3D interpolated

    private static final long FLASH_START = 0x10000L;
    private static final long FLASH_END = 0x2ffffL;
    private static final long MIRROR_END = 0x3fffL;   // page 0 alias of 0x10000-0x13FFF
    private static final long RAM_START = 0xee80L;

    private static final int MAX_PUSH_WALK = 8;
    private static final int MAX_AXIS_WALK = 80;

    private static final String OPT_WRITE_REFS = "Write references";
    private static final String OPT_BOOKMARKS = "Add bookmarks";
    private static final String OPT_OPERAND_REFS = "DP-aware operand references";
    private static final String OPT_MIRROR_LABELS = "Mirror labels";
    private static final String OPT_SPURIOUS = "Remove spurious constant references";
    private static final String OPT_PTRARR = "Follow far-pointer arrays (map selectors)";
    private static final String OPT_STUBS = "Mark header-only table stubs";
    private static final String MIRROR_BLOCK = "page0_mirror";
    private static final Pattern ABS_OPERAND =
        Pattern.compile("@(?:\\()?0x([0-9a-fA-F]+):16(?:,R[0-7]\\))?");
    private static final Pattern LDC_DP =
        Pattern.compile("ldc\\.b\\s+(?:0x([0-9a-fA-F]+)|(\\S+))\\s*,\\s*DP");

    private boolean writeRefs = false;
    private boolean addBookmarks = true;
    private boolean operandRefs = true;
    private boolean mirrorLabels = true;
    private boolean removeSpurious = true;
    private boolean followPtrArrays = false;
    private boolean markStubs = true;

    public H8TableAnalyzer() {
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
        options.registerOption(OPT_OPERAND_REFS, operandRefs, null,
            "Add READ references for absolute @aa:16 operands that reach flash, using the DP in "
                + "effect (DP=0: page-0 mirror 0x0000-0x3FFF to both the mirror and its 0x1xxxx "
                + "alias; DP=1/2: that page). Needs the page0_mirror block; skipped without it.");
        options.registerOption(OPT_MIRROR_LABELS, mirrorLabels, null,
            "Copy each label in 0x10000-0x13FFF to the page-0 mirror so decompiler output and "
                + "xrefs agree. Needs the page0_mirror block.");
        options.registerOption(OPT_SPURIOUS, removeSpurious, null,
            "Delete analysis DATA references that are not real accesses: references into the "
                + "undocumented 0xFFC0-0xFFFF range, and bit-mask constants (~(1<<n)) that "
                + "bset/bclr/bnot/btst instructions leak as pointers.");
        options.registerOption(OPT_STUBS, markStubs, null,
            "Bookmark (H8Table/HeaderStub) and comment table descriptors that are immediately followed by another descriptor or a 0xFF terminator, so they are not mistaken for table data. Flash 0x10100-0x13FFF.");
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
        operandRefs = options.getBoolean(OPT_OPERAND_REFS, operandRefs);
        mirrorLabels = options.getBoolean(OPT_MIRROR_LABELS, mirrorLabels);
        removeSpurious = options.getBoolean(OPT_SPURIOUS, removeSpurious);
        followPtrArrays = options.getBoolean(OPT_PTRARR, followPtrArrays);
        markStubs = options.getBoolean(OPT_STUBS, markStubs);
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
            new Kind(TABLE_LOOKUP_INTERP, "2D table", false),
            new Kind(TABLE_3AXIS_INTERP_TRIPLE, "3D table", false),
            new Kind(TABLE_LOOKUP_INDEXED, "indexed table", false),
            new Kind(TABLE_READ_INDEXED, "indexed table read", false),
            new Kind(AXIS_LOOKUP_INTERP, "axis", true),
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

        boolean hasMirror = program.getMemory().getBlock(MIRROR_BLOCK) != null;
        if (!hasMirror && (operandRefs || mirrorLabels)) {
            log.appendMsg(NAME, "no " + MIRROR_BLOCK + " block - mirror labels and DP-aware operand "
                + "references skipped (run the setup script step 3 first)");
        }
        else if (hasMirror) {
            if (mirrorLabels) {
                int n = addMirrorLabels(program, monitor);
                log.appendMsg(NAME, "mirror labels created=" + n);
            }
            if (operandRefs) {
                int[] c = addOperandRefs(program, monitor);
                log.appendMsg(NAME, String.format(
                    "operand refs created=%d (mirror/page-0 %d, DP window %d) already present=%d "
                        + "unresolved (missing area / unknown DP)=%d",
                    c[0], c[1], c[2], c[3], c[4]));
            }
        }
        if (removeSpurious) {
            int[] sp = removeSpuriousRefs(program, monitor);
            log.appendMsg(NAME, String.format(
                "spurious refs removed=%d (undocumented 0xFFC0-0xFFFF %d, bit-mask constants %d)",
                sp[0] + sp[1], sp[0], sp[1]));
        }

        log.appendMsg(NAME, String.format(
            "call sites=%d resolved=%d runtime(non-literal)=%d out-of-range=%d refs added=%d%s%s",
            sites, resolved, runtime, outOfRange, refsAdded,
            writeRefs ? "" : " (dry run: Write references is off)",
            helpersMissing > 0 ? " helpers missing=" + helpersMissing : ""));
        return true;
    }

    /**
     * Ghidra's constant propagation turns constants into DATA references. Two kinds are never
     * real accesses on the H8/539F: anything into 0xFFC0-0xFFFF (no documented registers there),
     * and the complement mask (~(1<<n)) that bit instructions, andc/orc/xorc and register pushes carry, e.g. 0xFFFE for bit 0.
     * Real operand references are READ/WRITE, so only DATA references are removed.
     */
    private int[] removeSpuriousRefs(Program program, TaskMonitor monitor) throws CancelledException {
        ReferenceManager rm = program.getReferenceManager();
        Listing listing = program.getListing();
        List<Reference> del = new ArrayList<>();
        int undoc = 0;
        int mask = 0;
        ReferenceIterator it = rm.getReferenceIterator(program.getMinAddress());
        while (it.hasNext()) {
            monitor.checkCancelled();
            Reference r = it.next();
            if (r.getSource() != SourceType.ANALYSIS || r.getReferenceType() != RefType.DATA
                    || !r.getToAddress().isMemoryAddress()
                    || r.getToAddress().getOffset() > 0xFFFFL) {
                continue;
            }
            long off = r.getToAddress().getOffset();
            if (off >= 0xFFC0L) {
                del.add(r);
                undoc++;
                continue;
            }
            Instruction in = listing.getInstructionAt(r.getFromAddress());
            if (in == null) {
                continue;
            }
            String mn = in.getMnemonicString().toLowerCase();
            boolean bitOp = mn.startsWith("bset") || mn.startsWith("bclr")
                || mn.startsWith("bnot") || mn.startsWith("btst")
                || mn.startsWith("andc") || mn.startsWith("orc") || mn.startsWith("xorc")
                || in.toString().toLowerCase().endsWith("@-sp");
            if (!bitOp) {
                continue;
            }
            boolean isMask = false;
            for (int k = 0; k < 16; k++) {
                if (off == (0xFFFFL & ~(1L << k))) {
                    isMask = true;
                    break;
                }
            }
            String hex = "0x" + Long.toHexString(off);
            String txt = in.toString().toLowerCase();
            if (isMask && !txt.contains("@" + hex) && !txt.contains("@(" + hex)) {
                del.add(r);
                mask++;
            }
        }
        for (Reference r : del) {
            rm.delete(r);
        }
        return new int[] { undoc, mask };
    }
    private int addMirrorLabels(Program program, TaskMonitor monitor) throws CancelledException {
        SymbolTable st = program.getSymbolTable();
        AddressSet src = new AddressSet(toAddr(program, FLASH_START), toAddr(program, FLASH_START + MIRROR_END));
        List<Symbol> syms = new ArrayList<>();
        SymbolIterator it = st.getSymbols(src, SymbolType.LABEL, true);
        while (it.hasNext()) {
            Symbol s = it.next();
            if (s.getSource() != SourceType.DEFAULT) {
                syms.add(s);
            }
        }
        int made = 0;
        for (Symbol s : syms) {
            monitor.checkCancelled();
            Address m = toAddr(program, s.getAddress().getOffset() - FLASH_START);
            boolean has = false;
            for (Symbol e : st.getSymbols(m)) {
                if (e.getName().equals(s.getName())) {
                    has = true;
                }
            }
            if (!has) {
                try {
                    st.createLabel(m, s.getName(), SourceType.ANALYSIS);
                    made++;
                }
                catch (Exception e) {
                    // duplicate / invalid name at this address: leave it
                }
            }
        }
        return made;
    }

    /**
     * Straight-line DP tracking per function: DP=0 at entry, ldc.b #n,DP sets n, a stack pop
     * (ldc.b @SP+,DP) restores 0, a register load makes DP unknown until the next known value.
     * Returns {created, mirror, window, alreadyPresent, unresolved}.
     */
    private int[] addOperandRefs(Program program, TaskMonitor monitor) throws CancelledException {
        Listing listing = program.getListing();
        ReferenceManager rm = program.getReferenceManager();
        int created = 0, mirror = 0, window = 0, present = 0, unresolved = 0;
        for (Function f : program.getFunctionManager().getFunctions(true)) {
            monitor.checkCancelled();
            int dp = 0;
            boolean unknown = false;
            InstructionIterator it = listing.getInstructions(f.getBody(), true);
            while (it.hasNext()) {
                Instruction i = it.next();
                Matcher lm = LDC_DP.matcher(i.toString());
                if (lm.find()) {
                    if (lm.group(1) != null) {
                        dp = Integer.parseInt(lm.group(1), 16);
                        unknown = false;
                    }
                    else if ("@SP+".equals(lm.group(2))) {
                        dp = 0;
                        unknown = false;
                    }
                    else {
                        unknown = true;
                    }
                    continue;
                }
                for (int k = 0; k < i.getNumOperands(); k++) {
                    Matcher m = ABS_OPERAND.matcher(i.getDefaultOperandRepresentation(k));
                    if (!m.find()) {
                        continue;
                    }
                    long off = Long.parseLong(m.group(1), 16);
                    if (off > 0xffffL) {
                        continue;
                    }
                    if (unknown) {
                        unresolved++;
                        continue;
                    }
                    List<Long> targets = new ArrayList<>();
                    boolean isMirror = false;
                    if (dp == 0) {
                        if (off <= MIRROR_END) {
                            targets.add(off);
                            targets.add(FLASH_START + off);
                            isMirror = true;
                        }
                        else if (off >= RAM_START) {
                            continue;              // RAM/registers: Ghidra already references these
                        }
                        else {
                            unresolved++;          // missing area (0x4000-0xEE7F)
                            continue;
                        }
                    }
                    else if (dp == 1 || dp == 2) {
                        targets.add(dp * 0x10000L + off);
                    }
                    else {
                        continue;
                    }
                    for (long t : targets) {
                        Address ta = toAddr(program, t);
                        if (ta == null || !program.getMemory().contains(ta)) {
                            continue;
                        }
                        if (hasRef(rm, i.getAddress(), ta)) {
                            present++;
                            continue;
                        }
                        rm.addMemoryReference(i.getAddress(), ta, RefType.READ, SourceType.ANALYSIS, k);
                        created++;
                        if (isMirror) {
                            mirror++;
                        }
                        else {
                            window++;
                        }
                    }
                }
            }
        }
        return new int[] { created, mirror, window, present, unresolved };
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

    private static String nearestAxis(Program program, Instruction tableCall) {
        Function fn = program.getFunctionManager().getFunctionContaining(tableCall.getAddress());
        if (fn == null) {
            return null;
        }
        Address axisEntry = toAddr(program, AXIS_LOOKUP_INTERP);
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
