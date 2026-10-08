// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {DelayedAdmin} from "./access/DelayedAdmin.sol";
import {Guarded} from "./lib/Guarded.sol";
import {SafeToken} from "./lib/SafeToken.sol";
import {IERC20Like} from "./lib/IERC20Like.sol";
import {FullMulDiv} from "./lib/FullMulDiv.sol";

contract HarborPool is DelayedAdmin, Guarded {
    using SafeToken for address;

    IERC20Like public immutable tokenA;
    IERC20Like public immutable tokenB;
    address public immutable guardian;
    address public immutable treasury;

    uint128 public reserveA;
    uint128 public reserveB;
    uint256 public totalShares;
    uint16 public swapFeeBps = 30;
    bool public paused;
    mapping(address => uint256) public shares;

    constructor(
        address initialGovernor,
        address initialGuardian,
        address initialTreasury,
        IERC20Like tokenA_,
        IERC20Like tokenB_
    ) DelayedAdmin(initialGovernor) {
        require(initialGuardian != address(0) && initialTreasury != address(0), "ZERO_ROLE");
        guardian = initialGuardian;
        treasury = initialTreasury;
        tokenA = tokenA_;
        tokenB = tokenB_;
    }

    modifier whenRunning() {
        require(!paused, "PAUSED");
        _;
    }

    function addLiquidity(
        uint256 amountA,
        uint256 amountB,
        uint256 minShares,
        uint256 deadline
    ) external lock whenRunning returns (uint256 minted) {
        require(block.timestamp <= deadline, "EXPIRED");
        uint256 receivedA = _pull(address(tokenA), amountA);
        uint256 receivedB = _pull(address(tokenB), amountB);
        uint128 boundedA = _asUint128(receivedA);
        uint128 boundedB = _asUint128(receivedB);

        if (totalShares == 0) {
            minted = _sqrt(uint256(boundedA) * uint256(boundedB));
        } else {
            uint256 byA = FullMulDiv.mulDiv(receivedA, totalShares, reserveA);
            uint256 byB = FullMulDiv.mulDiv(receivedB, totalShares, reserveB);
            minted = byA < byB ? byA : byB;
        }
        require(minted >= minShares && minted != 0, "MIN_SHARES");
        reserveA = _asUint128(uint256(reserveA) + receivedA);
        reserveB = _asUint128(uint256(reserveB) + receivedB);
        totalShares += minted;
        shares[msg.sender] += minted;
    }

    function removeLiquidity(
        uint256 burned,
        uint256 minA,
        uint256 minB,
        uint256 deadline
    ) external lock whenRunning returns (uint256 amountA, uint256 amountB) {
        require(block.timestamp <= deadline, "EXPIRED");
        require(shares[msg.sender] >= burned && burned != 0, "INSUFFICIENT_SHARES");
        amountA = FullMulDiv.mulDiv(burned, reserveA, totalShares);
        amountB = FullMulDiv.mulDiv(burned, reserveB, totalShares);
        require(amountA >= minA && amountB >= minB, "MIN_ASSETS");

        shares[msg.sender] -= burned;
        totalShares -= burned;
        reserveA -= uint128(amountA);
        reserveB -= uint128(amountB);
        address(tokenA).safeTransfer(msg.sender, amountA);
        address(tokenB).safeTransfer(msg.sender, amountB);
    }

    function swapExactInput(address tokenIn, uint256 amountIn)
        external
        lock
        whenRunning
        returns (uint256 amountOut)
    {
        require(tokenIn == address(tokenA) || tokenIn == address(tokenB), "UNKNOWN_TOKEN");
        bool aToB = tokenIn == address(tokenA);
        uint256 received = _pull(tokenIn, amountIn);
        amountOut = _quoteOut(received, aToB ? reserveA : reserveB, aToB ? reserveB : reserveA);

        if (aToB) {
            reserveA = _asUint128(uint256(reserveA) + received);
            reserveB -= uint128(amountOut);
            address(tokenB).safeTransfer(msg.sender, amountOut);
        } else {
            reserveB = _asUint128(uint256(reserveB) + received);
            reserveA -= uint128(amountOut);
            address(tokenA).safeTransfer(msg.sender, amountOut);
        }
    }

    function setSwapFee(uint16 newFeeBps) external {
        require(newFeeBps <= 100, "FEE_CAP");
        swapFeeBps = newFeeBps;
    }

    function pause() external {
        require(msg.sender == guardian, "ONLY_GUARDIAN");
        paused = true;
    }

    function unpause() external onlyGovernor {
        paused = false;
    }

    function sweepSurplus() external onlyGovernor lock {
        uint256 extraA = tokenA.balanceOf(address(this)) - reserveA;
        uint256 extraB = tokenB.balanceOf(address(this)) - reserveB;
        if (extraA != 0) address(tokenA).safeTransfer(treasury, extraA);
        if (extraB != 0) address(tokenB).safeTransfer(treasury, extraB);
    }

    function _pull(address token, uint256 requested) internal returns (uint256 received) {
        uint256 beforeBalance = IERC20Like(token).balanceOf(address(this));
        token.safeTransferFrom(msg.sender, address(this), requested);
        received = IERC20Like(token).balanceOf(address(this)) - beforeBalance;
        require(received != 0, "ZERO_RECEIVED");
    }

    function _quoteOut(uint256 amountIn, uint256 reserveIn, uint256 reserveOut)
        internal
        view
        returns (uint256)
    {
        uint256 amountAfterFee = amountIn * (10_000 - swapFeeBps);
        return (amountAfterFee * reserveOut) / (reserveIn * 10_000 + amountAfterFee);
    }

    function _asUint128(uint256 value) internal pure returns (uint128) {
        require(value <= type(uint128).max, "RESERVE_OVERFLOW");
        return uint128(value);
    }

    function _sqrt(uint256 value) internal pure returns (uint256 result) {
        if (value == 0) return 0;
        uint256 x = value;
        result = 1;
        if (x >> 128 > 0) { x >>= 128; result <<= 64; }
        if (x >> 64 > 0) { x >>= 64; result <<= 32; }
        if (x >> 32 > 0) { x >>= 32; result <<= 16; }
        if (x >> 16 > 0) { x >>= 16; result <<= 8; }
        if (x >> 8 > 0) { x >>= 8; result <<= 4; }
        if (x >> 4 > 0) { x >>= 4; result <<= 2; }
        if (x >> 2 > 0) { result <<= 1; }
        for (uint256 i = 0; i < 7; ++i) result = (result + value / result) >> 1;
        uint256 roundedDown = value / result;
        return result < roundedDown ? result : roundedDown;
    }
}
