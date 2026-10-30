package h8539f;

import ghidra.app.services.AbstractAnalyzer;
import ghidra.app.services.AnalysisPriority;
import ghidra.app.services.AnalyzerType;
import ghidra.app.util.importer.MessageLog;
import ghidra.framework.options.Options;
import ghidra.program.model.address.AddressSetView;
import ghidra.program.model.listing.Bookmark;
import ghidra.program.model.listing.BookmarkManager;
import ghidra.program.model.listing.BookmarkType;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.listing.Program;
import ghidra.util.exception.CancelledException;
import ghidra.util.exception.InvalidInputException;
import ghidra.util.task.TaskMonitor;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Preserved-register analyzer for the Renesas H8/539F processor module.
 *
 * The compiler spec's calling conventions list R1 and R2 as killed by a call. Many ROM helpers (the
 * div_*, muldiv_*, mul_*, adc_* helpers and others) save those registers at entry and restore them
 * before every return, so after such a call the caller's R1/R2 are still valid. Treating them as
 * killed makes the decompiler print extraout_R2 / junk base addresses after the call.
 *
 * For each function this analyzer finds the registers that are
 *   (a) saved by mov:g.w Rn,@-SP or stm (...),@-SP among the first instructions, and
 *   (b) restored by mov:g.w @SP+,Rn or ldm.w @SP+,(...) right before EVERY return,
 * and, when R1 and/or R2 qualify, switches the function to the matching clone of its CURRENT convention,
 * named &lt;base&gt;_pR1, &lt;base&gt;_pR2 or &lt;base&gt;_pR1R2 (defined in h8539f.cspec; identical to the base
 * convention except that those registers move from killedbycall to unaffected).
 *
 * Deliberately conservative, because existing conventions in the database are partly inferred:
 *  - it never changes anything about a convention except those registers;
 *  - it skips any function whose base convention is not one of the known bases;
 *  - it skips (and logs) if the wanted clone does not exist in the compiler spec;
 *  - every change is recorded as a bookmark (category "H8 Preserved Registers") with the evidence, and is
 *    undone automatically on re-analysis if the evidence no longer holds;
 *  - "Dry run" option logs what it would change without changing anything.
 * Disabled by default.
 */
public class H8PreservedRegsAnalyzer extends AbstractAnalyzer {

    private static final String ANALYZER_NAME = "H8 Preserved Registers Analyzer";
    private static final String DESCRIPTION =
        "Moves R1/R2 out of the killed-by-call set for functions that save and restore them (stm/ldm or push/pop).";
    private static final String OPTION_DRY_RUN = "Dry run (log only, change nothing)";
    private static final String BOOKMARK_CATEGORY = "H8 Preserved Registers";

    private static final Set<String> BASES = new HashSet<String>(Arrays.asList(
        "__stdcall", "__stdcall_far_allstack", "__stdcall_far", "__stdcall_far_allstack_32ret", "__stdcall_far_2arg"));
    private static final String[] SUFFIXES = { "_pR1R2", "_pR1", "_pR2" };

    private static final Pattern PUSH = Pattern.compile("^mov:g\\.w\\s+(R[0-5]),@-SP$");
    private static final Pattern POP = Pattern.compile("^mov:g\\.w\\s+@SP\\+,(R[0-5])$");
    private static final Pattern STM = Pattern.compile("^stm\\s+\\((.*)\\),@-SP$");
    private static final Pattern LDM = Pattern.compile("^ldm\\.w\\s+@SP\\+,\\((.*)\\)$");
    private static final Pattern REG = Pattern.compile("R[0-5]|FP");

    private boolean dryRun = false;

    public H8PreservedRegsAnalyzer() {
        super(ANALYZER_NAME, DESCRIPTION, AnalyzerType.FUNCTION_ANALYZER);
        // After the stack-purge analyzers (both run at FUNCTION_ANALYSIS.after()).
        setPriority(AnalysisPriority.FUNCTION_ANALYSIS.after().after());
        setDefaultEnablement(false);
    }

    @Override
    public boolean canAnalyze(Program program) {
        return program.getLanguage().getLanguageID().toString().toUpperCase().contains("H8539F");
    }

    @Override
    public void registerOptions(Options options, Program program) {
        options.registerOption(OPTION_DRY_RUN, Boolean.valueOf(dryRun), null,
            "Log which functions would be switched, and why, without changing any calling convention.");
    }

    @Override
    public void optionsChanged(Options options, Program program) {
        dryRun = options.getBoolean(OPTION_DRY_RUN, dryRun);
    }

    private static final class Evidence {
        final Set<String> pushed = new TreeSet<String>();
        Set<String> preserved = null;
        int returns = 0;
        String pushText = null;
        String popText = null;
    }

    private static void collectRegs(Pattern p, String text, Set<String> out) {
        Matcher m = p.matcher(text);
        if (m.matches()) {
            Matcher r = REG.matcher(m.group(1));
            while (r.find()) {
                out.add(r.group());
            }
        }
    }

    private static boolean isReturn(String mnemonic) {
        return mnemonic.equals("prts") || mnemonic.equals("rts") || mnemonic.startsWith("prtd")
            || mnemonic.startsWith("rtd") || mnemonic.equals("rte");
    }

