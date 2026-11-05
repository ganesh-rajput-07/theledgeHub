# How software for Indian CA firms is priced and licensed

_Research date: 5 Nov 2026. All prices in INR. Unless a row says otherwise, prices **exclude 18% GST**._

**How to read the source labels**

| Label | Meaning |
| --- | --- |
| **[V]** | Vendor's own page, which I opened. It is still vendor marketing, so "list price" may differ from what dealers actually charge. |
| **[3P]** | Third-party listing or reseller page that I opened (Techjockey, Freedom251, etc.). Often out of date. |
| **[S]** | Seen only in a search-result snippet. I did not open or confirm the page. Treat as a lead, not a fact. |
| **Not public** | The vendor shows no price ("contact sales" / "on request"). |

Anything in section 5 marked **Recommendation** or **Inference** is my own reasoning, not something a source says.

---

## 1. Summary

- **Invoice/bank-to-Tally automation is cheap and getting cheaper.** Vyapar TaxOne (formerly Suvit) sells one "Unlimited" plan at **₹7,000/year** (shown as 50% off ₹14,000), with a 7-day trial [V]. FinXtract charges **₹349–₹1,599/month** for 200–1,000 page credits [V*].
- **Tally now has its own invoice OCR.** "Docs by Ira" is sold as **₹200 per 100-page pack**, about ₹2 per page [V]. Every Tally user is a potential customer for it, so this sets the price CA firms will compare us against.
- **There are two big pricing families.** (a) Older desktop tax/GST software (Tally, Busy, Marg, SAG Genius/Gen GST, Winman, CompuTax, Saral) sells a **one-time licence plus a yearly renewal (TSS/AMC/"update")** of roughly 30–50% of the licence price. (b) Newer cloud tools sell **yearly subscriptions** (TaxOne, Spectrum Cloud, ClearTax) or **monthly page credits** (FinXtract).
- **What the unit is depends on the vendor.** The common units are: per user or computer (Tally Silver = 1 user on 1 computer; Gold = unlimited users on one LAN), per firm with a user cap (Spectrum Cloud: 1 or 2 users, unlimited clients), per GSTIN/invoice volume (ClearTax CA packs: 100 / 300 / unlimited GSTINs, 3,000 invoices per GSTIN per year, 5 users), and per page (FinXtract, Docs by Ira).
- **Small firms usually pay ₹5,000–₹25,000 a year per product.** Tally Silver costs ₹22,500 once plus ₹4,500/year, or ₹750/month to rent. Gen GST Desktop is ₹5,000 + ₹2,000/year, Genius ₹15,000 + ₹7,000/year, and Spectrum Cloud CA ₹6,300–₹7,200/year. Multi-user or "firm" editions cost 2–3 times the single-user price (Tally Gold ₹67,500, Busy Enterprise ₹22,000).
- **Multi-year deals get a 10–20% discount.** Tally's 2-year TSS is 10% off. TaxOne's 3-year plan is described as "save 20% more". AI Accountant reportedly offers "2 months free" on annual billing [S]. I found no public monthly price that undercuts the yearly price.
- **Trials run 7–30 days and are usually feature-complete.** TaxOne gives 7 days, FinXtract and Marg 14 days [S for Marg], Busy 15 days, and AI Accountant and Winman 30 days / 1 month. Free plans are rare: Busy Express is free, FinXtract has a 30-page DEMO tier, and AI Accountant offers free "workspaces".
- **Licence checks are usually forgiving.** Tally keeps working when TSS lapses, and only updates and connected features stop. Busy Magic subscriptions switch to **Demo Mode** when they expire, and Busy can bind data and users to chosen PCs or disks. None of the sources describes a mandatory online login at every app start, so our model is stricter than what CAs are used to.

---

## 2. Competitor pricing table (invoice/bank automation and GST reconciliation)

