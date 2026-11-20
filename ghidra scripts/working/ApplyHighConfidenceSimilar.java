// Pass 4: read evo5_similarity_candidates.csv (produced by FindSimilarCandidates.java)
// and apply name-only renames to EVO5 functions where BOTH:
//   - similarity >= 0.97
//   - rvr_instr_count >= 15  (guards against short-function structural collapse,
//     e.g. check_flag_fede_bit2_clear_if_set wrongly matching latch_flag_read_fede_bit1
//     at 1.0 similarity purely because both are short flag-check shapes)
//
// Never overwrites a function that already has a non-FUN_ name different from the
// proposed one (logs as SKIPPED_ALREADY_NAMED instead). Writes a full decision log.
// @category H8539F

import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressFactory;
import ghidra.program.model.symbol.SourceType;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.PrintWriter;
import java.util.ArrayList;
import java.util.List;

public class ApplyHighConfidenceSimilar extends GhidraScript {

    private static final double MIN_SIMILARITY = 0.97;
    private static final int MIN_INSTR_COUNT = 15;

    @Override
    public void run() throws Exception {
        String inPath = "C:\\Users\\j.brophy.CORKILLSYSTEMS\\github\\Ghidra-H8-Processor\\evo5_similarity_candidates.csv";
        String outPath = "C:\\Users\\j.brophy.CORKILLSYSTEMS\\github\\Ghidra-H8-Processor\\evo5_similarity_apply_log.csv";

        BufferedReader br = new BufferedReader(new FileReader(new File(inPath)));
        PrintWriter pw = new PrintWriter(new FileWriter(new File(outPath), false));
        pw.println("rvr_address,rvr_name,evo5_address,evo5_prior_name,similarity,rvr_instr_count,evo5_instr_count,decision");

        String header = br.readLine();
        String line;
        AddressFactory af = currentProgram.getAddressFactory();

        int applied = 0, skippedLowSim = 0, skippedShort = 0, skippedAlreadyNamed = 0, skippedNoCandidate = 0, total = 0;

        while ((line = br.readLine()) != null) {
            if (line.trim().isEmpty()) continue;
            String[] f = line.split(",");
            if (f.length < 7) continue;
            total++;

            String rvrAddrStr = f[0];
            String rvrName = f[1];
            String evoAddrStr = f[2];
            String evoNameInFile = f[3];
            double sim;
            int rvrCount, evoCount;
            try {
                sim = Double.parseDouble(f[4]);
                rvrCount = Integer.parseInt(f[5]);
                evoCount = Integer.parseInt(f[6]);
            } catch (Exception e) {
                continue;
            }

            if (evoAddrStr.isEmpty()) {
                pw.println(rvrAddrStr + "," + rvrName + ",,,0,0,0,NO_CANDIDATE");
                skippedNoCandidate++;
                continue;
            }

            if (rvrCount < MIN_INSTR_COUNT) {
                pw.println(rvrAddrStr + "," + rvrName + "," + evoAddrStr + "," + evoNameInFile + "," + sim + "," + rvrCount + "," + evoCount + ",SKIPPED_TOO_SHORT");
                skippedShort++;
                continue;
            }

            if (sim < MIN_SIMILARITY) {
                pw.println(rvrAddrStr + "," + rvrName + "," + evoAddrStr + "," + evoNameInFile + "," + sim + "," + rvrCount + "," + evoCount + ",SKIPPED_LOW_SIMILARITY");
                skippedLowSim++;
                continue;
            }

            Address evoAddr;
            try { evoAddr = af.getAddress(evoAddrStr); }
            catch (Exception e) { continue; }

            Function evoFunc = currentProgram.getListing().getFunctionAt(evoAddr);
            if (evoFunc == null) {
                pw.println(rvrAddrStr + "," + rvrName + "," + evoAddrStr + "," + evoNameInFile + "," + sim + "," + rvrCount + "," + evoCount + ",NO_FUNCTION_AT_CANDIDATE");
                continue;
            }

            String currentName = evoFunc.getName();
            if (!currentName.startsWith("FUN_") && !currentName.equals(rvrName)) {
                pw.println(rvrAddrStr + "," + rvrName + "," + evoAddrStr + "," + currentName + "," + sim + "," + rvrCount + "," + evoCount + ",SKIPPED_ALREADY_NAMED");
                skippedAlreadyNamed++;
                continue;
            }

            if (currentName.equals(rvrName)) {
                pw.println(rvrAddrStr + "," + rvrName + "," + evoAddrStr + "," + currentName + "," + sim + "," + rvrCount + "," + evoCount + ",ALREADY_CORRECT");
                continue;
            }

            try {
                evoFunc.setName(rvrName, SourceType.USER_DEFINED);
                pw.println(rvrAddrStr + "," + rvrName + "," + evoAddrStr + "," + currentName + "," + sim + "," + rvrCount + "," + evoCount + ",APPLIED");
                applied++;
            } catch (Exception e) {
                pw.println(rvrAddrStr + "," + rvrName + "," + evoAddrStr + "," + currentName + "," + sim + "," + rvrCount + "," + evoCount + ",APPLY_ERROR:" + e.getMessage());
            }
        }
        br.close();
        pw.close();

        println("Total rows: " + total);
        println("Applied: " + applied);
        println("Skipped (too short, <" + MIN_INSTR_COUNT + " instr): " + skippedShort);
        println("Skipped (similarity <" + MIN_SIMILARITY + "): " + skippedLowSim);
        println("Skipped (already named differently): " + skippedAlreadyNamed);
        println("No candidate found: " + skippedNoCandidate);
        println("Full log: " + outPath);
    }
}
