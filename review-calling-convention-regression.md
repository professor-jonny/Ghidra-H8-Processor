# Investigation: 9561 triggers wrong-return-value / decompiler-crash regression on multi-parameter functions

## Status: Root cause not yet found. Trigger confirmed and reproducible. Not yet fixed.

## Summary

Commit `9561` (fix for `RuleLoadVarnode::vnSpacebase` not recursively
unwrapping a SEGMENTOP nested inside an INT_ADD -- see the prior
`review16-19.md` series) causes a **new** regression on functions that
combine a stack-passed parameter (resolved via SEGMENTOP) with one or
more register-passed parameters, under this H8 target's
`__stdcall_far_allstack` / `_32ret` calling conventions.

This is **not** the same bug `9561` was written to fix. It is a
previously-latent defect elsewhere in the decompiler (most likely in
heritage / merge-group handling around `INDIRECT` ops, not in
`vnSpacebase` itself) that `9561`'s fix newly exposes, because it
changes the P-code shape of the affected LOAD from "unresolved,
generic pointer dereference" to "resolved stack parameter" -- and that
shape change appears to interact badly with this target's mixed
register/stack argument passing.

## Confirmed trigger

Reproduced against the real ROM (`RVR_1998_x3 4g63t 21000011
md352553.hex`, H8:BE:32:H8539F, 741 functions) on three separate
builds:

- **Unpatched baseline** (`RVR_1998_x3 4g63t 21000011 md352553.hex.c`):
  all affected functions below decompile correctly. No wrong return
  values. No crash.
- **9561-only** (`RVR_1998_x3 4g63t 21000011 md352553 only one.hex.c`,
  and confirmed live via Ghidra MCP against the same build): the
  regression is present.
- **9540 + 9561 + 9450 merged** (`RVR_1998_x3 4g63t 21000011 md352553
  all three.hex.c`): the regression is still present, unchanged.
  9450 does not appear to cause or worsen it (see "Ruled out" below).

## Affected functions (confirmed)

All four are 3-parameter functions mixing a stack-passed parameter
(resolved via SEGMENTOP) with register-passed parameters (`R1`/`R3`
on this target), under a non-trivial calling convention
(`__stdcall_far_allstack` or `__stdcall_far_allstack_32ret`):

| Function | Address | Symptom |
|---|---|---|
| `muldiv_u16` | `0x141ba` | `return b;` instead of the computed division result (`uVar3`) |
| `muldiv_u16_scaled` | `0x141dc` | Decompiler crash: "Decompiler process died" |
| `muldiv_s16_rounded` | `0x14219` | `return b;` instead of the computed result |
| `muldiv_s16_rounded_3op` | `0x14247` | Unresolved raw registers (`in_R1`, `unaff_R3`) in output; `return sVar5` skips the real computation |
| `weighted_blend_u8frac` | (see datatests / ROM) | Same `in_R1`/`unaff_R3` pattern; `return sVar3` ignores the real blend result (`uVar2`) |

By contrast, `sat_add_u16` -- the function `9561`'s own regression
test (`nestedsegmentop.xml`) targets -- is unaffected. It is a simple
2-parameter, plain `__stdcall_far_allstack` function with *no*
register-passed arguments at all. This is consistent with the theory
below: the trigger needs *both* a SEGMENTOP-resolved stack parameter
*and* at least one register-passed parameter in the same function.

## P-code trail (muldiv_u16, the clearest case)

Captured via `ghidra:get_function_pcode` against the live 9561-only
build (address `0x141ba`).

In the final basic block (`0x141ce`-`0x141da`):

1. `INT_DIV` computes the real division result into a unique varnode.
2. `SUBPIECE` truncates it to the 2-byte quotient (the real answer).
3. `COPY` moves it into `register:2` (**merge_group 1**) -- this is
   the correct value that should become the return value.
4. Immediately after, an `INDIRECT` fires on `register:2`, keyed to a
   call-site marker (`const:0x4a`) -- the decompiler's way of saying
   "a call between here and the next read of this register might
   clobber it."