| Product | Unit | Tiers and prices (ex-GST unless noted) | Trial / free | Offline or cloud | Source |
| --- | --- | --- | --- | --- | --- |
| **Vyapar TaxOne** (formerly **Suvit**; suvit.io/pricing redirects here) | Per account, yearly; no user/client/voucher limits stated | One "Unlimited Plan": **₹7,000/yr** (struck-through ₹14,000, "50% off"). 3-year option "save 20% more" (price not shown). No monthly price. GST extra. | 7-day free trial, no card. No free plan. | Cloud web app; works with Tally, WhatsApp automation | [V] taxone.vyapar.com/pricing. Capterra lists a "CA Unlimited Plan" at ₹10,000/yr [S], probably an older price. |
| **AI Accountant** | "Plans are per workspace, not per account"; "pricing scales with your company" | **Not public** for the CA product (contact sales). One snippet shows Starter ₹4,000/mo and Scale ₹6,000/mo + GST, "2 months free" annually [S]. That appears to be their business/virtual-accounting plan, not CA software. | 30-day free trial; free workspaces | Cloud; native Tally Prime / ERP 9 sync (vendor claim) | [V] aiaccountant.com/linkedin/built-for-ca; [3P] Software Advice says "pricing on request" |
| **FinXtract** (bank statement and invoice extraction to Tally) | **Per page credit** (1 credit = 1 PDF page), monthly | Starter **₹349/mo** (200 credits); Pro **₹1,599/mo** (1,000 credits); Enterprise contact sales (3,000+). Extra 1,000 credits ₹1,700 (no expiry). GST reconciliation add-on ₹399/mo (struck-through ₹799). Monthly credits do not roll over. Failed extractions are free. GST treatment not stated. | 14-day trial; DEMO tier of 30 pages | Cloud web dashboard | [V*] finxtract-marketing.pages.dev/pricing and /help. *Hosted on a pages.dev domain, so it may be a pre-launch or unofficial site. Verify on finxtract.com. |
| **Tally "Docs by Ira"** (built-in AI invoice/bank-PDF to voucher, with review before posting) | **Per page pack** | **₹200 per 100-page pack** | Not stated | Inside TallyPrime; where processing happens is not stated | [V] tallysolutions.com TCO guide (updated 13 Jul 2026); feature page dated 31 Aug 2026 |
| **KDK Spectrum Cloud (CA)** | Per user, yearly; unlimited clients and returns | Essential **₹6,300/yr** (1 user); Advanced **₹7,200/yr** (2 users). KDK's own blog cites **₹27,000/yr for 5 users**, unlimited ITR/TDS/GST, "14 months access". | Free trial "on request" (length not stated) | Cloud | [3P] techjockey.com/detail/spectrum-cloud; [V] kdksoftware.com blog (28 Feb 2026) |
| **KDK ExpressGST** | Per user, per number of returns | Capterra: "from ₹8,000" [S]. SourceForge: "Professional Silver ₹2,700/yr, 500 returns, 1 user" [S]. Techjockey: "Price on request". | Free trial | Desktop and cloud variants | [S] only. The numbers conflict, so treat as **not verified**. |
| **ClearTax / Clear: GST for CA and Experts packs** | **Per GSTIN count + invoice volume + users**, 1 year | Packs: up to 100 GSTIN, up to 300 GSTIN, or Unlimited GSTIN, each with **3,000 invoices/yr/GSTIN and 5 users**. Price shows as "$1,000" with no INR price (likely a display bug). **Rupee price not public.** Users report sharp renewal increases [S, Trustpilot]. Max ITC / Clear Capture: **not public**. | Not stated | Cloud | [V] cleartax.in/services/gst_for_ca_and_experts_pack_unlimitedGSTIN/p |
| **SAG Infotech: Gen GST** | Licence + yearly update | Gen GST Desktop **₹5,000 + ₹2,000/yr**. Online GST E-Filing ₹10,000 + ₹5,000. Online All-in-One GST ₹15,000 + ₹7,000. ICAI members' 2-year online plans: ₹14,000/₹7,000 and ₹20,000/₹10,000 [S]. | Free demo download | Desktop **and** online | [V] blog.saginfotech.com price list (updated 10 Sep 2026); GST treatment not stated |
| **Winman GST** | One-time licence | **₹9,470** and ₹4,740 (two figures shown, "after 25% discount", meaning not explained). Special price for CA-ERP holders. Techjockey: "on request". | 1-month free trial, then paid registration | Desktop | [3P] freedom251.com/apps/winman (9 Oct 2026) |
| **GST reconciliation tools (reference only)** | Mostly per GSTIN per year | GSTZen ₹4,000/yr per GSTIN; ReconBridge ₹2,999/yr (25 recons/month); TCS iON MSME Lite ₹25,000/yr for 4 GSTINs; Taxilla from ₹80,000/yr | Varies | Cloud | [S] all. Not opened. |
| **CAMonk** | n/a | **Not a competitor.** CAMonk is a careers/jobs and training platform for CAs. No pricing found. | n/a | n/a | [V] camonk.com/blog |
| **Tax2win** | n/a | Not researched in depth. It is consumer ITR filing, not a firm automation tool. | | | |

