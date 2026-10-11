#!/usr/bin/env python3
"""Categorize Gmail drafts by purpose and firm.

Input: one or more JSON files saved from the Gmail `list_drafts` tool
(view=DRAFT_VIEW_FULL), each shaped {"drafts": [...], "nextPageToken": ...},
or a plain JSON list of drafts.

Output (in --out, default ./out):
  index.json  - one record per draft: short number, draft id, firm, firm type,
                purpose, hook, recipient, greeting, subject, clean body, flags
  DRAFTS.md   - the same, grouped by purpose then firm, for reading in chat

Usage:
  python3 drafts/categorize.py PAGE1.json [PAGE2.json ...] \
      [--attachments HAS_ATTACHMENT.json] [--out out]

--attachments takes the saved output of `list_drafts` with query
"has:attachment"; without it, attachment mentions are only flagged to verify.
"""
import argparse
import html
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

# domain -> (firm name, firm type)
FIRMS = {
    "gs.com": ("Goldman Sachs", "Bulge Bracket"),
    "jpmorgan.com": ("J.P. Morgan", "Bulge Bracket"),
    "bofa.com": ("Bank of America", "Bulge Bracket"),
    "citi.com": ("Citi", "Bulge Bracket"),
    "citigroup.com": ("Citi", "Bulge Bracket"),
    "morganstanley.com": ("Morgan Stanley", "Bulge Bracket"),
    "barclays.com": ("Barclays", "Bulge Bracket"),
    "db.com": ("Deutsche Bank", "Bulge Bracket"),
    "ubs.com": ("UBS", "Bulge Bracket"),
    "wellsfargo.com": ("Wells Fargo", "Bulge Bracket"),
    "mizuhogroup.com": ("Mizuho", "Bulge Bracket"),
    "moelis.com": ("Moelis", "Elite Boutique"),
    "evercore.com": ("Evercore", "Elite Boutique"),
    "lazard.com": ("Lazard", "Elite Boutique"),
    "centerview.com": ("Centerview", "Elite Boutique"),
    "pwpartners.com": ("PJT / Perella Weinberg", "Elite Boutique"),
    "pjtpartners.com": ("PJT Partners", "Elite Boutique"),
    "rothschildandco.com": ("Rothschild & Co", "Elite Boutique"),
    "raine.com": ("Raine", "Elite Boutique"),
    "liontree.com": ("LionTree", "Elite Boutique"),
    "guggenheimsecurities.com": ("Guggenheim", "Middle Market / Boutique"),
    "breancapital.com": ("Brean Capital", "Middle Market / Boutique"),
    "jefferies.com": ("Jefferies", "Middle Market / Boutique"),
    "houlihan.com": ("Houlihan Lokey", "Middle Market / Boutique"),
    "hl.com": ("Houlihan Lokey", "Middle Market / Boutique"),
    "williamblair.com": ("William Blair", "Middle Market / Boutique"),
    "kkr.com": ("KKR", "Private Equity"),
    "veritascapital.com": ("Veritas Capital", "Private Equity"),
    "lindsaygoldbergllc.com": ("Lindsay Goldberg", "Private Equity"),
    "stonepoint.com": ("Stone Point", "Private Equity"),
    "vistaequitypartners.com": ("Vista Equity", "Private Equity"),
    "crestview.com": ("Crestview", "Private Equity"),
    "brookfield.com": ("Brookfield", "Private Equity"),
    "blackstone.com": ("Blackstone", "Private Equity"),
    "llrpartners.com": ("LLR Partners", "Private Equity"),
    "ardeapartners.com": ("Ardea Partners", "Investment Firm"),
    "point72.com": ("Point72", "Hedge Fund"),
    "mlp.com": ("Millennium", "Hedge Fund"),
    "fortress.com": ("Fortress", "Hedge Fund"),
    "citadel.com": ("Citadel", "Hedge Fund"),
}

# Names used in subject lines -> canonical firm name (for drafts whose
# recipient is missing or at a school address).
SUBJECT_ALIASES = {
    "goldman": "Goldman Sachs", "deutsche bank": "Deutsche Bank",
    "morgan stanley": "Morgan Stanley", "veritas": "Veritas Capital",
    "vista": "Vista Equity", "rothschild": "Rothschild & Co",
    "lindsay goldberg": "Lindsay Goldberg", "stone point": "Stone Point",
    "point72": "Point72", "millennium": "Millennium", "fortress": "Fortress",
    "crestview": "Crestview", "brookfield": "Brookfield", "kkr": "KKR",
    "brean capital": "Brean Capital", "citi": "Citi", "ubs": "UBS",
    "lazard": "Lazard", "moelis": "Moelis", "mizuho": "Mizuho",
    "raine": "Raine", "liontree": "LionTree", "ardea": "Ardea Partners",
    "evercore": "Evercore", "centerview": "Centerview",
}
TYPE_BY_FIRM = {name: kind for name, kind in FIRMS.values()}

