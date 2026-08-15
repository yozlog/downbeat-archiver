from __future__ import annotations

import html
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

ARCHIVE_URL = "https://www.downbeat.com/digitaledition/archive.html"
USER_AGENT = "DownBeatArchiver/1.0 (+personal archive sync)"
LOG = logging.getLogger("downbeat-archiver")


@dataclass
class Issue:
    name: str
    year: int
    source_url: str
    source_kind: str = "pdf"
    fallback_viewer_url: str | None = None

    @property
    def filename(self) -> str:
        return f"{self.name}.pdf"


class Fetcher:
    def __init__(self, retries: int = 4, timeout: int = 60) -> None:
        self.retries = retries
        self.timeout = timeout

    def request(self, url: str, *, headers: dict[str, str] | None = None):
        request_headers = {"User-Agent": USER_AGENT, **(headers or {})}
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                return urlopen(Request(url, headers=request_headers), timeout=self.timeout)
            except HTTPError as error:
                # Permanent client errors should immediately reach the caller;
                # 403/404 may trigger the modern viewer fallback.
                if error.code < 500 and error.code not in (408, 429):
                    raise
                last_error = error
                if attempt == self.retries:
                    raise
                delay = min(2**attempt, 15)
                LOG.warning("Request failed (%s); retrying in %ss: %s", error, delay, url)
                time.sleep(delay)
            except (URLError, TimeoutError) as error:
                last_error = error
                if attempt == self.retries:
                    raise
                delay = min(2**attempt, 15)
                LOG.warning("Request failed (%s); retrying in %ss: %s", error, delay, url)
                time.sleep(delay)
        raise RuntimeError(f"Unable to fetch {url}: {last_error}")

    def text(self, url: str) -> str:
        with self.request(url) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")

    def json(self, url: str) -> dict:
        return json.loads(self.text(url))


def infer_year(name: str, source_url: str = "") -> int:
    path_match = re.search(r"/digitaledition/(20\d{2})/", source_url)
    if path_match:
        return int(path_match.group(1))
    long_match = re.fullmatch(r"DB(20\d{2})\d{2}", name)
    if long_match:
        return int(long_match.group(1))
    underscore_match = re.match(r"DB(\d{2})_", name)
    if underscore_match:
        return 2000 + int(underscore_match.group(1))
    short_match = re.fullmatch(r"DB(\d{2})(\d{2})[a-z]?", name)
    if short_match:
        first, second = map(int, short_match.groups())
        if first <= 12 and second in (8, 9):
            return 2000 + second
        return 2000 + first
    raise ValueError(f"Cannot infer year from issue name: {name}")


def _absolute(url: str) -> str:
    return urljoin(ARCHIVE_URL, html.unescape(url)).replace("http://", "https://", 1)


def parse_archive(page: str) -> list[Issue]:
    issues: dict[str, Issue] = {}
    viewer_by_name: dict[str, str] = {}

    for cell in re.findall(r"<td\b.*?</td>", page, flags=re.I | re.S):
        cover = re.search(r"magazinecovers/(20\d{2})/(DB[^\"']+)\.(?:jpg|jpeg|png|gif)", cell, re.I)
        viewer = re.search(r"href=[\"'](https?://archive\.maherpublications\.com/view/[^\"']+)", cell, re.I)
        if cover and viewer:
            viewer_by_name[cover.group(2)] = html.unescape(viewer.group(1))

    hrefs = re.findall(r"href\s*=\s*[\"']([^\"']+)[\"']", page, flags=re.I)
    for href in hrefs:
        clean = html.unescape(href).strip()
        if re.search(r"\.pdf(?:[?#].*)?$", clean, re.I):
            url = _absolute(clean)
            name = Path(urlparse(url).path).stem
            issues[name] = Issue(
                name=name,
                year=infer_year(name, url),
                source_url=url,
                fallback_viewer_url=viewer_by_name.get(name),
            )

    for href in hrefs:
        clean = html.unescape(href).strip()
        if not re.search(r"/default\.html(?:[?#].*)?$", clean, re.I):
            continue
        url = _absolute(clean)
        name = Path(urlparse(url).path).parent.name
        if not name.startswith("DB") or name in issues:
            continue
        try:
            year = infer_year(name)
        except ValueError:
            continue
        path_year = re.search(r"/digitaledition/(20\d{2})/", url)
        if path_year and int(path_year.group(1)) != year:
            LOG.debug("Ignoring mismatched archive link: %s", url)
            continue
        issues[name] = Issue(name=name, year=year, source_url=url, source_kind="legacy")

    # A future issue may be viewer-only, without a working legacy PDF link.
    for name, viewer_url in viewer_by_name.items():
        if name not in issues:
            issues[name] = Issue(
                name=name,
                year=infer_year(name),
                source_url=viewer_url,
                source_kind="viewer",
            )
        elif not issues[name].fallback_viewer_url:
            issues[name].fallback_viewer_url = viewer_url

    return sorted(issues.values(), key=lambda item: (item.year, item.name))