---

## 3. Licence and subscription structures seen

| Structure | How it works | Examples (see tables for sources) |
| --- | --- | --- |
| **Perpetual licence + yearly renewal (TSS / AMC / "update" / BLS)** | Pay once to own the version. Pay yearly for statutory updates, new features and connected services. The software usually keeps working if you don't renew. | Tally Silver ₹22,500 + ₹4,500/yr; Busy 21 Basic ₹11,000 + ₹4,000 per 360 days; Genius ₹15,000 + ₹7,000; Gen GST ₹5,000 + ₹2,000 |
| **Single-user vs multi-user edition** | The same features. The higher edition allows more simultaneous users on one LAN or office, at 2–3 times the price. | Tally Silver (1 user, 1 PC) vs Gold (unlimited users on LAN, ₹67,500); Busy Basic vs Standard (unlimited users, one office) vs Enterprise (multiple offices); Marg Silver vs Gold [S] |
| **Extra-node / additional-licence add-on** | A base licence plus a priced extra seat. | Winman: "additional licence" ₹3,600/₹1,660 (TDS) and ₹2,420/₹1,810 (CA-ERP) [3P]; CompuGST "1+3 nodes on a single LAN" [S, IndiaMART reseller] |
| **Rental / time subscription of desktop software** | Monthly, quarterly or yearly fee. Includes updates. Stops (or goes to demo mode) when unpaid. | Tally Silver ₹750/mo, ₹2,138/3 mo, ₹8,100/12 mo; Gold ₹2,250/mo, ₹24,300/12 mo; Busy Magic START ₹5,000, SMART ₹8,000, POWER ₹12,000, POWER+ ₹50,000 (10 users, 150 companies) per 360 days |
| **Cloud subscription per firm/account (flat)** | One yearly price with "unlimited" usage. | Vyapar TaxOne ₹7,000/yr |
| **Cloud subscription per user** | Price rises with number of logins, with unlimited clients. | Spectrum Cloud 1 user ₹6,300, 2 users ₹7,200, 5 users ₹27,000 (bundle) |
| **Per GSTIN / invoice volume** | Packs sized by number of client GSTINs and invoices per GSTIN. | ClearTax CA packs (100/300/unlimited GSTIN, 3,000 invoices/GSTIN/yr, 5 users); GSTZen per GSTIN |
| **Usage credits (per page)** | A monthly credit allowance plus top-up packs. | FinXtract (₹349/200 pages, ₹1,599/1,000 pages, ₹1,700 per extra 1,000); Tally Docs by Ira (₹200/100 pages); KDK TDS "pack of 500 returns ₹1,800" [S] |
| **Per workspace with free tier** | Pay only for the workspaces (companies/clients) you upgrade. | AI Accountant |

**Effective per-page prices (my arithmetic, from the figures above):** FinXtract Starter ₹1.75/page, Pro ₹1.60/page, top-up ₹1.70/page. Docs by Ira ₹2.00/page.

---

## 4. Desktop software CAs already pay for (licensing references)