5. `COPY register:2 -> register:0` follows -- but by this point
   `register:2`'s value is the *post-INDIRECT* one, not the div
   result from step 3.
6. `register:0` is also where parameter `a` lives (same
   space/offset), and the return path ultimately reads `register:0`.

The correct division result and the wrong final register:0 value are
different SSA-ish generations of the *same* register storage location,
merged incorrectly across the `INDIRECT` call-clobber marker. The
SEGMENTOP-resolved LOAD for parameter `c` (`9561`'s actual fix target)
does resolve *correctly* in this same function -- the merge-array bug
`9561` targets is genuinely fixed here. The wrong-return-value bug is
downstream of that, in how the newly-resolved dataflow interacts with
register merge/heritage around the `INDIRECT`.

## Ruled out

- **Not caused by 9540** (register0x0e print-layer fix): confirmed via
  the `new.hex.gzf.c` export (9540-only, no 9561). `muldiv_u16`
  decompiles perfectly there -- correct return value, no `auStack_`
  array, no crash on `muldiv_u16_scaled`.
- **Not caused or worsened by 9450** (far-pointer argument-fusing
  mechanism, `ActionFarPointerJoin`): confirmed via the "all three"
  merged export. The regression is present and unchanged whether 9450
  is in the build or not. (9450 itself is separately unverified and
  has its own known issues -- not in scope here.)
- **Not a pre-existing decompiler defect unrelated to 9561**: the
  unpatched baseline decompiles all five affected functions correctly.
  The regression only appears once 9561's `vnSpacebase` fix is applied.

## Working theory

`9561` changes `checkSpacebase`'s LOAD for a SEGMENTOP-nested-in-INT_ADD
stack parameter from "unresolved / falls through to generic alias
handling" to "resolved as a proper stack varnode." That's the intended
fix. But in functions where the same P-code also has register-passed
parameters using the same physical registers the return value is
computed through, resolving that LOAD appears to change enough of the
surrounding P-code graph (fewer/different intermediate unique
varnodes, different rule-firing order in a later `Action` pass) that a
latent bug in how `INDIRECT` call-clobber markers get merged with
prior register definitions gets triggered where it previously wasn't.
This points at heritage (`Heritage` / `ActionMergeCopy` /
deadcode-elimination-adjacent logic in `coreaction.cc` or
`heritage.cc`), not at `vnSpacebase` or `RuleLoadVarnode` itself -- but
this has not been directly confirmed by stepping through those passes
yet.

## Major update: h8539f.cspec/.slaspec already documents this exact class of bug

`h8539f.cspec` (lines ~185-232) and `h8539f.slaspec` (lines ~23-39)
document a prior investigation (dated 2026-07-22, predating this
session) of the *identical* warning strings this regression produces
("Unable to track spacebase fully for stack" / "Restarted to delay
deadcode elimination for space: register"), on a named group of 6
"math helper" functions that need a 4-byte R0:R1 register-pair return
value but only have a 2-byte R0 output pentry available
(`__stdcall_far_allstack`/`_32ret`'s `<o>`/`<output>` only declares
`R0`, maxsize=2).

Key finding from that investigation, directly relevant here: **a
register-space or prototype change that has no direct call
relationship to the affected functions can still perturb the
decompiler's global return-value/stack-tracking model**, confirmed by
that investigation via the same pre/post whole-ROM diff methodology
used in this document (0 such warnings before a change, 27 after,
spread across 18 unrelated functions). Multiple attempted fixes (a
join-pentry R0:R1 output, a real overlapping R0R1 register in the
register space) were tried and reverted after confirming, via full
Ghidra restarts, that they did not fix the target functions and did
still cause the same broader pollution. The accepted state is a
plain 2-byte R0 pentry, accepting a known, narrower "dropped-R1-half"
warning on just the named 6 functions as the least-bad option.

**Important distinction**: the 6 functions named in that prior
investigation (`sat_add_s16`, `sat_sub_u16_clamp0`,
`muldiv_u16_scaled`, `muldiv_s16_rounded_3op`, `div_u32_u16_rounded`,
`select_min_xy_triple`) genuinely need a 4-byte return value and the
warning there is a real signature-modeling limitation. `muldiv_u16`
and `muldiv_s16_rounded` (the plain, non-suffixed functions showing
`return b;` in this investigation) return a plain 2-byte value that
*does* fit the R0 pentry -- they are not part of that named group, so
their wrong-return-value symptom is not simply "the same known
dropped-R1-half issue." However `muldiv_u16_scaled` (which crashes
outright under 9561) *is* one of the 6 named functions, so at least
that crash may be entangled with, or a worse manifestation of, the
pre-existing documented limitation rather than something wholly new.

This significantly changes the read on root cause: rather than a
`Merge::mergeIndirect` bug specific to 9561, the more likely
explanation is that **this decompiler target's parameter/return-value
recovery for register-pair and mixed register/stack calling
conventions is already known to be globally fragile** to any change
that shifts P-code shape, and 9561's SEGMENTOP-unwrap fix is simply
the latest such change to trigger it -- the same way the register
R0R1 overlap and the join-pentry attempt did in July, unrelated to
each other except via this shared fragility.

## Live debugging session (2026-09-02): scoped diagnostic + real trail

Added a scoped diagnostic directly to `Merge::mergeOp` in `merge.cc`
(gated strictly to `muldiv_u16`'s address range, `0x141ba`-`0x141da`;
temporary, writes to `mergeop_diag.txt`; not intended to ship), logging
each merge decision's op/varnode identities. Rebuilt full Ghidra with
the instrumentation in place and force-decompiled `muldiv_u16` via
Ghidra MCP against the live 9561-only instance to trigger it.

### Real assembly (confirmed via disassemble_bytes, not assumed)

```
000141ba  push  R2 (mov:g.w R2,@-SP)         -- callee-save c's register slot
000141c4  ...   (SEGMENTOP-resolved LOAD of c into R2, via 9561's fix)
000141c6  divxu.w R2,R0                       -- 32-bit R0:R1 / R2 -> quotient/remainder
000141ca  bhs   0x141d7 (branch on carry/high, skips the 0xffff path)
000141cc  ...
000141ce  ...   -- real division result computed here (INT_DIV, SUBPIECE)
000141d0  mov:g.w R1,R0                       -- move quotient into R0 (return reg)
000141d2  bra   0x141d7
000141d4  mov:i #0xffff:16,R0                 -- saturation/error path, R0 = 0xffff
000141d7  mov:g.w @SP+,R2                     -- restore c's saved register
000141d9  unlk
```

### Control-flow graph (via analyze_control_flow, confirmed not assumed)

5 basic blocks, cyclomatic complexity 3, two conditional blocks
(`0x141ba`, `0x141ca`) converging into a single exit block at
`0x141d7`. This is a completely ordinary if/else-converging-on-return
shape -- `0x141ce`'s real division result and `0x141d4`'s `0xffff`
saturation value are the two legitimate candidate values for R0 at the
join point. **This confirms the control flow itself is not the bug**
-- a MULTIEQUAL/join here merging these two paths' R0 value into one
HighVariable is exactly correct compiler-theory behavior.

### mergeOp diagnostic output (the actual merge event)

```
mergeOp at 0x141d7 opcode=BUILD out_addr=0x0 out_space=register out_high=...8410
  in[0] addr=0xaad02 space=unique high=...7ED0 is_written=1  def_op=SUBPIECE def_addr=0x141ce
  in[1] addr=0x0 space=register high=...8170 is_written=1  def_op=COPY def_addr=0x141d4
```

`in[0]` is the real division result (`SUBPIECE` truncating the 32-bit
quotient at the block ending in the division). `in[1]` is the `0xffff`
saturation value (`COPY` from the `mov:i #0xffff:16,R0` at `0x141d4`).
Both write to register offset `0x0` (R0) and get forced into the same
HighVariable by `Merge::mergeOp` (`merge.cc`), which is correct -- they
are the two legitimate join candidates for R0's value at the shared
exit block.

### Revised theory (supersedes the earlier INDIRECT/heritage theory)

The wrong-return-value bug is **not** in the join/merge decision
itself -- both real candidate values are correctly identified and
correctly merged into one HighVariable. The bug must be one level
higher: in how the decompiler picks a **representative
name/symbol/display value** for that merged HighVariable. Somewhere,
this representative-selection logic is choosing `b`'s storage/symbol
association instead of either of the two real R0-holding varnodes
(`uVar3`, the SUBPIECE result, or the 0xffff immediate) -- printing
`return b;`, which is neither of the two legitimate values.

This is consistent with 9561's fix as the trigger: before the fix, the
SEGMENTOP-resolved LOAD for `c` (at `0x141c4`) failed to resolve and
fell into generic alias-array handling (the `auStack_` shape). After
the fix, `c`'s LOAD resolves cleanly as a real stack variable -- which
changes what varnodes/symbols are "in scope" and considered as naming
candidates when Merge/HighVariable machinery picks a representative
for the R0 join. It is plausible `b`'s Varnode (also register/stack
resident nearby) becomes an eligible "same storage class" candidate
for the representative pick only once 9561's fix removes whatever was
previously occupying or shadowing that role.

