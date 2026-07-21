package h8539f;

import ghidra.app.services.AbstractAnalyzer;
import ghidra.app.services.AnalysisPriority;
import ghidra.app.services.AnalyzerType;
import ghidra.app.util.importer.MessageLog;
import ghidra.program.model.address.AddressSetView;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.listing.Program;
import ghidra.program.model.scalar.Scalar;
import ghidra.util.exception.CancelledException;
import ghidra.util.task.TaskMonitor;

/**
 * Automated stack purge analyzer for the Renesas H8/539F processor module.
 * Scans for PRTD and RTD instructions to cleanly align the decompiler spacebase.
 */
public class H8FunctionPurgeAnalyzer extends AbstractAnalyzer {

    private static final String ANALYZER_NAME = "H8 Function Purge Analyzer";
    private static final String DESCRIPTION = "Automatically updates function stack purge sizes from PRTD/RTD return instructions.";

    public H8FunctionPurgeAnalyzer() {
        super(ANALYZER_NAME, DESCRIPTION, AnalyzerType.FUNCTION_ANALYZER);
        // Phase-gated to execute immediately after initial function boundaries are mapped
        setPriority(AnalysisPriority.FUNCTION_ANALYSIS.after());
        setDefaultEnablement(true);
    }

    @Override
    public boolean canAnalyze(Program program) {
        // Enforce execution exclusively on your custom language ID architecture layout
        String languageId = program.getLanguage().getLanguageID().toString();
        return languageId.toUpperCase().contains("H8539F");
    }

    @Override
    public boolean added(Program program, AddressSetView set, TaskMonitor monitor, MessageLog log)
            throws CancelledException {

        Listing listing = program.getListing();
        FunctionManager functionManager = program.getFunctionManager();

        // Iterate only through newly tracked or re-analyzed code blocks
        InstructionIterator instructions = listing.getInstructions(set, true);

        while (instructions.hasNext()) {
            // Respect user UI cancellation requests gracefully
            monitor.checkCancelled();

            Instruction insn = instructions.next();
            String mnemonic = insn.getMnemonicString();

            // Trap your target purging return instructions defined in SLEIGH
            if ("prtd".equalsIgnoreCase(mnemonic) || "rtd".equalsIgnoreCase(mnemonic)) {

                // Read the stack pop immediate value from the first operand position
                if (insn.getNumOperands() > 0) {
                    Object[] opObjects = insn.getOpObjects(0);

                    if (opObjects.length > 0 && opObjects[0] instanceof Scalar) {
                        int purgeVal = (int) ((Scalar) opObjects[0]).getValue();

                        // Locate the current function context container
                        Function func = functionManager.getFunctionContaining(insn.getAddress());

                        if (func != null && func.getStackPurgeSize() != purgeVal) {
                            boolean alreadySet = func.isStackPurgeSizeValid()
                                    && func.getStackPurgeSize() != 0;

                            if (alreadySet) {
                                // A different purge value was already recorded from an earlier
                                // PRTD/RTD site in this same function -- don't silently overwrite,
                                // since one of the two return points is wrong and needs a human look.
                                log.appendMsg(ANALYZER_NAME, String.format(
                                    "Conflicting purge values for function %s: existing %d, new %d from %s at %s -- keeping existing value",
                                    func.getName(), func.getStackPurgeSize(), purgeVal, mnemonic,
                                    insn.getAddressString(false, false)
                                ));
                                continue;
                            }

                            // Inject ground truth tracking directly into the database schema
                            func.setStackPurgeSize(purgeVal);
                            log.appendMsg(ANALYZER_NAME, String.format(
                                "Auto-aligned stack frame purge to %d bytes for function %s at %s",
                                purgeVal, func.getName(), insn.getAddressString(false, false)
                            ));
                        }
                    }
                }
            }
        }
        return true;
    }
}