| Product | Editions and prices (ex-GST) | Unit | Renewal | Trial / free | Source |
| --- | --- | --- | --- | --- | --- |
| **TallyPrime** | Silver **₹22,500**; Gold **₹67,500** (both include 1 yr TSS). Rental: Silver ₹750/mo or ₹8,100/yr; Gold ₹2,250/mo or ₹24,300/yr. Cloud Access from ₹600 (needs an active licence + TSS). Auditor Edition TSS ₹6,750/yr. | Silver = 1 user on 1 computer; Gold = unlimited users on LAN | TSS ₹4,500/yr Silver, ₹13,500/yr Gold; 2-year ₹8,100 / ₹24,300 (10% off). Renewal page shows "10% off" offer. Some resellers quote ₹5,400 / ₹16,200 [S]. | "Education mode" until activated (free, limited) | [V] tallysolutions.com TCO guide (13 Jul 2026); [V] tipl.tallysolutions.com/renew-tss [S] |
| **BUSY** | BUSY 21 perpetual: Basic ₹11,000, Standard ₹16,500, Enterprise ₹22,000. BUSY Magic subscription (360 days): START ₹5,000, SMART ₹8,000, POWER ₹12,000, POWER+ ₹50,000. BUSY Online add-on ₹10,800 / ₹16,800. | Single user (Basic); unlimited users in one office (Standard); multi-office (Enterprise) | BLS ₹4,000 / ₹6,500 / ₹7,500 per 360 days | **Free "Express" edition**; 15-day trial, no card | [V] busy.in/pricing (no page date) |
| **Marg ERP 9+** | Basic ~₹7,200–8,991; Silver ~₹12,600 (single user); Gold ~₹25,200 (multi-user). Sold through dealers, who set their own prices. | Per edition / users | Not confirmed | 14-day trial mentioned | [S] aggregators only (margcompusoft.com did not load). **Not verified.** |
| **SAG Genius** (tax suite) | ₹15,000 install + ₹7,000/yr update | Per installation | Yearly update fee | Free demo | [V] SAG price list (10 Sep 2026) |
| **Winman CA-ERP** | ₹14,830 and ₹11,120 ("after 25% discount"); extra licence ₹2,420 / ₹1,810. Techjockey: from ₹9,850 (₹11,623 incl. GST). | Per licence + extra licences | Not stated | 1-month trial | [3P] freedom251.com (9 Oct 2026); [S] Techjockey |
| **CompuTax / CompuOffice** | Official prices **not public**. Techjockey: CompuTDS ₹4,500/yr, CompuTax GST ₹5,750 [S]. IndiaMART reseller: CompuGST ₹7,500 (₹8,850 incl. GST), 1 yr, "multi-user 1+3 nodes" [S]. KDK's blog cites CompuTax ₹5,800/yr. | Per licence with node count | Yearly | Not found | [S] / [V-competitor blog] |
| **Saral TaxOffice (Relyon)** | ₹8,800 (KDK blog and Techjockey); Techjockey review page also shows ₹5,500/user. Saral TDS from ₹5,640/yr. | Per user | Yearly | Not found | [S] / [V-competitor blog]. Numbers conflict. |

### Activation and online-check behaviour (documented)

| Product | What is documented |
| --- | --- |
| **TallyPrime** | Activate with serial number + activation key + email (which becomes the Tally.NET account ID). An unlock key is emailed. Until activated, it runs in **education mode**. Gold should be activated on an always-on "server" PC. Moving to a new PC = **surrender** (Ctrl+F7, admin Tally.NET login, or customer portal), then **reactivate** on the new machine. Reactivation surrenders the old one automatically if needed. **If TSS lapses, TallyPrime keeps working**; only updates and connected features stop. [V] help.tallysolutions.com, TCO guide. A third-party blog claims a **30-day offline limit** before it must reconnect to refresh the licence [S, penieltech.com]. **Not confirmed by Tally.** |
| **BUSY** | Standard can bind data/users to hard disks. SMART can bind data/users to selected computers. **BUSY Magic switches to Demo Mode when the subscription expires.** A release issued after BLS expiry may run in Demo Mode. [V] busy.in/pricing |
| **Winman** | Free 1-month trial, then "paid licence and registration" required. [3P] |
| **Others** (SAG, KDK, CompuTax, Saral, Marg) | No public documentation of activation or online-check behaviour found. |

**Gap:** I found **no** CA product that documents a required online login at every app start.

---

## 5. Implications and recommended starting pricing

### Implications (inference)

