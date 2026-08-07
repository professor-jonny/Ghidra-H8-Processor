IMPLEMENTATION PLAN: cspec-driven far-pointer call-argument fusion
(a real Ghidra decompiler C++ patch for the #817-class bug)
=====================================================================

STATUS: plan only, nothing written to the real Ghidra source yet.
Written 2026-08-03 after live investigation of the actual C++ (see
review2.md items 19, 26, 27 for the full dead-end history -- read
those first if picking this up cold). This file is the buildable
spec; review2.md item 27 is the investigation log that got us here.

---------------------------------------------------------------------
0. GOAL (confirmed with PJ before writing this)
---------------------------------------------------------------------
Both of:
  1. Proper fix for the reference/xref gap (already solved today by
     FixBankOffsetReferences_v2.java -- this plan does not replace
     that script, it's additive)
  2. Clean decompiled C display: a joined far-pointer argument
     (e.g. "bank<<16|offset" typed as one pointer) at call sites,
     instead of two raw pushed scalars
Delivered as a GENERAL, cspec-configurable mechanism -- not hardcoded
to one ROM's layout, so different H8/539F ROMs (or other segmented
processors) can each declare their own bank+offset call-argument
convention without touching C++ again after this lands.

---------------------------------------------------------------------
1. WHY THIS NEEDS NEW C++ (recap -- full detail in review2.md #27)
---------------------------------------------------------------------
Two existing Ghidra mechanisms were checked against the real source
and both dead-end for this specific bug shape:

  - SegmentOp::unify() / ActionSegmentize (userop.cc, coreaction.cc
    ~line 628): only ever inspects a SINGLE CALLOTHER op's own 3
    inputs. Structurally cannot see two separate prior push
    instructions -- there is no pcode-level link from a pjsr call op
    back to STOREs several instructions earlier. Not fixable by
    changing unify()'s matching logic; the information isn't there
    at that pipeline stage.

  - ParamEntry::resolveJoin() (fspec.cc line 94-116): requires each
    piece of a join to ALREADY match an independently-existing
    ParamEntry elsewhere in the same static compiler-spec model
    (findEntryByStorage, throws "<pentry> join must overlap at least
    one previous entry" otherwise). Our bank byte and offset word are
    never independently meaningful parameters anywhere else in the
    model -- they only ever exist together. Confirmed this throws at
    cspec-load time, not just "doesn't help."

The one REAL, live, per-call-site join mechanism that already exists
and actually fits our shape:
    FuncCallSpecs::checkInputJoin() / doInputJoin()   (fspec.cc ~5351)
    Architecture::constructJoinAddress()               (called at ~5392)
Currently only ever invoked from ActionParamDouble (coreaction.cc
~1692), gated on SplitVarnode::inHandHi/inHandLo -- i.e. it only
fires when some OTHER prior dataflow analysis already proved the two
Varnodes are secretly one bigger value via real arithmetic in the
program. Our bank+offset pair has no such arithmetic anywhere in the
caller -- the two pushes are genuinely independent immediates until
the callee's own (invisible-to-Ghidra) convention combines them.

CONCLUSION: checkInputJoin/doInputJoin/constructJoinAddress is the
right FUSION MECHANISM (reuse it, don't reinvent Varnode/Address
plumbing). What's missing is the right TRIGGER -- since there's no
dataflow evidence to detect this from, the trigger has to come from
"DECLARED cspec knowledge instead of a Rule pattern-matching existing
pcode. That's the new code this plan describes.

---------------------------------------------------------------------
1.5 ALL NON-C++ ALTERNATIVES NOW CONFIRMED CLOSED (2026-08-03)
---------------------------------------------------------------------
Three separate routes to avoid a C++ patch were checked this session
and all three are dead ends, not just \"harder than the C++ option\" --
worth recording so a future session doesn't re-attempt any of them:

 1. A second <segmentop> for the call-argument case. Confirmed via
    userop.cc (UserOpManage registration, ~line 516-527): a
    segmentop is indexed strictly by TARGET ADDRESS SPACE
    (s_op->getSpace()->getIndex()), and registering a second one for
    a space that already has one throws \"Multiple segmentops defined
    for same space\". This is also independently already documented
    in this repo's own NOTES.TXT (line 48-62, written before this
    session) as a hard, TESTED platform limit -- not unclaimed work.
    Even setting the throw aside, a second segmentop wouldn't help:
    the real blocker was never \"which segmentop resolves the
    address\", it's that no CALLOTHER exists at the call site at all
    for unify() to find.

 2. Restructuring the SLEIGH push constructors so the second push
    reads back the first and synthesizes one CALLOTHER, making the
    pattern single-instruction-visible to the EXISTING unify()
    mechanism (no C++ needed). Checked against the real call site:
    the actual instructions feeding table_lookup_interp /
    table_lookup_indexed are genuinely generic register pushes
    (\"mov R0,@-SP\" / \"mov R1,@-SP\" -- confirmed in review2.md item 19
    disassembly review, ~line 1084), each already independently
    calling spSegment(TP,SP) via the shared r0_push/r1_push-style
    constructors used for EVERY register-list push in the ISA, not
    something specific to far-pointer calls. Which register holds
    \"bank\" vs \"offset\" is a property of the CALLEE's calling
    convention, invisible to either push instruction's own encoding.
    Making r0_push/r1_push \"aware\" they're sometimes building a far
    pointer would require carrying call-site-specific ABI knowledge
    across two independently-matched instructions -- the identical
    cross-instruction problem as unify(), just relocated into SLEIGH.
    Structurally the same wall, not a smaller version of it.

 3. ParamEntry::resolveJoin() / <pentry><addr space=\"join\"> -- see
    section 1 above and review2.md item 27's TODO-closed entry.
    Confirmed by reading fspec.cc directly: no piece1/piece2 syntax
    exists in the decoder, and even a correctly-built join address
    would be rejected by resolveJoin's requirement that both pieces
    already match an independently-existing ParamEntry.

All three fail for a VARIANT OF THE SAME REASON: every existing
Ghidra mechanism for combining two values into one either (a) looks
at a single instruction/op in isolation, or (b) requires the pieces
to be independently meaningful elsewhere in the static model. Our
bank+offset pair is cross-instruction AND only ever meaningful
together -- it doesn't fit the shape any existing mechanism was built
to recognize. This is exactly why PIECE B below needs a genuinely new
Action rather than extending something that already exists: the gap
isn't a missing case in an existing rule, it's a class of problem none
of the existing rules were designed to address.

Net effect: this doesn't change the plan below, it just closes off
every remaining excuse to avoid it. If the display fix (goal 2) is
wanted, Pieces A-D are the only architecturally sound path found.

PIECE A -- new cspec schema element: <farpointerjoin>
-------------------------------------------------------
File: fspec.hh / fspec.cc

New ElementId + AttributeIds, following the exact pattern of the
existing ones at fspec.cc lines 21-52 (ATTRIB_*, ELEM_* registration
block). Pick unused numeric IDs -- existing ones run up through at
least 173 (ELEM_UNAFFECTED) and 286 (ELEM_INTERNAL_STORAGE) for a
newer addition, so use something clearly free, e.g.:
    ElementId ELEM_FARPOINTERJOIN = ElementId("farpointerjoin", 287);
    AttributeId ATTRIB_HISLOT = AttributeId("hislot", 130);
    AttributeId ATTRIB_JOINSIZE = AttributeId("joinsize", 131);
(Renumber against whatever the live tree actually has free at
implementation time -- re-grep ATTRIB_/ELEM_ id numbers immediately
before adding, since other patches may have claimed numbers since
this plan was written.)

XML shape, living INSIDE <prototype> (sibling of <returnsym>, per the
real decode loop read at fspec.cc line 4744-4776):

    <prototype name="__stdcall_far_2arg" ...>
      <returnsym> ... </returnsym>
      <input>
        <pentry minsize="2" maxsize="2"> <addr space="stack" offset="4"/> </pentry>
        <pentry minsize="1" maxsize="1"> <addr space="stack" offset="6"/> </pentry>
      </input>
      <farpointerjoin hislot="1" joinsize="3"/>   <!-- NEW -->
    </prototype>

hislot=N: index (0-based, matching input <pentry> declaration order)
of the MOST significant piece (the bank byte in our case -- matches
the ishislot bool that checkInputJoin/doInputJoin already take).
joinsize: sanity-check total byte size of the fused value (3 in our
case: 1-byte bank + 2-byte offset). Reject-and-throw at decode time
if it doesn't match the sum of the two adjacent pentry sizes -- fail
loud at cspec load, not silently at decompile time.

Only slot pair (hislot, hislot+1) is supported per prototype for a
first cut -- matches checkInputJoin/doInputJoin's existing signature
exactly (int4 slot1, bool ishislot), no new multi-piece plumbing
needed. Multiple <farpointerjoin> elements per <prototype> allowed
(a function could theoretically take more than one far pointer arg),
just decode into a vector.

WHERE THIS LIVES: NOT ParamListStandard (that's the shared default
parameter-model -- <pentry>/<group>/<modelrule> at fspec.cc line
1477-1500 -- it has no idea which specific function it's binding).
This must be a per-FuncProto property, decoded in FuncProto::decode()
(fspec.cc line 4677), stored as a new member on FuncProto:

    // in fspec.hh, class FuncProto, alongside effectlist/likelytrash:
    struct FarPointerJoinSpec {
      int4 hislot;
      int4 joinsize;
    };
    vector<FarPointerJoinSpec> farPointerJoins;

Decode block goes right after the <returnsym>/ELEM_ADDR handling
(after line 4776, before the voidinputlock/modellock flag-fixup at
line 4778), as a peekElement() loop consuming any <farpointerjoin>
siblings the same way the existing subId dispatch does.

Needs: getPieces()/setPieces()/copy() (fspec.hh lines 1384-1385, 1382)
updated to carry farPointerJoins through -- these are the existing
prototype-cloning paths (used e.g. by FuncCallSpecs::clone at fspec.hh
1684) and if we don't thread it through, a cloned call spec silently
loses the join spec. Check every call site of getPieces/setPieces/copy
in fspec.cc before considering this piece done -- do not assume the
three obvious ones are the only callers.

PIECE B -- new Action: ActionFarPointerJoin
-------------------------------------------------------
File: coreaction.cc

Modeled directly on ActionParamDouble::apply (coreaction.cc line
1692-1759), specifically the branch at line 1731-1758 (the
"!fc->isInputLocked()" search-for-joinable-adjacent-slots branch) --
copy its STRUCTURE, replace its TRIGGER.

Declaration (class definition, wherever ActionParamDouble's is
declared in coreaction.hh or similar -- grep for
"class ActionParamDouble" to find the exact header before writing):

    class ActionFarPointerJoin : public Action {
    public:
      ActionFarPointerJoin(const string &g) : Action(0,"farpointerjoin",g) {}
      virtual Action *clone(const ActionGroupList &grouplist) const {
        if (!grouplist.contains(getGroup())) return (Action *)0;
        return new ActionFarPointerJoin(getGroup());
      }
      virtual int4 apply(Funcdata &data);
    };

apply() body -- pseudocode grounded in the real API read this session:

    for (i = 0; i < data.numCalls(); ++i) {
      fc = data.getCallSpecs(i);
      if (!fc->isInputActive()) continue;          // mirrors line 1698
      if (fc->getFarPointerJoins().empty()) continue;   // new accessor, nothing declared for this prototype
      ParamActive *active = fc->getActiveInput();
      PcodeOp *op = fc->getOp();
      for (each FarPointerJoinSpec spec in fc->getFarPointerJoins()) {
        int4 j = spec.hislot;
        if (j+1 >= op->numInput()) continue;        // bounds check
        Varnode *vn1 = op->getIn(j);
        Varnode *vn2 = op->getIn(j+1);
        bool isslothi = true;                       // hislot IS vn1 by construction here, unlike ActionParamDouble's dataflow-derived isslothi
        if (fc->checkInputJoin(j, isslothi, vn1, vn2)) {
          data.opSetInput(op, /* need a real joined Varnode here -- see OPEN QUESTION below */, j);
          data.opRemoveInput(op, j+1);
          fc->doInputJoin(j, isslothi);
          count += 1;
        }
      }
    }
    return 0;

RESOLVED 2026-08-04 (was OPEN QUESTION -- now confirmed against real
source, no longer blocking): checked whether ActionParamDouble's
line 1751 pattern (`data.opSetInput(op, whole.getWhole(), j)`) has an
equivalent for us, given we have no pre-existing whole Varnode the
way double-precision recovery does (its whole is already real
because the compiler's own arithmetic built it -- ours never does).

Read double.hh/double.cc directly. SplitVarnode::createJoinedWhole()
(double.cc line ~566-578) is the exact precedent for our case --
its own doc comment is "Create a whole Varnode from pieces,
respecting piece storage," i.e. it already handles "no prior
arithmetic joins these, just synthesize the whole from fixed
storage locations," which is precisely our bank+offset shape. Its
body is short and requires no PIECE op:

    Address newaddr;
    if (!isAddrTiedContiguous(lo,hi,newaddr))
      newaddr = data.getArch()->constructJoinAddress(
                    data.getArch()->translate,
                    hi->getAddr(), hi->getSize(),
                    lo->getAddr(), lo->getSize());
    whole = data.newVarnode(wholesize, newaddr);
    whole->setWriteMask();

This maps directly onto ActionFarPointerJoin::apply's body: build
joinaddr the same way FuncCallSpecs::doInputJoin already does
internally (glb->constructJoinAddress, confirmed real at fspec.cc
line 5392), synthesize the whole Varnode with data.newVarnode(),
mark it with setWriteMask(), then proceed as originally planned:

    Address joinaddr = glb->constructJoinAddress(glb->translate,
                            hiAddr, hiSize, loAddr, loSize);
    Varnode *wholevn = data.newVarnode(joinsize, joinaddr);
    wholevn->setWriteMask();
    data.opSetInput(op, wholevn, j);
    data.opRemoveInput(op, j+1);
    fc->doInputJoin(j, isslothi);

No PIECE op needed -- that path (option (b) in the original
question) is NOT what SplitVarnode itself does for this shape, so
there's no reason to invent something more complex than the
library's own precedent.

setWriteMask() checked directly too (varnode.hh line 326: "Mark
this as not a true write when computing SSA form" / addlflags |=
Varnode::writemask). Confirmed narrow-scope by grep: only
heritage.cc reads/acts on the flag (SSA/heritage-form construction),
and the only other two setWriteMask() call sites in the whole
codebase (coreaction.cc lines 1956, 1988) use it for the same
reason ("Don't let new Varnode cause additional heritage"). No Rule
anywhere branches on it -- confirmed getWriteMask has zero call
sites outside Varnode's own accessor, i.e. nothing downstream
special-cases a write-masked Varnode's shape. Safe to use as-is.

REMAINING UNCERTAINTY (small, deferred to smoke test not design):
isAddrTiedContiguous() is checked first in the real precedent before
falling back to constructJoinAddress -- worth keeping that same
check in ActionFarPointerJoin for consistency, though for genuinely
independent stack slots (our case) it should always fall through to
the join-address branch. Confirm this is a no-op skip for our inputs
during the Piece 3 smoke test, not by additional reading -- this is
now a runtime verification detail, not an open design question.

PIECE C -- pipeline registration
-------------------------------------------------------
File: coreaction.cc, ActionDatabase::universalAction (line 5678)

Insert directly after ActionParamDouble (line 5709) and BEFORE
ActionSegmentize (line 5710) -- actually, reconsider: our trigger
doesn't depend on ActionSegmentize's output, and ActionParamDouble is
the closest structural sibling (same isInputActive/ParamTrial-era
timing), so slot immediately after it:

    actmainloop->addAction( new ActionParamDouble("protorecovery") );
    actmainloop->addAction( new ActionFarPointerJoin("protorecovery") );  // NEW
    actmainloop->addAction( new ActionSegmentize("base"));
    ...

Rationale for exact position: must run while fc->isInputActive() is
still true (checkInputJoin line 5354 returns false otherwise) -- so
strictly before ActionActiveParam's trimming/buildInputFromTrials
commit (line 1834-1852, same mainloop, runs later in the group so
this is safe) and after the trial list is populated. Confirm on a
real debug build that isInputActive() is true at this exact point
for a representative call site before trusting the plan blindly --
timing bugs here would silently no-op the whole feature rather than
crash, so it needs a positive-confirmation test, not just "it built."

PIECE D -- cspec authoring for your ROMs
-------------------------------------------------------
File: h8539f.cspec (or a new cspec if this needs to be opt-in per-ROM)

Once A-C build and pass a smoke test, add <farpointerjoin> to the
existing __stdcall_far_2arg-style prototypes (table_lookup_interp,
table_lookup_indexed, and whichever others the review2.md item 19/26
history identified as needing this). Confirm the stack pentry offsets
match your actual push order (offset word first at +4, bank byte at
+6, per review2.md's original description of the mov #offset/mov
#bank/pjsr sequence) -- re-verify against a live disassembly, don't
assume the offsets from earlier chat turns are exactly right without
checking a real function.

---------------------------------------------------------------------
3. BUILD / TEST PLAN
---------------------------------------------------------------------
1. Build the decompiler executable from
   C:\Users\j.brophy.CORKILLSYSTEMS\github\ghidra (confirm exact build
   command/target for the decompile/sleigh binary -- not yet checked
   this session, check Ghidra's build docs or existing build scripts
   in that checkout before assuming gradle vs make).
2. Point a dev Ghidra install's decompiler at the freshly-built binary
   (standard Ghidra decompiler-dev workflow -- swap the platform-
   specific binary under Ghidra/Features/Decompiler/os/<platform>/).
3. Smoke test on ONE function first (table_lookup_interp), same
   caution as the original (superseded) join-pentry TODO in review2.md
   item 27 -- verify via get_function_variables / decompiler output
   that:
     a. The two stack args now show as ONE joined parameter
     b. No regression on functions that do NOT have <farpointerjoin>
        declared (should be completely unaffected -- the whole
        mechanism is opt-in per prototype)
     c. No regression on any OTHER architecture's cspec that doesn't
        use this element at all (should be a pure no-op path for them
        -- confirm by running against a non-H8 binary if any is handy,
        since this is a shared coreaction.cc pipeline change)
4. Only after (3) passes cleanly, roll out <farpointerjoin> to the
   remaining known far-pointer-argument prototypes across ROMs.
5. FixBankOffsetReferences_v2.java stays in place regardless -- it
   handles the xref/reference-database side, which this C++ change
   does not touch or replace.

---------------------------------------------------------------------
4. HONEST RISK ASSESSMENT
---------------------------------------------------------------------
- This is a shared-pipeline change (coreaction.cc, fspec.cc/hh) --
  even though the new Action is opt-in per-prototype via cspec, it's
  still new code running in universalAction's mainloop for EVERY
  function on EVERY architecture. A bug here (bad bounds check, wrong
  timing assumption) risks affecting non-H8 decompilation. Test step
  3c above is not optional.
- UPDATE 2026-08-04: PIECE B's synthesis question is now RESOLVED,
  see the RESOLVED note in PIECE B above. SplitVarnode::createJoinedWhole
  (double.cc ~566-578) is a directly-read, already-working precedent
  for exactly our shape (join with no pre-existing dataflow "whole"),
  and setWriteMask()'s scope was confirmed narrow by grep (only
  heritage.cc reads it; no Rule branches on it). PIECE B is no longer
  the open unknown it was -- every piece of this plan now traces to
  source actually read across the two review sessions.
- This still requires a full decompiler rebuild per iteration --
  slow edit-test loop compared to cspec-only changes. Confirm the
  local build turnaround time before committing to this path over
  just living with FixBankOffsetReferences_v2.java's xref-only fix.
- REVISED ESTIMATE (2026-08-04): closer to 1-2 days of C++ work, not
  multi-day/could-blow-up -- PIECE A is mechanical (half a day),
  PIECE C is trivial (an hour), PIECE B now has a concrete ~10-line
  body grounded in a real precedent (should be well under a day
  including the smoke-test check on isAddrTiedContiguous mentioned
  above), plus build/test turnaround on top of all of it. The
  remaining unknowns are now build/tooling logistics (build command,
  turnaround time), not design risk. Still worth reconfirming
  isAddrTiedContiguous's no-op behavior on our inputs empirically
  before declaring PIECE B fully done, but that's a smoke-test line
  item, not an open research question anymore.
