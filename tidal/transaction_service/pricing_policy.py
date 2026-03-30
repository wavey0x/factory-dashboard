"""Pricing configuration loading and resolution."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml

from tidal.normalizers import normalize_address


@dataclass(frozen=True, slots=True)
class PricingProfile:
    name: str
    start_price_buffer_bps: int
    min_price_buffer_bps: int
    step_decay_rate_bps: int


@dataclass(frozen=True, slots=True)
class PricingPolicy:
    default_profile_name: str
    profiles: dict[str, PricingProfile]
    auction_profile_overrides: dict[tuple[str, str], str]

    def resolve(self, auction_address: str, sell_token: str) -> PricingProfile:
        auction_key = normalize_address(auction_address)
        sell_token_key = normalize_address(sell_token)
        profile_name = self.auction_profile_overrides.get(
            (auction_key, sell_token_key),
            self.default_profile_name,
        )
        return self.profiles[profile_name]


@dataclass(frozen=True, slots=True)
class TokenSizingPolicy:
    token_overrides: dict[str, Decimal]

    def resolve(self, token_address: str) -> Decimal | None:
        return self.token_overrides.get(normalize_address(token_address))


@dataclass(frozen=True, slots=True)
class PricingConfig:
    pricing_policy: PricingPolicy
    token_sizing_policy: TokenSizingPolicy


def _coerce_bps(value: object, *, field_name: str, profile_name: str) -> int:
    try:
        output = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{profile_name}.{field_name} must be an integer") from exc
    if output < 0:
        raise ValueError(f"{profile_name}.{field_name} must be non-negative")
    return output


def _coerce_positive_decimal(value: object, *, field_name: str, scope_name: str) -> Decimal:
    try:
        output = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{scope_name}.{field_name} must be a number") from exc
    if output <= 0:
        raise ValueError(f"{scope_name}.{field_name} must be greater than zero")
    return output


def _load_raw_pricing(pricing_path: Path) -> dict[str, object]:
    with pricing_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Pricing file must contain a mapping object: {pricing_path}")
    return raw


def _build_pricing_policy(raw: dict[str, object]) -> PricingPolicy:
    default_profile_name = str(raw.get("default_profile") or "").strip()
    if not default_profile_name:
        raise ValueError("pricing file must define default_profile")

    raw_profiles = raw.get("profiles")
    if not isinstance(raw_profiles, dict) or not raw_profiles:
        raise ValueError("pricing file must define profiles")

    profiles: dict[str, PricingProfile] = {}
    for profile_name, profile_raw in raw_profiles.items():
        if not isinstance(profile_raw, dict):
            raise ValueError(f"profile {profile_name} must be a mapping")
        profile_key = str(profile_name).strip()
        if not profile_key:
            raise ValueError("profile names must be non-empty")
        profiles[profile_key] = PricingProfile(
            name=profile_key,
            start_price_buffer_bps=_coerce_bps(
                profile_raw.get("start_price_buffer_bps"),
                field_name="start_price_buffer_bps",
                profile_name=profile_key,
            ),
            min_price_buffer_bps=_coerce_bps(
                profile_raw.get("min_price_buffer_bps"),
                field_name="min_price_buffer_bps",
                profile_name=profile_key,
            ),
            step_decay_rate_bps=_coerce_bps(
                profile_raw.get("step_decay_rate_bps"),
                field_name="step_decay_rate_bps",
                profile_name=profile_key,
            ),
        )

    if default_profile_name not in profiles:
        raise ValueError(f"default profile {default_profile_name!r} is not defined")

    raw_auctions = raw.get("auctions") or {}
    if not isinstance(raw_auctions, dict):
        raise ValueError("auctions must be a mapping")

    overrides: dict[tuple[str, str], str] = {}
    for auction_address, raw_sell_tokens in raw_auctions.items():
        if not isinstance(raw_sell_tokens, dict):
            raise ValueError(f"auction override for {auction_address} must be a mapping")
        normalized_auction = normalize_address(str(auction_address))
        for sell_token, profile_name in raw_sell_tokens.items():
            profile_key = str(profile_name).strip()
            if profile_key not in profiles:
                raise ValueError(f"profile {profile_key!r} is not defined")
            overrides[(normalized_auction, normalize_address(str(sell_token)))] = profile_key

    return PricingPolicy(
        default_profile_name=default_profile_name,
        profiles=profiles,
        auction_profile_overrides=overrides,
    )


def _build_token_sizing_policy(raw: dict[str, object]) -> TokenSizingPolicy:
    raw_limits = raw.get("usd_kick_limit") or {}
    if not isinstance(raw_limits, dict):
        raise ValueError("usd_kick_limit must be a mapping")

    token_overrides: dict[str, Decimal] = {}
    for token_address, raw_limit in raw_limits.items():
        token_overrides[normalize_address(str(token_address))] = _coerce_positive_decimal(
            raw_limit,
            field_name="value",
            scope_name=f"usd_kick_limit[{token_address}]",
        )

    return TokenSizingPolicy(token_overrides=token_overrides)


def load_pricing(pricing_path: Path | None = None) -> PricingConfig:
    if pricing_path is None:
        raise ValueError("pricing_path is required")
    resolved_path = Path(pricing_path).expanduser().resolve()
    raw = _load_raw_pricing(resolved_path)
    return PricingConfig(
        pricing_policy=_build_pricing_policy(raw),
        token_sizing_policy=_build_token_sizing_policy(raw),
    )