1. **Price anchors in the buyer's head.** Tally Silver rental is ₹750/month. TaxOne's "unlimited" automation is about ₹583/month (₹7,000/yr). FinXtract and Docs by Ira cost about ₹1.6–₹2 per page. A small firm will put us next to these.
2. **We can't win on lowest price; we win on what cloud tools don't do.** Our differences are: client documents never leave the office (offline), per-client validation rules, a human review/approval step, and Q&A over documents. That justifies a premium over TaxOne, but not a multiple of Tally.
3. **Don't charge per page.** OCR and AI run on the CA's own PC, so an extra invoice costs us nothing. Per-page credits are how cloud tools pass on *their* compute costs. Unlimited invoices is a selling point against FinXtract and Docs by Ira. It also suits CA workloads, which spike around GST due dates.
4. **Charging per computer is familiar** (Tally Silver = 1 PC, Winman/CompuGST extra nodes). It also matches our licence server, which already tracks computers.
5. **The online check at every start is stricter than the market norm.** Tally keeps working without TSS, and Busy falls back to Demo Mode rather than locking out. Expect pushback from firms with unreliable internet, especially near filing deadlines. A short offline grace period would bring us closer to the norm. This is a product decision for the founder; see `docs/licensing-plan.md`.
6. **Billing norms.** Indian CA software is mostly bought **yearly**, often in March–April (new financial year) or before GST and ITR deadlines. Monthly billing is uncommon outside Tally rental and FinXtract, so it lowers the barrier to trying us. Prices are normally quoted **+ 18% GST**.

### Recommendation: starting price list (to test, not final)

All prices below are **my recommendation**, not market data. Prices are + 18% GST, per firm, with unlimited invoices and clients.

| Plan | Computers | Monthly | Yearly (≈ 2 months free) | Who it's for |
| --- | --- | --- | --- | --- |
| **Solo** | 1 | ₹999 | ₹9,990 | Sole practitioner, 1–2 staff |
| **Team** | up to 3 | ₹2,499 | ₹24,990 | Small firm, 3–5 staff |
| **Firm** | up to 6 | ₹4,499 | ₹44,990 | Mid firm, 5–15 staff |
| **Extra computer** | +1 | ₹699 | ₹6,990 | Any plan |
| **Larger (10+ PCs)** | custom | contact us | contact us | 15–20+ staff |

**Why these numbers:**

- **Solo, ₹999/mo:** a little above Tally Silver rental (₹750/mo) and TaxOne (~₹583/mo), justified by offline privacy plus review workflow plus Q&A. Over a year (₹9,990) it sits in the same range as Gen GST, Spectrum Cloud and Saral (₹5,000–₹9,000/yr), well below Tally Silver's ₹22,500 purchase price.
- **Team/Firm:** each extra computer costs less than the one before (₹833 then ₹750 per PC per month). This copies how Tally Gold and Busy Standard reward multi-user firms, while staying below Tally Gold rental (₹2,250/mo) per seat for Team.
- **Annual = 10× monthly:** "2 months free" is about a 17% discount. That sits inside the 10–20% norm (Tally 2-year TSS 10%, TaxOne 3-year 20%, AI Accountant "2 months free" [S]). Optionally offer a 2-year plan at about 25% off to lock in firms before the April renewal season.
- **No invoice cap:** this is our differentiation (see implication 3). If heavy users ever become a support burden, add a fair-use clause rather than credits.
- **Launch discount:** almost every competitor shows a struck-through "50% off" or "25% off" price. Consider showing these as launch prices with the struck-through "standard" price above them. That is a market convention, not a requirement.

**Trial approach (recommendation):**

- **14-day trial, 1 computer, full features**, granted from the admin panel. The market range is 7–30 days, and 14 days covers at least one GST cycle (GSTR-1 on the 11th, GSTR-3B on the 20th). This fits the licensing plan's rule of "no trial unless you grant one by hand".
- Run it as a guided pilot, like AI Accountant's "bring your real bills and one bank statement" demo. Do a 30-minute onboarding, load one real client's invoices and rules, and have a review call on day 10.
- When the trial ends, the app goes **read-only** (data can still be viewed and exported) instead of hard-locking. This is the same idea as Busy's Demo Mode. CAs will not adopt a tool that can lock them out of client data.
- Give no permanent free plan at launch, because manual payments make free users costly to support. Revisit once Razorpay is live.

**What to validate with 5–10 pilot firms before fixing prices:**

