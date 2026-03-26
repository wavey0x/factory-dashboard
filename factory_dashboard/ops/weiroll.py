"""Small wei-roll encoder for literal-only CALL plans.

This intentionally implements only the subset used by repo scripts:
standard CALL commands whose arguments are all literal ABI values.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from eth_abi import encode as abi_encode
from eth_abi import grammar as abi_grammar
from eth_utils import keccak, to_checksum_address

from factory_dashboard.normalizers import normalize_address

FLAG_CALL = 0x01
ARG_UNUSED = 0xFF
_MAX_COMMAND_ARGS = 6


@dataclass(slots=True, frozen=True)
class LiteralArg:
    abi_type: str
    value: Any


@dataclass(slots=True, frozen=True)
class LiteralCall:
    target: str
    signature: str
    args: tuple[LiteralArg, ...]


def function_selector(signature: str) -> bytes:
    """Return the 4-byte function selector for a Solidity signature."""

    return keccak(text=signature)[:4]


def is_dynamic_type(abi_type: str) -> bool:
    """Return True when the ABI type is dynamic in wei-roll state."""

    return bool(abi_grammar.parse(abi_type).is_dynamic)


def encode_literal_arg(arg: LiteralArg) -> bytes:
    """ABI-encode a literal argument for placement in wei-roll state."""

    value = arg.value
    if arg.abi_type == "address":
        value = to_checksum_address(normalize_address(value))
    return bytes(abi_encode([arg.abi_type], [value]))


def pack_command(
    selector: bytes,
    *,
    target: str,
    arg_slots: list[int],
    flags: int = FLAG_CALL,
    out_slot: int = ARG_UNUSED,
) -> bytes:
    """Pack a standard wei-roll command word."""

    if len(selector) != 4:
        raise ValueError("selector must be exactly 4 bytes")
    if len(arg_slots) > _MAX_COMMAND_ARGS:
        raise ValueError("literal-only command builder supports at most 6 arguments")

    padded_slots = list(arg_slots) + [ARG_UNUSED] * (_MAX_COMMAND_ARGS - len(arg_slots))
    command = int.from_bytes(selector, "big") << 224
    command |= int(flags) << 216

    shifts = (208, 200, 192, 184, 176, 168)
    for slot, shift in zip(padded_slots, shifts, strict=True):
        command |= int(slot) << shift

    command |= int(out_slot) << 160
    command |= int(normalize_address(target), 16)
    return command.to_bytes(32, "big")


def build_literal_calls(calls: list[LiteralCall]) -> tuple[list[bytes], list[bytes]]:
    """Encode literal-only CALL commands plus their state slots."""

    commands: list[bytes] = []
    state: list[bytes] = []

    for call in calls:
        arg_slots: list[int] = []
        for arg in call.args:
            slot = len(state)
            state.append(encode_literal_arg(arg))
            if is_dynamic_type(arg.abi_type):
                slot |= 0x80
            arg_slots.append(slot)

        commands.append(
            pack_command(
                function_selector(call.signature),
                target=call.target,
                arg_slots=arg_slots,
            )
        )

    return commands, state


def build_enable_calls(auction_address: str, token_addresses: list[str]) -> tuple[list[bytes], list[bytes]]:
    """Encode `enable(address)` calls for a single auction."""

    calls = [
        LiteralCall(
            target=auction_address,
            signature="enable(address)",
            args=(LiteralArg("address", token_address),),
        )
        for token_address in token_addresses
    ]
    return build_literal_calls(calls)
