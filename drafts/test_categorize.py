import unittest

from categorize import build, clean_body, firm_for, purpose_for


def draft(id, to, subject, body, html=None):
    return {"id": id, "toRecipients": to, "subject": subject,
            "plaintextBody": body, "htmlBody": html}


class CategorizeTest(unittest.TestCase):
    def test_firm_from_domain_and_subject(self):
        self.assertEqual(firm_for("a.b@gs.com", ""), ("Goldman Sachs", "Bulge Bracket"))
        self.assertEqual(firm_for("", "Penn Sprint Football | Point72 Quick Question")[0], "Point72")
        self.assertEqual(firm_for("x@sas.upenn.edu", "Re: Penn | Raine Quick Question...")[0], "Raine")

    def test_purposes(self):
        self.assertTrue(purpose_for("Re: Penn | Raine Quick Question", "Hi A, Following up on my note").startswith("Follow-up"))
        self.assertTrue(purpose_for("Thank You from This Morning", "Hi").startswith("Thank-you"))
        self.assertEqual(purpose_for("Gilman Alum | 15 Min Call Request", "Hi"), "Call request")
        self.assertEqual(purpose_for("Penn | KKR Quick Question", "Hi"), "Cold outreach")

    def test_html_reply_drops_quote(self):
        html = ('<div>Hi Winnie,<br/><br/>Following up.<br/><br/>Thanks,<br/>Aashir</div>'
                '<div class="gmail_extra">On Mon wrote: old text</div>')
        self.assertEqual(clean_body({"htmlBody": html}), "Hi Winnie,\n\nFollowing up.\n\nThanks,\nAashir")

    def test_flags(self):
        recs = build([
            draft("1", [], "Penn | Point72 Quick Question", "Hi David,\n\nAttached is my resume."),
            draft("2", ["t.p@lazard.com"], "Penn | 15 Min Call Request", "Tyler,\n\nPenn, [SPORT]."),
            draft("3", ["t.p@lazard.com"], "Penn | Lazard Quick Question", "Hi Tyler,\n\nHello."),
            draft("4", ["jane.doe@kkr.com"], "Penn | KKR Quick Question", "Hi Mark,\n\nAttached is my resume."),
        ], attached_ids={"4"})
        flags = {r["draftId"]: " ".join(r["flags"]) for r in recs}
        self.assertIn("NO RECIPIENT", flags["1"])
        self.assertIn("NOTHING IS ATTACHED", flags["1"])
        self.assertIn("placeholder", flags["2"])
        self.assertIn("DUPLICATE", flags["3"])
        self.assertIn("may not match", flags["4"])
        self.assertNotIn("ATTACHED", flags["4"])


if __name__ == "__main__":
    unittest.main()