## Root cause confirmed (2026-09-02, second diagnostic pass)

Added a second scoped diagnostic to `HighVariable::getNameRepresentative`
(`variable.cc`), gated to any merged HighVariable containing a member
defined within `muldiv_u16`'s address range, logging the full `inst`
member list and the chosen representative. Rebuilt full Ghidra, ran
against the live instance.

The critical entry:

```
getNameRepresentative: inst.size()=3 chosen_addr=0x6 chosen_space=stack chosen_isInput=1 chosen_isAddrTied=1 chosen_isWritten=0
  member addr=0x2 space=register isInput=0 isAddrTied=0 isWritten=1 def_op=DELAY_SLOT def_addr=0x141ce
  member addr=0x2 space=register isInput=0 isAddrTied=0 isWritten=1 def_op=DELAY_SLOT def_addr=0x141c2
  member addr=0x6 space=stack isInput=1 isAddrTied=1 isWritten=0
```

**This is the actual bug.** A single HighVariable contains three
members that should never share one logical variable:

- Two `register:2` varnodes, both defined by `DELAY_SLOT` ops at
  `0x141c2`/`0x141ce` -- these are working-register generations
  belonging to the `divxu.w R2,R0` 32-bit division (R1/R2 hold
  dividend/divisor halves per H8 semantics).
