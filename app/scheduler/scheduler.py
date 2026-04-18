"""Sync orchestrator — runs the full pipeline every N hours.

Pipeline per ТЗ + доработки v2:
1. Load JK synonym dictionary from DB
2. For each active source:
   a. Pre-flight check (DNS, HTTP, timeout, size, XML validity)
   b. Fetch content — on error use cached file (if available)
   c. Save raw content to cache after successful fetch
   d. Parse with appropriate parser
   e. Normalize (with JK synonym lookup)
   f. Identify (assign/confirm ExternalId)
   g. Handle anomalous volume changes (drop protection)
   h. Mark missing objects (3-miss rule)
3. Generate unified XML feed
4. Send Telegram summary
"""

from __future__ import annotations

import logging
import os
import socket
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
import chardet
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from lxml import etree
from sqlalchemy import select

from app.config import settings
from app.database import async_session
from app.models.source import Source
from app.models.sync_log import SyncLog
from app.models.jk_synonym import JkSynonym
from app.parsers import get_parser
from app.normalizer import normalize_object
from app.identifier import IdentificationEngine
from app.generator import FeedGenerator
from app.monitoring import TelegramNotifier

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


# ─────────────────────────────────────────────────────────────────────────────
# Pre-flight diagnostics
# ─────────────────────────────────────────────────────────────────────────────

class PreflightResult:
    """Holds result of all pre-flight checks for a source."""

    def __init__(self):
        self.checks: dict[str, dict] = {}
        self.passed = True

    def add(self, name: str, ok: bool, detail: str = ""):
        self.checks[name] = {"ok": ok, "detail": detail}
        if not ok:
            self.passed = False

    def to_dict(self) -> dict:
        return {"passed": self.passed, "checks": self.checks}


async def run_preflight(source: Source) -> PreflightResult:
    """Execute 5 pre-flight checks before synchronisation.

    Checks (all must pass):
    1. DNS resolution
    2. HTTP 200 response
    3. Response time < preflight_timeout_s
    4. Content not empty
    5. Valid XML root tag
    """
    result = PreflightResult()

    if not source.url:
        result.add("url_set", False, "Source has no URL configured")
        return result

    result.add("url_set", True)

    # 1. DNS resolve
    try:
        from urllib.parse import urlparse
        host = urlparse(source.url).hostname or ""
        socket.getaddrinfo(host, None)
        result.add("dns", True, f"Resolved: {host}")
    except OSError as e:
        result.add("dns", False, f"DNS error: {e}")
        return result   # Cannot proceed without DNS

    # 2 & 3. HTTP response + timing
    start = time.time()
    content: Optional[bytes] = None
    try:
        async with httpx.AsyncClient(
            timeout=settings.preflight_timeout_s,
            follow_redirects=True,
        ) as client:
            resp = await client.get(source.url)
            elapsed_ms = int((time.time() - start) * 1000)

            if resp.status_code == 200:
                result.add("http_status", True, f"HTTP {resp.status_code}")
            else:
                result.add("http_status", False, f"HTTP {resp.status_code}")
                return result

            if elapsed_ms <= settings.preflight_timeout_s * 1000:
                result.add("response_time", True, f"{elapsed_ms} ms")
            else:
                result.add("response_time", False, f"{elapsed_ms} ms (too slow)")

            content = resp.content

    except httpx.TimeoutException:
        elapsed_ms = int((time.time() - start) * 1000)
        result.add("http_status", False, f"Timeout after {elapsed_ms} ms")
        result.add("response_time", False, "Timed out")
        return result
    except Exception as e:
        result.add("http_status", False, str(e))
        return result

    # 4. Content not empty
    if content and len(content) > 0:
        result.add("not_empty", True, f"{len(content):,} bytes")
    else:
        result.add("not_empty", False, "Empty response body")
        return result

    # 5. Valid XML (root tag parseable)
    try:
        root = etree.fromstring(content)  # Validate full content
        result.add("xml_valid", True, f"Root: <{root.tag}>")
    except etree.XMLSyntaxError as e:
        # Try with recovery parser (some feeds have minor XML issues)
        try:
            recover_parser = etree.XMLParser(recover=True)
            root = etree.fromstring(content, parser=recover_parser)
            if root is not None and len(root) > 0:
                result.add("xml_valid", True, f"Root: <{root.tag}> (recovered)")
            else:
                raise etree.XMLSyntaxError("Recovery produced empty tree", None, None, None)
        except Exception:
            # Not necessarily fatal — could be Excel/CSV
            if source.type in ("excel", "csv"):
                result.add("xml_valid", True, "Non-XML format (Excel/CSV)")
            else:
                result.add("xml_valid", False, f"XML error: {str(e)[:120]}")

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Feed cache helpers
# ─────────────────────────────────────────────────────────────────────────────