PURPOSE_ORDER = [
    "Follow-up (nudge on earlier email)",
    "Thank-you / post-event",
    "Reconnect (someone you know)",
    "Call request",
    "Cold outreach",
    "Other",
]

NICKNAMES = {
    "matt": "matthew", "mike": "michael", "gabe": "gabriel", "will": "william",
    "ben": "benjamin", "tom": "thomas", "tommy": "thomas", "nick": "nicholas",
    "alex": "alexander", "andy": "andrew", "drew": "andrew", "sam": "samuel",
    "dan": "daniel", "jon": "jonathan", "rob": "robert", "bob": "robert",
    "chris": "christopher", "joe": "joseph", "jack": "john", "theo": "theophile",
}


def html_to_text(s):
    s = re.split(r'<div class="gmail_extra"|<div class="gmail_quote"|<blockquote', s)[0]
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</(div|p)>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s)


def clean_body(d):
    text = d.get("plaintextBody") or html_to_text(d.get("htmlBody") or "")
    # Drop quoted history ("On Mon, ... wrote:" and below).
    text = re.split(r"\n\s*On .{5,120}wrote:\s*\n", text)[0]
    lines = [line.rstrip() for line in text.strip().splitlines()]
    # Re-join hard-wrapped lines (plain-text bodies wrap at ~76 chars) but
    # keep short lines like "Thanks,\nAashir" as they are.
    out = []
    for line in lines:
        if out and out[-1] and line and len(out[-1]) >= 60:
            out[-1] += " " + line.strip()
        else:
            out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def firm_for(recipient, subject):
    domain = recipient.split("@")[-1].lower() if recipient else ""
    if domain in FIRMS:
        return FIRMS[domain]
    m = re.search(r"\|\s*(.+?)\s+(Quick Question|15 Min)", subject)
    candidates = [m.group(1)] if m else []
    candidates.append(subject)
    for text in candidates:
        low = text.lower()
        for alias in sorted(SUBJECT_ALIASES, key=len, reverse=True):
            if re.search(r"\b" + re.escape(alias) + r"\b", low):
                name = SUBJECT_ALIASES[alias]
                return name, TYPE_BY_FIRM.get(name, "Other")
    if domain:
        base = domain.split(".")[-2] if domain.count(".") >= 1 else domain
        return base.capitalize(), "Other"
    return "Unknown", "Other"


def purpose_for(subject, body):
    s, b = subject.lower(), body.lower()
    if s.startswith("re:") and re.search(r"follow(ing)? up|got buried|last note|bumping", b):
        return PURPOSE_ORDER[0]
    if re.search(r"thank|great session|having us", s):
        return PURPOSE_ORDER[1]
    if "good seeing you" in s or "good seeing you" in b[:200]:
        return PURPOSE_ORDER[2]
    if "call request" in s:
        return PURPOSE_ORDER[3]
    if "quick question" in s:
        return PURPOSE_ORDER[4]
    if s.startswith("re:"):
        return PURPOSE_ORDER[0]
    return PURPOSE_ORDER[5]


def hook_for(subject):
    """The connection the email leads with, e.g. 'Penn Sprint Football'."""
    head = re.sub(r"^(re:\s*)+", "", subject, flags=re.I).split("|")[0]
    head = re.sub(r",?\s*(Current|now)\s+Soph.*$", "", head, flags=re.I)
    head = re.sub(r"\s+(Student|Alum|Soph\.?.*)$", "", head.strip(), flags=re.I)
    return head.strip(" ,.") or "-"


def greeting_name(body):
    m = (re.match(r"\s*(?:Hi|Hello|Hey|Dear)\s+((?:(?:Mr|Ms|Mrs|Dr)\.?\s+)?[A-Z][\w'\-]*)", body)
         or re.match(r"\s*([A-Z][\w'\-]*),\s*\n", body))
    return m.group(1) if m else ""


