from tidal.transaction_service.types import (
    KickCandidate,
    KickPlan,
    KickRecoveryPlan,
    PreparedKick,
    PreparedSweepAndSettle,
    SkippedPreparedCandidate,
    TxIntent,
)


def _candidate(*, token_address: str, token_symbol: str = "CRV") -> KickCandidate:
    return KickCandidate(
        source_type="strategy",
        source_address="0x1111111111111111111111111111111111111111",
        token_address=token_address,
        auction_address="0x3333333333333333333333333333333333333333",
        normalized_balance="1000",
        price_usd="2.5",
        want_address="0x4444444444444444444444444444444444444444",
        usd_value=2500.0,
        decimals=18,
        source_name="Test Strategy",
        token_symbol=token_symbol,
        want_symbol="USDC",
    )


def _prepared_kick(candidate: KickCandidate) -> PreparedKick:
    return PreparedKick(
        candidate=candidate,
        sell_amount=10**21,
        starting_price_unscaled=2750,
        minimum_price_scaled_1e18=2_375_000_000_000_000_000,
        minimum_quote_unscaled=2375,
        sell_amount_str="1000",
        starting_price_unscaled_str="2750",
        minimum_price_scaled_1e18_str="2375000000000000000",
        minimum_quote_unscaled_str="2375",
        usd_value_str="2500",
        live_balance_raw=10**21,
        normalized_balance="1000",
        quote_amount_str="2500",
        start_price_buffer_bps=1000,
        min_price_buffer_bps=50,
        step_decay_rate_bps=50,
        pricing_profile_name="stable",
        recovery_plan=KickRecoveryPlan(
            settle_after_start=("0x5555555555555555555555555555555555555555",),
        ),
    )


def test_tx_intent_round_trips_payload() -> None:
    intent = TxIntent(
        operation="kick",
        to="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        data="0xdeadbeef",
        value="0x0",
        chain_id=1,
        sender="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        gas_estimate=210000,
        gas_limit=252000,
    )

    payload = intent.to_payload()

    assert payload == {
        "operation": "kick",
        "to": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "data": "0xdeadbeef",
        "value": "0x0",
        "chainId": 1,
        "sender": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "gasEstimate": 210000,
        "gasLimit": 252000,
    }
    assert TxIntent.from_payload(payload) == intent


