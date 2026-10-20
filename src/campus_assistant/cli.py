"""campus login | check | sync | import-mail | analyze | serve | service | upcoming"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from .config import Config
from .store import Store

LOCAL_TZ = ZoneInfo("Asia/Singapore")


def _runner(cfg: Config):
    from .runner import BrightspaceRunner

    cfg.ensure_dirs()
    return BrightspaceRunner(Store(cfg.db_path), cfg)


def _via_server(cfg: Config, method: str, path: str, what: str) -> dict | None:
    """When `campus serve` (e.g. the background service) is running, it owns the browser profile and
    a second Chromium can't open it — so hand the operation to the server instead."""
    from .service import server_running

    if not server_running(cfg):
        return None
    import httpx

    print(f"campus serve is running at {cfg.base_url}; asking it to {what}.")
    r = httpx.request(method, cfg.base_url + path, json={} if method == "POST" else None, timeout=120)
    r.raise_for_status()
    return r.json()


def cmd_login(cfg: Config, args) -> int:
    if _via_server(cfg, "POST", "/auth/brightspace/login", "open the sign-in window") is not None:
        print(f"Finish signing in in the window; status: {cfg.base_url}/ui/system")
        return 0
    # Through the runner so the API's auth state is updated too.
    auth = asyncio.run(_runner(cfg).login(args.hosts or list(cfg.bs_hosts), sync_after=False))
    return 0 if auth["state"] == "ok" else 1


def cmd_sync(cfg: Config, args) -> int:
    if (res := _via_server(cfg, "POST", "/sync/brightspace", "sync")) is not None:
        print("Sync started." if res.get("started") else f"Busy ({res.get('busy')}); try again shortly.")
        return 0
    if args.hosts:
        cfg.bs_hosts = args.hosts
    report = asyncio.run(_runner(cfg).sync())
    print(json.dumps(report.as_dict(), indent=2))
    return 1 if report.login_required or report.errors else 0


def cmd_check(cfg: Config, args) -> int:
    auth = _via_server(cfg, "POST", "/auth/brightspace/check", "check sessions") or asyncio.run(_runner(cfg).check())
    for host, v in auth["hosts"].items():
        print(f"{host}: {v['state']}" + (f" ({v['user']})" if v.get("user") else ""))
    return 0 if auth["state"] == "ok" else 1


def cmd_import_mail(cfg: Config, args) -> int:
    from pathlib import Path

    from .mail import email_item, iter_archive

    cfg.ensure_dirs()
    store = Store(cfg.db_path)
    root = Path(args.root).expanduser()
    batch, total, failed = [], {}, 0

    def flush():
        nonlocal failed
        try:
            counts = store.upsert_many(batch)
        except Exception:
            # Find the bad one(s) instead of losing the whole batch.
            counts = {}
            for item in batch:
                try:
                    c = store.upsert(item)
                    counts[c] = counts.get(c, 0) + 1
                except Exception as err:
                    failed += 1
                    logging.warning("Skipping %s: %s", item.data.get("meta", {}).get("eml_path"), err)
        for k, v in counts.items():
            total[k] = total.get(k, 0) + v
        batch.clear()

    for m in iter_archive(root):
        try:
            batch.append(email_item(m))
        except Exception as err:
            failed += 1
            logging.warning("Skipping %s: %s", m.eml_path, err)
        if len(batch) >= 500:
            flush()
    flush()
    print(f"Imported from {root}: {total}, failed: {failed}")
    return 0


def cmd_analyze(cfg: Config, args) -> int:
    from .runner import AnalysisRunner

    cfg.ensure_dirs()
    run = AnalysisRunner(Store(cfg.db_path))
    report = asyncio.run(run.run_now(triage=not args.briefs_only, briefs=not args.triage_only,
                                     since_days=args.days, horizon_days=args.horizon, limit=args.limit,
                                     force=args.force, capped=not args.no_cap))
    print(json.dumps(report, indent=2))
    return 0


def cmd_eval(cfg: Config, args) -> int:
    from .analysis.evaluate import evaluate

    print(json.dumps(evaluate(Store(cfg.db_path), args.cutoff), indent=2))
    return 0


def cmd_llm(cfg: Config, args) -> int:
    from .llm import llm_status

    print(json.dumps(asyncio.run(llm_status()), indent=2))
    return 0


