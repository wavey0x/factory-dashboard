from eth_abi import encode as abi_encode
from eth_utils import to_checksum_address

from factory_dashboard.ops.weiroll import (
    ARG_UNUSED,
    LiteralArg,
    LiteralCall,
    build_enable_calls,
    build_literal_calls,
    function_selector,
    pack_command,
)


def test_pack_command_matches_foundry_transfer_from_vector() -> None:
    target = "0xd533a949740bb3306d119cc777fa900ba034cd52"
    command = pack_command(
        function_selector("transferFrom(address,address,uint256)"),
        target=target,
        arg_slots=[0, 1, 2],
    )

    assert command.hex() == "23b872dd01000102ffffffffd533a949740bb3306d119cc777fa900ba034cd52"


def test_build_enable_calls_encodes_expected_command_and_state() -> None:
    auction = "0xa00e6b35c23442fa9d5149cba5dd94623ffe6693"
    token = "0x09fd37d9aa613789c517e76df1c53aece2b60df4"

    commands, state = build_enable_calls(auction, [token])

    assert len(commands) == 1
    assert len(state) == 1
    assert commands[0].hex() == "5bfa1b680100ffffffffffffa00e6b35c23442fa9d5149cba5dd94623ffe6693"
    assert state[0] == abi_encode(["address"], [to_checksum_address(token)])


def test_build_literal_calls_marks_dynamic_slots() -> None:
    target = "0x1111111111111111111111111111111111111111"

    commands, state = build_literal_calls(
        [
            LiteralCall(
                target=target,
                signature="store(bytes)",
                args=(LiteralArg("bytes", b"\x12\x34"),),
            )
        ]
    )

    assert len(commands) == 1
    assert len(state) == 1
    assert commands[0][5] == (0x80 | 0)
    assert commands[0][11] == ARG_UNUSED