def test_kick_plan_serializes_preview_and_transactions() -> None:
    kick_candidate = _candidate(token_address="0x2222222222222222222222222222222222222222")
    skipped_candidate = _candidate(
        token_address="0x6666666666666666666666666666666666666666",
        token_symbol="YFI",
    )
    prepared_kick = _prepared_kick(kick_candidate)
    prepared_sweep = PreparedSweepAndSettle(
        candidate=kick_candidate,
        sell_token=kick_candidate.token_address,
        minimum_price_scaled_1e18=2_375_000_000_000_000_000,
        minimum_price_public_raw=2375,
        available_raw=10**21,
        sell_amount_str="1000",
        minimum_price_scaled_1e18_str="2375000000000000000",
        minimum_price_public_str="2375",
        usd_value_str="2500",
        normalized_balance="1000",
        stuck_abort_reason="forced sweep requested",
        token_symbol="CRV",
    )
    sweep_intent = TxIntent(
        operation="sweep-and-settle",
        to="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        data="0xaaaa",
        value="0x0",
        chain_id=1,
        sender="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        gas_estimate=180000,
        gas_limit=216000,
    )
    kick_intent = TxIntent(
        operation="kick",
        to="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        data="0xbbbb",
        value="0x0",
        chain_id=1,
        sender="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        gas_estimate=210000,
        gas_limit=252000,
    )
    plan = KickPlan(
        source_type="strategy",
        source_address=kick_candidate.source_address,
        auction_address=kick_candidate.auction_address,
        token_address=None,
        limit=2,
        eligible_count=4,
        selected_count=3,
        ready_count=2,
        ignored_skips=[
            {
                "sourceAddress": "0x7777777777777777777777777777777777777777",
                "auctionAddress": kick_candidate.auction_address,
                "tokenAddress": "0x8888888888888888888888888888888888888888",
                "tokenSymbol": "CVX",
                "detail": "ignored source",
            }
        ],
        cooldown_skips=[
            {
                "sourceAddress": "0x9999999999999999999999999999999999999999",
                "auctionAddress": kick_candidate.auction_address,
                "tokenAddress": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "tokenSymbol": "BAL",
                "detail": "cooldown active",
            }
        ],
        deferred_same_auction_count=1,
        limited_count=1,
        kick_operations=[prepared_kick],
        sweep_operations=[prepared_sweep],
        tx_intents=[sweep_intent, kick_intent],
        skipped_during_prepare=[
            SkippedPreparedCandidate(
                candidate=skipped_candidate,
                reason="Gas estimate failed: call to 0x3333…3333 failed: active auction",
            )
        ],
        warnings=["Curve quote unavailable"],
    )

    assert plan.status() == "ok"
    assert plan.to_transaction_payloads() == [sweep_intent.to_payload(), kick_intent.to_payload()]
    assert plan.to_preview_payload() == {
        "sourceType": "strategy",
        "sourceAddress": "0x1111111111111111111111111111111111111111",
        "auctionAddress": "0x3333333333333333333333333333333333333333",
        "tokenAddress": None,
        "limit": 2,
        "eligibleCount": 4,
        "selectedCount": 3,
        "readyCount": 2,
        "ignoredCount": 1,
        "ignoredSkips": [
            {
                "sourceAddress": "0x7777777777777777777777777777777777777777",
                "auctionAddress": "0x3333333333333333333333333333333333333333",
                "tokenAddress": "0x8888888888888888888888888888888888888888",
                "tokenSymbol": "CVX",
                "detail": "ignored source",
            }
        ],
        "deferredSameAuctionCount": 1,
        "limitedCount": 1,
        "cooldownCount": 1,
        "cooldownSkips": [
            {
                "sourceAddress": "0x9999999999999999999999999999999999999999",
                "auctionAddress": "0x3333333333333333333333333333333333333333",
                "tokenAddress": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "tokenSymbol": "BAL",
                "detail": "cooldown active",
            }
        ],
        "skippedDuringPrepare": [
            {
                "sourceAddress": "0x1111111111111111111111111111111111111111",
                "sourceName": "Test Strategy",
                "auctionAddress": "0x3333333333333333333333333333333333333333",
                "tokenAddress": "0x6666666666666666666666666666666666666666",
                "tokenSymbol": "YFI",
                "wantSymbol": "USDC",
                "reason": "Gas estimate failed: call to 0x3333…3333 failed: active auction",
            }
        ],
        "preparedOperations": [
            {
                "operation": "sweep-and-settle",
                "auctionAddress": "0x3333333333333333333333333333333333333333",
                "sourceAddress": "0x1111111111111111111111111111111111111111",
                "sourceType": "strategy",
                "tokenAddress": "0x2222222222222222222222222222222222222222",
                "tokenSymbol": "CRV",
                "wantAddress": "0x4444444444444444444444444444444444444444",
                "wantSymbol": "USDC",
                "reason": "forced sweep requested",
                "sellAmount": "1000",
                "minimumPrice": "2375",
                "minimumPriceScaled1e18": "2375000000000000000",
                "usdValue": "2500",
                "normalizedBalance": "1000",
            },
            {
                "operation": "kick",
                "auctionAddress": "0x3333333333333333333333333333333333333333",
                "sourceAddress": "0x1111111111111111111111111111111111111111",
                "sourceName": "Test Strategy",
                "sourceType": "strategy",
                "tokenAddress": "0x2222222222222222222222222222222222222222",
                "tokenSymbol": "CRV",
                "wantAddress": "0x4444444444444444444444444444444444444444",
                "wantSymbol": "USDC",
                "wantPriceUsd": None,
                "sellAmount": "1000",
                "startingPrice": "2750",
                "startingPriceDisplay": "2,750 USDC (+10.00% buffer)",
                "minimumPrice": "2375000000000000000",
                "minimumPriceDisplay": "2,375,000,000,000,000,000 (scaled 1e18 floor)",
                "minimumQuote": "2375",
                "minimumQuoteDisplay": "2,375 USDC (-0.50% buffer)",
                "minimumPriceScaled1e18": "2375000000000000000",
                "quoteAmount": "2500",
                "quoteResponseJson": None,
                "usdValue": "2500",
                "bufferBps": 1000,
                "minBufferBps": 50,
                "pricingProfileName": "stable",
                "stepDecayRateBps": 50,
                "quoteRate": "2.5",
                "startRate": "2.75",
                "floorRate": "2.375",
                "settleToken": None,
                "recoveryPlan": {
                    "settleAfterStart": ["0x5555555555555555555555555555555555555555"],
                    "settleAfterMin": [],
                    "settleAfterDecay": [],
                },
            },
        ],
    }


def test_kick_plan_status_is_noop_without_transactions() -> None:
    plan = KickPlan(
        source_type=None,
        source_address=None,
        auction_address=None,
        token_address=None,
        limit=None,
        eligible_count=0,
        selected_count=0,
        ready_count=0,
    )

    assert plan.status() == "noop"
    assert plan.to_transaction_payloads() == []
