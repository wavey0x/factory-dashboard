from decimal import Decimal

import pytest

from factory_dashboard.constants import CVX_ADDRESS, CVX_PRICE_ALIAS_ADDRESS, CVX_WRAPPER_ALIAS_ADDRESS
from factory_dashboard.pricing.service import PriceToken, TokenPriceRefreshService
from factory_dashboard.pricing.token_price_agg import TokenPriceQuote


class FakePriceProvider:
    source_name = "token_price_agg_usd_price"

    def __init__(self, prices: dict[str, Decimal | None], logo_urls: dict[str, str | None] | None = None):
        self.prices = prices
        self.logo_urls = logo_urls or {}
        self.calls: list[tuple[str, int]] = []

    async def quote_usd(self, token_address: str, token_decimals: int) -> TokenPriceQuote:
        self.calls.append((token_address, token_decimals))
        return TokenPriceQuote(
            price_usd=self.prices[token_address],
            quote_amount_in_raw=1,
            logo_url=self.logo_urls.get(token_address),
        )


class FakeTokenRepository:
    def __init__(self) -> None:
        self.updates: list[dict[str, str | None]] = []
        self.logo_updates: list[dict[str, str | None]] = []

    def set_latest_price(
        self,
        *,
        address: str,
        price_usd: str | None,
        source: str,
        status: str,
        fetched_at: str,
        run_id: str,
        error_message: str | None,
    ) -> None:
        self.updates.append(
            {
                "address": address,
                "price_usd": price_usd,
                "source": source,
                "status": status,
                "fetched_at": fetched_at,
                "run_id": run_id,
                "error_message": error_message,
            }
        )

    def set_logo_url(self, *, address: str, logo_url: str | None) -> None:
        self.logo_updates.append(
            {
                "address": address,
                "logo_url": logo_url,
            }
        )


@pytest.mark.asyncio
async def test_price_alias_uses_cvx_quote_for_alias_token_and_persists_logo() -> None:
    repo = FakeTokenRepository()
    provider = FakePriceProvider(
        prices={
            CVX_ADDRESS: Decimal("3.25"),
        },
        logo_urls={
            CVX_ADDRESS: "https://cdn.example/cvx.png",
        },
    )
    service = TokenPriceRefreshService(
        chain_id=1,
        enabled=True,
        concurrency=2,
        price_provider=provider,
        token_repository=repo,
    )

    stats, errors = await service.refresh_many(
        run_id="run-1",
        tokens=[
            PriceToken(address=CVX_PRICE_ALIAS_ADDRESS, decimals=18),
            PriceToken(address=CVX_WRAPPER_ALIAS_ADDRESS, decimals=18),
            PriceToken(address=CVX_ADDRESS, decimals=18),
        ],
    )

    assert errors == []
    assert stats["tokens_seen"] == 3
    assert stats["tokens_succeeded"] == 3
    assert provider.calls == [(CVX_ADDRESS, 18)]

    updates_by_address = {item["address"]: item for item in repo.updates}
    assert updates_by_address[CVX_ADDRESS]["price_usd"] == "3.25"
    assert updates_by_address[CVX_PRICE_ALIAS_ADDRESS]["price_usd"] == "3.25"
    assert updates_by_address[CVX_WRAPPER_ALIAS_ADDRESS]["price_usd"] == "3.25"

    logo_updates_by_address = {item["address"]: item for item in repo.logo_updates}
    assert logo_updates_by_address[CVX_ADDRESS]["logo_url"] == "https://cdn.example/cvx.png"
    assert logo_updates_by_address[CVX_PRICE_ALIAS_ADDRESS]["logo_url"] == "https://cdn.example/cvx.png"
    assert logo_updates_by_address[CVX_WRAPPER_ALIAS_ADDRESS]["logo_url"] == "https://cdn.example/cvx.png"


@pytest.mark.asyncio
async def test_price_refresh_always_updates_logo_url() -> None:
    """Logo URL from price API is always written, even if it changes."""
    token_address = "0x4e3fbd56cd56c3e72c1403e103b45db9da5b9d2b"
    repo = FakeTokenRepository()
    provider = FakePriceProvider(
        prices={token_address: Decimal("4.2")},
        logo_urls={token_address: "https://cdn.example/new-logo.png"},
    )
    service = TokenPriceRefreshService(
        chain_id=1,
        enabled=True,
        concurrency=1,
        price_provider=provider,
        token_repository=repo,
    )

    stats, errors = await service.refresh_many(
        run_id="run-1",
        tokens=[PriceToken(address=token_address, decimals=18)],
    )

    assert errors == []
    assert stats["tokens_succeeded"] == 1
    assert repo.logo_updates == [{"address": token_address, "logo_url": "https://cdn.example/new-logo.png"}]


@pytest.mark.asyncio
async def test_price_refresh_writes_null_logo_when_api_returns_none() -> None:
    token_address = "0x4e3fbd56cd56c3e72c1403e103b45db9da5b9d2b"
    repo = FakeTokenRepository()
    provider = FakePriceProvider(
        prices={token_address: None},
        logo_urls={token_address: None},
    )
    service = TokenPriceRefreshService(
        chain_id=1,
        enabled=True,
        concurrency=1,
        price_provider=provider,
        token_repository=repo,
    )

    stats, errors = await service.refresh_many(
        run_id="run-1",
        tokens=[PriceToken(address=token_address, decimals=18)],
    )

    assert errors == []
    assert stats["tokens_not_found"] == 1
    assert repo.logo_updates == [{"address": token_address, "logo_url": None}]
