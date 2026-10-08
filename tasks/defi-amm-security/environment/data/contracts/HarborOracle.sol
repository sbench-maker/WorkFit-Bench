// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {DelayedAdmin} from "./access/DelayedAdmin.sol";
import {IHarborReserves} from "./lib/IERC20Like.sol";
import {FullMulDiv} from "./lib/FullMulDiv.sol";

contract HarborOracle is DelayedAdmin {
    IHarborReserves public pool;
    uint256 public storedPriceX18;
    uint64 public updatedAt;

    constructor(address initialGovernor, IHarborReserves initialPool)
        DelayedAdmin(initialGovernor)
    {
        require(address(initialPool) != address(0), "ZERO_POOL");
        pool = initialPool;
    }

    function update() external returns (uint256 nextPriceX18) {
        require(block.timestamp >= uint256(updatedAt) + 60, "TOO_SOON");
        uint256 currentReserveA = pool.reserveA();
        uint256 currentReserveB = pool.reserveB();
        require(currentReserveA != 0 && currentReserveB != 0, "EMPTY_POOL");

        nextPriceX18 = FullMulDiv.mulDiv(currentReserveB, 1e18, currentReserveA);
        storedPriceX18 = nextPriceX18;
        updatedAt = uint64(block.timestamp);
    }

    function setPool(IHarborReserves newPool) external onlyGovernor {
        require(address(newPool) != address(0), "ZERO_POOL");
        pool = newPool;
    }

    function consult() external view returns (uint256 priceX18, uint64 timestamp) {
        return (storedPriceX18, updatedAt);
    }
}
