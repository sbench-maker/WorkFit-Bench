// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

abstract contract Guarded {
    uint256 private _lockState = 1;

    modifier lock() {
        require(_lockState == 1, "REENTRANT");
        _lockState = 2;
        _;
        _lockState = 1;
    }
}
