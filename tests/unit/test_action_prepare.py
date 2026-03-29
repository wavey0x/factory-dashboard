from types import SimpleNamespace

import pytest

from tidal.api.services.action_prepare import _estimate_transaction


class _FailingWeb3Client:
    async def estimate_gas(self, tx):  # noqa: ANN001
        del tx
        payload = (
            "0xef3dcb2f"
            "0000000000000000000000000000000000000000000000000000000000000020"
            "0000000000000000000000009cd1fe813c8a7e74f9c6c2c2d2cc63afd634b187"
            "0000000000000000000000000000000000000000000000000000000000000060"
            "000000000000000000000000000000000000000000000000000000000000000b"
            "6e6f7420656e61626c6564000000000000000000000000000000000000000000"
        )
        raise RuntimeError((payload, payload))


@pytest.mark.asyncio
async def test_estimate_transaction_decodes_execution_failed_reverts() -> None:
    gas_estimate, gas_limit, gas_warning = await _estimate_transaction(
        _FailingWeb3Client(),
        SimpleNamespace(chain_id=1),
        sender="0x1111111111111111111111111111111111111111",
        to_address="0x2222222222222222222222222222222222222222",
        data="0xdeadbeef",
        gas_cap=500000,
    )

    assert gas_estimate is None
    assert gas_limit is None
    assert gas_warning == "Gas estimate failed: call to 0x9cd1…b187 failed: not enabled"
