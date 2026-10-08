// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

abstract contract DelayedAdmin {
    address public governor;
    address public pendingGovernor;

    event AdminTransferStarted(address indexed currentGovernor, address indexed nominee);
    event AdminTransferred(address indexed oldGovernor, address indexed newGovernor);
    event AdminTransferCancelled(address indexed nominee);

    constructor(address initialGovernor) {
        require(initialGovernor != address(0), "ZERO_GOVERNOR");
        governor = initialGovernor;
    }

    modifier onlyGovernor() {
        require(msg.sender == governor, "ONLY_GOVERNOR");
        _;
    }

    function beginAdminTransfer(address nominee) external onlyGovernor {
        require(nominee != address(0), "ZERO_NOMINEE");
        pendingGovernor = nominee;
        emit AdminTransferStarted(governor, nominee);
    }

    function acceptAdmin() external {
        require(msg.sender == pendingGovernor, "ONLY_NOMINEE");
        address oldGovernor = governor;
        governor = msg.sender;
        pendingGovernor = address(0);
        emit AdminTransferred(oldGovernor, msg.sender);
    }

    function cancelAdminTransfer() external onlyGovernor {
        address nominee = pendingGovernor;
        pendingGovernor = address(0);
        emit AdminTransferCancelled(nominee);
    }
}
