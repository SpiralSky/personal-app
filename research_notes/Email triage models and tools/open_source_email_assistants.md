# Open-source and self-hostable LLM email assistants (as of 2026-10-08)

Method note: GitHub metadata (stars, licence SPDX, last push date) was taken from the GitHub REST API on 2026-10-08 for the repos listed in the table under Q1. The API rate limit ran out partway through, so for some repos stars and dates come from the README page or are missing (shown as "n/a"). Licence and feature details come from READMEs, LICENSE files and docs, as cited.

## Q1. Which open-source projects exist in this space, and what are their key attributes?

### Takeaway
The space has one large, actively maintained, full-stack product: Inbox Zero. It has about 12.4k stars and was pushed on 2026-10-08. Its licence is AGPL-3.0 plus extra commercial restrictions, and it supports Gmail and Outlook only. Beyond that there is one mature Thunderbird add-on (ThunderAI, GPL-3.0, active) and one notmuch tagger with no LLM (afew). Everything else is a long tail of small, recent single-author repos. Of those, ollamail (AGPL, FastAPI + Postgres, IMAP/M365/Gmail, any OpenAI-compatible endpoint) is architecturally the closest to the target stack.

### Cited Findings

**Comparison table (GitHub API, 2026-10-08)**

| Project | Stars | Licence | Last push | Lang | Status |
|---|---|---|---|---|---|
| elie222/inbox-zero | 12,430 | AGPL-3.0 + custom restrictions (GitHub shows NOASSERTION) | 2026-10-08 | TypeScript | Very active |
| Mail-0/Zero (0.email) | 10,840 | MIT | 2026-05-26 | TypeScript | Slowing (no push for about 4.5 months) |
| langchain-ai/agents-from-scratch | 2,370 | MIT | 2026-08-11 | Jupyter/Python | Active (tutorial) |
| langchain-ai/executive-ai-assistant | 2,210 | MIT | 2026-07-27 | Python | **Archived** |
| micz/ThunderAI | 353 | GPL-3.0 | 2026-10-07 | JavaScript | Very active |
| afewmail/afew | 342 | ISC | 2026-07-26 | Python | Maintained (not LLM) |
| andywalters47/clearmail | 92 | none | 2024-02-13 | JavaScript | **Abandoned** |
| aomail-ai/aomail-app | 65 | NOASSERTION | 2025-04-04 | Vue (+Python) | **Stale (about 18 months)** |
| ColeMurray/gmail-llm-labeler | 13 | none stated | 2025-10-10 | Python | Stale (1 year) |
| kl3inIT/zero-mail | 5 | MIT | 2026-10-08 | Java/Spring | New, tiny |
| joryeugene/notmuch-ai | 2 | MIT | 2026-10-06 | Python | New, tiny |
| claudiogiu/Local-Email-Triage-Agent | 0 | MIT | 2026-09-13 | Python | New, tiny |
| mattheuswhale/llm-mail-sorter | 0 | GPL-3.0 | 2026-10-03 | Python | New, tiny |
| dusseligerdussel/ollamail | 0 | AGPL-3.0 | n/a (353 commits) | Python/React | New, active |
| MundaPlus/MundaMail | n/a | n/a | n/a | n/a | **Repo returns 404** (deleted or private) |

