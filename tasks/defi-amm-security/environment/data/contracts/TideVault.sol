// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {DelayedAdmin} from "./access/DelayedAdmin.sol";
import {Guarded} from "./lib/Guarded.sol";
import {SafeToken} from "./lib/SafeToken.sol";
import {IERC20Like} from "./lib/IERC20Like.sol";
import {FullMulDiv} from "./lib/FullMulDiv.sol";

contract TideVault is DelayedAdmin, Guarded {
    using SafeToken for address;

    IERC20Like public immutable asset;
    address public immutable guardian;
    address public keeper;
    uint256 public trackedAssets;
    uint256 public totalShares;
    bool public paused;
    mapping(address => uint256) public shares;

    constructor(
        address initialGovernor,
        address initialGuardian,
        address initialKeeper,
        IERC20Like asset_
    ) DelayedAdmin(initialGovernor) {
        require(initialGuardian != address(0) && initialKeeper != address(0), "ZERO_ROLE");
        guardian = initialGuardian;
        keeper = initialKeeper;
        asset = asset_;
    }

    modifier whenRunning() {
        require(!paused, "PAUSED");
        _;
    }

    function deposit(uint256 assets, address receiver)
        external
        whenRunning
        returns (uint256 minted)
    {
        uint256 liveBalance = asset.balanceOf(address(this));
        minted = totalShares == 0 ? assets : FullMulDiv.mulDiv(assets, totalShares, liveBalance);
        require(minted != 0, "ZERO_SHARES");

        asset.transferFrom(msg.sender, address(this), assets);
        trackedAssets += assets;
        totalShares += minted;
        shares[receiver] += minted;
    }

    function redeem(uint256 burned, address receiver)
        external
        whenRunning
        returns (uint256 assets)
    {
        require(burned != 0 && shares[msg.sender] >= burned, "INSUFFICIENT_SHARES");
        assets = FullMulDiv.mulDiv(burned, trackedAssets, totalShares);

        asset.transfer(receiver, assets);
        shares[msg.sender] -= burned;
        totalShares -= burned;
        trackedAssets -= assets;
    }

    function syncAssets() external {
        trackedAssets = asset.balanceOf(address(this));
    }

    function harvest(uint256 requestedYield) external lock {
        require(msg.sender == keeper, "ONLY_KEEPER");
        uint256 beforeBalance = asset.balanceOf(address(this));
        address(asset).safeTransferFrom(msg.sender, address(this), requestedYield);
        uint256 received = asset.balanceOf(address(this)) - beforeBalance;
        trackedAssets += received;
    }

    function setKeeper(address newKeeper) external onlyGovernor {
        require(newKeeper != address(0), "ZERO_KEEPER");
        keeper = newKeeper;
    }

    function pause() external {
        require(msg.sender == guardian, "ONLY_GUARDIAN");
        paused = true;
    }

    function unpause() external onlyGovernor {
        paused = false;
    }
}
