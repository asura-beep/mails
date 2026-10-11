# mails

A draft desk for Gmail, run from a Claude chat.

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