- One `stack:0x6` varnode, `isInput=1`, `isAddrTied=1` -- this is
  parameter storage for one of the function's real incoming
  arguments (stack offset 0x6).

`HighVariable::compareName`'s priority rules (see `variable.cc`
~line 456) give `isInput()`+`isAddrTied()` varnodes top priority for
the *display name* -- correctly, by that function's own logic, once
handed this member list. The bug is **upstream**: `stack:0x6` and
`register:2` are being merged into the same HighVariable at all. They
have no legitimate reason to share storage or be treated as the same
logical variable -- one is a parameter's stack home, the other is a
transient division-computation register. This merge decision is made
by `Merge`'s cover/liveness-intersection logic (most likely
`Merge::mergeLinear` or `Merge::merge` in `merge.cc`, not the
per-op `mergeOp` that was the first diagnostic's target -- that one
only showed the *legitimate* R0 join, which is a separate, correct
merge from this one).

**Working theory, refined**: 9561's fix changes what LOAD resolves for
the SEGMENTOP-nested-in-INT_ADD access (parameter `c`'s stack read at
`0x141c4`). This is very likely changing the computed address-cover
range the decompiler associates with the surrounding stack frame
during heritage/cover analysis, in a way that causes the *unrelated*
`stack:0x6` parameter's cover to be computed as overlapping with
`register:2`'s liveness range when it should not. This is consistent
with the multi-parameter-only trigger pattern (functions needing
several distinct stack/register slots resolved close together in the
same frame are the ones exposed) and with `sat_add_u16` being
unaffected (only one SEGMENTOP-resolved access, no register-argument
neighbors to collide with).

