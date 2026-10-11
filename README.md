# mails

A draft desk for Gmail.

**Draft Desk** (`desk/draft-desk.html`, published at
https://claude.ai/artifact/2HgHH5FvbiJhVNT1kGQ6A8) is the app: it loads your
Gmail drafts live through the Gmail connector, sorts them by purpose and firm,
flags problems (missing recipient, placeholders, "resume attached" with nothing
attached, duplicates, stale drafts, people who already replied), and lets you
edit, ask Claude to rewrite, delete, and send one draft or a batch of ready ones.
Nothing sends without a confirm step, and before sending it checks your Sent
folder for people you've already emailed.

The chat version of the same workflow:

- `drafts/categorize.py` sorts Gmail drafts by **purpose** (follow-up, thank-you,
  reconnect, call request, cold outreach) and **firm** (from the recipient's
  domain), and flags problems before sending: no recipient, leftover
  placeholders like `[SPORT]`, "resume attached" with nothing attached,
  duplicate recipients, and greetings that don't match the address.
- `.claude/skills/drafts/SKILL.md` is the chat workflow. Say "show my drafts" and
  Claude pulls the drafts through the Gmail connector, runs the categorizer, and
  then edits (`#12: change Tuesday to Wednesday`) or sends (`send all Raine
  follow-ups`) on your confirmation.

Generated output goes to `out/` (gitignored: it holds contacts' emails).

Tests: `cd drafts && python3 -m unittest`
