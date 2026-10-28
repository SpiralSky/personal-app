# Local API security model: loopback transport, explicit principals, scoped credentials

| Field | Value |
|---|---|
| ID | ADR-003 |
| Status | accepted |
| Date | 2026-10-28 |
| Affects | F-001, F-013, F-015, F-016, F-004, F-018 |
| Supersedes | — |

## Context

The specs describe four different layers of protection and disagree about
whether the daemon has authentication at all:

- F-001 (Accepted) requires a lock screen, local authentication and RBAC
  (`owner`, `student`, `agent`, `guest`), with a session cookie for the web UI,
  tokens for the KDE tray/widget and a feed token for `/calendar.ics`.
- F-015 (Draft) says authentication is a **non-goal** ("single-user local
  tool", NG-1) and specifies only Host/Origin validation.
- F-016 (Draft) requires the CLI to read `$XDG_DATA_HOME/campus-assistant/.daemon-token`
  (mode `0600`) and send it as a bearer token when proxying to a running daemon.
- F-013 (Draft) requires the HTTP MCP endpoint to verify a local bearer token
  or Host/Origin per F-015, and forbids any non-loopback bind.

A single-user app still needs a lock screen because the machine may be shared
(F-001 §2). Origin/Host checks alone protect against browser-origin attacks but
not against a person at the keyboard or a local process reading the store.

## Decision

Security is layered; each layer answers a different threat.

1. **Transport.** The daemon binds only `127.0.0.1` and `::1` (F-001 FR-001-03,
   F-015 FR-8, F-013 NG-1). No TLS, no public bind, no reverse-proxy guidance.
2. **Request provenance (always on).** Every HTTP request is validated for an
   allowed `Host` (loopback names only) and, when present, an allowed `Origin`
   (`http://localhost:*`, `http://127.0.0.1:*`, `vscode-webview://*`; F-015
   FR-8/FR-9). Foreign `Origin` → 403 `origin_forbidden`; unknown `Host` → 400.
   This is mandatory even for authenticated requests.
3. **Principals and authentication.** Every request resolves to one principal
   with a role from F-001 §4.2. Roles and credentials:

   | Principal | Credential | Storage | Scope |
   |---|---|---|---|
   | `owner` (interactive) | passphrase/PIN login → session cookie (HttpOnly, SameSite=Strict, session-only) | signed with a first-boot local secret | full API |
   | `student` (interactive) | same login flow, own profile | as above | academic data read/write; no credential/system management |
   | CLI | `.daemon-token`, 0600 file | `$XDG_DATA_HOME/campus-assistant/.daemon-token` (F-016 Q-016-02) | effective role `owner` for local CLI; token is a machine secret, never exposed over HTTP |
   | KDE tray / Plasma widget | per-surface token generated at pairing | `meta` store (hash only) | `student` / `guest` respectively, per F-001 §5 |
   | `/calendar.ics` | feed token in query string | `meta` store (hash only) | `guest`, calendar data only |
   | MCP stdio | process stdin/stdout, no network | — | role supplied by the launching config (default `agent`) |
   | MCP HTTP/SSE | bearer token | `meta` store (hash only) | `agent` unless explicitly elevated |

4. **Authorization.** A single role matrix (A-001 §9.2) is applied server-side to
   every route. `agent` is denied raw email bodies, credentials and settings
   (F-001 AC-001-03); `guest` is denied email bodies, notes and grades. Denial is
   403 with the standard error envelope, never a silent filter.
5. **Sessions.** Inactivity lock after a configurable timeout (default 15 min,
   F-001 §4.3) revokes the in-memory session and its tokens; the browser keeps
   only an HttpOnly cookie. Password/PIN material is stored as a memory-hard
   hash (Argon2id or PBKDF2-HMAC-SHA256 ≥ 100 000 iterations), never reversible.
6. **UI bootstrap exception.** `/api/v1/health`, the login/lock endpoints, and
   the static SPA shell needed to render the lock screen are the only
   unauthenticated routes. They expose no item, email, grade or credential data.
7. **MCP.** stdio is authenticated by the launching process. HTTP/SSE requires a
   bearer token **and** the same Host/Origin checks; it is never exempt because
   it is "local" (F-013 FR-013-16).
8. **Egress.** No request leaves the machine without passing the anonymizer
   (F-013 FR-013-09/10/11). If the anonymizer is unavailable the remote call is
   aborted (`PrivacyEgressBlockedError`), never failed open. No telemetry.
9. **Non-goals stay non-goals.** No OAuth2, no cloud identity, no public
   hosting, no multi-tenant authorisation, no remote user accounts. The
   `agent`/`guest` principals are local capability scopes, not accounts on a
   network.

## Consequences

- **F-015 NG-1 must be amended**: "no authentication" is replaced by "no remote
  authentication / no multi-user server"; its Origin/Host rules remain and become
  the provenance layer. This is a feature-visible change and is raised to the
  owner before F-015 is accepted (Phase 1, step 3).
- F-016's `.daemon-token` is retained as the CLI credential rather than a second
  auth system; `campus` when no daemon runs operates in-process under the
  invoking OS user (F-016), which is equivalent to `owner`.
- Every route must be role-tagged. Adding a route requires choosing a minimum
  role; the spec check enforces that new `/api/v1` routes appear in the A-001
  route table.
- Route-name aliases are compatibility sugar, not security boundaries: aliases
  (for example `POST /api/v1/sync/run` → `POST /api/v1/sources/brightspace/sync`)
  inherit the target route's authorisation exactly.
- Tests must cover: unauthenticated access to a private route, wrong-role
  access, expired session, foreign Origin, unknown Host, and egress-blocked
  anonymizer. A green unit suite without these is not evidence of the model.

## Related

- [A-001 §6 (API contract), §9 (security)](A-001-runtime-contracts-persistence.md)
- F-001 §4 (RBAC), F-015 §7 (Origin/Host), F-013 §6 (egress), F-016 §4 (daemon token)