## Call-site elimination (2026-09-02, third diagnostic pass)

Confirmed via `Merge::merge` diagnostic that the bad pairing is real
and reproducible on every rebuild:

```
Merge::merge caller=unknown isspeculative=0 willIntersect=0
 high1 numInstances=1
   addr=0x2 space=register isInput=0 isAddrTied=0 def_op=DELAY_SLOT def_addr=0x141c2
 high2 numInstances=1
   addr=0x6 space=stack isInput=1 isAddrTied=1
```

Added a static `DIAG_callerTag` string (file-scope in `merge.cc`,
declared before first use) that the two known `isspeculative=false`
call sites *within merge.cc* (`Merge::mergeOpcode`'s required-merge
loop, and `Merge::mergeMultiEntry`'s second loop) set immediately
before calling `merge()`, so the diagnostic inside `merge()` could
report which one is actually responsible.

**Result: every single logged call, including the register:2/stack:0x6
one, shows `caller=unknown`.** Neither tag was ever set before this
particular call fired. This positively rules out both remaining
`merge.cc`-internal candidates:

- `Merge::mergeOpcode`: only fires for legitimate, unrelated pairs in
  this function (e.g. `register:2`/`unique` COPY-merges) -- confirmed
  via an earlier, separate diagnostic pass at that exact call site.
- `Merge::mergeMultiEntry`: an even earlier diagnostic (gated on the
  same address/offset pair, placed at the `mergeList` construction
  point) never fires at all for this pair -- `symentry_diag.txt` and
  `multientry_diag.txt` are both empty across multiple rebuild/test
  cycles.
- `Merge::mergeAdjacent` (line ~1081): ruled out on `isspeculative`
  value alone (`mergeAdjacent` always calls `merge(...,true)`; the
  real bad call is `isspeculative=0`).

**Conclusion: the call originates outside `merge.cc` entirely.**
Most likely `coreaction.cc` (an `Action` subclass calling
`data.getMerge().merge(...)` or an equivalent public entry point) or
another file with a legitimate reason to force a required merge. An
earlier broad keyword search found candidates at `coreaction.cc:3563`
(`ActionMergeRequired`-adjacent, calls `inflateTest`, a related but
distinct function -- not yet fully explored) and `coreaction.cc:5209`
(not yet examined at all).

## Further elimination (2026-09-02, fourth diagnostic pass)

Checked the two remaining `coreaction.cc` candidates from the earlier
broad search:

- `coreaction.cc:3563` (`ActionMarkImplied::checkImpliedCover`): calls
  `inflateTest` (read-only, blocks marking-implied on `true`) but never
  calls `merge()` at all. Not a candidate; ruled out by inspection.
- `coreaction.cc:5209` (`ActionHideShadow::apply`): calls
  `Merge::hideShadows(high)`, which doesn't call `merge()` directly --
  it uses `copyShadow()` to test whether two varnodes are pure-COPY
  shadows of each other, then rewrites the P-code graph directly via
  `data.opSetInput(...)` (redirecting one COPY's input), which could
  indirectly cause a later, already-tagged merge to succeed. Added a
  diagnostic directly inside `hideShadows`'s `copyShadow` check, gated
  on the same register:2/stack:0x6 pair.

**Result: `hideshadow_diag.txt` is empty.** `copyShadow()` never
returns true for this pair -- confirmed correct, since they have no
legitimate common COPY-chain origin. This rules out `hideShadows` as
the mechanism, whether direct or indirect.

**State of elimination so far**: every `isspeculative=false` call site
in `merge.cc` (`mergeOpcode`, `mergeMultiEntry`, `mergeAdjacent` by
its `isspeculative` value alone) is ruled out by direct evidence.
`hideShadows`'s indirect route is also ruled out. The `Merge::merge`
call that actually performs the bad merge continues to log
`caller=unknown` on every rebuild, meaning the true call site has not
yet had `DIAG_callerTag` set before it fires.

## Not yet done

- The remaining possibility is that `Merge::merge` is called from a
  location not yet searched at all -- the earlier keyword search
  (`grep "merge\(high|merge\(.*High"` etc.) may have missed the real
  call site due to variable naming or indirection (e.g. called via a
  function pointer, a virtual method, or through `Funcdata`'s own
  wrapper rather than `Merge`'s methods directly). Worth a broader,
  less keyword-specific search across the whole `cpp/` directory for
  anything invoking `getMerge()` or constructing/calling into `Merge`.
- Alternative approach: rather than keep tagging individual call
  sites reactively, consider instrumenting `Merge::merge` to print
  a full call stack (platform-specific; may need `CaptureStackBackTrace`
  on Windows or similar) the first time it's called with our specific
  pair, to get the actual caller directly instead of eliminating
  candidates one at a time.
- Given the number of rebuild cycles this has taken, also worth
  reconsidering whether a synthetic, self-contained datatest fixture
  for `muldiv_u16` is worth another attempt (see "decompile_test
  isolation" notes below) to cut iteration time from ~4-8 minutes
  (full Ghidra rebuild) to under 2 minutes (native-only rebuild).

## decompile_test isolation attempt (2026-09-02, not yet successful)

Attempted to build a standalone `.xml` datatest fixture for
`muldiv_u16` (same format as `nestedsegmentop.xml`) to allow using the
much faster `decompile_test`/`ghidra_test.exe` native-only build
(~15s-1m19s) instead of `buildGhidra` (~4-8 min, and has repeatedly
exceeded the tool-call timeout in this session) for the remaining
diagnostic iterations.

Extracted the real 32 bytes for `muldiv_u16` via
`disassemble_bytes`/`disassemble_function` and assembled them into a
`bytechunk`, following `nestedsegmentop.xml`'s exact format. Running
this in isolation fails with `Bytes at <addr> are not mapped`, where
`<addr>` is always some offset past the declared 32-byte range,
proportional to the chosen base address. `get_function_xrefs` (calls
*into* `muldiv_u16`) shows 13 callers but no outgoing references,
consistent with the function being pure arithmetic with no calls or
data-table reads in its own body -- so the missing-memory reference is
likely implicit (e.g. a default stack region the harness doesn't
provide automatically the way `sat_add_u16`'s working test apparently
gets, possibly because `divxu.w`'s underlying pcodeop or the specific
calling convention triggers a lookup `sat_add_u16`'s simpler shape
does not).

A parallel attempt to extract real surrounding bytes directly from the
raw ROM file (`RVR_1998_x3 4g63t 21000011 md352553.hex`) using
`fileOffset = memAddress - min_address` (`min_address=0xee80` per
`get_current_program_info`) produced bytes that did **not** match the
already-confirmed disassembly at the expected offset -- meaning the
ROM file's raw layout does not map linearly to memory address via
`min_address` alone (likely bank-switched/paged addressing typical of
H8 firmware). Not pursued further given the mismatch.

**Not resolved.** Still relying on `buildGhidra` + live MCP connection
for the actual trigger/observe cycle; `decompile_test` is only being
used as a fast pre-flight compile-check before each full rebuild,
which is a smaller but still real time saving.

### Second attempt: decompile.exe with `load file` (also not successful)

Discovered `decompile.exe` alongside `ghidra_test.exe`/`sleigh.exe` in
the native build output -- this is the same interactive
`IfaceStatus`/console binary the datatests harness is built on, but
without the test-runner wrapper, and it registers extra
console-specific commands not available to datatests scripts:
`load file`, `addpath`, `save`, `restore` (see `consolemain.cc`).
`load file <filename> [<target>]` calls
`ArchitectureCapability::findCapability(filename)`, which raised the
possibility of loading the real ROM binary directly (avoiding both the
missing-memory problem and the raw-file offset-mismatch problem from
the first attempt, since the real file's bytes would all be present).

Tried `load file "<path to .hex>" H8:BE:32:H8539F:default` via an init
script (`decompile.exe -i script.txt`). This hung indefinitely with no
output at all (not even an error), and had to be killed manually.

Reading `ArchitectureCapability::findCapability`
(`architecture.cc:92`) shows capability matching is done via
`isFileMatch(filename)` -- almost certainly extension-based -- not via
the target/language string passed as the second argument (that string
is only used later, as `target`, once a capability has already
matched). It's likely no registered `ArchitectureCapability` in this
build recognizes a bare `.hex` extension as raw binary, and the load
call is blocking on something (possibly an interactive prompt on
stdin that the init-script mode doesn't satisfy) rather than failing
cleanly.

**Not pursued further.** Confirmed the process was fully killed
afterward (`Get-Process decompile` returns nothing). Reverting to the
proven `buildGhidra` + live MCP connection path for the next
diagnostic iteration (call-stack capture in `Merge::merge`).

**Real wins from this exploration, despite the `load file` dead end**:
confirmed `decompile_test`'s ~15s-1m19s compile-only rebuild is a
genuine, reliable way to catch syntax errors before committing to a
`buildGhidra` cycle (already in active use); cleared a disk-space
exhaustion issue (`C:` was down to ~1.6MB free at one point this
session, causing a `buildGhidra` failure unrelated to any source
change) that would otherwise have kept blocking builds silently.

### Third attempt: swap the fast-rebuilt decompile.exe into the already-running Ghidra instance (disproved)

Hypothesis: Ghidra's Java side spawns the native `decompile`/`decompile.exe`
as a subprocess for actual decompilation, and this session's Ghidra
instance appeared to be launched from the source tree directly (only
one `decompile.exe` exists anywhere under the repo, at
`Ghidra/Features/Decompiler/build/os/win_x86_64/decompile.exe`, the
exact `buildNatives.gradle`-produced output). If true, rebuilding just
this one native executable via the fast, existing
`:Decompiler:decompileWin_x86_64Executable` Gradle task (confirmed
~15s when up-to-date, ~1m10s on a real rebuild -- much faster than
`buildGhidra`'s 4-8 min) and leaving the already-running Ghidra
instance alone (no restart) might be enough to pick up native-side
diagnostic changes live.

Tested decisively: added a unique marker string
(`PATHTEST_MARKER_v2`) to the already-reliable `Merge::merge`
diagnostic (known to fire on every decompile of `muldiv_u16`, not
gated on the bug reproducing), rebuilt via
`decompileWin_x86_64Executable` only (no `buildGhidra`), cleared the
diagnostic output file, and force-decompiled `muldiv_u16` via MCP
against the **already-running, not-restarted** instance.

**Result: the marker did not appear.** `Get-CimInstance
Win32_Process -Filter "Name='decompile.exe'"` also showed no running
`decompile.exe` process at the time, consistent with the live instance
either using a separately-packaged/copied binary from a prior
`buildGhidra` run, or a different subprocess invocation path than
assumed. **This disproves the swap-in-place hypothesis.**

**Conclusion**: `buildGhidra` (or at minimum, a Ghidra restart against
freshly-copied native binaries) is genuinely required to observe
native-side changes live via MCP -- there is no shortcut around it
with the current setup. `decompileWin_x86_64Executable` (or
`decompile_test`) remain useful only as fast pre-flight
compile-and-logic sanity checks before paying the full `buildGhidra`
cost, not as a replacement for it. Marker strings removed from both
diagnostics after this test.

### Fourth attempt: restart Ghidra (not just swap the binary) against the fast-rebuilt decompile.exe (also disproved)

Re-tested the same idea, this time with an actual Ghidra restart (not
just leaving the old process running), on the theory that the running
instance might cache/lock its subprocess binary at startup and only
need a restart, not a full `buildGhidra`, to pick up a fresh native
build. This distinction matters because `h8539f.cspec` itself
documents this exact successful pattern for a past cspec-only change
(2026-07-22 R0R1 revert, confirmed via "a genuine full Ghidra restart
+ fresh ROM reopen").

Added a fresh marker (`RESTARTTEST_MARKER_v1`) to the same reliable
`Merge::merge` diagnostic, rebuilt via `decompileWin_x86_64Executable`
only (1m2s), then had the user fully restart Ghidra and reopen the
ROM before force-decompiling `muldiv_u16` again.

**Result: marker still absent**, even after a genuine restart -- the
diagnostic fired 9 times with real content, confirming the instance
*is* running compiled diagnostic code, just an older version that
predates this session's most recent `merge.cc` edits. This is a
stronger, more conclusive negative than the third attempt (which only
tested without a restart) -- it shows the discrepancy is likely a
build/packaging-location mismatch (this Ghidra instance is not reading
`decompile.exe` from `build/os/win_x86_64/` at all, contrary to what
"only one decompile.exe exists in the repo" suggested), not merely a
question of restart-vs-no-restart.

**Confirmed for good: `buildGhidra` is the only reliable way found so
far to get native changes observed live.** No further attempts at a
shortcut planned unless new evidence emerges about where the live
instance's actual binary comes from.

### Bonus finding from this test's diagnostic output: two independent merge chains, not one

The full `mergecall_diag.txt` capture from this test showed the
`register:2`/`stack:0x6` bad pairing is only one of *two separate*
merge chains active in this function, which happen to collide because
H8's calling convention reuses register numbers across unrelated
roles:

1. **Chain A (register 0, legitimate)**: `register:0` (the `BUILD` join
   at `0x141d7`, i.e. the real R0 return-value convergence point)
   progressively merges with `unique:0xaad02` (`SUBPIECE` division
   result, `0x141ce`) and then with `register:0`/`COPY` (`0x141d4`,
   the `0xffff` saturation value) -- this is the correct, intended R0
   join discussed in the second diagnostic pass above.
2. **Chain B (register 2, the bug)**: `register:2` (`DELAY_SLOT`,
   `0x141c2`) merges with `unique:0xa2700`/`0xa2702` (also
   `SUBPIECE`/`COPY` of the division's *other* half) and, separately
   and incorrectly, with `stack:0x6` (the real parameter).

These two chains don't fully overlap, but the presence of *two*
concurrent, unrelated merge chains both touching registers that
`divxu.w`'s 32-bit dividend (R0:R1 pair per H8 semantics, occupying
register offsets 0x0 and 0x2) writes through is a plausible reason the
decompiler's per-op merge logic ends up conflating storage that should
stay separate -- worth keeping in mind for whichever call site
eventually turns out to be the real culprit.

- Confirm the theory above by tracing which `Action` actually performs
  the incorrect merge (add debug instrumentation to
  `ActionMergeCopy`/`Heritage` gated to these specific functions'
  addresses, the same disciplined way the original `vnSpacebase`
  investigation did -- see `review17.md`'s tooling notes).
- Determine whether the fix belongs in heritage/merge logic (general,
  affects all targets) or is specific to this H8 sleigh spec's mixed
  register/stack calling convention definitions.
- Check whether `muldiv_u16_shr8_sat` and the remaining `mul_u16_*`
  family (visible in the function list, not yet checked) show the
  same pattern -- would help confirm the "stack param + register
  param" precondition more rigorously.
- Once root cause is confirmed, decide whether the fix ships as its
  own separate PR (referencing this doc and #9561), gated behind a
  clean regression test the same way `nestedsegmentop.xml` was built
  for `9561`.

## Relationship to 9561 / #9561

This regression blocks `9561` from safely coming out of draft as-is:
trading the merged-array symptom for a silently wrong computed return
value is a worse outcome for the affected functions, not a strict
improvement. `9561`'s own fix is not being reverted or changed based
on this -- the merge-array resolution it performs is correct and
necessary -- but it should not ship until this triggered regression is
understood and either fixed or the trigger is avoided.
