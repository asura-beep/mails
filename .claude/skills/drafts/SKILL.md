---
name: drafts
description: Categorize Aashir's Gmail drafts by purpose and firm, then review, edit and send them from chat. Use when he says "drafts", "show my drafts", "send my drafts", "edit #12", "send all Raine", or similar.
---

# Draft desk

Work Aashir's Gmail drafts from chat: pull them, categorize them by purpose
and firm, flag problems, then edit and send on his word.

## 1. Refresh the queue

1. Call `mcp__Gmail__list_drafts` with `pageSize: 50`, `view: DRAFT_VIEW_FULL`.
   The result is usually too big and gets saved to a file; note each saved path.
   Keep calling with `pageToken` until the result is `{}` or has no
   `nextPageToken`.
2. Call `mcp__Gmail__list_drafts` with `query: "has:attachment"`, `pageSize: 50`
   (paginate the same way) and save the result as JSON to the scratchpad.
   This is the only way to know which drafts have the resume attached.
3. Run:
   ```
   python3 drafts/categorize.py <page1> <page2> ... --attachments <has_attachment.json> --out out
   ```
   This writes `out/index.json` (one record per draft: `n`, `draftId`, `firm`,
   `firmType`, `purpose`, `hook`, `recipient`, `greeting`, `subject`, `body`,
   `hasAttachment`, `flags`) and `out/DRAFTS.md`. `out/` is gitignored and
   holds contacts' emails, so never commit it.

Draft numbers (`#n`) are only stable until the next refresh. Refresh after
any send or edit batch, and before acting on a number from an older listing.

## 2. Show the overview

Show the purpose and firm count tables and the "Needs attention" list from
`out/DRAFTS.md`, then ask how he wants to go: by firm, by purpose, flagged
first, or one by one. Do not paste all 100 drafts at once; show one group at
a time (a group = one firm, or one purpose within a firm).

When showing a single draft, show: `#n`, To, Subject, the flags, 📎 if it has
an attachment, and the full `body` from `index.json`.

## 3. Edit

Edits come in plain language ("#12: change Tuesday to Wednesday", "fix
[SPORT] to 'on the sprint football team' in all Lazard drafts").

1. Re-fetch the draft with `mcp__Gmail__get_draft` (`messageFormat: FULL_CONTENT`)
   so the edit starts from the live version, not the cached index.
2. Apply the change to both the plain text and the HTML body: keep the HTML's
   existing structure (`<br>`, `<div dir="ltr">`) and change only the text.
   For a reply draft (`Re:` subject) keep the quoted history below the new text.
3. **Attachments are dropped by `update_draft` unless re-sent.** If the draft has
   an attachment (📎), tell him the edit would remove it and offer: (a) edit in
   Gmail via the draft's `viewUrl`, or (b) re-attach the resume (step 5).
   Never silently strip an attachment.
4. Show the edited version and the exact change, then call
   `mcp__Gmail__update_draft` with `draftId`, `body`, `htmlBody` (and `to`/
   `subject` only if those changed).
5. Bulk edits (same fix across a group): show the before/after for one draft,
   list which `#n`s it will apply to, get one "yes", then apply to each.

## 4. Send

Sending cannot be undone. Only send on an explicit instruction that names
which drafts ("send #12", "send all Raine follow-ups", "send everything
not flagged").

1. Check history: `mcp__Gmail__search_threads` with `in:sent (to:a OR to:b ...)`
   for the recipients (25 per query). If the person has already replied in
   that thread (read it with `get_thread`), a "following up / in case it got
   buried" draft is stale: don't send it, and offer to delete it. A cold or
   thank-you draft to someone already emailed the same thing is a duplicate.
2. Before sending, re-check each draft against its flags. Refuse to send a
   draft that has `NO RECIPIENT`, `placeholder text left in`, or `EMPTY BODY`
   until it is fixed. For `says resume is attached but NOTHING IS ATTACHED`
   and `DUPLICATE RECIPIENT`, say so and ask whether to send anyway, fix it,
   or skip.
3. For a batch, list the exact drafts (`#n`, name, firm, subject) and the
   count, and wait for a "yes" to that list. A send instruction from earlier
   in the chat does not cover a new batch.
4. Send each with `mcp__Gmail__send_message` passing only `draftId`. Sending by
   draft id keeps the thread, the quoted history and any attachments.
5. Report what was sent and what failed, then refresh the queue (step 1).

## 5. Attaching the resume

The Gmail connector only takes attachments as base64 typed into the tool call.
His resume is about 160KB (about 210K base64 characters), so attaching it
from chat is only practical for one or two drafts, never a batch. For a batch,
the options are: he attaches it in Gmail, the "Attached is my resume" line
becomes a Drive link (the file must be shared view-only by link, which he
approves), or the line comes out and the resume goes in his reply.
Never leave "Attached is my resume" on a draft with nothing attached.

## Duplicates

When one person has two drafts, keep the newest complete one (no placeholders)
and delete the other. Before deleting, save the full drafts to
`out/deleted_drafts_backup.json` so they can be recreated. Leave drafts
created in the last hour alone and ask: he may still be writing them.

## Categories

Purpose (from subject and body):
- **Follow-up**: `Re:` drafts that nudge an earlier email ("following up", "in case it got buried")
- **Thank-you / post-event**: thanks after a session or visit
- **Reconnect**: someone he already knows ("good seeing you")
- **Call request**: "15 Min Call Request" subjects
- **Cold outreach**: "Quick Question" subjects
- **Other**: anything else

Firm comes from the recipient's domain (`FIRMS` in `drafts/categorize.py`),
falling back to the firm named in the subject. Add new domains to `FIRMS`
when a firm shows up as a bare domain name. Firm types: Bulge Bracket,
Elite Boutique, Middle Market / Boutique, Private Equity, Hedge Fund,
Investment Firm, Other.

The `hook` is the connection the email leads with (Penn Sprint Football,
Gilman, Providence Day, ...), taken from the subject.
