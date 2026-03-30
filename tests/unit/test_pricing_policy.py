from decimal import Decimal

from tidal.transaction_service.pricing_policy import load_pricing


def test_load_pricing_reads_token_overrides(tmp_path):
    pricing_path = tmp_path / "pricing.yaml"
    pricing_path.write_text(
        """
default_profile: volatile

profiles:
  volatile:
    start_price_buffer_bps: 1000
    min_price_buffer_bps: 500
    step_decay_rate_bps: 50

usd_kick_limit:
  "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa": 5000
  "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb": 25000
""".strip()
        + "\n",
        encoding="utf-8",
    )

    pricing = load_pricing(pricing_path)

    rule_a = pricing.token_sizing_policy.resolve("0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
    rule_b = pricing.token_sizing_policy.resolve("0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
    rule_missing = pricing.token_sizing_policy.resolve("0xcccccccccccccccccccccccccccccccccccccccc")

    assert rule_a == Decimal("5000")
    assert rule_b == Decimal("25000")
    assert rule_missing is None
    assert pricing.pricing_policy.default_profile_name == "volatile"


def test_load_pricing_defaults_to_empty_token_overrides_when_absent(tmp_path):
    pricing_path = tmp_path / "pricing.yaml"
    pricing_path.write_text(
        """
default_profile: volatile

profiles:
  volatile:
    start_price_buffer_bps: 1000
    min_price_buffer_bps: 500
    step_decay_rate_bps: 50
""".strip()
        + "\n",
        encoding="utf-8",
    )

    pricing = load_pricing(pricing_path)

    assert pricing.token_sizing_policy.token_overrides == {}
