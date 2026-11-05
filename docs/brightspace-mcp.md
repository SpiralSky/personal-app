# Share and run Brightspace MCP

Brightspace MCP is a separate process, **not a standalone Brightspace client**.
It reads cached data from the Campus backend, which owns browser login, syncing,
and storage. The source bundle includes both Python components. It does not need
the web UI, Node.js tooling, Outlook setup, or an LLM account.

## Create a bundle to send

From the repository root:

```bash
python3 scripts/package_brightspace.py
```

Send `dist/brightspace-mcp.zip`. It includes current source changes, even before
commit. It deliberately includes only Python source, package metadata, the lockfile,
and setup documentation/example configuration. It excludes `.mcp.json` (your local
paths and other MCP servers), Git history, browser profiles, databases, downloads,
environment files, caches, and research notes. Rebuild after changing the source.

This shares the software; the recipient signs in with their own account. It does
not grant access to your Brightspace data or your running MCP endpoint.

## Recipient setup

Use Linux with a desktop session and `uv` installed. Extract the ZIP and open a
terminal in its `brightspace-mcp` directory. `START-HERE.md` is this guide; the full
project README also describes components omitted from this smaller bundle.

```bash
uv sync --locked --no-dev
uv run playwright install chromium
uv run campus login
uv run campus sync
CAMPUS_AUTO_ANALYZE=0 uv run campus serve
```

Keep the last command running. The backend listens at `http://127.0.0.1:8765` and
syncs hourly by default. A missing-web-UI message is expected for this bundle.
If Chromium reports missing system libraries, install its prerequisites for your
Linux distribution. Login opens a browser for institutional SSO/MFA.

The configured Brightspace hosts default to Singapore Polytechnic / POLITEMall:
`splms.polite.edu.sg,lms.polite.edu.sg`. For another institution, set
`CAMPUS_BS_HOSTS` to its comma-separated Brightspace hostnames in the terminal
before login, sync, and serve. Other institutions have not been verified.

## Connect a local MCP client

Merge the `brightspace` entry from `examples/brightspace.mcp.json` into your
client's MCP configuration. Replace `/absolute/path/to/brightspace-mcp` with the
extracted folder's absolute path. The client launches `campus-mcp` over stdio;
the backend above must also be running. Ensure the client can find `uv` on PATH.

Call `brightspace_status`, then `list_courses` to check the connection and freshness.
The other tools are `search_items`, `get_item`, `upcoming_deadlines`, and
`recent_changes`. Tools are read-only and limited to cached Brightspace records;
search covers titles and bodies, not downloaded document text.

For a client that supports local HTTP MCP, run in another terminal:

```bash
uv run campus-mcp --transport streamable-http
```

Connect it to `http://127.0.0.1:8766/mcp`. Both services bind to loopback by
default; they have no application-level authentication. Do not expose these
ports publicly. A remote client requires a separately configured private transport.

## Local data and troubleshooting

Each recipient's database, downloads, and browser session live under
`~/.local/share/campus-assistant/` by default, outside the extracted bundle.
Never send that directory with the software. `CAMPUS_DATA_DIR` overrides it.

- Backend unavailable: check that `campus serve` is still running.
- Login required: run `uv run campus login`, then `uv run campus sync`.
- Empty/stale results: inspect `brightspace_status`; an empty list does not prove
  there are no assignments. Login and sync must succeed first.
- Non-default backend address: set `CAMPUS_API_HOST` / `CAMPUS_API_PORT` consistently
  for both the backend and MCP process (including the client's environment).
