# Email triage & extraction: techniques, taxonomies, libraries (as of 2026-10-08)

Scope note: research budget was limited (~17 tool calls). Several vendor pages (Superhuman help centre, Proofpoint EmailBench blog) returned HTTP 403 and could not be read in full; those items are flagged in Gaps. Target labels referenced throughout: categories `action_required, deadline, notice, opportunity, personal, system, newsletter, other`; priorities `urgent, soon, whenever, ignore`.

## Q1. How do major providers categorise mail, and which signals are cheap to compute locally?

### Takeaway
Every major provider converges on the same split: (a) a human/"important" bucket, (b) transactional/automated notices, (c) bulk/marketing/newsletters, plus (d) social/forums. Their documented signals are sender identity/reputation, content type, and engagement history; the cheapest local signals are RFC headers (List-Unsubscribe, List-Id, Precedence, Auto-Submitted), schema.org markup, and the user's own reply/open history with a sender. Note that providers also let time-sensitive items "escape" a low bucket into the primary view, which is equivalent to separating category from priority, as the user's schema does.

### Cited Findings
**Gmail**
- Gmail tabs: five categories, Primary, Social, Promotions, Updates, Forums. Primary = "person-to-person conversations and messages that don't appear in other tabs"; Social = social networks/media sharing/dating; Promotions = marketing, interests, social/political causes; Updates = "personal, auto-generated updates such as confirmations, receipts, bills, and statements"; Forums = online groups, discussion boards, mailing lists — [Swarthmore KB summarising Google help](https://kb.swarthmore.edu/wiki/Gmail_Categories_and_Inbox_Tabs)
- Gmail's classification "applies machine learning ... based on signals including who the email comes from, what type of content is in the message, and how Gmail users have interacted with similar content" — [Google Workspace blog](https://workspace.google.com/blog/productivity-collaboration/how-gmail-sorts-your-email-based-on-your-preferences)
- Gmail Highlights / schema.org email markup: senders can embed structured data. Supported Highlight types are bus/car rental/train/flight/hotel/restaurant reservations, Order, Parcel delivery, Invoice and Ticketed event reservation. EventReservation carries `reservationNumber`, `underName`, `reservationFor` (Event with `name`, `startDate`, `location`); marked-up event confirmations can be auto-added to Google Calendar — [Google Developers: Gmail markup](https://developers.google.com/gmail/markup/), [Highlights](https://developers.google.com/gmail/markup/highlights)
- Bulk-sender rules (Gmail/Yahoo, in force since 2024): senders of more than 5,000 msgs/day to Gmail must support one-click unsubscribe for marketing/subscribed mail. RFC 8058 one-click = `List-Unsubscribe: <https://...>` plus `List-Unsubscribe-Post: List-Unsubscribe=One-Click` — [Mailgun on RFC 8058](https://www.mailgun.com/blog/deliverability/what-is-rfc-8058/), [Suped](https://www.suped.com/learn/email-deliverability/does-google-require-list-unsubscribe-for-one-click-unsubscribe-in-emails)
- RFC 3834 (auto-responses): autoresponders should not reply to messages with `Precedence: list|junk|bulk`, and should mark their own output (`Auto-Submitted: auto-replied`) — [Mailpro/RFC summary](https://www.mailpro.com/blog/one-click-unsubscribe-rfc-8058); [Buttondown glossary on Precedence: bulk](https://docs.buttondown.com/glossary-precedence-bulk); [IANA message header registry](https://www.iana.org/assignments/message-headers/perm-headers.html)

**Apple Mail (iOS 18.2+/macOS)**
- Four categories: Primary ("personal messages, direct communications, and time-sensitive information"), Transactions ("confirmations, receipts, and shipping notices"), Updates ("news, newsletters, and social updates"), Promotions ("marketing, coupons, and sale messages"). Transactions/Updates/Promotions messages that contain time-sensitive information are *also* shown in Primary. Non-primary categories open as a per-sender digest — [Apple Support: Use categories (iCloud Mail)](https://support.apple.com/guide/icloud-ipad/mmafbebd3108/icloud)

**Outlook Focused Inbox / Copilot**
- Focused vs Other: a per-account classifier learning from opens, replies, moves between Focused/Other and explicit "Always move to Focused/Other" overrides; newsletters, automated notifications and rarely-engaged senders go to Other — [Spark glossary](https://sparkmailapp.com/glossary/focused-inbox), [smtpedia 2026 explainer](https://smtpedia.com/?p=35170) (secondary sources; no Microsoft primary doc read)
- Copilot "Prioritize my inbox" ranks importance using sender, content and context — [Microsoft Support (ro-RO)](https://support.microsoft.com/ro-ro/Outlook/copilot-outlook/prioritize-my-inbox); third-party write-up claims it also uses organisational context and past behaviour — [NuTech Digital](https://nutechdigital.com/outlook-priority-view-explained-microsofts-new-smart-inbox/) (secondary, treat cautiously)

**Superhuman / Shortwave / SaneBox / HEY**
- Superhuman: Split Inbox (sections) plus Auto Labels (per-message tags); April 2025 update added Auto Reminders, Auto Drafts, Auto Labels, Custom Auto Labels (user-written AI prompts and rules) and Auto Archive — [AlternativeTo news, Apr 2025](https://alternativeto.net/news/2025/4/superhuman-s-new-update-brings-auto-reminders-auto-drafts-auto-labels-and-auto-archive/), [Superhuman blog](https://blog.superhuman.com/solving-customer-success-email-overload/)
- Shortwave: "Splits" defined by importance, built-in labels, custom labels, specific senders or search queries; configurable via Gmail filters or auto-apply rules — [Shortwave docs: migrating from Superhuman](https://shortwave.com/docs/migrations/migrating-from-superhuman/)
- SaneBox analyses headers and history: normal mail stays in Inbox; less important → @SaneLater; mailing lists → @SaneNews; unwanted → @SaneBlackHole (train-by-moving) — [The Sweet Setup](https://thesweetsetup.com/sanebox-blackhole-new-gatekeeper)
- HEY: first-time senders go through the Screener (approve/deny); approved mail goes to Imbox (important), The Feed (newsletters, non-urgent) or Paper Trail (receipts, transactional) — [HEY: How it works](https://www.hey.com/how-it-works/)

**Draft mapping onto the user's labels (inference; see below)**

| User category | Gmail | Apple | Outlook | HEY | SaneBox |
|---|---|---|---|---|---|
| personal | Primary | Primary | Focused | Imbox | Inbox |
| action_required / deadline | Primary (or any tab + time-sensitive) | Primary (time-sensitive escalation) | Focused / Copilot "high priority" | Imbox | Inbox |
| notice | Updates | Transactions | Other/Focused | Paper Trail | SaneLater |
| system | Updates | Transactions | Other | Paper Trail | SaneLater |
| newsletter | Promotions / Forums / Social | Updates / Promotions | Other | The Feed | SaneNews |
| opportunity | (no equivalent; Promotions or Primary) | (none) | (none) | (none) | (none) |
| other | – | – | – | – | SaneBlackHole ≈ ignore |

### Inferences
- No provider has an "opportunity" class (scholarships, jobs, calls for papers, events). This label is specific to the user's campus use case and will need its own few-shot examples. It also overlaps with newsletter content, since opportunities often arrive inside digests.
- Apple's "time-sensitive escalates to Primary" behaviour suggests treating **priority as orthogonal to category**. A newsletter can carry a deadline, so let `deadline` or `urgent` override placement and do not force it into a single category.
- Cheap local signals, in rough order of value/cost: (1) `List-Unsubscribe` / `List-Unsubscribe-Post` / `List-Id` → newsletter/bulk; (2) `Precedence: bulk|list|junk` and `Auto-Submitted: auto-generated` → system/notice; (3) no-reply sender local-parts and ESP fingerprints (`X-Mailer`, Return-Path domain); (4) schema.org JSON-LD/microdata in HTML → notice/deadline/event, with structured dates for free; (5) the user's history with the sender (has the user ever replied to or sent mail to this address?), which is the strongest "personal" signal used by Focused Inbox and HEY; (6) whether the user is in To vs CC/BCC, and recipient count.
- A Screener/allow-list (HEY) or a per-sender override (Outlook's "Always move to") is a cheap and very effective user-feedback loop. It is worth copying before building any trained model.

### Gaps
- Could not access Superhuman's help article listing default Auto Labels (HTTP 403). Commonly reported defaults (e.g. Marketing, News, Pitch, Social, Calendar, Respond/Waiting) are **unverified** and not cited.
- No primary Google doc found on "Gemini in Gmail" summaries or on the 2025 Gmail "Manage subscriptions" view; no primary Microsoft doc read on the Focused Inbox algorithm. Apple's on-device "Priority Messages" (Apple Intelligence) signals were not documented in what I found.
- Not verified whether Gmail still has the legacy "Important" marker model publicly described (Aberdeen et al., 2010 "Priority Inbox" paper). Worth checking if needed.

## Q2. Research and tools for action-item / commitment / deadline extraction and event/date extraction

### Takeaway
Microsoft Research has the main academic lineage: action-item detection (2005), commitment detection with domain adaptation on Enron/Avocado (WSDM 2019), deferral prediction (WSDM 2019), and Smart To-Do generation (ACL 2020). It established a request/commitment taxonomy at sentence level and showed cross-corpus domain shift as the main problem. For dates, the reusable Python building blocks are `dateparser` (with `RELATIVE_BASE` = the email's sent date), Duckling (Haskell service; future-biased resolution), and HeidelTime (Java/Perl, via the `py_heideltime` wrapper). Senders' schema.org markup gives exact event dates when present.

### Cited Findings
- **Detecting Action-Items in E-mail** (Bennett & Carbonell, SIGIR 2005): detects emails needing an action/response and highlights the request sentences — [MSR publication](https://www.microsoft.com/en-us/research/publication/detecting-action-items-e-mail/); companion "Feature Representation for Effective Action-Item Detection" — [MSR](https://www.microsoft.com/en-us/research/?p=354020)
- **Domain Adaptation for Commitment Detection in Email** (Azarbonyad, Sim, White; WSDM 2019): commitments such as "I'll send the report by end of day". Trained/evaluated on Enron and Avocado; uses feature-level adaptation, sample-level adaptation (weighting similar emails) and an adversarial autoencoder for domain-independent representations. Commitment detection already existed in Cortana at the time — [MSR blog, Feb 2019](https://www.microsoft.com/en-us/research/blog/email-overload-using-machine-learning-to-manage-messages-commitments/), [paper PDF](https://microsoft.com/en-us/research/uploads/prod/2019/01/AzarbonyadWSDM2019.pdf)
- **Characterizing and Predicting Email Deferral Behaviour** (Sarrafzadeh, Hassan Awadallah, Lin, Lee, Shokouhi, Dumais; WSDM 2019): 15 interviews plus logs of 40,000 users. Features include message length, number of unanswered emails, and human vs machine-generated sender — [MSR blog](https://www.microsoft.com/en-us/research/blog/email-overload-using-machine-learning-to-manage-messages-commitments/)
- **Smart To-Do** (Mukherjee et al., ACL 2020): a new dataset/task to generate To-Do items from emails where the sender has promised an action. Two stages (commitment detection, then seq2seq generation); BLEU 0.23 / ROUGE 0.63 — [ACL Anthology](https://aclanthology.org/2020.acl-main.767), [arXiv 2005.06282](https://arxiv.org/pdf/2005.06282)
- Patent: "Automatic extraction of commitments and requests from communications and content" (US10361981B2, Microsoft) — [Google Patents](https://patents.google.com/patent/US10361981)
- **schema.org in email**: EventReservation/`reservationFor.startDate`, ParcelDelivery, FlightReservation, Invoice etc. are machine-readable in the HTML part when senders include them — [Google Developers](https://developers.google.com/gmail/markup/highlights)
- **dateparser** (Python, Scrapinghub/Zyte): `RELATIVE_BASE` sets the datetime used to resolve relative expressions; `PREFER_DATES_FROM='future'|'past'` resolves incomplete dates (e.g. "March"). Also has timezone settings (`TIMEZONE`, `TO_TIMEZONE`, `RETURN_AS_TIMEZONE_AWARE`) — [dateparser settings docs](https://dateparser.readthedocs.io/en/stable/settings.html)
- **Duckling**: a parser for natural language into structured data (Time, Numeral, Ordinal, Distance…), handling intervals; by default resolves ambiguity to the nearest future time — [Rasa forum discussion](https://forum.rasa.com/t/ducklingentityextractor-how-to-extract-the-nearest-time-in-the-past/50122), [Rasa forum on intervals](https://forum.rasa.com/t/categorizing-dates-into-from-date-and-to-date/13369/2)
- **HeidelTime**: a multilingual, cross-domain temporal tagger (TimeML/TIMEX3). The Python wrapper `py_heideltime` needs Java JDK and Perl — [HeidelTime home](https://heideltime.ifi.uni-heidelberg.de/heideltime/), [py_heideltime GitHub](https://github.com/rncampos/py_heideltime)

### Inferences
- A practical schema derived from this lineage: per email, `requests[]` (asks of the user: `text`, `due`, `owner=me`), `commitments[]` (promises the user made, from Sent mail, which is Smart To-Do's case), `events[]` (`title`, `start`, `end`, `location`, `source=markup|text`) and `deadlines[]` (`what`, `due`, `hard|soft`). This maps directly onto `action_required` / `deadline`.
- Recommended date pipeline: have the LLM extract the **verbatim date span** ("next Friday 5pm", "by EOD 10/12") rather than an ISO date. Resolve it deterministically with `dateparser` using `RELATIVE_BASE = email Date header` (converted to the user's timezone) and `PREFER_DATES_FROM='future'`, and keep the original span for audit. Small LLMs are unreliable at calendar arithmetic, so this split avoids a known failure mode.
- Watch for ambiguous numeric dates (US vs international `DATE_ORDER`), forwarded mails where the relevant base date is the *quoted* message's date, and "Friday" in a Friday email.
- The domain-adaptation result (Enron→Avocado shift) implies that classifiers trained on public corpora will degrade on student/campus mail. A small locally labelled set is necessary.

### Gaps
- Did not retrieve accuracy figures from the WSDM 2019 commitment paper or Bennett & Carbonell. Numbers would need to come from the PDFs.
- SUTime (Stanford CoreNLP, Java) not researched. No 2024–2026 LLM-era benchmark on email *deadline* extraction found.
- Maintenance status of Duckling (Facebook repo), dateparser's latest release, and `py_heideltime` not verified in this pass.

## Q3. Practical patterns for small local LLMs (7–9B): constrained decoding, cascades, evaluation, published numbers

### Takeaway
llama.cpp (llama-server) natively supports JSON-Schema→GBNF constrained decoding via `json_schema` (completion) or OpenAI-style `response_format` (`/chat/completions`). The schema is **not** injected into the prompt, so the prompt must still describe the fields. Use enums for labels and keep schemas flat; several schema features are unsupported or broken. Published small-model numbers for email are sparse. Available evidence suggests Qwen2.5-7B beats Llama-3.1-8B on email-understanding tasks, and fine-tuning gives large gains. A rules → cheap classifier → LLM cascade is the common practitioner pattern.

### Cited Findings
- llama.cpp converts "a subset of JSON Schema" to GBNF. Pass `json_schema` on completion endpoints, `response_format` on `/chat/completions`, `--json/-j` on the CLI — [llama.cpp grammars/README](https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md)
- Limits per the same README: `additionalProperties` defaults to false (faster, fewer hallucinations); string `format` lacks `uri`/`email`; `pattern` must start with `^` and end with `$`; min/max only for integers; no `uniqueItems`, `contains`, if/then/else, or remote refs; nested `$ref` and `prefixItems` are broken. Crucially, "The JSON schema is only used to constrain the model output and is not injected into the prompt" — [llama.cpp grammars/README](https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md)
- Constrained decoding works by masking next-token logits that would make the partial output invalid — [ZeroEntropy explainer](https://www.zeroentropy.dev/concepts/constrained-decoding/); llama.cpp also offers an optional llguidance backend — [llguidance.md mirror](https://huggingface.co/OpenTransformer/llama.cpp-prismml/blob/main/docs/llguidance.md)
- EmailBench (Proofpoint): an open-source email-understanding benchmark built from open sources. Qwen2.5-7B-Instruct outperformed Llama-3.1-8B-Instruct and security-tuned 8B variants (Foundation-Sec-8B, Llama-Primus-Merged); Qwen2.5 was the best open-weight family at both size classes — [Proofpoint blog](https://www.proofpoint.com/us/blog/engineering-insights/introducing-emailbench-open-source-benchmark-email-understanding) (full page 403; finding from search snippet only)
- A Korean study (GNU scholarworks) reports fine-tuned Qwen-7B gaining 8.5–38.6 points accuracy across text-classification datasets (best 83.88% acc / 84.33% F1), and Llama-3-8B spam-SMS detection going from 39% to 98% after fine-tuning — [GNU ScholarWorks](https://scholarworks.gnu.ac.kr/handle/sw.gnu/79411) (snippet only; dataset details unverified)
- A practitioner blog (May 2026) claims flash-tier cloud models (Gemini 2.5 Flash-Lite, DeepSeek V4-Flash) hit 95%+ on common triage labels (sales, support, spam, recruiter, billing, urgent) — [CallSphere blog](https://callsphere.ai/blog/llm-comparison-email-triage-classification-small-models-may-2026.md) (vendor blog, low evidential weight)
- Local-AI email/ticket classification write-up comparing decision rules, LLM and trained classifier approaches — [WZ-IT blog](https://wz-it.com/en/blog/email-classification-local-ai/); Intercom/Fin on when small LLMs suffice — [fin.ai "David vs Goliath"](https://fin.ai/research/david-vs-goliath-are-small-llms-any-good/)

### Inferences
- Schema design for 7–9B models: one flat object; `category` and `priority` as `enum`s; short arrays with `maxItems`; dates as **strings** (verbatim span) resolved post-hoc; put an optional `reason` field (short) *before* the label fields if you want light chain-of-thought inside the constraint; avoid `$ref` nesting given the README's known bugs.
- Cascade: (1) header rules (List-Unsubscribe/Precedence/Auto-Submitted/no-reply) settle newsletter/system for the majority of bulk mail without an LLM; (2) per-sender memory (user overrides, past labels) short-circuits repeat senders; (3) the LLM only sees remaining mail plus bulk mail that rules flag as possibly containing deadlines/opportunities.
- Prompt-length management: strip quoted replies and signatures, convert HTML to text, collapse/replace tracking URLs with placeholders (e.g. `[link3]` with a side table, after unwrapping redirect parameters), and truncate long marketing bodies to the first N tokens plus any sentences containing date or deadline keywords.
- Near-duplicate bulk mail: hash a normalised body (lowercased, digits and URLs masked) or use MinHash/SimHash (e.g. `datasketch`) keyed by sender domain, and reuse the prior classification. This is not sourced here (see gaps) but is standard practice.
- Confidence: grammar-constrained output gives no calibrated probability. Options are reading logprobs of the enum token (llama-server can return `n_probs`/logprobs), self-consistency across 2–3 samples, or a "needs_review" bucket when rules and LLM disagree.
- Evaluation: build a stratified hand-labelled set of ~200–500 of the user's own emails across all 8 categories. Report per-class precision/recall plus confusion between newsletter↔opportunity and notice↔action_required, which are the likely hard pairs. Score date extraction on resolved-date exact match.

### Gaps
- No published accuracy numbers found specifically for 7–9B models on **action/deadline extraction from email**; EmailBench numbers could not be read (403).
- Did not find a primary source quantifying accuracy loss or gain from grammar-constrained decoding for small models on this task.
- Near-duplicate detection and tracking-URL handling: no authoritative source retrieved; recommendations above are inference.

## Q4. Python libraries for email parsing/cleaning (licence and maintenance)

### Takeaway
Use the stdlib `email` package (policy=default) or `mail-parser` (Apache-2.0) for MIME/headers; `inscriptis` (Apache-2.0) for layout-aware HTML→text of email bodies (trafilatura, Apache-2.0, targets web articles and may drop email content); for quote/signature stripping, Mailgun's `talon` (Apache-2.0) is the classic option but appears unmaintained. Lighter forks exist (`claw`, `ktalon`).

### Cited Findings
- `mail-parser` (SpamScope author): wrapper around stdlib `email`, Apache-2.0 — [PyPI mail-parser](https://pypi.org/project/mail-parser/), [SpamScope PyPI](https://pypi.python.org/pypi/SpamScope)
- `inscriptis`: HTML→text converter preserving layout (tables, lists); Apache-2.0; JOSS paper — [PyPI inscriptis](https://pypi.org/project/inscriptis/), [JOSS](https://joss.theoj.org/papers/10.21105/joss.03557.pdf)
- `trafilatura`: web text extraction, Apache-2.0 (v2.x) — [PyPI trafilatura 2.2.0](https://pypi.org/project/trafilatura/2.2.0/)
- `talon` (Mailgun): quotation and signature extraction; rule-based plus scikit-learn SVM signature classifier trained on personal and Enron mail; Apache-2.0; PyPI page fetched shows latest 1.4.4 (Aug 2017), i.e. inactive — [PyPI talon](https://pypi.python.org/pypi/talon), [Mailgun announcement](https://blog.mailgun.com/open-sourcing-our-email-signature-parsing-library/)
- Alternatives: `claw` ("more light-weight version of the original Talon") and `ktalon` (talon with ML removed) — [PyPI claw](https://pypi.org/project/claw/), [libraries.io ktalon](https://libraries.io/pypi/ktalon); AgentMail documents using talon for reply extraction — [AgentMail docs](https://docs.agentmail.to/talon-reply-extraction)

### Inferences
- For a campus assistant, most of the body is HTML newsletters, so inscriptis' table/list preservation is valuable. trafilatura's boilerplate removal may discard the very event listings needed.
- Quote stripping: a small regex set ("On … wrote:", "-----Original Message-----", leading `>` lines, Outlook "From: … Sent:" blocks) covers most cases. talon's pattern-only `quotations.extract_from_plain` can be vendored if pip compatibility is a problem.
- List-Unsubscribe parsing needs no library: split the header on commas and strip `<>` to get `mailto:` and `https:` URIs.

### Gaps
- PyPI talon version history conflicts with my recollection that later releases exist (possibly 1.5/1.6, ~2022). Verify on PyPI or GitHub before relying on the "inactive since 2017" claim.
- `html2text` (GPL-3.0, I believe) licence/maintenance, `mail-parser-reply`, and `email-reply-parser` (Zapier) were not verified in this pass.
- Latest release dates for mail-parser and inscriptis were not checked.

## Q5. Privacy techniques when using cloud LLMs on email

### Takeaway
Microsoft Presidio (MIT, regex + spaCy NER, pluggable recognisers, reversible anonymisation operators) is the default open-source redactor. Its own docs state there is no guarantee it finds all PII: recall depends on the NER model and language, and false positives can destroy meaning. scrubadub is older and only lightly maintained. Redaction should therefore be treated as risk reduction, not anonymisation, and combined with keeping most processing local.

### Cited Findings
- Presidio FAQ: because it uses automated detection, "there is no guarantee that Presidio will find all sensitive information"; additional protections should be employed — [Presidio FAQ](https://microsoft.github.io/presidio/faq/)
- NER-based detection of names/locations is probabilistic and misses unusual names, transliterations, or unconfigured languages. Defaults are English-tuned, and false positives (product codes, surnames that are common words) can harm downstream tasks — [Grepture blog](https://grepture.com/blog/presidio-not-enough-pii-redaction), [ai-tldr explainer](https://ai-tldr.dev/learn/evaluation-safety/alignment-safety/what-is-microsoft-presidio/)
- scrubadub: maintained by LeapBeyond (v2 changelog), but Snyk rates the `cs-scrubadub` fork "Inactive" (no PyPI release in the past 12 months) — [scrubadub changelog](https://github.com/LeapBeyond/scrubadub/blob/v1.2.2/docs/changelog.rst), [Snyk cs-scrubadub](https://snyk.io/advisor/python/cs-scrubadub)

### Inferences
- Pattern for cloud fallback: redact with Presidio, replacing names, emails, phones and student IDs with consistent placeholders (`<PERSON_1>`), and keep a local mapping to de-anonymise the structured output. Add custom recognisers for institution-specific IDs (student numbers, room codes). Send only the trimmed body, never headers or full threads.
- Prefer sending only emails the local cascade could not resolve, which minimises exposure.

### Gaps
- Zero-data-retention (ZDR) terms for specific cloud LLM providers (OpenAI, Anthropic, Google) were not researched in this pass. Check each provider's current data-usage/ZDR documentation; ZDR is typically an enterprise or approved-account arrangement, not a default (unverified).
- No quantitative recall figures for Presidio on email text were found.
