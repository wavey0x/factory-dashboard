// SPDX-License-Identifier: AGPL-3.0
pragma solidity ^0.8.20;

import {ITradeHandler} from "./interfaces/ITradeHandler.sol";
import {IAuction} from "./interfaces/IAuction.sol";
import {IERC20} from "./interfaces/IERC20.sol";
import {WeiRollCommandLib} from "./utils/WeiRollCommandLib.sol";

contract AuctionKicker {
    bytes4 internal constant TRANSFER_SELECTOR = bytes4(keccak256("transfer(address,uint256)"));
    bytes4 internal constant TRANSFER_FROM_SELECTOR = bytes4(keccak256("transferFrom(address,address,uint256)"));
    bytes4 internal constant SET_STARTING_PRICE_SELECTOR = bytes4(keccak256("setStartingPrice(uint256)"));
    bytes4 internal constant SET_MINIMUM_PRICE_SELECTOR = bytes4(keccak256("setMinimumPrice(uint256)"));
    bytes4 internal constant SET_STEP_DECAY_RATE_SELECTOR = bytes4(keccak256("setStepDecayRate(uint256)"));
    bytes4 internal constant SETTLE_SELECTOR = bytes4(keccak256("settle(address)"));
    bytes4 internal constant SWEEP_SELECTOR = bytes4(keccak256("sweep(address)"));
    bytes4 internal constant KICK_SELECTOR = bytes4(keccak256("kick(address)"));
    bytes4 internal constant DISABLE_SELECTOR = bytes4(keccak256("disable(address)"));
    bytes4 internal constant ENABLE_SELECTOR = bytes4(keccak256("enable(address)"));
    uint8 internal constant PATH_NOOP = 0;
    uint8 internal constant PATH_SETTLE_ONLY = 1;
    uint8 internal constant PATH_SWEEP_ONLY = 2;
    uint8 internal constant PATH_SWEEP_AND_SETTLE = 3;
    uint8 internal constant PATH_RESET_ONLY = 4;
    uint8 internal constant PATH_SWEEP_AND_RESET = 5;
    address public constant tradeHandler = 0xb634316E06cC0B358437CbadD4dC94F1D3a92B3b;

    event OwnerUpdated(address indexed owner);
    event KeeperUpdated(address indexed account, bool allowed);
    event Kicked(
        address indexed source,
        address indexed auction,
        address sellToken,
        uint256 sellAmount,
        uint256 startingPrice,
        uint256 minimumPrice,
        uint256 stepDecayRateBps
    );
    event AuctionResolved(
        address indexed auction, address indexed sellToken, uint8 path, address receiver, uint256 recoveredBalance
    );

    struct KickParams {
        address source;
        address auction;
        address sellToken;
        uint256 sellAmount;
        address wantToken;
        uint256 startingPrice;
        uint256 minimumPrice;
        uint256 stepDecayRateBps;
    }

    address public owner;
    mapping(address => bool) public keeper;

    constructor(address[] memory initialKeepers) {
        owner = msg.sender;
        emit OwnerUpdated(msg.sender);

        for (uint256 i = 0; i < initialKeepers.length; i++) {
            _setKeeper(initialKeepers[i], true);
        }
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "unauthorized");
        _;
    }

    modifier onlyKeeperOrOwner() {
        require(msg.sender == owner || keeper[msg.sender], "unauthorized");
        _;
    }

    function setOwner(address newOwner) external onlyOwner {
        require(newOwner != address(0), "zero address");
        owner = newOwner;
        emit OwnerUpdated(newOwner);
    }

    function setKeeper(address account, bool allowed) external onlyOwner {
        _setKeeper(account, allowed);
    }

    function _setKeeper(address account, bool allowed) internal {
        keeper[account] = allowed;
        emit KeeperUpdated(account, allowed);
    }

    function kick(
        address source,
        address auction,
        address sellToken,
        uint256 sellAmount,
        address wantToken,
        uint256 startingPrice,
        uint256 minimumPrice,
        uint256 stepDecayRateBps
    ) external onlyKeeperOrOwner {
        _kick(KickParams(source, auction, sellToken, sellAmount, wantToken, startingPrice, minimumPrice, stepDecayRateBps));
    }

    function batchKick(KickParams[] calldata kicks) external onlyKeeperOrOwner {
        for (uint256 i = 0; i < kicks.length; i++) {
            _kick(kicks[i]);
        }
    }

    function previewResolveAuction(address auction, address sellToken)
        external
        view
        returns (uint8 path, bool active, uint256 kickedAt, uint256 balance, bool requiresForce, address receiver)
    {
        return _previewResolveAuction(auction, sellToken);
    }

    function resolveAuction(address auction, address sellToken, bool forceLive) external onlyKeeperOrOwner {
        (uint8 path, bool active, uint256 kickedAt, uint256 balance, bool requiresForce, address receiver) =
            _previewResolveAuction(auction, sellToken);

        if (requiresForce) {
            require(forceLive, "force required");
        }

        uint256 recoveredBalance = _executeResolveAuction(auction, sellToken, path, active, kickedAt, balance, receiver);
        emit AuctionResolved(auction, sellToken, path, receiver, recoveredBalance);
    }

    function enableTokens(address auction, address[] calldata sellTokens) external onlyKeeperOrOwner {
        require(sellTokens.length != 0, "no tokens");
        require(IAuction(auction).governance() == tradeHandler, "governance mismatch");
        require(sellTokens.length <= uint256(type(uint8).max) + 1, "too many tokens");

        bytes[] memory state = new bytes[](sellTokens.length);
        bytes32[] memory commands = new bytes32[](sellTokens.length);

        for (uint256 i = 0; i < sellTokens.length; i++) {
            address sellToken = sellTokens[i];
            require(sellToken != address(0), "zero token");
            state[i] = abi.encode(sellToken);
            commands[i] = WeiRollCommandLib.cmdCall(
                ENABLE_SELECTOR, uint8(i), WeiRollCommandLib.ARG_UNUSED, WeiRollCommandLib.ARG_UNUSED, auction
            );
        }

        ITradeHandler(tradeHandler).execute(commands, state);
    }

    function _validateKick(address source, address auction, address sellToken, address wantToken, uint256 startingPrice)
        internal
        view
    {
        require(startingPrice != 0, "starting price zero");
        require(IAuction(auction).governance() == tradeHandler, "governance mismatch");
        require(IAuction(auction).want() == wantToken, "want mismatch");
        require(sellToken != wantToken, "sell token is want");
        require(IAuction(auction).receiver() == source, "receiver mismatch");
    }

    function _kick(KickParams memory p) internal {
        _validateKick(p.source, p.auction, p.sellToken, p.wantToken, p.startingPrice);

        bytes[] memory state = new bytes[](7);
        state[0] = abi.encode(p.source);
        state[1] = abi.encode(p.auction);
        state[2] = abi.encode(p.sellAmount);
        state[3] = abi.encode(p.startingPrice);
        state[4] = abi.encode(p.minimumPrice);
        state[5] = abi.encode(p.sellToken);
        state[6] = abi.encode(p.stepDecayRateBps);

        bytes32[] memory commands = new bytes32[](5);
        commands[0] = WeiRollCommandLib.cmdCall(TRANSFER_FROM_SELECTOR, 0, 1, 2, p.sellToken);
        commands[1] = WeiRollCommandLib.cmdCall(
            SET_STARTING_PRICE_SELECTOR, 3, WeiRollCommandLib.ARG_UNUSED, WeiRollCommandLib.ARG_UNUSED, p.auction
        );
        commands[2] = WeiRollCommandLib.cmdCall(
            SET_MINIMUM_PRICE_SELECTOR, 4, WeiRollCommandLib.ARG_UNUSED, WeiRollCommandLib.ARG_UNUSED, p.auction
        );
        commands[3] = WeiRollCommandLib.cmdCall(
            SET_STEP_DECAY_RATE_SELECTOR, 6, WeiRollCommandLib.ARG_UNUSED, WeiRollCommandLib.ARG_UNUSED, p.auction
        );
        commands[4] = WeiRollCommandLib.cmdCall(
            KICK_SELECTOR, 5, WeiRollCommandLib.ARG_UNUSED, WeiRollCommandLib.ARG_UNUSED, p.auction
        );

        ITradeHandler(tradeHandler).execute(commands, state);
        emit Kicked(p.source, p.auction, p.sellToken, p.sellAmount, p.startingPrice, p.minimumPrice, p.stepDecayRateBps);
    }

    function _validateResolveAuction(address auction, address sellToken) internal view returns (address receiver) {
        require(IAuction(auction).governance() == tradeHandler, "governance mismatch");
        require(sellToken != address(0), "zero token");
        require(sellToken != IAuction(auction).want(), "sell token is want");
        return IAuction(auction).receiver();
    }

    function _previewResolveAuction(address auction, address sellToken)
        internal
        view
        returns (uint8 path, bool active, uint256 kickedAt, uint256 balance, bool requiresForce, address receiver)
    {
        receiver = _validateResolveAuction(auction, sellToken);
        active = IAuction(auction).isActive(sellToken);
        kickedAt = IAuction(auction).kicked(sellToken);
        balance = IERC20(sellToken).balanceOf(auction);
        requiresForce = active && balance > 0;

        if (active) {
            if (balance == 0) {
                return (PATH_SETTLE_ONLY, active, kickedAt, balance, requiresForce, receiver);
            }
            return (PATH_SWEEP_AND_SETTLE, active, kickedAt, balance, requiresForce, receiver);
        }

        if (kickedAt != 0) {
            if (balance == 0) {
                return (PATH_RESET_ONLY, active, kickedAt, balance, requiresForce, receiver);
            }
            return (PATH_SWEEP_AND_RESET, active, kickedAt, balance, requiresForce, receiver);
        }

        if (balance != 0) {
            return (PATH_SWEEP_ONLY, active, kickedAt, balance, requiresForce, receiver);
        }

        return (PATH_NOOP, active, kickedAt, balance, requiresForce, receiver);
    }

    function _executeResolveAuction(
        address auction,
        address sellToken,
        uint8 path,
        bool active,
        uint256 kickedAt,
        uint256 balance,
        address receiver
    ) internal returns (uint256 recoveredBalance) {
        if (path == PATH_SETTLE_ONLY) {
            _executeSettleOnly(auction, sellToken);
            return 0;
        }

        if (path == PATH_SWEEP_ONLY) {
            _executeSweepTransfer(auction, sellToken, receiver, balance);
            return balance;
        }

        if (path == PATH_SWEEP_AND_SETTLE) {
            _executeSweepTransferSettle(auction, sellToken, receiver, balance);
            return balance;
        }

        if (path == PATH_RESET_ONLY) {
            _executeDisableEnable(auction, sellToken);
            return 0;
        }

        if (path == PATH_SWEEP_AND_RESET) {
            _executeSweepTransferDisableEnable(auction, sellToken, receiver, balance);
            return balance;
        }

        require(!active && kickedAt == 0 && balance == 0, "invalid noop");
        return 0;
    }

    function _executeSettleOnly(address auction, address sellToken) internal {
        bytes[] memory state = new bytes[](1);
        state[0] = abi.encode(sellToken);
        bytes32[] memory commands = new bytes32[](1);
        commands[0] = WeiRollCommandLib.cmdCall(
            SETTLE_SELECTOR, 0, WeiRollCommandLib.ARG_UNUSED, WeiRollCommandLib.ARG_UNUSED, auction
        );
        ITradeHandler(tradeHandler).execute(commands, state);
    }

    function _executeSweepTransfer(address auction, address sellToken, address receiver, uint256 recoveredBalance)
        internal
    {
        bytes[] memory state = new bytes[](3);
        state[0] = abi.encode(sellToken);
        state[1] = abi.encode(receiver);
        state[2] = abi.encode(recoveredBalance);
        bytes32[] memory commands = new bytes32[](2);
        commands[0] = WeiRollCommandLib.cmdCall(
            SWEEP_SELECTOR, 0, WeiRollCommandLib.ARG_UNUSED, WeiRollCommandLib.ARG_UNUSED, auction
        );
        commands[1] = WeiRollCommandLib.cmdCall(TRANSFER_SELECTOR, 1, 2, WeiRollCommandLib.ARG_UNUSED, sellToken);
        ITradeHandler(tradeHandler).execute(commands, state);
    }

    function _executeSweepTransferSettle(address auction, address sellToken, address receiver, uint256 recoveredBalance)
        internal
    {
        bytes[] memory state = new bytes[](3);
        state[0] = abi.encode(sellToken);
        state[1] = abi.encode(receiver);
        state[2] = abi.encode(recoveredBalance);
        bytes32[] memory commands = new bytes32[](3);
        commands[0] = WeiRollCommandLib.cmdCall(
            SWEEP_SELECTOR, 0, WeiRollCommandLib.ARG_UNUSED, WeiRollCommandLib.ARG_UNUSED, auction
        );
        commands[1] = WeiRollCommandLib.cmdCall(TRANSFER_SELECTOR, 1, 2, WeiRollCommandLib.ARG_UNUSED, sellToken);
        commands[2] = WeiRollCommandLib.cmdCall(
            SETTLE_SELECTOR, 0, WeiRollCommandLib.ARG_UNUSED, WeiRollCommandLib.ARG_UNUSED, auction
        );
        ITradeHandler(tradeHandler).execute(commands, state);
    }

    function _executeDisableEnable(address auction, address sellToken) internal {
        bytes[] memory state = new bytes[](1);
        state[0] = abi.encode(sellToken);
        bytes32[] memory commands = new bytes32[](2);
        commands[0] = WeiRollCommandLib.cmdCall(
            DISABLE_SELECTOR, 0, WeiRollCommandLib.ARG_UNUSED, WeiRollCommandLib.ARG_UNUSED, auction
        );
        commands[1] = WeiRollCommandLib.cmdCall(
            ENABLE_SELECTOR, 0, WeiRollCommandLib.ARG_UNUSED, WeiRollCommandLib.ARG_UNUSED, auction
        );
        ITradeHandler(tradeHandler).execute(commands, state);
    }

    function _executeSweepTransferDisableEnable(
        address auction,
        address sellToken,
        address receiver,
        uint256 recoveredBalance
    ) internal {
        bytes[] memory state = new bytes[](3);
        state[0] = abi.encode(sellToken);
        state[1] = abi.encode(receiver);
        state[2] = abi.encode(recoveredBalance);
        bytes32[] memory commands = new bytes32[](4);
        commands[0] = WeiRollCommandLib.cmdCall(
            SWEEP_SELECTOR, 0, WeiRollCommandLib.ARG_UNUSED, WeiRollCommandLib.ARG_UNUSED, auction
        );
        commands[1] = WeiRollCommandLib.cmdCall(TRANSFER_SELECTOR, 1, 2, WeiRollCommandLib.ARG_UNUSED, sellToken);
        commands[2] = WeiRollCommandLib.cmdCall(
            DISABLE_SELECTOR, 0, WeiRollCommandLib.ARG_UNUSED, WeiRollCommandLib.ARG_UNUSED, auction
        );
        commands[3] = WeiRollCommandLib.cmdCall(
            ENABLE_SELECTOR, 0, WeiRollCommandLib.ARG_UNUSED, WeiRollCommandLib.ARG_UNUSED, auction
        );
        ITradeHandler(tradeHandler).execute(commands, state);
    }
}