def resolve_legacy_pdf(issue: Issue, fetcher: Fetcher) -> str:
    page = fetcher.text(issue.source_url)
    match = re.search(r"href\s*=\s*[\"']([^\"']+\.pdf(?:[?#][^\"']*)?)[\"']", page, re.I)
    if not match:
        raise RuntimeError(f"No PDF download link found in {issue.source_url}")
    return urljoin(issue.source_url, html.unescape(match.group(1))).replace("http://", "https://", 1)


def _extract_field(page: str, field: str) -> str:
    match = re.search(rf"\b{re.escape(field)}:\s*'([^']+)'", page)
    if not match:
        raise RuntimeError(f"Viewer field not found: {field}")
    return html.unescape(match.group(1))


def _signed_url(url: str, policies: list[dict]) -> str:
    match_value = re.sub(r"^https?", "", url)
    for policy in policies:
        if match_value.startswith(policy["PathPrefix"]):
            separator = "&" if "?" in url else "?"
            return (
                f"{url}{separator}Policy={policy['Policy']}"
                f"&Signature={policy['Signature']}&Key-Pair-Id={policy['KeyId']}"
            )
    return url


def resolve_viewer_pdf(viewer_url: str, fetcher: Fetcher) -> tuple[str, int | None]:
    page = fetcher.text(viewer_url)
    policies_match = re.search(r"var\s+initialPolicies\s*=\s*(\[.*?\]);", page, re.S)
    if not policies_match:
        raise RuntimeError(f"Viewer access policies not found: {viewer_url}")
    policies = json.loads(policies_match.group(1))
    content_root = _extract_field(page, "ContentRoot")
    private_root = _extract_field(page, "PrivateContentRoot")
    workspace_url = _signed_url(urljoin(content_root, "html/workspace.json"), policies)
    workspace = fetcher.json(workspace_url)
    downloads = workspace.get("downloads") or {}
    if not downloads.get("enabled") or not downloads.get("url"):
        raise RuntimeError(f"PDF download is disabled: {viewer_url}")
    download_url = urljoin(private_root, f"common/downloads/{downloads['url']}")
    return _signed_url(download_url, policies), downloads.get("size")


def is_valid_pdf(path: Path, expected_size: int | None = None) -> bool:
    try:
        size = path.stat().st_size
        if size < 1024 or (expected_size is not None and size != expected_size):
            return False
        with path.open("rb") as handle:
            return handle.read(5) == b"%PDF-"
    except OSError:
        return False


def download_pdf(url: str, destination: Path, fetcher: Fetcher, expected_size: int | None = None) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    headers: dict[str, str] = {}
    existing = partial.stat().st_size if partial.exists() else 0
    if existing:
        headers["Range"] = f"bytes={existing}-"

    with fetcher.request(url, headers=headers) as response:
        resumed = existing > 0 and getattr(response, "status", None) == 206
        mode = "ab" if resumed else "wb"
        if existing and not resumed:
            LOG.info("Server did not resume %s; restarting it", destination.name)
        with partial.open(mode) as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)

    if not is_valid_pdf(partial, expected_size):
        raise RuntimeError(f"Downloaded file failed PDF validation: {destination.name}")
    os.replace(partial, destination)


def sync_archive(
    output: Path,
    *,
    archive_url: str = ARCHIVE_URL,
    fetcher: Fetcher | None = None,
    progress: Callable[[str], None] = print,
) -> tuple[int, int, int]:
    fetcher = fetcher or Fetcher()
    output = output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    page = fetcher.text(archive_url)
    issues = parse_archive(page)
    downloaded = skipped = failed = 0
    progress(f"Found {len(issues)} issues in the archive")

    for issue in issues:
        destination = output / str(issue.year) / issue.filename
        if is_valid_pdf(destination):
            skipped += 1
            progress(f"SKIP {issue.year}/{issue.filename}")
            continue

        try:
            expected_size = None
            if issue.source_kind == "legacy":
                url = resolve_legacy_pdf(issue, fetcher)
            elif issue.source_kind == "viewer":
                url, expected_size = resolve_viewer_pdf(issue.source_url, fetcher)
            else:
                url = issue.source_url
            progress(f"GET  {issue.year}/{issue.filename}")
            try:
                download_pdf(url, destination, fetcher, expected_size)
            except HTTPError as error:
                if not issue.fallback_viewer_url or error.code not in (403, 404):
                    raise
                progress(f"FALLBACK viewer for {issue.year}/{issue.filename}")
                url, expected_size = resolve_viewer_pdf(issue.fallback_viewer_url, fetcher)
                download_pdf(url, destination, fetcher, expected_size)
            downloaded += 1
        except Exception as error:  # Continue so one broken issue does not stop monthly sync.
            failed += 1
            LOG.error("FAILED %s/%s: %s", issue.year, issue.filename, error)

    return downloaded, skipped, failed
