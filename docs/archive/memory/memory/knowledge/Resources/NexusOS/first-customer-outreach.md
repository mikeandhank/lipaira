# First Customer Outreach

## The Person

**Name:** SDS-Mike
**Source:** GitHub Issue #2545 - anthropics/claude-code repository
**Profile:** https://github.com/SDS-Mike
**Problem:** Severe session memory loss in Claude Code

---

## The Problem

From issue #2545 (opened June 24, 2025):

> "Claude Code is experiencing severe memory loss within sessions, failing to retain explicit instructions, configuration settings, and context from earlier in the same conversation."

**Specific pain points:**
- Sets Git config, 30 minutes later Claude uses wrong username/email
- Asks for same configuration multiple times per session
- Forgets file locations and project structure discussed earlier
- Loses track of actions performed earlier in conversation
- "Workaround: Instruct Claude Code to read JSONL history files to make it remember"

**Impact:**
- Productivity loss: constantly re-explaining
- Operational errors: wrong configurations applied
- Workflow disruption: cannot maintain consistent session state

**Status:** Issue closed as "duplicate" - still not fixed (as of Aug 2025).

---

## Why This Person Matters

1. **Real pain, publicly documented** - Not a hypothetical
2. **Technical user** - Developer using CLI tools, understands the problem
3. **Active in community** - Opened issue, engaged with responses
4. **No solution yet** - Claude Code still hasn't fixed this
5. **Already looking for workarounds** - Mentioned "Persistent_Claude" tool

---

## Outreach Draft

**Subject:** Solving the Claude Code memory problem you documented

**Message:**

> Hi Mike,
> 
> I saw your GitHub issue (#2545) on Claude Code's memory loss. I've been working on exactly this problem - persistent memory for AI agents that survives sessions.
> 
> Your description hit home: "30 minutes later, Claude Code attempted to push with username 'claude'" - that's exactly the pain point.
> 
> I'm building NexusOS (github.com/nexusosai/nexusos) - an agent operating system with three-tier memory (working, episodic, semantic) that persists across restarts. It's designed specifically to solve the "forgets everything between conversations" problem.
> 
> Would love to get your feedback. Would you be open to a quick call to understand what would actually solve your workflow?
> 
> - Hank

---

## Why This outreach would work

1. **Specific** - References their exact issue, not generic
2. **Shows understanding** - Quoted their exact problem
3. **Offers solution** - Not just "sorry you're experiencing that"
4. **Low friction** - Asks for feedback, not commitment
5. **Timing** - They're still dealing with this (issue Aug 2025, now March 2026)

---

## Alternative Targets (if SDS-Mike doesn't respond)

1. **stefans71** - Created "Persistent_Claude" workaround tool (already solving this problem)
2. **BaanMaa** - Commented on the issue, clearly frustrated
3. **emci-user-bot** - "the same here... he has forgotten the thing I asked it before"

---

**Note:** Not sent yet. Awaiting approval before outreach.

_Last updated: 2026-03-13_