def cmd_serve(cfg: Config, args) -> int:
    import uvicorn

    from .api import create_app

    from .service import UNIT_NAME, installed, server_running, ui_hint, ui_state

    if server_running(cfg):
        extra = f" (background service: `systemctl --user stop {UNIT_NAME}`)" if installed() else ""
        print(f"Already running at {cfg.base_url}{extra}.", file=sys.stderr)
        return 1
    ui = ui_state(cfg)
    print(f"Web UI: {cfg.base_url}/ui/" if ui == "ok" else ui_hint(ui))
    uvicorn.run(create_app(cfg, schedule=not args.no_schedule), host=cfg.host, port=cfg.port)
    return 0


def cmd_service(cfg: Config, args) -> int:
    from . import service

    match args.action:
        case "install":
            return service.install(cfg, start=not args.no_start)
        case "uninstall":
            return service.uninstall()
        case "restart":
            service.restart_if_installed()
            return 0
        case "status":
            return service.exec_status()
        case "logs":
            return service.exec_logs(args.follow)
    return 2


def cmd_upcoming(cfg: Config, args) -> int:
    store = Store(cfg.db_path)
    now = datetime.now(UTC)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    rows = store.upcoming(now.strftime(fmt), (now + timedelta(days=args.days)).strftime(fmt))
    for r in rows:
        due = datetime.fromisoformat(r["due_at"].replace("Z", "+00:00")).astimezone(LOCAL_TZ)
        done = " ✓" if r["data"].get("submitted") else ""
        print(f"{due:%a %d %b %H:%M}  {r['kind']:<10} {r['title']}{done}  — {r['course_name']}")
    if not rows:
        print("Nothing due.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="campus")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("login", help="Sign in to Brightspace in a visible browser window")
    s.add_argument("hosts", nargs="*")
    s.set_defaults(fn=cmd_login)

    s = sub.add_parser("sync", help="Sync Brightspace now")
    s.add_argument("hosts", nargs="*")
    s.set_defaults(fn=cmd_sync)

    s = sub.add_parser("check", help="Check Brightspace sessions without syncing")
    s.set_defaults(fn=cmd_check)

    s = sub.add_parser("import-mail", help="Import an existing Prospect Mail archive directory")
    s.add_argument("root", nargs="?", default="~/Documents/Prospect Mail Archive")
    s.set_defaults(fn=cmd_import_mail)

    s = sub.add_parser("analyze", help="Run LLM triage of messages and briefs for upcoming tasks")
    s.add_argument("--days", type=int, default=30, help="triage messages from the last N days")
    s.add_argument("--horizon", type=int, default=60, help="brief tasks due in the next N days")
    s.add_argument("--limit", type=int, help="at most N items per step")
    s.add_argument("--force", action="store_true", help="redo items already analysed")
    s.add_argument("--no-cap", action="store_true", help="ignore the per-run caps (heavy on a local GPU)")
    g = s.add_mutually_exclusive_group()
    g.add_argument("--triage-only", action="store_true")
    g.add_argument("--briefs-only", action="store_true")
    s.set_defaults(fn=cmd_analyze)

    s = sub.add_parser("eval", help="Triage accuracy and classifier calibration against your labels")
    s.add_argument("--cutoff", type=float, default=0.8)
    s.set_defaults(fn=cmd_eval)

    s = sub.add_parser("llm", help="Show which LLM each task uses and probe the local server")
    s.set_defaults(fn=cmd_llm)

    s = sub.add_parser("serve", help="Run the local API (and scheduled syncs)")
    s.add_argument("--no-schedule", action="store_true")
    s.set_defaults(fn=cmd_serve)

    s = sub.add_parser("service", help="Run `serve` in the background as a systemd user service (Linux)")
    s.add_argument("action", choices=["install", "uninstall", "restart", "status", "logs"])
    s.add_argument("--no-start", action="store_true", help="install: enable for next login but don't start now")
    s.add_argument("-f", "--follow", action="store_true", help="logs: keep following")
    s.set_defaults(fn=cmd_service)

    s = sub.add_parser("upcoming", help="List what is due")
    s.add_argument("--days", type=int, default=21)
    s.set_defaults(fn=cmd_upcoming)

    args = p.parse_args()
    from ._logging import configure_logging
    configure_logging(verbose=args.verbose)
    return args.fn(Config(), args)


if __name__ == "__main__":
    raise SystemExit(main())