    private Evidence analyze(Listing listing, Function f) {
        List<Instruction> body = new ArrayList<Instruction>();
        for (Instruction i : listing.getInstructions(f.getBody(), true)) {
            body.add(i);
        }
        Evidence ev = new Evidence();
        if (body.isEmpty()) {
            return ev;
        }
        for (int k = 0; k < Math.min(12, body.size()); k++) {
            Instruction in = body.get(k);
            String text = in.toString();
            int before = ev.pushed.size();
            collectRegs(STM, text, ev.pushed);
            Matcher m = PUSH.matcher(text);
            if (m.matches()) {
                ev.pushed.add(m.group(1));
            }
            else if (in.getFlowType().isJump() || in.getFlowType().isCall()) {
                break;
            }
            if (ev.pushed.size() > before && ev.pushText == null) {
                ev.pushText = in.getAddress() + " " + text;
            }
        }
        for (int k = 0; k < body.size(); k++) {
            if (!isReturn(body.get(k).getMnemonicString())) {
                continue;
            }
            ev.returns++;
            Set<String> popped = new TreeSet<String>();
            for (int b = k - 1; b >= 0 && b >= k - 12; b--) {
                Instruction p = body.get(b);
                if (p.getFlowType().isJump() || p.getFlowType().isCall() || p.getFlowType().isTerminal()) {
                    break;
                }
                String text = p.toString();
                int before = popped.size();
                collectRegs(LDM, text, popped);
                Matcher m = POP.matcher(text);
                if (m.matches()) {
                    popped.add(m.group(1));
                }
                if (popped.size() > before && ev.popText == null) {
                    ev.popText = p.getAddress() + " " + text;
                }
            }
            if (ev.preserved == null) {
                ev.preserved = new TreeSet<String>(popped);
            }
            else {
                ev.preserved.retainAll(popped);
            }
        }
        if (ev.preserved == null) {
            ev.preserved = new TreeSet<String>();
        }
        ev.preserved.retainAll(ev.pushed);
        return ev;
    }

    private static String suffixOf(Set<String> preserved) {
        boolean r1 = preserved.contains("R1");
        boolean r2 = preserved.contains("R2");
        if (r1 && r2) {
            return "_pR1R2";
        }
        if (r1) {
            return "_pR1";
        }
        if (r2) {
            return "_pR2";
        }
        return "";
    }

    private static String stripSuffix(String convention) {
        for (String s : SUFFIXES) {
            if (convention.endsWith(s)) {
                return convention.substring(0, convention.length() - s.length());
            }
        }
        return convention;
    }

    @Override
    public boolean added(Program program, AddressSetView set, TaskMonitor monitor, MessageLog log)
            throws CancelledException {

        Listing listing = program.getListing();
        FunctionManager functionManager = program.getFunctionManager();
        BookmarkManager bookmarks = program.getBookmarkManager();
        FunctionIterator functions = (set == null) ? functionManager.getFunctions(true)
                                                   : functionManager.getFunctions(set, true);
        int changed = 0, reverted = 0, missingClone = 0;
        boolean missingLogged = false;

        while (functions.hasNext()) {
            monitor.checkCancelled();
            Function f = functions.next();

            String current = f.getCallingConventionName();
            if (current == null) {
                current = "unknown";
            }
            boolean currentIsClone = !stripSuffix(current).equals(current);
            String base = stripSuffix(current);
            if (base.equals("unknown") || base.equals("default")) {
                base = "__stdcall";
            }
            if (!BASES.contains(base)) {
                continue;
            }

            Evidence ev = analyze(listing, f);
            String suffix = ev.returns == 0 ? "" : suffixOf(ev.preserved);

            if (suffix.isEmpty() && !currentIsClone) {
                continue; // never touch a function we have no evidence for
            }
            String wanted = base + suffix;
            if (wanted.equals(current)) {
                continue;
            }
            if (!suffix.isEmpty() && program.getCompilerSpec().getCallingConvention(wanted) == null) {
                missingClone++;
                if (!missingLogged) {
                    log.appendMsg(ANALYZER_NAME, "Calling convention " + wanted
                        + " is not defined in the compiler spec (update h8539f.cspec); skipping such functions");
                    missingLogged = true;
                }
                continue;
            }

            String what = suffix.isEmpty()
                ? "evidence no longer holds; reverting " + current + " -> " + wanted
                : "R1/R2 preserved " + ev.preserved + " (saved " + ev.pushText + ", restored " + ev.popText
                    + ", returns=" + ev.returns + "); " + current + " -> " + wanted;
            if (dryRun) {
                log.appendMsg(ANALYZER_NAME, "[dry run] " + f.getName() + " at " + f.getEntryPoint() + ": " + what);
                continue;
            }
            try {
                f.setCallingConvention(wanted);
            }
            catch (InvalidInputException e) {
                log.appendMsg(ANALYZER_NAME, "Could not set " + wanted + " on " + f.getName() + " at "
                    + f.getEntryPoint() + ": " + e.getMessage());
                continue;
            }
            Bookmark old = bookmarks.getBookmark(f.getEntryPoint(), BookmarkType.ANALYSIS, BOOKMARK_CATEGORY);
            if (suffix.isEmpty()) {
                if (old != null) {
                    bookmarks.removeBookmark(old);
                }
                reverted++;
            }
            else {
                bookmarks.setBookmark(f.getEntryPoint(), BookmarkType.ANALYSIS, BOOKMARK_CATEGORY, what);
                changed++;
            }
        }
        if (changed > 0 || reverted > 0 || missingClone > 0 || dryRun) {
            log.appendMsg(ANALYZER_NAME, "Preserved-register conventions: " + changed + " set, " + reverted
                + " reverted, " + missingClone + " skipped (clone missing)" + (dryRun ? " [dry run]" : ""));
        }
        return true;
    }
}