Sources: GitHub API for each repo, for example [inbox-zero](https://github.com/elie222/inbox-zero), [ThunderAI](https://github.com/micz/ThunderAI), [Zero](https://github.com/Mail-0/Zero), [executive-ai-assistant](https://github.com/langchain-ai/executive-ai-assistant), [agents-from-scratch](https://github.com/langchain-ai/agents-from-scratch), [afew](https://github.com/afewmail/afew), [clearmail](https://github.com/andywalters47/clearmail), [aomail](https://github.com/aomail-ai/aomail-app), [gmail-llm-labeler](https://github.com/ColeMurray/gmail-llm-labeler), [zero-mail](https://github.com/kl3inIT/zero-mail), [notmuch-ai](https://github.com/joryeugene/notmuch-ai), [Local-Email-Triage-Agent](https://github.com/claudiogiu/Local-Email-Triage-Agent), [llm-mail-sorter](https://github.com/mattheuswhale/llm-mail-sorter), [ollamail](https://github.com/dusseligerdussel/ollamail).

**Inbox Zero (elie222/inbox-zero)**
- Stack: Next.js, Tailwind, shadcn/ui, Prisma, Upstash, Turborepo, Node.js v24+. Self-hosting needs Docker, PostgreSQL and Redis. — [GitHub README](https://github.com/elie222/inbox-zero)
- Mail sources: Gmail and Outlook (Microsoft Graph). The README documents no IMAP support, and `.env.example` has no IMAP variables. — [README](https://github.com/elie222/inbox-zero); [.env.example](https://raw.githubusercontent.com/elie222/inbox-zero/main/apps/web/.env.example)
- Features: AI rules, draft replies, "Reply Zero" reply tracking, Cold Email Blocker, bulk unsubscriber, email analytics, meeting briefings, attachment management, Slack/Telegram integration. — [README](https://github.com/elie222/inbox-zero)
- LLM support: per-tier model slots (`DEFAULT_LLMS`, `ECONOMY_LLMS`, `CHAT_LLMS`, `NANO_LLMS`, `DRAFT_LLMS`). Providers: OpenAI, Anthropic, Azure, Google/Vertex, Bedrock, Groq, Cerebras, OpenRouter, plus local options `OLLAMA_BASE_URL`/`OLLAMA_MODEL` and **`OPENAI_COMPATIBLE_BASE_URL` / `OPENAI_COMPATIBLE_MODEL` / `OPENAI_COMPATIBLE_AUTH_HEADER`**. This means a llama.cpp server can be used directly. — [.env.example](https://raw.githubusercontent.com/elie222/inbox-zero/main/apps/web/.env.example)
- Telemetry hooks: Sentry, PostHog (including `POSTHOG_LLM_EVALS_APPROVED_EMAILS`) and Axiom are configurable through env vars. They appear to be opt-in when self-hosting, because they need keys. — [.env.example](https://raw.githubusercontent.com/elie222/inbox-zero/main/apps/web/.env.example)
- Licence: AGPL-3.0 with added terms. Using it "for commercial purposes that involve monetizing the software itself" needs written permission, and organisations with 5 or more employees need an enterprise licence. Personal, educational and research use are exempt. — [LICENSE](https://github.com/elie222/inbox-zero/blob/main/LICENSE)
- Rule model: rules combine **AI conditions** (plain-language, e.g. "apply this rule if this email is asking me to set up a call") with **static conditions** (from, to or subject contains). The system learns sender/domain patterns, and a History tab has a "Fix" action that explains a wrong match and updates the rule. — [Inbox Zero docs](https://docs.getinboxzero.com/essentials/email-ai-personal-assistant)
- The vendor markets it as open source and self-hostable, with hosted plans starting at $20/month. — [getinboxzero.com](https://www.getinboxzero.com/ai-email-assistant)

**ThunderAI (micz/ThunderAI)** – Thunderbird add-on
- Features: compose/reply, grammar check, summarisation (single or batch), translation, **automatic tagging/classification, spam detection, calendar event and task extraction**, and custom prompts. — [README](https://github.com/micz/ThunderAI)
- Backends: ChatGPT web, OpenAI API, Gemini, Claude, Ollama, LM Studio and "any OpenAI-compatible server". The provider can be set per prompt. Requires Thunderbird 140+. GPL-3.0. — [README](https://github.com/micz/ThunderAI)

**ollamail (dusseligerdussel/ollamail)**
- Stack: Python 3.12+, **FastAPI**, SQLAlchemy, Pydantic. PostgreSQL 16 + pgvector serves as the DB, full-text/vector index and job queue (Procrastinate). React 19/Vite frontend. Piper TTS. AGPL-3.0. — [README](https://github.com/dusseligerdussel/ollamail)
- Mail sources: IMAP (with IDLE and autodiscovery), Microsoft 365 via Graph, Gmail/Workspace. — [README](https://github.com/dusseligerdussel/ollamail)
- Features: categories and priority per mail, each with a stated reason; task extraction exported to CalDAV, Microsoft To Do and Google Tasks; hybrid search with cited answers ("ask your inbox"); daily audio digest. — [README](https://github.com/dusseligerdussel/ollamail); [TrueNAS app request #6006, 2026-10-06](https://github.com/truenas/apps/issues/6006)
- Backends: Ollama or any OpenAI-compatible provider. Runs on CPU only, with GPU optional. — [README](https://github.com/dusseligerdussel/ollamail); [TrueNAS issue](https://github.com/truenas/apps/issues/6006)
- Privacy: "DSGVO (GDPR) by design". Logs contain no mail content, subjects or addresses. Credentials are encrypted, and there is audit logging, retention policies, export and account deletion. — [README](https://github.com/dusseligerdussel/ollamail)

**Zero / 0.email (Mail-0/Zero)**
- MIT. Next.js/React/TypeScript, Drizzle ORM, PostgreSQL, Better Auth with Google OAuth. Self-hosting also needs Autumn and Twilio. The README is mainly Gmail-focused. — [README](https://github.com/Mail-0/Zero)
- Described as an AI-native, self-hostable client. — [emailexpert.com](https://emailexpert.com/examining-zero-an-ai-native-email-client-taking-a-new-approach-to-inbox-management/)

**LangChain email agents**
- `executive-ai-assistant` (MIT, 2.2k stars) is **archived** per the GitHub API. `agents-from-scratch` ("Build an email assistant with human-in-the-loop and memory", MIT, 2.4k stars, pushed 2026-08-11) is its maintained tutorial successor. — [GitHub API / repo](https://github.com/langchain-ai/agents-from-scratch)

**Small local-first projects**
- **Local-Email-Triage-Agent**: LangGraph + Ollama. Classification is done by a distilled small model (`distil-labs/distil-email-classifier` on Hugging Face), priority comes from deterministic signals, and reply drafting is human-supervised. MIT. The README does not mention OpenAI-compatible endpoints. — [README](https://github.com/claudiogiu/Local-Email-Triage-Agent)
- **MundaMail**: according to a search snippet, it mirrored several IMAP accounts into a local Maildir and classified mail through a staged pipeline of deterministic rules, then sender history, then Ollama models. It always archived the raw .eml bytes, never deleted messages, and ran dry-run by default. — [search snippet of github.com/MundaPlus/MundaMail](https://github.com/MundaPlus/MundaMail). **The repo returned 404 on 2026-10-08.**
- **gmail-llm-labeler**: uses the Gmail API with OpenAI or Ollama for categorisation. — [README](https://github.com/ColeMurray/gmail-llm-labeler); [author's guide](https://murraycole.com/posts/gmail-auto-labeler-llm)
- **notmuch-ai**: "classifies every incoming email, tags it, and exits". No server, no UI, no daemon. Uses the Anthropic API (~1 s/email) or a Claude Code subscription (~5–10 s/email). — [README](https://github.com/joryeugene/notmuch-ai)
- **afew**: initial tagging for notmuch, using header/folder rules, spam handling and killed threads. It can learn tagging from content and can move mail between Maildir folders using notmuch queries. It has no LLM, but it is a natural place to hook in a tagger. — [afew GitHub](https://github.com/afewmail/afew)
- **redei-ma/email-triage**: a benchmark comparing keyword rules, a local LLM (Ollama), a cloud LLM (Gemini) and hybrids on a held-out test set. TypeScript. — [repo](https://github.com/redei-ma/email-triage)
- **azmeraa/AI-Email-Agent**: LangChain + Ollama + SQLite, with drafting behind a human-in-the-loop approval gate. — [repo](https://github.com/azmeraa/AI-Email-Agent)
- **ClaudineiAlves/triagem-email-llm**: n8n + Ollama (llama3.1) sorting into 8 categories, with a confidence threshold and a watchdog. — [repo](https://github.com/ClaudineiAlves/triagem-email-llm)
- **Llamail** (DEV article): a private email agent on llama.cpp's OpenAI-compatible server with Llama 3.1 8B Q8_0 and Nomic Embed v2 MoE embeddings, for search and summarisation. — [DEV Community](https://dev.to/sviat_barbutsa/from-inbox-to-character-building-a-private-local-ai-email-agent-c3k)
- **kl3inIT/zero-mail**: Gmail-only auto-triage, natural-language rules and drafting. Java 25 / Spring Boot 4 / Spring AI + Next.js. — [repo](https://github.com/kl3inIT/zero-mail)
- **aomail**: connects to Gmail, Outlook or IMAP and uses LLMs to categorise and summarise. Last push 2025-04-04. — [repo](https://github.com/aomail-ai/aomail-app)
- **clearmail**: "Filter gmail with AI". Last push 2024-02-13. — [repo](https://github.com/andywalters47/clearmail)

**Workflow and server-side approaches**
- n8n + LLM categorisation guide (Gmail trigger, n8n in Docker). — [kirill-markin.com](https://kirill-markin.com/articles/how-to-automate-email-categorization-with-n8n-and-llm/)
- One 2026 article describes three practical setups: an IMAP Python script calling Ollama on a schedule, Thunderbird with an Ollama plugin, and n8n with an Ollama node. It also describes rspamd's GPT plugin pointed at a local model. — [search summary of promptquorum / localaimaster / tech-couch](https://tech-couch.com/post/sorting-email-inboxes-with-local-llms) (aggregator-level claims; lower confidence)
- An XDA writer triages mail every morning with a local LLM but will not let it send replies. — [XDA](https://www.xda-developers.com/i-used-a-local-llm-to-triage-my-email-but-ill-still-never-let-it-send-replies/)

### Inferences
- Projects that accept **any OpenAI-compatible endpoint** and so work directly with llama.cpp `llama-server`: Inbox Zero (`OPENAI_COMPATIBLE_BASE_URL`), ThunderAI, ollamail, and Llamail (built on llama.cpp). Projects that document only Ollama or a single provider: Local-Email-Triage-Agent, gmail-llm-labeler, notmuch-ai (Anthropic only), and the n8n Ollama workflows. These would need a small patch, which is usually trivial because Ollama also exposes `/v1`.
- No mature project takes **.eml files on disk** as its native input. The closest are MundaMail (archived .eml + Maildir, now gone), outlook_skill (.eml + SQLite), and notmuch/afew (Maildir). The user's existing .eml capture already sits at the right layer, so components are more useful than whole apps.

### Gaps
- Star counts and dates were unavailable for ollamail (only "0 stars" from the page), redei-ma, azmeraa, ClaudineiAlves and outlook_skill (8 stars, no date), because the GitHub API rate limit ran out.
- The Llamail repo URL was not confirmed.
- Zero (Mail-0) LLM provider configuration was not documented in the README. Whether it supports local models is unverified.
- No sieve/procmail + LLM hook project was found. Home Assistant email-LLM integrations were not found in this pass.
- Reddit and Hacker News threads were not fetched directly. The community-sentiment items come from blogs only.

## Q2. Which parts are reusable, and which projects are not worth adopting?

### Takeaway
Reuse ideas and designs rather than code: Inbox Zero's hybrid static+AI rule model and its learn-from-correction loop, MundaMail/Local-Email-Triage-Agent's staged pipeline (rules, then sender history, then LLM), ollamail's "category + priority + reason" output plus task export, ThunderAI's task/calendar extraction prompts (GPL), and redei-ma's held-out evaluation of rules vs local vs cloud. Do not fork Inbox Zero, Zero or ollamail wholesale: they carry heavy Node/Postgres/Redis stacks, AGPL copyleft, and Gmail/Graph coupling.

### Cited Findings
- Hybrid rules: static conditions (from/to/subject) and plain-language AI conditions can be combined in one rule. Sender/domain patterns are learned, and a "Fix" action rewrites a rule after a mistake. — [Inbox Zero docs](https://docs.getinboxzero.com/essentials/email-ai-personal-assistant)
- Cold Email Blocker, Reply Zero (to-reply / awaiting-reply tracking) and bulk unsubscriber are distinct features. They are reusable as concept categories (cold outreach, needs reply, newsletter). — [Inbox Zero README](https://github.com/elie222/inbox-zero)
- Model-tier pattern: separate `NANO`/`ECONOMY`/`DEFAULT`/`DRAFT`/`CHAT` model slots. This maps well to "Qwen3 8B local for classification, optional cloud for drafting". — [.env.example](https://raw.githubusercontent.com/elie222/inbox-zero/main/apps/web/.env.example)
- Staged pipeline: deterministic rules, then sender history, then local model. Raw .eml is always archived, nothing is deleted, and dry-run is the default. — [MundaMail snippet](https://github.com/MundaPlus/MundaMail)
- A distilled small classifier (`distil-labs/distil-email-classifier`) plus deterministic priority signals, as an alternative to prompting an 8B model for every mail. — [Local-Email-Triage-Agent](https://github.com/claudiogiu/Local-Email-Triage-Agent)
- Per-mail categories and priority **with reasoning**. Tasks are extracted and exported to CalDAV, Microsoft To Do or Google Tasks. Logs never contain content. — [ollamail](https://github.com/dusseligerdussel/ollamail)
- Calendar event/task extraction and spam detection, with the provider chosen per prompt. — [ThunderAI](https://github.com/micz/ThunderAI)
- An evaluation design that compares keyword rules, a local LLM, a cloud LLM and hybrids on a held-out test set. — [redei-ma/email-triage](https://github.com/redei-ma/email-triage)
- Confidence threshold with fallback (8 categories, llama3.1). — [triagem-email-llm](https://github.com/ClaudineiAlves/triagem-email-llm)
- Human-in-the-loop approval gate before any drafted reply is sent. — [azmeraa/AI-Email-Agent](https://github.com/azmeraa/AI-Email-Agent); [agents-from-scratch](https://github.com/langchain-ai/agents-from-scratch)

### Inferences
- **Not worth adopting wholesale:**
  - Inbox Zero: AGPL plus custom commercial terms, Next.js/Postgres/Redis, and Gmail/Graph only with no IMAP or .eml. Personal and educational use is permitted, so studying it or running it is fine. Copying its code into the project would bring AGPL obligations.
  - Zero/Mail-0: Gmail/OAuth, Twilio and Autumn dependencies, and activity slowing since May 2026.
  - executive-ai-assistant: archived.
  - clearmail and aomail: abandoned.
  - gmail-llm-labeler and zero-mail: Gmail-only.
  - notmuch-ai: Anthropic-only.
  - ollamail: the best functional match, but AGPL and Postgres/pgvector-bound. Use it as a design reference unless the project is willing to adopt AGPL.
- **Best fit as components:** the MIT-licensed small Python repos (Local-Email-Triage-Agent, agents-from-scratch) are safe to copy patterns from. afew (ISC) is useful if the project adopts Maildir/notmuch. ThunderAI is a usable companion UI only if the student uses Thunderbird (GPL, so keep it as a separate add-on).
- Suggested starting design for Qwen3 8B: a sender/header rule layer and a newsletter/List-Unsubscribe heuristic first, then LLM JSON classification into a small fixed label set (needs-reply, deadline/action, course/academic, admin/institution, newsletter, notification, cold/marketing, FYI) with priority + reason + extracted tasks, then confidence-threshold fallback to cloud or to review. This synthesises the patterns above and is not taken from any single source.

### Gaps
- No project's actual prompt text or full label taxonomy was retrieved. Inbox Zero's prompts live in its source (not fetched), and ollamail's taxonomy was not shown in the README.
- No published accuracy numbers from any project (including redei-ma) were retrieved.
- Newsletter deduplication specifics were not found in any project.

## Q3. Are there projects specifically handling Microsoft 365/Outlook for students or institutions?

### Takeaway
One institution-built project exists: EPFL's outlookLLM-EPFL Outlook add-in, which uses Azure AD + Graph with an LLM inference API. Several small Graph-based tools also exist. outlook_skill (.eml + SQLite storage) is the closest architectural match, but its shared client ID works only for personal accounts. School tenants need their own Entra app registration, which may require admin consent.

### Cited Findings
- **outlookLLM-EPFL**: an Outlook add-in using Azure AD auth and Microsoft Graph to search emails/folders, integrated with an LLM inference API and deployed via manifest to M365 tenants. — [GitHub](https://github.com/YannickPezeu/outlookLLM-EPFL)
- **outlook_skill (grapeot)**: a library-first Python CLI for Outlook.com. OAuth2 via Graph with a bundled shared Entra client ID for personal Microsoft accounts. Work/school accounts must "bring your own client ID". Stores raw `.eml`, Markdown with YAML frontmatter, and SQLite (messages, spam_rules, triage_labels). "All data stays local." It is LLM-agnostic and aimed at agent harnesses. 8 stars, 37 commits, licence not stated. — [GitHub](https://github.com/grapeot/outlook_skill)
- **outlook-bob**: an LLM assistant for answering Outlook emails using local Ollama models. — [GitHub](https://github.com/haesleinhuepf/outlook-bob)
- **AI-Email-Manager**: LLMs + Graph to classify, prioritise and draft replies. — [GitHub](https://github.com/aliyanz85/AI-Email-Manager)
- **AI-Outlook-Manager** (kroll-software). — [GitHub](https://github.com/kroll-software/AI-Outlook-Manager)
- **MNabikhel/outlook-email**: a PR adds local-LLM enrichment, triage bins and digest history. — [PR #4](https://github.com/MNabikhel/outlook-email/pull/4)
- **outlook-assistant** (littlebearapps): an MCP server for Outlook mail, calendar and contacts. — [GitHub](https://github.com/littlebearapps/outlook-assistant)
- Inbox Zero and ollamail both support Microsoft Graph / Microsoft 365. — [Inbox Zero](https://github.com/elie222/inbox-zero); [ollamail](https://github.com/dusseligerdussel/ollamail)
- A third-party "Outlook Categorizer" agent (Claude via Graph) is listed on a commercial community site, so it is not a self-hosted candidate. — [techsy.io](https://techsy.io/en/community/ai-automations/outlook-categorizer)

### Inferences
- The main barrier for students is **tenant consent for Graph**, not the LLM. University tenants often block user consent for third-party apps. The user already captures .eml files, presumably via the outlook-desktop Electron wrapper, which sidesteps this. Graph-based projects are therefore mainly useful for their categorisation logic, not their ingestion.
- **Commercial products, for design ideas only (not researched in depth this pass):** Superhuman (split inbox, auto-labels), Shortwave (AI bundles, ask-your-inbox), SaneBox (sender-based learned folders, "SaneLater"), and Gmail/Outlook built-in categories, Focused Inbox and Copilot summaries. These descriptions are general knowledge and were not verified with sources in this pass.

### Gaps
- Licence, stars and last commit for outlookLLM-EPFL, outlook-bob, AI-Email-Manager and AI-Outlook-Manager were not retrieved (rate limit).
- No evidence was found of any project designed specifically for students (course and deadline taxonomies, LMS notifications such as Canvas/Moodle).
