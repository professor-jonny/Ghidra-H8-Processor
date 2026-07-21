This is a great start for a custom processor module! The fact that Ghidra is successfully decompiling the function into conditional logic means your SLEIGH specifications are mostly correct.

However, looking closely at the decompilation, there are a few distinct signs of bad data and artifacts that point to specific areas in your SLEIGH file (.slaspec or .sinc) that need tightening up.

🚩 Areas to Fix in Your SLEIGH
1. The Stack Pointer (unaff_SP) is Floating
C
short unaff_SP;
...
*(undefined2 *)(uint)(ushort)(unaff_SP - 2) = 0x50ff;
The Issue: unaff_SP stands for "unaffected Stack Pointer." Ghidra is treating the stack pointer as a random, uninitialized local variable rather than the actual hardware stack pointer. Because of this, it can't track stack depth, resulting in ugly pointer arithmetic casting (*(undefined2 *)(uint)(ushort)...).

The Fix: Ensure your stack pointer register (usually SP or R7 on H8) is explicitly defined with the stackpointer compiler spec attribute in your .cspec file:

XML
<stackpointer register="SP" space="ram"/>
Also, make sure the instruction pushing 0x50ff and 2 onto the stack is properly using the SP register in SLEIGH so Ghidra recognizes it as a standard stack store.

2. Strange Function Pointer Decompilation
C
sVar2 = (*f0ec_bit1_threshold_gate_check)();
The Issue: Ghidra is trying to call f0ec_bit1_threshold_gate_check as a function pointer, but look at how it's defined at the top: undefined f0ec_bit1_threshold_gate_check;. It’s declared as a single byte variable, not a function.

The Fix: This usually happens if a BSR (Branch to Subroutine) or JSR instruction is pulling its target address from a memory location or register, and the SLEIGH syntax isn't computing the destination correctly, or the global variable at f0ec was typed incorrectly by Ghidra's auto-analysis. Check your jsr or bsr SLEIGH definitions to ensure the target is explicitly marked as an instruction address (:ram).

3. Hardcoded RAM Address Calculations
C
puVar1 = (ushort *)((uint)bVar3 << 0x10 | 0xf3a4);
*puVar1 = *puVar1 & 0xfbff;
The Issue: The decompiler is calculating a memory address manually using bVar3 (which is hardcoded to 1) shifted left by 16, combined with 0xf3a4. This results in the address 0x1f3a4. Because Ghidra doesn't realize this is a direct memory access, it creates a local pointer variable puVar1 instead of just showing a clean variable modification.

The Fix: This implies your H8 implementation uses banked memory or an 8-bit/16-bit absolute addressing mode where the upper bits are assumed.

If bVar3 represents a page or status register (like EXR or a bit in CCR), ensure that changes to it are accurately reflected in your SLEIGH spaces.

If this instruction is a bit manipulation instruction (like BCLR or BSET), ensure your SLEIGH definition uses a semantic section that directly references the memory space, rather than building the address dynamically via temporary registers (inst_next, etc.) if it can be avoided.

🛠️ Recommended Tidy-up Checklist
Check the .cspec File: Verify that your stack pointer register, calling conventions, and global memory spaces are properly mapped. This will immediately clean up the unaff_SP clutter.

Review Bit Operations: H8 is famous for its intensive bit manipulation instructions on memory (e.g., BCLR #2, @0xf3a4). If the original assembly was a bit set/clear, make sure your SLEIGH semantics are using the [ram]:2 or similar direct assignment rather than shifting variables.

Fix Types in Ghidra: Some of this is just Ghidra guessing wrong on data types. Right-click f0ec_bit1_threshold_gate_check, change the type to a function signature (or clear it), and see if the decompiler output cleans up.