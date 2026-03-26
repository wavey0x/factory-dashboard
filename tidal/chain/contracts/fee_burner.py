"""Fee burner contract reader."""

from __future__ import annotations

from eth_utils import to_checksum_address

from tidal.chain.contracts.abis import FEE_BURNER_ABI
from tidal.chain.web3_client import Web3Client
from tidal.normalizers import normalize_address


class FeeBurnerReader:
    """Reads spender approvals from fee burner contracts."""

    def __init__(self, web3_client: Web3Client):
        self.web3_client = web3_client

    async def get_approvals(self, fee_burner_address: str, spender_address: str) -> list[str]:
        fee_burner_address = normalize_address(fee_burner_address)
        spender_address = normalize_address(spender_address)
        contract = self.web3_client.contract(fee_burner_address, FEE_BURNER_ABI)
        values = await self.web3_client.call(
            contract.functions.getApprovals(to_checksum_address(spender_address))
        )
        return [normalize_address(value) for value in values]

    async def is_token_spender(self, fee_burner_address: str, spender_address: str) -> bool:
        fee_burner_address = normalize_address(fee_burner_address)
        spender_address = normalize_address(spender_address)
        contract = self.web3_client.contract(fee_burner_address, FEE_BURNER_ABI)
        return bool(
            await self.web3_client.call(
                contract.functions.isTokenSpender(to_checksum_address(spender_address))
            )
        )