def _cache_dir_for(source_id: int) -> Path:
    base = Path(settings.feed_cache_dir)
    d = base / f"source_{source_id}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save_to_cache(source_id: int, content: bytes) -> str:
    """Atomically save content to cache, return path."""
    cache_dir = _cache_dir_for(source_id)
    target = cache_dir / "latest.xml"

    # Atomic write: temp → rename
    fd, tmp_path = tempfile.mkstemp(dir=cache_dir, prefix=".tmp_", suffix=".xml")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
        os.replace(tmp_path, target)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    logger.debug(f"[Cache] Source {source_id}: saved {len(content):,} bytes → {target}")
    return str(target)


def _load_from_cache(source: Source) -> Optional[bytes]:
    """Load the last cached feed for a source, if it exists."""
    if not source.cache_last_path:
        return None
    path = Path(source.cache_last_path)
    if path.exists():
        logger.info(
            f"[Cache] Source {source.name}: using cached feed from "
            f"{source.cache_last_success_at} ({path})"
        )
        return path.read_bytes()
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Main orchestrator
# ─────────────────────────────────────────────────────────────────────────────

class SyncOrchestrator:
    """Runs the full synchronization pipeline."""

    def __init__(self):
        # JK synonym dict loaded at start of each sync cycle
        # Format: {raw_name_lower: canonical_name}
        self._jk_synonyms: dict[str, str] = {}

    async def run_full_sync(self):
        """Execute complete sync cycle for all active sources."""
        logger.info("=" * 60)
        logger.info("Starting full synchronization cycle")
        logger.info("=" * 60)

        async with async_session() as session:
            notifier = TelegramNotifier(session)

            # Load JK synonyms from DB once per cycle
            await self._load_jk_synonyms(session)

            # Create global sync log
            global_log = SyncLog(status="running")
            session.add(global_log)
            await session.flush()

            # Get all active sources
            stmt = select(Source).where(Source.is_active == True)
            result = await session.execute(stmt)
            sources = list(result.scalars().all())

            total_new = total_updated = total_removed = total_objects = total_errors = 0
            any_critical = False

            for source in sources:
                try:
                    stats = await self._sync_source(session, source, notifier)
                    total_new      += stats["new"]
                    total_updated  += stats["updated"]
                    total_removed  += stats["removed"]
                    total_objects  += stats["total"]
                    total_errors   += stats["errors"]
                except Exception as e:
                    total_errors += 1
                    logger.error(
                        f"Critical error syncing source {source.name}: {e}", exc_info=True
                    )
                    source.consecutive_failures = (source.consecutive_failures or 0) + 1
                    source.status = "error"
                    if source.consecutive_failures >= settings.threshold_source_fail_count:
                        await notifier.notify_source_unavailable(
                            source.name, source.url or "", str(e)
                        )
                        any_critical = True

            # Generate feed
            try:
                generator = FeedGenerator(session)
                feed_path = await generator.generate()
                logger.info(f"Feed generated at: {feed_path}")
            except Exception as e:
                logger.error(f"Feed generation failed: {e}", exc_info=True)
                await notifier.notify_feed_generation_error(str(e))
                any_critical = True

            # Update global sync log
            global_log.finished_at    = datetime.now(timezone.utc)
            global_log.objects_total  = total_objects
            global_log.objects_new    = total_new
            global_log.objects_updated = total_updated
            global_log.objects_removed = total_removed
            global_log.errors_count   = total_errors
            global_log.status = (
                "fail" if any_critical else
                ("partial" if total_errors > 0 else "success")
            )

            await notifier.notify_sync_complete(
                len(sources), total_objects, total_new, total_updated, total_removed
            )
            await session.commit()

        logger.info("Synchronization cycle complete")

    async def _load_jk_synonyms(self, session) -> None:
        """Load all JK synonyms from DB into in-memory dict."""
        result = await session.execute(select(JkSynonym))
        synonyms = result.scalars().all()
        self._jk_synonyms = {s.raw_name.lower(): s.normalized_name for s in synonyms}
        logger.info(f"Loaded {len(self._jk_synonyms)} JK synonyms")

    async def _sync_source(
        self, session, source: Source, notifier: TelegramNotifier
    ) -> dict:
        """Sync a single source. Returns stats dict."""
        logger.info(f"--- Syncing source: {source.name} ({source.type}) ---")
        stats = {"new": 0, "updated": 0, "removed": 0, "total": 0, "errors": 0}

        source_log = SyncLog(source_id=source.id, status="running")
        session.add(source_log)
        await session.flush()

        start_time = time.time()

        # ── Step 1: Pre-flight check ─────────────────────────────────────────
        preflight = await run_preflight(source)
        elapsed_ms = int((time.time() - start_time) * 1000)
        source_log.response_time_ms = elapsed_ms

        if not preflight.passed:
            failed = [k for k, v in preflight.checks.items() if not v["ok"]]
            logger.warning(
                f"Pre-flight FAILED for {source.name}: {failed}"
            )
            source.status = "error"

            # Try to use cached feed
            content = _load_from_cache(source)
            if content:
                source.status = "warning"
                logger.info(f"Using cached feed for {source.name}")
                source_log.details = (
                    f"Pre-flight failed ({failed}), using cached data from "
                    f"{source.cache_last_success_at}"
                )
            else:
                source.consecutive_failures = (source.consecutive_failures or 0) + 1
                await notifier.notify_source_unavailable(
                    source.name, source.url or "",
                    f"Pre-flight failed: {failed}. No cache available."
                )
                source_log.status = "fail"
                source_log.finished_at = datetime.now(timezone.utc)
                stats["errors"] = 1
                return stats
        else:
            source.status = "ok"
            logger.info(f"Pre-flight OK for {source.name}")
            # Fetch fresh content
            content = await self._fetch_content(source)

        if content is None:
            source.status = "error"
            source_log.status = "fail"
            source_log.details = "Failed to fetch content (no content returned)"
            source_log.finished_at = datetime.now(timezone.utc)
            source.consecutive_failures = (source.consecutive_failures or 0) + 1
            stats["errors"] = 1
            return stats

        # ── Step 2: Save to cache (only on fresh successful fetch) ───────────
        if preflight.passed:
            try:
                cache_path = _save_to_cache(source.id, content)
                source.cache_last_path = cache_path
                source.cache_last_success_at = datetime.now(timezone.utc)
            except Exception as e:
                logger.warning(f"Failed to save cache for {source.name}: {e}")

        # ── Step 3: Parse ────────────────────────────────────────────────────
        parser_cls = get_parser(source.type)
        parser = parser_cls(self._source_to_dict(source))
        raw_objects = parser.parse(content)

        if parser.errors:
            stats["errors"] = len(parser.errors)
            if len(parser.errors) > 5:
                await notifier.notify_parse_errors(
                    source.name, len(parser.errors), parser.errors
                )

        # Check for empty result
        if not raw_objects:
            await notifier.notify_empty_source(source.name, source.last_object_count or 0)
            source_log.status = "fail"
            source_log.details = "Parser returned 0 objects"
            source_log.finished_at = datetime.now(timezone.utc)
            return stats

        # ── Step 4: Anomalous volume check (drop / spike protection) ─────────
        prev_count = source.last_object_count or 0
        if prev_count > 0:
            diff_pct = abs(len(raw_objects) - prev_count) / prev_count * 100
            if diff_pct >= settings.threshold_drop_critical:
                direction = "drop" if len(raw_objects) < prev_count else "spike"
                logger.warning(
                    f"Anomalous {direction} ({diff_pct:.0f}%) for {source.name} — "
                    f"keeping previous data"
                )
                source_log.status = "fail"
                source_log.details = (
                    f"Anomalous {direction}: {prev_count} → {len(raw_objects)} "
                    f"({diff_pct:.0f}%)"
                )
                source_log.finished_at = datetime.now(timezone.utc)
                return stats
            elif diff_pct >= settings.threshold_drop_warning:
                await notifier.notify_object_drop(
                    source.name, prev_count, len(raw_objects), diff_pct
                )

        # ── Step 5: Normalize + Identify ─────────────────────────────────────
        engine = IdentificationEngine(session)
        seen_ids: set[int] = set()
        price_changes = 0

        for raw in raw_objects:
            try:
                unified = normalize_object(
                    raw, source.id,
                    phone_override=source.phone_override,
                    jk_synonyms=self._jk_synonyms,
                )
                result = await engine.identify_and_upsert(unified)

                if result.object_id:
                    seen_ids.add(result.object_id)

                if result.action == "created":
                    stats["new"] += 1
                elif result.action in ("matched", "fuzzy_matched"):
                    if result.changes:
                        stats["updated"] += 1
                        for ch in result.changes:
                            if ch["field"] == "price":
                                try:
                                    old_p, new_p = int(ch["old"]), int(ch["new"])
                                    if old_p > 0:
                                        pct = abs(new_p - old_p) / old_p * 100
                                        if pct > settings.threshold_price_change_min:
                                            price_changes += 1
                                except (ValueError, ZeroDivisionError):
                                    pass

                    if result.action == "fuzzy_matched" and result.old_flat_number:
                        await notifier.notify_renumbering(
                            result.old_flat_number, unified.flat_number,
                            unified.jk_name, unified.floor, unified.total_area
                        )

            except Exception as e:
                stats["errors"] += 1
                logger.error(
                    f"Error processing object {raw.source_object_id}: {e}", exc_info=True
                )

        # ── Step 6: Handle missing objects (3-miss rule) ─────────────────────
        removed_ids = await engine.handle_missing_objects(source.id, seen_ids)
        stats["removed"] = len(removed_ids)

        # ── Step 7: Mass price change alert ──────────────────────────────────
        total_processed = len(raw_objects)
        if total_processed > 0 and price_changes > 0:
            pct = (price_changes / total_processed) * 100
            if pct >= settings.threshold_price_change_pct:
                await notifier.notify_mass_price_change(source.name, price_changes, pct)

        stats["total"] = len(raw_objects)

        # ── Update source state ───────────────────────────────────────────────
        source.last_sync_at = datetime.now(timezone.utc)
        source.last_object_count = len(raw_objects)
        source.consecutive_failures = 0

        source_log.finished_at     = datetime.now(timezone.utc)
        source_log.objects_total   = stats["total"]
        source_log.objects_new     = stats["new"]
        source_log.objects_updated = stats["updated"]
        source_log.objects_removed = stats["removed"]
        source_log.errors_count    = stats["errors"]
        source_log.status = "success" if stats["errors"] == 0 else "partial"

        await session.flush()
        logger.info(f"Source {source.name}: {stats}")
        return stats

    async def _fetch_content(self, source: Source) -> Optional[bytes]:
        """Fetch feed content from URL, with encoding detection."""
        if not source.url:
            logger.error(f"Source {source.name} has no URL configured")
            return None

        try:
            async with httpx.AsyncClient(
                timeout=settings.http_timeout,
                follow_redirects=True,
            ) as client:
                resp = await client.get(source.url)
                resp.raise_for_status()
                content = resp.content

                # Auto-detect encoding and convert to UTF-8
                detected = chardet.detect(content[:10000])
                encoding = detected.get("encoding", "utf-8")
                if encoding and encoding.lower() not in ("utf-8", "ascii"):
                    try:
                        content = content.decode(encoding).encode("utf-8")
                    except (UnicodeDecodeError, LookupError):
                        pass

                return content

        except httpx.TimeoutException:
            logger.error(f"Timeout fetching {source.name}: {source.url}")
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching {source.name}: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching {source.name}: {e}")

        # On any fetch error — try cache as fallback
        cached = _load_from_cache(source)
        if cached:
            source.status = "warning"
        return cached

    @staticmethod
    def _source_to_dict(source: Source) -> dict:
        return {
            "name": source.name,
            "developer_name": source.developer_name,
            "type": source.type,
            "url": source.url,
            "mapping_config": source.mapping_config,
            "phone_override": source.phone_override,
        }


def start_scheduler():
    """Start APScheduler with the sync job."""
    orchestrator = SyncOrchestrator()
    scheduler.add_job(
        orchestrator.run_full_sync,
        "interval",
        hours=settings.sync_interval_hours,
        id="full_sync",
        name="Full feed synchronization",
        replace_existing=True,
        next_run_time=None,
    )
    scheduler.start()
    logger.info(f"Scheduler started: sync every {settings.sync_interval_hours} hours")
