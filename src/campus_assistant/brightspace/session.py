"""Logged-in browser session for Brightspace.

Login goes through institutional SSO with MFA, so it is done by hand once in
a visible browser (`campus login`). After that, syncs run headless on the same
persistent Chromium profile. Brightspace's own session cookies are
browser-session cookies that a profile does not keep, so they are also saved
to a storage-state file and restored on start. If they have expired anyway,
loading /d2l/home usually re-authenticates silently through the SSO
provider's longer-lived cookies; only when that fails is a new login needed.
"""

import asyncio
import json
import logging
import os
from pathlib import Path

from playwright.async_api import BrowserContext, Playwright, async_playwright

from ..config import Config
from .client import BrightspaceClient, SessionExpired

log = logging.getLogger(__name__)

LOGIN_TIMEOUT_S = 600
REFRESH_POLLS, REFRESH_POLL_S = 10, 2.5


class BrowserSession:
    def __init__(self, cfg: Config, headless: bool = True):
        self.cfg = cfg
        self.headless = headless
        self.pw: Playwright | None = None
        self.context: BrowserContext | None = None

    async def __aenter__(self) -> "BrowserSession":
        self.cfg.ensure_dirs()
        self.pw = await async_playwright().start()
        # No session D-Bus: otherwise Chromium moves itself into its own systemd scope
        # (app-org.chromium.Chromium-*.scope), escaping the service's cgroup, TasksMax and stop/kill.
        kwargs = {"headless": self.headless, "env": {**os.environ, "DBUS_SESSION_BUS_ADDRESS": "disabled:"}}
        if self.cfg.browser_channel:
            kwargs["channel"] = self.cfg.browser_channel
        try:
            self.context = await self.pw.chromium.launch_persistent_context(str(self.cfg.browser_profile), **kwargs)
            await self._restore_cookies()
        except BaseException:
            # __aexit__ doesn't run when __aenter__ fails; don't leave the Playwright driver (and a
            # half-started Chromium, e.g. on a locked profile) running.
            if self.context:
                await self.context.close()
            await self.pw.stop()
            raise
        return self

    async def __aexit__(self, *exc) -> None:
        try:
            await self.save_cookies()
        finally:
            if self.context:
                try:
                    await self.context.close()
                except Exception:
                    pass  # the user closed the window
            if self.pw:
                await self.pw.stop()

    async def _restore_cookies(self) -> None:
        path: Path = self.cfg.cookie_jar
        if not path.exists():
            return
        try:
            cookies = json.loads(path.read_text()).get("cookies", [])
            if cookies:
                await self.context.add_cookies(cookies)
        except Exception as err:
            log.warning("Could not restore saved cookies: %s", err)

    async def save_cookies(self) -> bool:
        """Persist cookies (including session cookies). False if the browser is already gone."""
        if not self.context:
            return False
        try:
            state = await self.context.storage_state()
        except Exception as err:
            log.warning("Could not save cookies (browser closed?): %s", err)
            return False
        path: Path = self.cfg.cookie_jar
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"cookies": state["cookies"]}))
        os.chmod(tmp, 0o600)
        tmp.replace(path)
        return True

    def client(self, host: str) -> BrightspaceClient:
        return BrightspaceClient(self.context.request, host, delay=self.cfg.bs_request_delay)

    async def _visit_home(self, host: str) -> None:
        page = await self.context.new_page()
        try:
            await page.goto(f"https://{host}/d2l/home", wait_until="domcontentloaded", timeout=45_000)
            try:
                await page.wait_for_url(f"https://{host}/d2l/**", timeout=30_000)
                await page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass
        finally:
            await page.close()

    async def connect(self, host: str) -> BrightspaceClient:
        """Client for a host with a working session, refreshing it via SSO if needed."""
        client = self.client(host)
        if not await client.check_session():
            log.info("%s: session not valid, trying silent SSO refresh", host)
            await self._visit_home(host)
            # The page can finish loading before the re-authentication completes
            # in the background, so give it a little time.
            for _ in range(REFRESH_POLLS):
                if await client.check_session():
                    log.info("%s: session refreshed silently", host)
                    break
                await asyncio.sleep(REFRESH_POLL_S)
            else:
                raise SessionExpired(host)
        await client.load_versions()
        await self.save_cookies()
        return client

    async def interactive_login(self, hosts: list[str]) -> dict[str, bool]:
        """Open each host in a visible window and wait until the user has signed in.

        One tab is reused for every host: closing the last tab of a persistent
        context closes the whole browser. Cookies are saved straight after each
        sign-in so closing the window early never loses them.
        """
        results: dict[str, bool] = {host: False for host in hosts}
        page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        for host in hosts:
            client = self.client(host)
            if await client.check_session():
                print(f"✓ {host}: already signed in as {client.user.get('UniqueName')}")
                results[host] = True
                await self.save_cookies()
                continue
            if page.is_closed():
                print(f"✗ {host}: browser window was closed, run `campus login` again")
                break
            await page.goto(f"https://{host}/d2l/home")
            print(f"→ Sign in to {host} in the browser window (waiting up to {LOGIN_TIMEOUT_S // 60} min)...")
            for _ in range(LOGIN_TIMEOUT_S // 3):
                await asyncio.sleep(3)
                if await client.check_session():
                    results[host] = True
                    break
                if page.is_closed():
                    break
            if results[host]:
                saved = await self.save_cookies()
                print(f"✓ {host}: signed in as {client.user.get('UniqueName')}" + ("" if saved else " (cookies not saved)"))
            else:
                print(f"✗ {host}: not signed in")
        if all(results.values()):
            print("All done, you can close the browser window.")
        return results