def ascii_lower(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def name_mismatch(greet, recipient):
    if not greet or not recipient:
        return False
    local = recipient.split("@")[0].lower()
    if "." not in local:
        return False  # initials-style addresses (jsmith@) are ambiguous
    parts = [re.sub(r"\d", "", x) for x in local.split(".")]
    titled = re.match(r"(?:Mr|Ms|Mrs|Dr)\.?\s+(.+)", greet)
    if titled:  # "Mr. Bernhard" -> compare with the last name
        return ascii_lower(titled.group(1)) != parts[-1]
    first = parts[0]
    g = ascii_lower(greet)
    full = NICKNAMES.get(g, g)
    return not (first.startswith(g[:3]) or first == full or first.startswith(full[:4]))


def build(drafts, attached_ids=None):
    recip_counts = Counter(r.lower() for d in drafts for r in (d.get("toRecipients") or []))
    records = []
    for d in drafts:
        to = d.get("toRecipients") or []
        recipient = to[0] if to else ""
        subject = d.get("subject") or ""
        body = clean_body(d)
        firm, ftype = firm_for(recipient, subject)
        greet = greeting_name(body)
        flags = []
        if not to:
            flags.append("NO RECIPIENT")
        if recipient and recip_counts[recipient.lower()] > 1:
            flags.append("DUPLICATE RECIPIENT (another draft to same person)")
        if name_mismatch(greet, recipient):
            flags.append(f"greeting 'Hi {greet}' may not match {recipient}")
        has_attachment = None if attached_ids is None else d["id"] in attached_ids
        if re.search(r"\battach(ed|ing)?\b|\bresume\b", body, re.I):
            if has_attachment is None:
                flags.append("mentions attachment/resume: verify it is attached")
            elif not has_attachment:
                flags.append("says resume is attached but NOTHING IS ATTACHED")
        if re.search(r"\[[^\]]*\]|\bTODO\b|\bXX+\b|\{\{", body + subject):
            flags.append("placeholder text left in")
        subj_firm = None
        m = re.search(r"\|\s*(.+?)\s+(Quick Question|15 Min)", subject)
        if m:
            subj_firm = firm_for("", m.group(1))[0]
        if (subj_firm and subj_firm != "Unknown" and recipient
                and recipient.split("@")[-1].lower() in FIRMS and subj_firm != firm):
            flags.append(f"subject says {subj_firm} but recipient is at {firm}")
        if not body.strip():
            flags.append("EMPTY BODY")
        records.append({
            "draftId": d["id"],
            "threadId": d.get("threadId"),
            "to": to,
            "cc": d.get("ccRecipients") or [],
            "recipient": recipient,
            "greeting": greet,
            "firm": firm,
            "firmType": ftype,
            "purpose": purpose_for(subject, body),
            "hook": hook_for(subject),
            "subject": subject,
            "date": d.get("date"),
            "body": body,
            "hasAttachment": has_attachment,
            "isReply": subject.lower().startswith("re:"),
            "flags": flags,
            "viewUrl": d.get("viewUrl"),
        })
    records.sort(key=lambda r: (PURPOSE_ORDER.index(r["purpose"]), r["firmType"], r["firm"], r["recipient"]))
    for i, r in enumerate(records, 1):
        r["n"] = i
    return records


def render_md(records):
    out = ["# Draft queue", ""]
    by_p = Counter(r["purpose"] for r in records)
    by_f = Counter(r["firm"] for r in records)
    flagged = [r for r in records if r["flags"]]
    out.append(f"**{len(records)} drafts** · {len(by_f)} firms · {len(flagged)} flagged")
    out.append("")
    out.append("| Purpose | Count |")
    out.append("|---|---|")
    for p in PURPOSE_ORDER:
        if by_p[p]:
            out.append(f"| {p} | {by_p[p]} |")
    out.append("")
    out.append("| Firm | Type | Count |")
    out.append("|---|---|---|")
    for firm, c in sorted(by_f.items(), key=lambda kv: (-kv[1], kv[0])):
        ftype = next(r["firmType"] for r in records if r["firm"] == firm)
        out.append(f"| {firm} | {ftype} | {c} |")
    out.append("")
    if flagged:
        out.append("## Needs attention before sending")
        out.append("")
        for r in flagged:
            out.append(f"- **#{r['n']}** {r['firm']} · {r['recipient'] or '(no recipient)'}: " + "; ".join(r["flags"]))
        out.append("")
    groups = defaultdict(lambda: defaultdict(list))
    for r in records:
        groups[r["purpose"]][r["firm"]].append(r)
    for p in PURPOSE_ORDER:
        if p not in groups:
            continue
        out.append(f"## {p}")
        out.append("")
        for firm, rs in groups[p].items():
            out.append(f"### {firm} ({rs[0]['firmType']}): {len(rs)}")
            out.append("")
            for r in rs:
                flag = " ⚠️" if r["flags"] else ""
                clip = " 📎" if r["hasAttachment"] else ""
                out.append(f"- **#{r['n']}**{flag}{clip} {r['greeting'] or '?'} <{r['recipient'] or 'no recipient'}>: _{r['subject']}_ (hook: {r['hook']})")
            out.append("")
    return "\n".join(out)


def load(paths):
    drafts = []
    for p in paths:
        data = json.loads(Path(p).read_text())
        drafts.extend(data.get("drafts", []) if isinstance(data, dict) else data)
    seen, unique = set(), []
    for d in drafts:
        if d.get("id") and d["id"] not in seen:
            seen.add(d["id"])
            unique.append(d)
    return unique


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--attachments", help="saved list_drafts output for query has:attachment")
    ap.add_argument("--out", default="out")
    args = ap.parse_args()
    attached = {d["id"] for d in load([args.attachments])} if args.attachments else None
    records = build(load(args.inputs), attached)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.json").write_text(json.dumps(records, indent=2, ensure_ascii=False))
    (out / "DRAFTS.md").write_text(render_md(records))
    print(f"{len(records)} drafts -> {out/'index.json'}, {out/'DRAFTS.md'}")


if __name__ == "__main__":
    main()
