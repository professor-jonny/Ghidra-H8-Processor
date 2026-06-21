# Updated Mitsubishi H8/539F Setup (Physical Mapping Base 0x0)
# @category MitsubishiECU
from java.math import BigInteger  # <-- Fixed import syntax for Jython
from ghidra.program.flatapi import FlatProgramAPI
from ghidra.program.model.mem import MemoryConflictException
flat_api = FlatProgramAPI(currentProgram)

# 0. Create the missing on-chip RAM / peripheral I/O memory block (0xEE80-0xFFFF).
#    This region is never created by the Binary Loader (which only maps the ROM
#    image at 0x0-0x1FFFF) and was being silently dropped by the .pspec's
#    default_memory_blocks due to a (non-)overlap check during import, so any
#    instruction touching SFRs/RAM in this range previously had no backing
#    memory at all -- this is what was causing the ArrayIndexOutOfBoundsException
#    in ConstantPropagationAnalyzer / StackVariableAnalyzer during auto-analysis.
mem = currentProgram.getMemory()
addr_space = currentProgram.getAddressFactory().getDefaultAddressSpace()
ram_block_start = addr_space.getAddress(0xEE80)
ram_block_length = 0x1180  # covers 0xEE80-0xFFFF inclusive

tx_mem = currentProgram.startTransaction("Create H8/539F RAM block")
try:
    existing = mem.getBlock(ram_block_start)
    if existing is not None:
        print("RAM block already exists at {} ({}), skipping creation.".format(
            ram_block_start, existing.getName()))
    else:
        try:
            new_block = mem.createUninitializedBlock(
                "RAM", ram_block_start, ram_block_length, False)
            new_block.setRead(True)
            new_block.setWrite(True)
            new_block.setExecute(False)
            new_block.setVolatile(True)
            print("Created RAM block at {} length 0x{:x}".format(
                ram_block_start, ram_block_length))
        except MemoryConflictException as mce:
            print("Could not create RAM block (conflict): {}".format(mce))
finally:
    currentProgram.endTransaction(tx_mem, True)

# 1. Define memory boundaries based on physical 0x000000 mapping
start_addr = currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(0x000000)
end_addr = currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(0x01FFFF)
tx = currentProgram.startTransaction("H8/539F Physical Base Setup")
try:
    # Set the Data Page (DP) register to 1 globally across the ROM area
    ctx_reg = currentProgram.getProgramContext().getRegister("DP") 
    if ctx_reg:
        dp_value = BigInteger.valueOf(1)
        currentProgram.getProgramContext().setValue(ctx_reg, start_addr, end_addr, dp_value)
        print("Set context register DP to 1 from {} to {}".format(start_addr, end_addr))
    
    # 2. Read the 24-bit entry point from the reset vector at 0x000000
    reset_vector_raw = flat_api.getInt(start_addr)
    entry_offset = reset_vector_raw & 0x00FFFFFF
    entry_point = currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(entry_offset)
    
    print("Reset vector points to entry address: {}".format(entry_point))
    
    # 3. Disassemble and create the function at the proper location
    flat_api.disassemble(entry_point)
    flat_api.createFunction(entry_point, "entry")
    print("Function 'entry' successfully defined at {}".format(entry_point))
except Exception as e:
    print("Initialization failed: {}".format(e))
finally:
    currentProgram.endTransaction(tx, True)
# 4. Run auto-analysis to populate the decompiler
print("Kicking off Auto-Analysis...")
flat_api.analyzeAll(currentProgram)
print("Done! Check the decompiler at address {}".format(entry_point))
