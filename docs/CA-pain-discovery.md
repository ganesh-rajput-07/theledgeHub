# Finding the real pain: CA discovery guide

_Last updated: 4 Nov 2026. Companion to [CA-gap-analysis.md](CA-gap-analysis.md)._

**Rule: build only where there is real pain.** Pain isn't found by thinking about it; it's found by watching people
work. Use this guide in every CA meeting and record what you learn in the log at the bottom.

## 1. How to recognise real pain

A problem is worth building for when most of these are true:

| Signal | Why it matters |
| --- | --- |
| **A deadline** (GSTR-1 on the 11th, GSTR-3B on the 20th, ITR, audit) | Pain spikes and people pay to remove it |
| **Money at stake** (lost tax credit, penalties, interest) | Easy to justify paying you |
| **Repeats every month for every client** | Turns into a subscription |
| **Solved today with Excel, WhatsApp and phone calls** | No good tool exists yet: an opening |
| **They've already tried to fix it** (hired staff, bought a tool, built a sheet) | Proof they care |
| **They ask "when can I have it?"** | The strongest signal of all |

> "That would be nice" is **not** pain. "Last month we lost 2 days on this" **is**.

## 2. Where the pain probably is (hypotheses, not facts)

Each of these must be confirmed or rejected by real firms.

### H1. Missing bills and blocked tax credit (top candidate)

**The pain:** every month the client hasn't sent all purchase bills, some vendors haven't filed their returns (so
the credit doesn't appear in GSTR-2B), and the deadline is the 20th. Staff chase clients on WhatsApp for bills and
chase vendors to file.

**What we could build:** compare GSTR-2B against the bills received and produce three lists:
- **In 2B but no bill received:** ask the client for it.
- **Bill received but not in 2B:** credit at risk, so chase the vendor.
- **Amounts differ:** check with the vendor or correct the books.

Then send the reminders automatically (WhatsApp or email) and track who has replied.

**Why it fits us:** we already extract and validate bills, with an audit trail. Competitors match the numbers; the
**chasing** (what's missing, who has to act) is where the hours go and the money is lost.

### H2. Collecting documents from clients

**The pain:** clients send bills late, in pieces, as WhatsApp photos, at month-end. Staff spend days just *getting*
the documents.

**What we could build:** a per-client monthly checklist, a WhatsApp or email inbox that files photos into the right
client automatically, and automatic reminders saying what's still missing.

### H3. GST department notices

**The pain:** notices (mismatch or scrutiny notices) arrive with deadlines and real penalties. Someone has to
understand the notice, find the relevant invoices and returns, and draft a reply.

**What we could build:** read the notice, pull up the matching documents (our document Q&A fits here), draft a
response, track the deadline. Rarer than monthly work, but high stakes, so high willingness to pay per case.

### H4. Peak-season capacity

July (ITR) and September (audits): firms can't hire enough staff. Not a product on its own; use it as a test for
the others: *"Does this save time in July?"*

### H5. Bank statement entries

Tedious, but competitors already sell this. Low priority unless a firm says it hurts most.

## 3. Questions to ask (before showing the demo)

Ask about **what happened last month**; past behaviour is honest, opinions aren't. Don't pitch first.

1. "Walk me through last month's GSTR-3B filing for one client, from collecting bills to filing."
2. "Which step took the longest? Who did it?"
3. "When did something last go wrong (missed credit, late filing, a notice)? What did it cost?"
4. "What have you tried to fix that? Why didn't it work?"
5. "If that step disappeared, what would you do with the time?"

Then show the demo and **watch which part makes them lean forward**.

Also ask:
- "How do you get purchase invoices into Tally today, and how long does it take per client per month?"
- "Do clients send bills on WhatsApp? Photos or PDFs?"
- "Which tools have you tried (Suvit, others), and why did you stop or stay?"
- "Could we test on 50–100 of your real invoices (anonymised if you prefer)?"

## 4. The best method: sit in their office

Ask one firm if you can **sit in their office for a day between the 11th and 20th of the month**, when filing
pressure is highest. Watch what the staff actually do: the WhatsApp chasing, the Excel matching, the phone calls.
**One such day is worth twenty interviews.**

## 5. Deciding what to build

After **5–10 firms**, the same pain will keep coming up. That's what we build, because they told us, not because we
guessed.

Current bet: **H1 (missing bills and blocked credit)**. It has a deadline, money at stake, repeats monthly, runs on
WhatsApp and Excel today, and builds directly on what we have. It stays a bet until the log below confirms it.

## 6. Discovery log

Fill in one row per conversation.

| Date | Firm (size, clients) | Step that took longest | Money / penalty involved | Tools used today | Asked "when can I have it?" | Hypothesis supported |
| --- | --- | --- | --- | --- | --- | --- |
| | | | | | | |

### Tally of evidence

| Hypothesis | Firms confirming | Firms rejecting | Notes |
| --- | --- | --- | --- |
| H1 Missing bills / blocked credit | 0 | 0 | |
| H2 Collecting documents | 0 | 0 | |
| H3 GST notices | 0 | 0 | |
| H4 Peak-season capacity | 0 | 0 | |
| H5 Bank statements | 0 | 0 | |
| Something new | | | |
