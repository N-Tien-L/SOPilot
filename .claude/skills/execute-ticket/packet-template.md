# Work packet template

The orchestrator fills one packet per `v2-coder` spawn and passes it as the whole prompt. Keep it self-contained: the coder does not see this conversation. Do not paste your own conclusions about how hard or easy it is.

```markdown
# Packet <TICKET-ID>-P<n>: <short goal>

## Goal
<one or two sentences: the behaviour this packet delivers>

## Acceptance criteria covered
- <AC id>: <criterion text copied from the ticket>

## Read first
- CLAUDE.md (constraints 1-13)
- Rule: .claude/rules/<core-api|ai-service|migrations|frontend|docs>.md
- Ticket: docs/execution/initiatives/<initiative>/tickets/<file>.md
- Design: <doc path> §<section>
- Code path: <files/classes/functions to read before editing>

## Frozen contract (do not change)
<endpoint/method/path/status codes, request/response shape, DB columns, function signatures, error codes
that the orchestrator fixed; other packets depend on them>

## May edit
- <path> (existing)
- <path> (new)

## Read only
- <paths the coder needs but must not change>

## Tests to write
- <test file>::<test name> — <behaviour, including the negative tenant case if tenant-scoped>

## Commands to run (exactly these, with timeouts)
- <e.g. cd services/core-api; ./mvnw test -Dtest=XTest>
- <e.g. ./scripts/run-tests.ps1 -Scope core-api -Type unit>

## Forbidden
git/gh writes; new dependencies or manifest/lockfile edits; editing committed migrations; `.env`;
ticket/PLAN status; `.claude/**`; files outside "May edit". Stop and ask under "open questions" instead.

## Reply
Use the reply format in your agent definition (.claude/agents/v2-coder.md).
```

## Fix-round message (SendMessage to the same coder)

```markdown
Fix round <n> for packet <id>. Change only what these findings need; keep the frozen contract.
- [BLOCKER|WARNING] path:line — <finding as the reviewer wrote it, with the failure scenario>
Re-run: <commands>. Reply in the same format.
```