- Do firms want to pay monthly or yearly?
- Do they count "computers" or "staff"?
- Would they pay extra for Tally export and GSTR-2B reconciliation when those ship (for example as a ₹300–₹500/mo add-on, priced near FinXtract's ₹399/mo reconciliation add-on), or do they expect them included?

---

## 6. Sources

All accessed 5 Nov 2026. [V] = vendor, [3P] = third party, [S] = snippet only.

- [V] Vyapar TaxOne (formerly Suvit) pricing: https://taxone.vyapar.com/pricing (redirect from https://www.suvit.io/pricing)
- [S] Vyapar acquires Suvit: https://entrackr.com/snippets/vyapar-acquires-accounting-automation-startup-suvit-10817806
- [S] Capterra Suvit / Vyapar TaxOne: https://www.capterra.com/p/10031523/Suvit/
- [V] AI Accountant for CAs: https://www.aiaccountant.com/linkedin/built-for-ca
- [3P] AI Accountant, Software Advice: https://www.softwareadvice.com/product/528834-AI-Accountant
- [V*] FinXtract pricing: https://finxtract-marketing.pages.dev/pricing and help: https://finxtract-marketing.pages.dev/help
- [V] TallyPrime total cost of ownership (updated 13 Jul 2026): https://tallysolutions.com/business-guides/tallyprime-total-cost-of-ownership-india/
- [V] Tally AI invoice processing / Docs by Ira (31 Aug 2026): https://tallysolutions.com/tally/tallyprime-ai-invoice-processing-indian-smes/
- [S] Tally TSS renewal page: https://tipl.tallysolutions.com/renew-tss
- [V] Tally licence activation help: https://help.tallysolutions.com/?p=110787
- [V] Tally reactivate / surrender licence: https://help.tallysolutions.com/reactivate-license/ and https://help.tallysolutions.com/surrender-license/
- [S] Tally 30-day offline claim (third-party): https://www.penieltech.com/blog/tally-prime-license-error-fix
- [S] Reseller TSS prices: https://markitsolutions-website.pages.dev/blogs/tally-renewal-charges-2026-guide
- [V] BUSY pricing: https://busy.in/pricing/
- [S] Marg ERP prices (aggregator): https://www.erpresearch.com/pricing/marg-erp
- [V] KDK blog, competitor price comparison (28 Feb 2026): https://www.kdksoftware.com/blog/what-is-the-affordable-software-equivalent-to-taxcloud-cleartax/
- [3P] KDK Spectrum Cloud, Techjockey: https://www.techjockey.com/detail/spectrum-cloud
- [S] ExpressGST, Capterra: https://www.capterra.com.sg/software/1036361/expressgst ; SourceForge: https://www.sourceforge.net/software/product/Express-GST
- [V] ClearTax GST for CA Expert Pack (unlimited GSTIN): https://cleartax.in/services/gst_for_ca_and_experts_pack_unlimitedGSTIN/p
- [S] ClearTax 300-GSTIN pack: https://cleartax.in/services/gst_for_ca_and_experts_pack_300GSTIN/p
- [S] ClearTax reviews (renewal increases): https://ca.trustpilot.com/review/cleartax.in
- [V] SAG Infotech price list (updated 10 Sep 2026): https://blog.saginfotech.com/new-price-list-sag-infotech-software-tax-practitioners
- [S] SAG on ICAI member page: https://betacmp.icai.org/?p=1624
- [3P] Winman price list (9 Oct 2026): https://freedom251.com/apps/winman/
- [S] Winman CA-ERP, Techjockey: https://techjockey.com/detail/winman-ca-erp
- [S] CompuTax, Techjockey: https://techjockey.com/detail/computax-income-tax-software ; CompuGST reseller: https://m.indiamart.com/proddetail/latest-compugst-software-multi-user-21602588430.html
- [S] Saral TaxOffice, Techjockey: https://techjockey.com/reviews/relyonsoft-saral-taxoffice
- [S] GSTZen pricing: https://gstzen.in/a/pricing-for-taxpayer.html ; ReconBridge: https://reconbridge.vercel.app/ ; TCS iON: https://us.fitgap.com/products/056914/tcs-ion-gst-compliance-solution ; Taxilla: https://taxilla.com/encomply
- [V] CAMonk (careers platform, no pricing): https://www.camonk.com/blog/

**Not found / not public:** AI Accountant CA pricing, ClearTax CA-pack rupee prices, Clear Max ITC / Clear Capture, CompuTax and Saral official price lists, Marg official list, Tally licence offline-validation period, Gen GST trial length.
