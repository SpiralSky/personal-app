# campus-assistant

Local backend that collects Brightspace (POLITEMall / SP LMS) and Outlook mail
into one SQLite store, tracks what changed, and serves it over a local API.

## Setup

Needs Linux with a desktop session, [uv](https://docs.astral.sh/uv/) and Node.js 20+.

```bash
git clone <this repo> && cd <repo>
./setup.sh                       # Python deps, Playwright Chromium, builds the web UI
uv run campus login              # sign in to Brightspace once (opens a browser window)
uv run campus service install    # run in the background, start at every desktop login
```

Then open **http://127.0.0.1:8765/ui/**. To use it like an app, click the install icon in Chrome/Edge's
address bar (or ⋮ → Cast, save and share → Install page as app): it gets its own window and launcher entry.

**Updating** after `git pull`: run `./setup.sh` again (it rebuilds and restarts the service).
Without the service, run `uv run campus serve` in a terminal instead.

Other commands: `campus check` (session status), `campus sync`, `campus upcoming`,
`campus import-mail [archive dir]` (one-off import of the Prospect Mail archive), `campus analyze`, `campus eval`.
Only one process can use the Brightspace browser profile, so while the server/service is running,
`campus login | sync | check` hand the operation to it instead of opening their own browser.

## Background service

`campus service install | uninstall | restart | status | logs [-f]` manages a systemd **user** service
(`~/.config/systemd/user/campus-assistant.service`, no root). It starts with your graphical session —
it needs your display to open the sign-in window — and stops when you log out. Stopping it with
`systemctl --user stop campus-assistant` or `campus service uninstall` removes it completely.

### What runs in the background

| Process | When | Count |
|---|---|---|
| `python3 … campus_assistant.cli serve` (API, web UI, scheduler) | always, while logged in | 1 process, ~6 threads, ~90 MB |
| Playwright driver (`node`) + headless Chromium | only during a Brightspace sync/check (≈1 min, hourly by default) or a sign-in window | +7 processes (~80 threads), closed afterwards |
| LLM analysis | after syncs/new mail, as HTTP requests to *your* LLM server — nothing is started | 0 |

At most one browser runs at a time (sync, check and login share a lock). Everything the service starts
stays in its cgroup (Chromium is kept from moving itself into its own systemd scope), so systemd stops all of
it together, and `TasksMax=256` hard-caps processes+threads (a sync peaks around 85). If it keeps crashing,
systemd gives up after 10 starts in 5 minutes (`campus service restart` resets that). Check with `campus service status` (shows the task count
and process tree) or `campus service logs -f`.

Data: `~/.local/share/campus-assistant/` (database, downloaded files, browser profile).
Settings: `~/.config/campus-assistant/env` — restart the service after editing.

## Sources

| Source | How | Kinds |
|---|---|---|
| `brightspace:splms`, `brightspace:lms` | Valence REST API with the logged-in browser session (Playwright) | course, assignment, quiz, announcement, content, event, grade |
| `outlook` | Prospect Mail fork pushes each archived message to `POST /ingest/email` | email |

Document files (pdf, docx, pptx, ...) from courses with recent activity are
downloaded to `~/.local/share/campus-assistant/files`.

## Login state (for the central app)

Brightspace logins go through SSO with MFA, so they can't be fully automated.
Each sync (and `POST /auth/brightspace/check`) first tries a silent SSO refresh;
only when that fails does a host become `login_required`.

```
GET  /auth/brightspace          → {"state": "ok" | "login_required" | "unknown",
                                   "hosts": {"splms.polite.edu.sg": {"state", "user", "checked_at", "since", "detail"}, ...},
                                   "login_in_progress": bool, "busy": "sync" | "check" | "login" | null}
POST /auth/brightspace/check    → same shape; re-checks now (~2 s when logged in, up to ~1 min when not)
POST /auth/brightspace/login    → 202; opens the sign-in window on this machine's display for the
                                   hosts that need it, then syncs. Body (optional): {"hosts": [...], "sync_after": true}
```

Suggested flow: poll `GET /auth/brightspace` (cheap, no network). On
`login_required`, notify the user; their click calls `POST /auth/brightspace/login`,
then poll until `state == "ok"`. The window needs a display, so run `serve`
inside the desktop session (not a headless system service).

## LLM analysis

Two tasks, each with its own provider (`CAMPUS_LLM_TRIAGE`, `CAMPUS_LLM_BRIEF` = `claude | local | auto | off`;
`auto` = Claude when credentials exist, else local):

| Task | What | Default |
|---|---|---|
| `triage` | emails + announcements → category, priority, summary, actions, dates, opportunity, links | `local` |
| `brief` | upcoming unsubmitted assignments/quizzes + matching course files → summary, deliverables, requirements, plan, open questions | `auto` |

Categories: `action_required`, `deadline`, `notice`, `opportunity`, `personal`, `system`, `newsletter`, `other`;
priorities: `urgent`, `soon`, `whenever`, `ignore`. Brightspace/Teams notification mail and mail you sent
are triaged by rules without a model call.

Results are cached per item by an input hash (content + prompt version + related files), so only new or
changed items are analysed. With `serve`, analysis runs automatically after each sync and email push
(`CAMPUS_AUTO_ANALYZE=0` to disable); `campus analyze` runs it by hand.

**Local models**: nothing is bundled. Run any OpenAI-compatible server with JSON-schema output —
llama.cpp's `llama-server` or a fork, Ollama (`/v1`), LM Studio — and point `CAMPUS_LOCAL_LLM_URL` at it.
Without `CAMPUS_LOCAL_LLM_MODEL` the first loaded model is used; on llama.cpp the input budget follows the
server's context size (`/props`). `campus llm` / `GET /llm/status` show what was detected.

**Keeping a shared GPU usable**: local requests are serialised with a pause after each
(`CAMPUS_LOCAL_LLM_PAUSE_S`, 3), each run handles at most `CAMPUS_ANALYZE_MAX_CLASSIFY` (60) classifications
and `CAMPUS_ANALYZE_MAX_LLM` (15) generations (the rest waits for the next run; `campus analyze --no-cap`
overrides), and models used are unloaded from a llama-server router afterwards (`CAMPUS_LOCAL_LLM_UNLOAD`, 1).
Starting llama-server with `--sleep-idle-seconds N` does the same on the server side.

**Classifier (Jev-style)**: before generation, category and priority are classified in one forward pass
each by reading option-letter probabilities from the local model (`top_logprobs`; no text generated).
Options are shown as neutral letters with their definitions (option names bias decision heads);
`CAMPUS_CLASSIFY_PERMUTATIONS` > 1 averages over shuffled letter assignments. Raw probabilities from
an instruct model are **not calibrated** (most calls come out ≈1.00, including wrong ones), so
`CAMPUS_CLASSIFIER_MODE` defaults to `gate`: the classifier only decides confident newsletter/system/ignore
messages (which then skip generation); otherwise the LLM decides, and classifier/LLM disagreement sets
`needs_review`. `trust` (classifier overrides when p ≥ `CAMPUS_CLASSIFY_CUTOFF`) should only be enabled once
`campus eval` / `GET /triage/eval` shows high accuracy above the cutoff on your labels. `shadow` records only.
A dedicated calibrated decision model (e.g. Laya, Kev) could replace the logprob classifier behind the same
interface.

**Claude**: credentials via `ANTHROPIC_API_KEY` or `ant auth login`; model `CAMPUS_CLAUDE_MODEL`
(default `claude-opus-5-5`), with server-side refusal fallback enabled.

Settings can live in `~/.config/campus-assistant/env` (KEY=VALUE lines; real environment variables win).

```
GET  /triage?days=14&category=&priority=&kind=&include_ignored=false
GET  /tasks?days=60              upcoming tasks with "brief" (null until analysed)
POST /items/{id}/label           {"category", "priority", "note"} — your correction; overrides the model
POST /analyze                    {"triage", "briefs", "since_days", "horizon_days", "limit", "force"}
GET  /llm/status
```

## Other endpoints

```
GET  /status                     counts per source/kind, auth, last sync report
GET  /upcoming?days=30           items with a due date in the window (assignments, quizzes, content, standalone events)
GET  /changes?since=<iso>        created / updated (with changed field names, e.g. "due_at") / removed / restored
GET  /items?source=&kind=&course_id=&q=&limit=&offset=
GET  /items/{id}                 one item (+ downloaded file info)
GET  /items/{id}/history         previous versions
GET  /items/{id}/file            the downloaded file
GET  /calendar.ics               deadlines feed for calendar apps
POST /sync/brightspace           start a sync now
POST /ingest                     {"items": [ItemIn...]} generic ingest
POST /ingest/email               {"messages": [{item_id, folder, received_at, eml_path | mime_base64 | html, ...}]}
```

Item ids are `<source>:<kind>:<external_id>`. Dates are UTC (`...Z`).
`data.raw` (full source object) and `data.meta` (file locations etc.) are not
part of change detection.

## Web UI

A React app in `web/` (Vite + TypeScript + TanStack Query + Tailwind) that uses the JSON API above.
`campus serve` serves the built app at `/ui/` (and redirects `/` there) when `web/dist` exists.

| Page | What |
|---|---|
| Today | sign-in banner, deadlines for the next 7 days, urgent/soon messages, changes from the last 3 days, "Sync now" |
| Inbox | triaged messages with filters; **labelling** — `j`/`k` move, `1`–`8` category, `q`/`w`/`e`/`r` priority (goes to next), `Enter` accepts as-is. "Review queue" = `needs_review` |
| Tasks | upcoming assignments/quizzes with their brief and plan |
| Browse | search all items; body, analyses, raw data, version history, downloaded file |
| System | session state + sign in/check, stored counts, run analysis, LLM status, triage accuracy vs your labels, calendar feed URL |

```bash
cd web && npm run build    # after changing the UI; the running server picks it up without a restart
npm run dev                # development: hot reload on http://localhost:5173/ui/, proxies /api → :8765
```

`campus serve` warns when the build is missing or older than `web/src`.

In dev, `CAMPUS_API` overrides the proxied backend URL. `CAMPUS_WEB_DIST` points the backend at a different build.

## Config (environment)

`CAMPUS_DATA_DIR`, `CAMPUS_BS_HOSTS`, `CAMPUS_BS_SKIP` (regex of course names to skip),
`CAMPUS_SYNC_INTERVAL_MIN` (60), `CAMPUS_MAX_FILE_MB` (50), `CAMPUS_API_HOST`/`PORT`
(127.0.0.1:8765), `CAMPUS_BROWSER_CHANNEL` ("" = bundled Chromium).
