// Read-only. For every function, writes the low 16 bits (hex) of the return address of every call
// instruction to %TEMP%\retaddr_by_func.txt, one line per function: name|addr,addr,...
// Used to look for decompiler constants that are really pushed return addresses (todo.md item 13).
//@category H8

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;

import java.io.File;
import java.io.FileWriter;
import java.io.PrintWriter;

public class DumpRetAddrs extends GhidraScript {
	@Override
	public void run() throws Exception {
		File out = new File(System.getenv("TEMP"), "retaddr_by_func.txt");
		int n = 0, calls = 0;
		try (PrintWriter w = new PrintWriter(new FileWriter(out))) {
			for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
				StringBuilder sb = new StringBuilder();
				InstructionIterator it = currentProgram.getListing().getInstructions(f.getBody(), true);
				while (it.hasNext()) {
					Instruction in = it.next();
					if (in.getFlowType().isCall()) {
						Address ft = in.getFallThrough();
						if (ft != null) {
							sb.append(Long.toHexString(ft.getOffset() & 0xffffL)).append(',');
							calls++;
						}
					}
				}
				w.println(f.getName() + "|" + sb);
				n++;
			}
		}
		println("DUMP functions=" + n + " calls=" + calls + " file=" + out);
	}
}
