# Student LMS + Email + LLM Assistants: Existing Projects to Fork, Borrow From, or Use (as of 2026-10-08)

Method note: GitHub repo metadata (licence, `pushed_at`, stars) was pulled from the GitHub REST API on 2026-10-08. "Pushed" means the last push to any branch, not necessarily a meaningful commit. Many repos in this space are a few weeks old, have no stars, and were probably written mostly with AI coding agents (a 2026 trend), so a recent push date does not mean the project is mature. Two Valence documentation pages (calendar, news) could not be fetched because of a tool session limit; see Gaps.

---

## 1. Open-source Brightspace/D2L tools (Valence clients, MCP servers, scrapers, calendar exporters, notifiers, downloaders)

### Takeaway
The Brightspace ecosystem grew quickly in 2025–2026: there are now more than 25 community MCP servers. The strongest by far is **RohanMuppa/brightspace-mcp-server** (MIT, active, about 56 stars). It already has a **Ngee Ann Polytechnic (POLITEMall) preset**, automates Microsoft Entra SSO and MFA, and turns session cookies into a Valence Bearer token. That matches the user's setup (SSO + MFA + session cookies) exactly, and makes it the best component to fork or borrow from. The older Valence SDKs (Java, Ruby, PHP, JS demos, 2013–2020) are abandoned and assume registered OAuth/ID-key apps, so they are not worth adopting.

### Cited Findings

**Tier 1: the most relevant and most mature**

