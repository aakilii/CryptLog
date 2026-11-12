from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import dataclass
from typing import Set

import duckdb

from .storage import remove_lineage_s3, select_live_rows, tombstone_lineage


@dataclass
class JanitorFlags:
    notified_20: Set[str]
    notified_10: Set[str]
    notified_0: Set[str]


def _now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


async def run_janitor_loop(con: duckdb.DuckDBPyConnection, flags: JanitorFlags, tick_seconds: float = 1.0) -> None:
    while True:
        await asyncio.sleep(tick_seconds)
        now = _now_utc()
        rows = select_live_rows(con)

        for lineage, created_at, ttl_seconds, is_locked in rows:
            if created_at is None:
                continue
            if isinstance(created_at, str):
                continue

            diff = (now - created_at).total_seconds()
            left = int((ttl_seconds or 0) - diff)

            if 10 < left <= 20 and lineage not in flags.notified_20:
                flags.notified_20.add(lineage)

            if 0 < left <= 10 and lineage not in flags.notified_10:
                flags.notified_10.add(lineage)

            if left <= 0 and lineage not in flags.notified_0:
                flags.notified_0.add(lineage)
                if bool(is_locked):
                    tombstone_lineage(con, str(lineage))
                else:
                    remove_lineage_s3(str(lineage))
