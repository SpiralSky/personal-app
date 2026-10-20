# Frontend Issues
_Files touched: web/src/api/client.ts, web/src/App.tsx, web/src/components/, web/src/pages/_

## HIGH

- **`App.tsx:42`** — No React error boundary anywhere. One unhandled render error blanks the entire app with no recovery.
- **`client.ts:162–168` / `Inbox.tsx:50–53`** — `useAction` has no `onError`; mutation failures (sync, login, analyze, label) silently discarded. User gets no feedback.
- **`Settings.tsx:52–73`** — "Fetch Models" and "Save" errors both swallowed. A failed save looks like success (panel closes immediately).
- **`Inbox.tsx:32` vs `Inbox.tsx:387`** — `useLabel()` called twice in `Detail`; two independent mutation instances; `saving` prop tracks outer, inner is invisible.

## MEDIUM

- **`client.ts:80–108`** — No `staleTime` on any query. Refetches on every window focus/remount; causes constant loading states.
- **`Inbox.tsx:213–275`** — `FilterDropdown` and `DateRangeFilter` use raw `document.addEventListener` for click-outside; no escape-key close, no ARIA, no keyboard navigation.
- **`Browse.tsx:54–61` / `Inbox.tsx:176`** — `<tr onClick>` with no `onKeyDown`/`tabIndex`/`role`; inaccessible to keyboard users.
- **`Tasks.tsx:38` / `Today.tsx:41`** — `(t.data as { submitted?: boolean }).submitted` cast duplicated in two files. Field belongs on the `Task` type.
- **`client.ts:55`** — Status polling every 3s with no timeout or backoff if backend hangs.
- **`Inbox.tsx:379–471`** — `Detail` mixes data fetching, mutation, state, and rendering in 80+ lines. Split into data shell + presentational component.
- **`App.tsx:54`** — Dynamic Tailwind strings (`` `${sidebarExpanded ? 'pl-56' : 'pl-14'}` ``) can be purged in production. Use static classes with `clsx`.
- **`ui.tsx:77`** — `e.target.value as T | ''` is an unsafe cast; TS won't catch future option additions.

## LOW

- **`format.ts:44`** — `humanize()` replaces underscores but doesn't capitalize. `'action_required'` → `'action required'` in badges.
- **`format.ts:17`** — `relative()` returns `''` for null/undefined; calling code doesn't guard, creates invisible layout gaps.
- **`Errors.tsx:28`** — Key `${e.time}-${i}` is index-based; unstable on list refresh. Use stable hash of time+logger+message.
- **`App.tsx:67`** — 404 route is a bare `<p>Not found.</p>`. No styling, no back navigation.
- **`Sidebar.tsx:4–16`** — Nav items are untyped `[path, label, icon]` tuples. Should be typed objects with narrowed icon type.
- **`ui.tsx:85–88`** — `Json` component has no copy button.
- No keyboard shortcut support (expected in productivity apps).
- No PWA offline fallback; manifest exists but no service worker.
