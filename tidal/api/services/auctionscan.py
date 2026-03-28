"""AuctionScan lookup and persistence service."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from tidal.api.errors import APIError
from tidal.config import Settings
from tidal.read.kick_logs import KickLogReadService
from tidal.time import utcnow_iso


class AuctionScanService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.kick_logs = KickLogReadService(
            session,
            chain_id=settings.chain_id,
            auctionscan_base_url=settings.auctionscan_base_url,
        )

    async def resolve_kick_auctionscan(self, kick_id: int) -> dict[str, object]:
        try:
            kick = self.kick_logs.load_kick_auctionscan_context(kick_id)
        except ValueError as exc:
            raise APIError(str(exc), status_code=404) from exc

        if kick["auctionscan_round_id"] is not None:
            return self.kick_logs.build_auctionscan_response(kick, resolved=True, cached=True)
        if not kick["eligible"]:
            return self.kick_logs.build_auctionscan_response(kick, resolved=False, cached=False)
        if self._should_skip_recheck(kick["auctionscan_last_checked_at"]):
            return self.kick_logs.build_auctionscan_response(kick, resolved=False, cached=False)

        round_payload = await self._lookup_round(
            auction_address=str(kick["auction_address"]),
            from_token=str(kick["token_address"]),
            transaction_hash=str(kick["tx_hash"]),
        )
        checked_at = utcnow_iso()
        if round_payload and round_payload.get("round_id") is not None:
            round_id = int(round_payload["round_id"])
            self.kick_logs.persist_auctionscan_match(
                kick_id,
                round_id=round_id,
                checked_at=checked_at,
                matched_at=checked_at,
            )
            kick["auctionscan_round_id"] = round_id
            kick["auctionscan_last_checked_at"] = checked_at
            kick["auctionscan_matched_at"] = checked_at
            return self.kick_logs.build_auctionscan_response(kick, resolved=True, cached=False)

        self.kick_logs.persist_auctionscan_check(kick_id, checked_at=checked_at)
        kick["auctionscan_last_checked_at"] = checked_at
        return self.kick_logs.build_auctionscan_response(kick, resolved=False, cached=False)

    async def _lookup_round(self, *, auction_address: str, from_token: str, transaction_hash: str) -> dict[str, object] | None:
        params = {
            "chain_id": self.settings.chain_id,
            "from_token": from_token,
            "transaction_hash": transaction_hash,
        }
        request_url = (
            f"{self.settings.auctionscan_api_base_url.rstrip('/')}/auctions/"
            f"{auction_address}/rounds?{urlencode(params)}"
        )
        try:
            async with httpx.AsyncClient(timeout=self.settings.price_timeout_seconds) as client:
                response = await client.get(request_url, headers={"Accept": "application/json"})
        except httpx.HTTPError as exc:
            raise APIError(f"AuctionScan request failed: {exc}") from exc

        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise APIError(f"AuctionScan request failed with HTTP {response.status_code}", status_code=502)

        payload = response.json()
        if not isinstance(payload, dict):
            return None
        rounds = payload.get("rounds")
        if not isinstance(rounds, list) or not rounds:
            return None
        first = rounds[0]
        return first if isinstance(first, dict) else None

    def _should_skip_recheck(self, last_checked_at: object) -> bool:
        if not last_checked_at or self.settings.auctionscan_recheck_seconds <= 0:
            return False
        try:
            checked_at = datetime.fromisoformat(str(last_checked_at).replace("Z", "+00:00"))
        except ValueError:
            return False
        delta = datetime.now(timezone.utc) - checked_at
        return delta.total_seconds() < self.settings.auctionscan_recheck_seconds

