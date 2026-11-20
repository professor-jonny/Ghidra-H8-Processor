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
 * Chip-level H8/539F analysis that does not depend on any particular firmware: it copies labels
 * to the page-0 flash mirror, adds DP-aware references for absolute @aa:16 operands that reach
 * flash, and removes analysis DATA references that cannot be real accesses.
 *
 * Split out of H8EcuTableAnalyzer so that analyzer holds only the Mitsubishi ECU table-helper
 * specifics. The option names and defaults are unchanged from the old combined analyzer.
 */
public class H8MemoryMapAnalyzer extends AbstractAnalyzer {

    private static final String NAME = "H8 Memory Map Analyzer";
    private static final String DESCRIPTION =
        "Chip-level H8/539F fixes: page-0 mirror labels, DP-aware operand references into flash, "
            + "and removal of spurious constant references.";

    private static final long FLASH_START = H8MemoryMap.FLASH_START;
    private static final long FLASH_END = H8MemoryMap.FLASH_END;
    private static final long MIRROR_END = H8MemoryMap.MIRROR_END;
    private static final long RAM_START = H8MemoryMap.RAM_START;

    private static final String OPT_OPERAND_REFS = "DP-aware operand references";
    private static final String OPT_MIRROR_LABELS = "Mirror labels";
    private static final String OPT_SPURIOUS = "Remove spurious constant references";
    private static final String MIRROR_BLOCK = "page0_mirror";
    private static final Pattern ABS_OPERAND =
        Pattern.compile("@(?:\\()?0x([0-9a-fA-F]+):16(?:,R[0-7]\\))?");
    private static final Pattern LDC_DP =
        Pattern.compile("ldc\\.b\\s+(?:0x([0-9a-fA-F]+)|(\\S+))\\s*,\\s*DP");

    private boolean operandRefs = true;
    private boolean mirrorLabels = true;
    private boolean removeSpurious = true;

    public H8MemoryMapAnalyzer() {
        super(NAME, DESCRIPTION, AnalyzerType.FUNCTION_ANALYZER);
        setPriority(AnalysisPriority.DATA_ANALYSIS.after());
        setDefaultEnablement(true);
    }

    @Override
    public boolean canAnalyze(Program program) {
        return program.getLanguage().getLanguageID().toString().toUpperCase().contains("H8539F");
    }

    @Override
    public void registerOptions(Options options, Program program) {
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
    }

    @Override
    public void optionsChanged(Options options, Program program) {
        operandRefs = options.getBoolean(OPT_OPERAND_REFS, operandRefs);
        mirrorLabels = options.getBoolean(OPT_MIRROR_LABELS, mirrorLabels);
        removeSpurious = options.getBoolean(OPT_SPURIOUS, removeSpurious);
    }

    @Override
    public boolean added(Program program, AddressSetView set, TaskMonitor monitor, MessageLog log)
            throws CancelledException {
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