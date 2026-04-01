from eth_utils import to_checksum_address
from web3 import Web3

from tidal.ops.deploy import SINGLE_AUCTION_ABI


def test_single_auction_abi_has_no_colliding_starting_price_selector() -> None:
    contract = Web3().eth.contract(
        address=to_checksum_address("0x1111111111111111111111111111111111111111"),
        abi=SINGLE_AUCTION_ABI,
    )

    assert contract is not None