- **RohanMuppa/brightspace-mcp-server**: https://github.com/RohanMuppa/brightspace-mcp-server, MIT, last pushed 2026-10-08, ~56 stars, TypeScript/Node ≥20, npm `brightspace-mcp-server`. Read-only ("never submits, edits, or deletes"). Covers courses, grades, assignments/dropbox, rubrics, feedback, quizzes, announcements and their attachments, content and file downloads, syllabus, classlist, discussions, calendar, and Kaltura/YouTube lecture videos. — [GitHub API + README](https://github.com/RohanMuppa/brightspace-mcp-server)
  - Built-in sign-in presets cover Purdue, SUNY, Western, TU Delft, CUNY, Leiden, McGill, Javeriana and **Ngee Ann Polytechnic (`--ngeeann`, "Plain Microsoft Entra, no extra steps")**. — [docs/sign-in.md](https://github.com/RohanMuppa/brightspace-mcp-server/blob/main/docs/sign-in.md)
  - Auth: a hidden Playwright browser drives SSO. It handles MFA number matching and TOTP, and replays the saved Microsoft session silently (silent SSO) when the session lapses. The password is kept in the OS keychain (or Linux Secret Service) and session state is encrypted with AES-256-GCM. It also has a "passwordless" mode, and two env vars for skipping the browser: `D2L_SESSION_COOKIE` (`d2lSessionVal` + `d2lSecureSessionVal`) and `D2L_ACCESS_TOKEN`. Pasted cookies do not renew themselves. — [docs/sign-in.md](https://github.com/RohanMuppa/brightspace-mcp-server/blob/main/docs/sign-in.md)
  - Cookie→token mint: `src/auth/token-mint.ts` POSTs to `{base}/d2l/lp/auth/oauth2/token` with the session cookie, an `x-csrf-token` header, and `scope=*:*:*`, and gets back a Bearer token. Without the CSRF header the request returns 403. — [token-mint.ts](https://github.com/RohanMuppa/brightspace-mcp-server/blob/main/src/auth/token-mint.ts)
  - Code layout worth borrowing: `src/api/` (client, cache, paginate, rate-limiter, retry, **version-discovery** via `/d2l/api/versions/`), `src/auth/` (one SSO module per school, session-store, token-manager), `src/tools/` (one file per tool), and `src/prompts/` (`study-planner.ts`, `weekly-briefing.ts`, `course-summary.ts`, `grade-audit.ts`). — [repo tree](https://github.com/RohanMuppa/brightspace-mcp-server/tree/main/src)
  - `weekly_briefing` prompt: calls get_upcoming_due_dates (7 days), get_calendar_events, get_announcements (modifiedSince 7 days ago) and get_my_grades; organizes the result by course; leads with anything due in the next 48 h; and flags announcements or grade changes that need a reply or decision. — [weekly-briefing.ts](https://github.com/RohanMuppa/brightspace-mcp-server/blob/main/src/prompts/weekly-briefing.ts)
  - The author also has **RohanMuppa/Brightspace-API** (MIT, pushed 2026-10-07): "log in once, then pull your courses, grades, due dates", apparently a non-MCP library/CLI. — [GitHub search](https://github.com/RohanMuppa/Brightspace-API)

- **JhostinAleck/brightspace-mcp**: https://github.com/JhostinAleck/brightspace-mcp, MIT, pushed 2026-10-05, ~13 stars, npm `brightspace-mcp`. 26+ tools plus MCP resources, prompts and a TUI dashboard. Uses a DDD architecture with retry, circuit breaker, cache tiers and optional Redis. Write operations (submit, post) are opt-in. — [README](https://github.com/JhostinAleck/brightspace-mcp), [docs site](https://jhostinaleck.github.io/brightspace-mcp/)
  - Auth strategies: `api_token` (an admin-issued Valence token, which students cannot get), `headless` HTTP login with Duo push/TOTP/manual MFA, and `browser` (Playwright, for Azure AD/SAML, with Microsoft selectors `#i0116`/`#i0118`). Has "known-good presets (Microsoft AAD)". — [README](https://github.com/JhostinAleck/brightspace-mcp)
  - Documents useful D2L quirks. D2L reports `IsActive: true` for past enrollments, and students cannot read semester dates, so the server decides which courses are current with heuristics (access end date, start date within ~6 months, last opened within 45 days, or a shared term token such as `202620`). The upcoming-due-dates tool merges dropbox and quiz due/close dates. Feedback comes from `/grades/{id}/values/myGradeValue` plus `/le/unstable/{ou}/assessment?assessmentType=Rubric`. Course content loads with a single `GET /content/toc`. The syllabus is found by `/overview`, falling back to keyword search in content. — [docs/tools.md](https://github.com/JhostinAleck/brightspace-mcp/blob/main/docs/tools.md)

- **haziq21/politeshop** (POLITEShop): https://github.com/haziq21/politeshop, **no licence file**, TypeScript, created 2024-09, pushed 2026-09-06. A "third-party client for POLITEMall, the LMS used by Polytechnics and ITEs in Singapore". A browser extension reads `d2lSessionVal`/`d2lSecureSessionVal` and `D2L.Fetch.Token` from localStorage, then proxies them to a webapp that calls the Brightspace APIs. Includes a reverse-engineered client library (`lib/clients/brightspace.ts`, `polite.ts`) and **`lib/docs/brightspace-reveng.md`**, which documents Brightspace's internal Siren hypermedia APIs (`*.api.brightspace.com`: enrollments, organizations, sequences, content-service, announcements, folio) and maps them to polytechnic terms: course-offering = Module, programme = Diploma, semester = "24S1", organization = "Ngee Ann Polytechnic (org id 6665)". — [README](https://github.com/haziq21/politeshop), [brightspace-reveng.md](https://github.com/haziq21/politeshop/blob/HEAD/lib/docs/brightspace-reveng.md)
  - Valence routes used for POLITEMall (in `lib/clients/polite.ts`): `/d2l/api/lp/1.0/users/whoami`, `/d2l/api/lp/1.46/enrollments/myenrollments/`, `/d2l/api/lp/1.46/organization/info`, `/d2l/api/lp/1.46/courses/parentorgunits`, `/d2l/api/le/1.75/{ou}/content/toc`, `/d2l/api/le/1.75/{ou}/dropbox/folders/`, `…/dropbox/folders/{id}/submissions/`, `/d2l/api/le/1.75/{ou}/quizzes/`, and the token mint `/d2l/lp/auth/oauth2/token`. POLITEMall host: `politemall.polite.edu.sg` (`*.polite.edu.sg`). — [polite.ts](https://github.com/haziq21/politeshop/blob/HEAD/lib/clients/polite.ts)

**Tier 2: other Brightspace MCP servers and CLIs (mostly 2026, few stars, institution-specific)**

| Repo | Licence | Last push | Notes |
|---|---|---|---|
| [cyanprot/brightspace-mcp](https://github.com/cyanprot/brightspace-mcp) | MIT | 2026-09-25 | Courses, assignments, grades, content for Claude Code |
| [micho911/brightspace-mcp](https://github.com/micho911/brightspace-mcp) | MIT | 2026-10-07 | Go |
| [Exhabition/brightspace-mcp-rs](https://github.com/Exhabition/brightspace-mcp-rs) | none | 2026-10-01 | Rust, read-only |
| [AnonymousOnyx22/brightspace-d2l-mcp](https://github.com/AnonymousOnyx22/brightspace-d2l-mcp) | NOASSERTION | 2026-10-04 | "One-command setup" |
| [CarlSvejstrup/dtu-learn-mcp](https://github.com/CarlSvejstrup/dtu-learn-mcp) | MIT | 2026-10-07 | DTU; deadlines, slides, Panopto |
| [danieltyukov/tudelft-mcp](https://github.com/danieltyukov/tudelft-mcp), [viftode4/my-tudelft-mcp](https://github.com/viftode4/my-tudelft-mcp) | MIT | 2026-10-07 / 09-19 | TU Delft Brightspace + timetable |
| [LiamVDB1/ufora-ai](https://github.com/LiamVDB1/ufora-ai) | MIT | 2026-10-04 | UGent Ufora CLI + MCP |
| [sahildayal/mycourses-mcp](https://github.com/sahildayal/mycourses-mcp) | MIT | 2026-08-22 | RIT; includes submitting assignments |
| [chrldb/mcgill-mycourses-mcp](https://github.com/chrldb/mcgill-mycourses-mcp) | Apache-2.0 | 2026-09-15 | McGill |
| [WayneWei228/brightspace-hub-mcp](https://github.com/WayneWei228/brightspace-hub-mcp) | MIT | 2026-07-03 | Waterloo; deadlines + announcements + Piazza + Crowdmark; local cookies, ~60 min cache, `get_weekly_summary` |
| [hamzakammar/mcp-workspace](https://github.com/hamzakammar/mcp-workspace) ("Horizon") | MIT | 2026-09-17 | **Hosted** multi-user service (sends credentials to a third party; not suitable) |
| [u-hashmi/desire2learn-mcp](https://github.com/u-hashmi/desire2learn-mcp) | none | 2026-09-03 | Valence API |
| [bencered/d2l-mcp-server](https://github.com/bencered/d2l-mcp-server) | none | 2025-11-28 | Playwright SSO, 12 tools; **one-day project, effectively abandoned** |
| [joshuasoup/d2l-mcp](https://github.com/joshuasoup/d2l-mcp) | none | 2025-12-07 | Built for Poke; **stale** |
| [XiyaoWang0519/Brightspace_MCP](https://github.com/XiyaoWang0519/Brightspace_MCP), [ParsaKargari/d2l-mcp](https://github.com/ParsaKargari/d2l-mcp) | none/MIT | 2026-02 / 2026-03 | **Stale** |
| [cu-cs-courses/brightspace-cli](https://github.com/cu-cs-courses/brightspace-cli) | MIT | 2026-10-07 | Single-file stdlib Python CLI; **reads the session straight out of Firefox's cookie store (lz4)**; keepalive to stop idle timeout; instructor-oriented |
| [clintonwrong53/d2l-cli](https://github.com/clintonwrong53/d2l-cli) | MIT | 2026-10-07 | Read-only CLI: grades, assignments, content, syllabi |
| [JobDoesburg/bsapi](https://github.com/JobDoesburg/bsapi) (PyPI `brightspace-api` 2.1.2, 2026-05-07) | MIT | 2026-05-07 | Python Valence wrapper using **OAuth 2.0** (needs a registered app) |

Sources: GitHub API search results for "brightspace mcp" / "d2l mcp" (2026-10-08), [PyPI brightspace-api](https://pypi.org/project/brightspace-api/), and the READMEs linked above.

**Brightspace + LLM / calendar / local-assistant projects (closest to the user's app)**

- **Miguel121699/academic-assistant**: https://github.com/Miguel121699/academic-assistant, no licence, pushed 2026-08-05. **This is the closest analogue: Brightspace + Outlook (Office 365) + local files + GitHub, running on Ollama (llama3.1:8b) or OpenAI, as a chat agent plus a standalone MCP server.** Brightspace auth is either manual copying of `d2lSessionVal`/`d2lSecureSessionVal` ("expire every ~24 hours") or Shibboleth auto-login with a plaintext password in `.env`. Outlook uses the **Microsoft device code flow with no Azure app registration** (`academic-oauth-utrgv`). Built for UTRGV, macOS-tested. — [README](https://github.com/Miguel121699/academic-assistant)
- **aaravhmodi/study-agent** (StudyAgent): https://github.com/aaravhmodi/study-agent, no licence, pushed 2026-10-08. A "local-first academic workload assistant" for Waterloo LEARN (D2L). It attaches to the user's **already-signed-in Chrome over CDP via Browser Use**, never storing passwords, MFA codes or cookies. It syncs courses, announcements, calendar due items, content and submissions into SQLAlchemy/SQLite, runs a FastAPI dashboard, an hourly daemon and an OpenAI vector-store RAG chat. Completion is explicit: viewing a page does not mark it done. — [README](https://github.com/aaravhmodi/study-agent)
- **Adamolids/Brightspace_Assignment_Tracker**: https://github.com/Adamolids/Brightspace_Assignment_Tracker, no licence, Java, pushed 2026-09-08. Brightspace REST → SQLite → Claude enrichment (summary + priority) → Google Calendar. Its README spells out good design rules. Sync is idempotent, keyed by `orgUnitId`/`folderId`. Writes are atomic. `daysUntilDue` is computed in code, not by the LLM, as a hallucination safeguard. Each calendar event carries the `folderId` in an extended property so sync can recover itself. Removed assignments are tombstoned as "[OLD]" rather than deleted. LLM output is constrained to a JSON-schema `Enrichment` record. Brightspace, LLM and calendar sit behind interfaces so a demo mode can swap them. — [README](https://github.com/Adamolids/Brightspace_Assignment_Tracker)
- **DavidChen-006/Brightspace-Bar**: https://github.com/DavidChen-006/Brightspace-Bar, MIT, pushed 2026-10-01, ~51 stars. macOS menu-bar heatmap of due dates. Split into a Swift UI with **no network code or credentials** and a Node `session-capture` daemon that owns a persistent Chromium profile and renews cookie/JWT on an escalation "ladder". Ships an agent CLI (`bsb`) and skill. — [README](https://github.com/DavidChen-006/Brightspace-Bar)
- **vinilpolepalli/vidya**: https://github.com/vinilpolepalli/vidya, MIT, pushed 2026-09-10. "LLM at the edges, code in the middle" deadline-diff engine with tested invariants. No calendar write happens without a review gate. A failed or empty read never causes a deletion, and a deletion needs the item to be absent on two successful reads on different days. Ambiguous items go to a needs-review bucket. Re-runs are idempotent. 11:59 PM is pinned to the course timezone. Every event carries provenance (source URL, read time, verbatim text, assumptions, confidence). — [README](https://github.com/vinilpolepalli/vidya)
- **SchoolsInBeirut/fellers-agenda**: https://github.com/SchoolsInBeirut/fellers-agenda, MIT, pushed 2026-09-15. A template that runs Claude Code on a schedule. It uses a Brightspace MCP (`get_my_courses`), "works out how much time each course actually deserves, packs study blocks around your class timetable", and renders a single phone page with tickable items. — [README](https://github.com/SchoolsInBeirut/fellers-agenda)
- **iabounaaj/deadlines**: https://github.com/iabounaaj/deadlines, no licence, pushed 2026-05-06 (**one-day project, likely abandoned**). Parses the Brightspace iCal feed plus a syllabus PDF/DOCX, and uses Gemini JSON mode to classify urgency, course, type and weight. — [README](https://github.com/iabounaaj/deadlines)
- Other calendar exporters: [dnikitski/hw-tracker](https://github.com/dnikitski/hw-tracker) (MIT, 2026-10-05, Brightspace + WebAssign + WileyPLUS → Google Calendar), [khui0/brightspace-calendar-middleware](https://github.com/khui0/brightspace-calendar-middleware) (MIT, 2026-04-15, fixes "11:59-11:59" events in the iCal subscription feed), [SeanLee12345/brightspace_sync](https://github.com/SeanLee12345/brightspace_sync) (2026-04, CSV/ICS), [krishik23/D2L-Calendar-Sync](https://github.com/krishik23/D2L-Calendar-Sync), [notsaad/deadline-sync](https://github.com/notsaad/deadline-sync), [AbhisarAnand/Sync-Assignments](https://github.com/AbhisarAnand/Sync-Assignments) (2025-08), [lonkaars/brightspace-decsync](https://github.com/lonkaars/brightspace-decsync) (2022, **abandoned**). — GitHub API search "brightspace calendar"
- Scrapers are mostly old Selenium one-offs (2021–2025, many abandoned), for example [ThomasvanBommel/brightspace-assignment-scraper](https://github.com/ThomasvanBommel/brightspace-assignment-scraper) (2021) and [arnavarora1710/brightspace-is-dumb](https://github.com/arnavarora1710/brightspace-is-dumb) (2024, content download). — GitHub API search "brightspace scraper"
- Legacy official/semi-official Valence SDKs are **abandoned**: [Brightspace/valence-sdk-java](https://github.com/Brightspace/valence-sdk-java) (last push 2020-10-12), Ruby clients [michael-harrison/d2l-valence](https://github.com/michael-harrison/d2l-valence) (2018) and [WIU/d2l_sdk](https://github.com/WIU/d2l_sdk) (2017), and [davemcp/brightspace-valence-js-demo](https://github.com/davemcp/brightspace-valence-js-demo) (2015). — GitHub API search "d2l valence"
- The Valence API lives under `https://{host}/d2l/api/` and is split into "lp" (Learning Platform) and "le" (Learning Environment) components, versioned per component and authenticated with OAuth 2 bearer tokens. — [Jentic API summary](https://jentic.com/apis/desire2learn.com/d2l-brightspace-valence-api)

### Inferences
- **Auth fit.** Projects that need a registered OAuth app or an admin-issued token (bsapi/`brightspace-api`, JhostinAleck's `api_token` mode, the legacy SDKs) will not work for a polytechnic student. The approaches that do work all build on the session cookie, which the user has already shown to work:
  - Playwright SSO automation with a persisted profile (RohanMuppa, JhostinAleck `browser`, bencered, Brightspace-Bar)
  - Attaching to an existing signed-in browser over CDP (StudyAgent)
  - Reading the browser's cookie store (cu-cs-courses/brightspace-cli reads Firefox)
  - Pasting the two cookies (`d2lSessionVal`, `d2lSecureSessionVal`) by hand
- **Best fork or dependency candidate: RohanMuppa/brightspace-mcp-server.** It is MIT, has the most recent activity, already has an NP (POLITEMall) Entra preset, and has a cookie→Bearer token mint, version discovery and a file reader. Two ways to use it:
  - Run it as a subprocess MCP server.
  - Lift `src/auth/microsoft-session.ts`, `token-mint.ts` and `src/api/*`.

  Because the user's app is local and Electron/Node-based (the `outlook-desktop` repo), TypeScript reuse is natural.
- **Best POLITEMall domain knowledge: POLITEShop.** It has the endpoint and versions list (le 1.75 / lp 1.46) and the Siren internal-API notes. However, **it has no licence file**, so copying its code is legally unclear. Use it only as reference documentation, or ask the author for a licence.
- **Patterns from Adamolids and vidya** are worth adopting regardless of language:
  - deterministic date math outside the LLM
  - schema-constrained enrichment
  - idempotent keys
  - tombstoning instead of deletion
  - deletion only after two consecutive absences
  - a review gate before any calendar write
  - provenance attached to every derived task

### Gaps
- I could not fetch the Valence reference pages for calendar (`/le/{v}/calendar/events/myEvents/`) and news (`/le/{v}/{ou}/news/`) to confirm exact routes, parameters and field names, because of a tool session limit. The user should check them against docs.valence.desire2learn.com.
- I did not verify whether POLITEMall's tenant allows the `/d2l/lp/auth/oauth2/token` cookie→token mint. POLITEShop calls that endpoint, which suggests it does, but I did not confirm this independently. Ngee Ann support in RohanMuppa is claimed in its docs, but I did not find independent user reports.
- I did not check the READMEs of several small MCP repos (micho911, Exhabition, AnonymousOnyx22, cyanprot) because the GitHub API rate limit was reached.

---

## 2. Similar tools for Canvas / Moodle / Blackboard that integrate LLMs

### Takeaway
Canvas has the most mature student-agent tooling: **vishalsachdev/canvas-mcp** (MIT, ~284 stars, active) has student tools and packaged "agent skills" such as a weekly plan and a morning check. Moodle has several smaller MCP servers. Their designs translate well to Brightspace, but the code does not, because the APIs differ. Canvas's native Planner/TODO API has no direct Brightspace equivalent, so a Brightspace app has to build its own aggregation.

### Cited Findings
- **vishalsachdev/canvas-mcp**: https://github.com/vishalsachdev/canvas-mcp, MIT, pushed 2026-10-08, ~284 stars, Python. Up to 125 tools and 8 agent skills ("weekly plan, morning check, bulk grading, peer review, course QC"), installable via `npx skills add vishalsachdev/canvas-mcp`. Student tools include `get_my_upcoming_assignments`, `get_my_todo_items`, `list_my_announcements`, `list_calendar_events`, `list_planner_notes`, `get_my_peer_reviews_todo`, and `calculate_grade_scenarios`. — [README](https://github.com/vishalsachdev/canvas-mcp)
  - Its security work is a useful model. v1.9.0 added prompt-injection hardening, where "Canvas-authored text arrives provenance-fenced as data-not-instructions". Student write tools sit behind an explicit allowlist (v1.6.0). Delete tools require a `confirmation_token` (v1.12.0). Auth is a Canvas personal access token, which students can usually generate themselves, unlike in Brightspace. — [README changelog](https://github.com/vishalsachdev/canvas-mcp)
- **DMontgomery40/mcp-canvas-lms**: https://github.com/DMontgomery40/mcp-canvas-lms, no licence detected, pushed 2026-05-31, ~103 stars, 54 tools, aimed at students, instructors and admins. — [GitHub API](https://github.com/DMontgomery40/mcp-canvas-lms), [mcpservers.org](https://mcpservers.org/servers/DMontgomery40/mcp-canvas-lms)
- **sa1emie/sentinel**: https://github.com/sa1emie/sentinel, no licence, pushed 2026-06-16 (single push). Features:
  - Canvas sync plus syllabus PDF ingestion by Claude ("Canvas wins on date conflicts; conflicts logged for review")
  - RRULE-based fixed commitments
  - a study planner that fills gaps with 45–120 min blocks and 15 min buffers, weighted toward exams and scaled by urgency
  - escalating reminders at 7d/3d/1d/day-of/2h, with tone moving from gentle to urgent to blunt
  - quiet hours, and an alert if sync has stalled for more than 24 h — [README](https://github.com/sa1emie/sentinel)
- **alrawi10/studie-os**: https://github.com/alrawi10/studie-os, MIT, pushed 2026-10-01, Danish. A multi-LMS study system for Claude (Canvas/Moodle/Brightspace/itslearning → NotebookLM per course, Anki cards with source citations, and a planner that writes study blocks to Apple Calendar around the timetable, with commands like `nåede ikke X` / "didn't finish X" that re-plan). — [README](https://github.com/alrawi10/studie-os)
- Moodle MCP servers: [peancor/moodle-mcp-server](https://github.com/peancor/moodle-mcp-server) (MIT, 2026-02-22, 43★), [loyaniu/moodle-mcp](https://github.com/loyaniu/moodle-mcp) (2026-06-29, 38★), [IsaacAnwar/moodle-mcp](https://github.com/IsaacAnwar/moodle-mcp) (MIT, 2026-10-04, read-only courses/materials/deadlines/grades, Claude Code plugin), [EdmundD28/moodle-codex](https://github.com/EdmundD28/moodle-codex) (MIT, 2026-09-27, "local-first, read-only … course change tracking"), and [onbirdev/moodle-webservice_mcp](https://github.com/onbirdev/moodle-webservice_mcp) (a server-side Moodle plugin, 2026-07-23). — GitHub API search "moodle mcp"
- Canvas student chatbots such as [Armaan204/uoft-agent](https://github.com/Armaan204/uoft-agent) (MIT, 2026-07, grade calculator and syllabus parsing) are small and early-stage. — GitHub API search
- I found no notable open-source Blackboard + LLM student assistant. — GitHub searches returned none

### Inferences
- Worth adapting from canvas-mcp:
  - its *skill* layer (a weekly plan and a morning check as reusable multi-step recipes)
  - provenance-fencing of LMS-authored text, which matters because announcement and email text can contain prompt injections
  - allowlisted writes

  Its tool naming (`get_my_upcoming_assignments`, `list_my_announcements`) is a sensible API shape for the user's own internal service.
- Sentinel's planner rules (block sizes, buffers, exam weighting, escalation ladder) and studie-os's re-planning commands are concrete planning heuristics that can be ported without any code dependency.

### Gaps
- I did not inspect canvas-mcp's actual skill prompt text (the weekly-plan SKILL.md) to quote its planning prompt.

---

## 3. Student-focused email + LMS assistants, and "second-brain" email→task agents

### Takeaway
Very few open-source projects combine the LMS with institutional email. The closest are **Miguel121699/academic-assistant** (Brightspace + Outlook + Ollama) and **shabajsha/AgCalender** (college email → calendar/tasks with local Ollama, Telegram approvals). Generic local inbox-triage agents are plentiful but young; **tarunlnmiit/inbox-to-action** (MIT, PyPI, MCP registry) is the most packaged. Commercial "unified student assistant" products exist, but I found little verifiable detail on them.

### Cited Findings
- **Miguel121699/academic-assistant**: Brightspace + Outlook (@utrgv.edu) + Ollama. Outlook access uses the Microsoft device code flow, "no Azure app registration needed". It can read and send email and view and create calendar events. — [README](https://github.com/Miguel121699/academic-assistant)
- **shabajsha/AgCalender**: https://github.com/shabajsha/AgCalender, no licence, pushed 2026-10-03. Reads college (IIITH) emails forwarded to Gmail and turns deadlines, meetings and events into Google Calendar events and Tasks, using local **Ollama gemma2:9b**. Design:
  - a keyword pre-filter runs before the LLM
  - "All date math lives here [dates.py], not in the LLM"
  - `.ics` attachments are imported deterministically, with no LLM
  - a SQLite state DB fingerprints processed and skipped emails
  - a confidence threshold applies
  - **every proposed item is sent to Telegram with Add/Skip buttons**, and the tool offers to block senders the user always skips
  - a morning routine produces a plan — [README](https://github.com/shabajsha/AgCalender)
- **tarunlnmiit/inbox-to-action**: https://github.com/tarunlnmiit/inbox-to-action, MIT, pushed 2026-07-26. "One-pass agentic inbox triage: classify, summarise, extract tasks and draft replies", draft-only (no sending). On PyPI and the Official MCP Registry, with a `--mock` sample inbox and multi-provider support (Gmail OAuth documented). — [README](https://github.com/tarunlnmiit/inbox-to-action)
- Other local triage agents (all small, 2026): [gauravch-code/winnow](https://github.com/gauravch-code/winnow) ("tiered classifier + LLM"), [JoeCotellese/inboxzero](https://github.com/JoeCotellese/inboxzero) ("heuristic + LLM classification pipeline", 2026-03), [alicecommits/scoped-inbox-agent](https://github.com/alicecommits/scoped-inbox-agent) (least-privilege OAuth2, deterministic action layer), [nonozone/MailCli](https://github.com/nonozone/MailCli) (Apache-2.0, local-first email interface for agents), [shariqhameedca/mail-router](https://github.com/shariqhameedca/mail-router) (MIT, routes between local Ollama and cloud), and [GuavaEater/Organizer](https://github.com/GuavaEater/Organizer) (Outlook + LLM triage on Windows 11). — GitHub API searches "inbox triage llm local", "outlook email triage llm"
- **drwjkirkpatrick-web/executive-assistant**: MIT, 2026-08-07. Morning briefings and evening wrap-ups to Telegram covering calendar, email, tasks and weather. — [GitHub search](https://github.com/drwjkirkpatrick-web/executive-assistant)
- Commercial or idea-stage products: "UniFlow Assistant" is described as a platform integrating "LMS platforms, calendars, emails, and collaboration tools", but the listing is on an ideas site, and I could not verify that it is a shipping product. — [turbostarter.dev](https://www.turbostarter.dev/ideas/productivity/uniflow-assistant). Swiftask markets a Brightspace integration that "sync[s] course deadlines with student calendars". — [swiftask.ai](https://swiftask.ai/ai-integration/d2l-brightspace)
- Brightspace's built-in "Intelligent Agents" are instructor-configured rules that email students (for example deadline reminders). They are a source of LMS-generated email the user's triage should recognize. — [MUN CITL](https://blog.citl.mun.ca/technologyresources/tech-res-dev/intelligent-agents-introduction/), [UVM](https://ctl.w3.uvm.edu/brightspaceminutearchive/01-19-24-Intelligent%20Agents.html)

### Inferences
- The recurring good design in email→task tools has six parts:
  1. a cheap deterministic pre-filter or rules tier
  2. an LLM used only for extraction, into a schema
  3. deterministic date resolution
  4. a dedupe and fingerprint store
  5. human approval before writes (Telegram buttons, draft-only)
  6. sender-level learning ("always skip")

  This matches the user's "triage with LLMs and produce task briefs" goal, and can be implemented natively without adopting any one repo.
- Microsoft's device code flow (as used by academic-assistant) is an Outlook-access path for students that needs no app registration. The user's app already ingests Outlook mail via the desktop wrapper, so this matters mainly as a fallback.
- Deduplicating across sources is an unsolved gap in existing tools. Brightspace notification emails, Intelligent Agent emails and the LMS API all report the same deadline, so the user's app needs a merge key (for example orgUnitId + folderId/quizId, with email-derived items linked by course code + title + date).

### Gaps
- I found no open-source project that does Outlook + Brightspace + cross-source dedupe + brief generation all together. academic-assistant comes closest but is a chat agent, not a sync and triage pipeline.
- I found no reliable details on commercial student assistants (for example pricing, or whether they support Brightspace SSO).
- Reddit and Hacker News searches surfaced no specific student posts. That is weak evidence; the search engine may index them poorly.

---

## 4. Singapore polytechnic / POLITEMall-specific projects, and D2L's own AI (Lumi)

### Takeaway
POLITEMall-specific open source is sparse. There are only three items: POLITEShop (the substantive client and reverse-engineering notes), RohanMuppa's `--ngeeann` preset, and a cosmetic theme extension. D2L's own student AI (Lumi Tutor, Study Support, and Lumi Learner Mode, beta from September 2026 for Lumi Pro) lives inside course content, depends on what the institution licenses, and has no cross-course email or deadline triage. It complements the user's app rather than replacing it.

### Cited Findings
- POLITEMall is "the Learning Management System (LMS) used by Polytechnics and ITEs in Singapore" at politemall.polite.edu.sg. POLITEShop reverse-engineers it. — [POLITEShop README](https://github.com/haziq21/politeshop)
- POLITEShop includes `lib/data/nplms-modules-20260610.jsonl` (an NP module dataset) and maps Brightspace classes to poly terms (Module, Diploma, Semester "24S1"). — [repo tree](https://github.com/haziq21/politeshop), [brightspace-reveng.md](https://github.com/haziq21/politeshop/blob/HEAD/lib/docs/brightspace-reveng.md)
- RohanMuppa's server lists "Ngee Ann Polytechnic | `--ngeeann` | Plain Microsoft Entra, no extra steps." — [docs/sign-in.md](https://github.com/RohanMuppa/brightspace-mcp-server/blob/main/docs/sign-in.md)
- [Pushkaltoocool/Politemall-Plus](https://github.com/Pushkaltoocool/Politemall-Plus) is a dark-theme Chrome extension only (2025-10-31, no licence). [HengJingSeng/EGL301…Politemall](https://github.com/HengJingSeng/EGL301_Assignment1_JingSeng_Politemall) is a school assignment. Neither is relevant. — GitHub API search "politemall"
- **D2L Lumi (2025):** Lumi Tutor is "an intelligent teaching and learning chat integrated into course content", helping learners with "due dates, personalized study plans, instant practice, and roleplay". Lumi Study Support gives tailored recommendations after a quiz. — [D2L newsroom](https://www.d2l.com/newsroom/d2l_advances_breakthrough_personalized_learning_with_new_ai_features/), [Campus Technology, 2025-08-14](https://campustechnology.com/Articles/2025/08/14/D2L-Lumi-AI-Updates-Add-Personalized-Study-Supports.aspx)
- **Fusion 2026 (press release dated 2026-07-09):** D2L Lumi Learner Mode adds notes, highlights, examples, knowledge checks, progress tracking and "AI-powered tutoring alongside their learning materials", in **beta from September 2026 for Lumi Pro users**. Lumi Remix is aimed at educators. The release mentions no MCP/agent integrations or cross-course study planning. — [D2L Fusion 2026 release](https://www.d2l.com/newsroom/d2l-announces-new-ai-enhanced-content-creation-and-personalized-learning-at-fusion-2026/), [Fusion 2026 highlights blog](https://www.d2l.com/blog/in-case-you-missed-it-product-highlights-from-fusion-2026/)
- I found no official D2L MCP server. Brightspace MCP servers in registries are community projects. — [Glama](https://glama.ai/mcp/servers/@RohanMuppa/brightspace-mcp-server), [Enterprise DNA directory](https://enterprisedna.co/directories/mcp/rohanmuppa-brightspace-mcp-server)
- Brightspace Pulse (D2L's student mobile app for due dates and notifications) is still active. D2L retired SMS notifications in 2024. — [MSU Tech news](https://tech.msu.edu/news/2024/07/d2l-retiring-sms-notifications), [SUNY Oswego](https://oswego.edu/news/announcements/new-pulse-mobile-app-widget-brightspace). A 2026 repo, [rileyallyn/grade-checker](https://github.com/rileyallyn/grade-checker), describes itself as "an idea to replace the 'brightspace pulse' app" (MIT, 2026-10-08).

### Inferences
- Whether Lumi Tutor or Learner Mode is available to the user depends on whether the polytechnics license Lumi Pro. Nothing found indicates POLITEMall has enabled it. Even where enabled, it only works inside Brightspace and cannot see Outlook mail, so the user's app does not duplicate it.
- The `--ngeeann` preset strongly suggests other POLITEMall polytechnics (which share politemall.polite.edu.sg) use a similar Entra flow, though they may differ by tenant.

### Gaps
- I did not check whether D2L publishes a list of Lumi-enabled institutions, or whether the Singapore polytechnics have announced Lumi adoption.
- I found no student-built POLITEMall + LLM assistant beyond POLITEShop, which is a UX client, not an LLM tool.
- I did not determine which polytechnic the user attends, or whether every POLITEMall polytechnic uses the same Entra tenant flow.

---

## 5. What is reusable vs not worth adopting

### Takeaway
Reuse **auth/session management, the endpoint map, and design patterns**. Do not adopt a whole app. RohanMuppa's server (MIT) is the one component worth depending on or vendoring. Everything else is better treated as design reference, especially the many unlicensed repos.

### Cited Findings
**Reusable (with licence status):**
- *Auth/session* (MIT): RohanMuppa `src/auth/microsoft-session.ts`, `token-mint.ts`, `session-store.ts`, `encrypted-store.ts`, and keychain credential storage. — [repo](https://github.com/RohanMuppa/brightspace-mcp-server/tree/main/src/auth)
- *Auth/session* (MIT): JhostinAleck's strategy abstraction (headless / browser / api_token, plus MFA strategies). — [README](https://github.com/JhostinAleck/brightspace-mcp)
- *Auth/session* (MIT, pattern): Brightspace-Bar's "renewal ladder" daemon split. — [README](https://github.com/DavidChen-006/Brightspace-Bar)
- *API layer* (MIT): RohanMuppa `src/api/version-discovery.ts` (uses `/d2l/api/versions/`), plus `paginate`, `rate-limiter`, `retry` and `cache`. — [repo](https://github.com/RohanMuppa/brightspace-mcp-server/tree/main/src/api)
- *Endpoint map:* POLITEMall's Valence routes and versions (le 1.75, lp 1.46) and the internal Siren API notes. These are reference only, because there is **no licence**. — [POLITEShop](https://github.com/haziq21/politeshop/blob/HEAD/lib/clients/polite.ts)
- *Endpoint map:* JhostinAleck's tools.md, covering rubric/feedback endpoints, the "current course" heuristics and syllabus discovery (MIT). — [tools.md](https://github.com/JhostinAleck/brightspace-mcp/blob/main/docs/tools.md)
- *Prompts* (MIT): the `weekly_briefing` and `study_planner` MCP prompts. — [prompts](https://github.com/RohanMuppa/brightspace-mcp-server/tree/main/src/prompts)
- *Prompts* (MIT): canvas-mcp's weekly-plan and morning-check skills. — [canvas-mcp](https://github.com/vishalsachdev/canvas-mcp)
- *Sync and calendar export patterns:* Adamolids, which has no licence, so copy the patterns, not the code. — [Adamolids](https://github.com/Adamolids/Brightspace_Assignment_Tracker)
- *Sync and calendar export patterns:* vidya's invariants test suite (MIT, stdlib Python). — [vidya](https://github.com/vinilpolepalli/vidya)
- *Sync and calendar export patterns:* the iCal "11:59-11:59" fix (MIT). — [khui0 middleware](https://github.com/khui0/brightspace-calendar-middleware)
- *Notification and approval design:* AgCalender's Telegram Add/Skip approvals and sender blocking. — [AgCalender](https://github.com/shabajsha/AgCalender)
- *Notification and approval design:* Sentinel's escalation ladder and quiet hours. — [Sentinel](https://github.com/sa1emie/sentinel)
- *Notification and approval design:* StudyAgent's explicit-completion rule. — [StudyAgent](https://github.com/aaravhmodi/study-agent)
- *Security:* canvas-mcp's provenance-fencing of LMS text as data, not instructions. — [canvas-mcp](https://github.com/vishalsachdev/canvas-mcp)

**Not worth adopting:**
- Legacy Valence SDKs from 2013–2020: abandoned, and they assume ID/key app registration. — [GitHub search](https://github.com/Brightspace/valence-sdk-java)
- OAuth-app Python wrappers such as `brightspace-api`/bsapi: need a registered app. — [PyPI](https://pypi.org/project/brightspace-api/)
- Hosted multi-tenant services such as Horizon: they send credentials to a third party. — [README](https://github.com/hamzakammar/mcp-workspace)
- Approaches that store a plaintext password in `.env`, such as academic-assistant's Method B. — [README](https://github.com/Miguel121699/academic-assistant)
- Selenium HTML scrapers: brittle. Adamolids moved from scraping to REST because "reliance on front end CSS selectors proved unstable". — [Adamolids](https://github.com/Adamolids/Brightspace_Assignment_Tracker)
- One-day or abandoned MCP repos (bencered, joshuasoup, iabounaaj/deadlines, XiyaoWang0519).

### Inferences
- Recommended architecture: run or vendor RohanMuppa's server (or its auth and API modules) as the Brightspace adapter. Because it is MCP, the user's own LLM triage layer can call it directly, and so can Claude Desktop or Claude Code. Build the email+LMS merge, the deterministic date and dedupe core (vidya/Adamolids style), and the approval-gated brief/plan generation yourself, since no existing project does this.
- Verify the cookie→token mint (`/d2l/lp/auth/oauth2/token`, `scope=*:*:*`, CSRF header) against POLITEMall first. If it works, the user's existing session-cookie approach can call the Valence API with Bearer tokens, the same way the browser does.

### Gaps
- I could not confirm the precise licence status of DMontgomery40/mcp-canvas-lms (the API reported none), or of several small repos.
- I did not benchmark how stable the RohanMuppa Ngee Ann flow is over long unattended periods. Its docs warn that passwordless mode needs a phone approval on every sign-in, which is bad for unattended jobs.
