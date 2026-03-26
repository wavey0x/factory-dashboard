# Scripts

## `enable_auction_tokens.py`

Interactive helper for enabling all relevant sell tokens on a newly deployed auction.

Usage:

```bash
python scripts/enable_auction_tokens.py 0xYourAuctionAddress
```

Optional extras:

```bash
python scripts/enable_auction_tokens.py 0xYourAuctionAddress \
  --config ./config.yaml \
  --extra-token 0xTokenA \
  --extra-token 0xTokenB
```

The script:

- verifies the auction against the configured factory and governance
- resolves whether the receiver is a strategy or monitored fee burner
- discovers candidate tokens from live contract state plus local DB history
- probes balances and `enable(address)` callability
- previews the wei-roll payload through the trade handler
- optionally signs and broadcasts the final transaction
