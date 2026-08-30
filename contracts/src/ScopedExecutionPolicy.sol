// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title Scoped Execution Policy
/// @notice Onchain permission envelope for one hired agent/executor.
/// @dev It authorizes calls but does not custody funds or execute arbitrary calls itself.
///      The reference implementation is not audited.
contract ScopedExecutionPolicy {
    address public immutable owner;
    address public immutable executor;
    uint256 public immutable maxValuePerCall;
    uint256 public immutable maxTotalValue;
    uint64 public immutable expiresAt;

    mapping(address => bool) public allowedTarget;
    mapping(bytes4 => bool) public allowedSelector;
    mapping(bytes32 => bool) public consumedIntent;
    uint256 public totalConsumed;
    bool public revoked;

    event IntentConsumed(bytes32 indexed intentId, address indexed target, bytes4 selector, uint256 value);
    event Revoked(address indexed owner);

    error Unauthorized();
    error PolicyExpired();
    error PolicyRevoked();
    error TargetDenied();
    error SelectorDenied();
    error ValueCapExceeded();
    error DuplicateIntent();
    error InvalidConfiguration();

    constructor(
        address executor_,
        address[] memory targets,
        bytes4[] memory selectors,
        uint256 maxValuePerCall_,
        uint256 maxTotalValue_,
        uint64 expiresAt_
    ) {
        if (
            executor_ == address(0) || targets.length == 0 || selectors.length == 0 ||
            maxValuePerCall_ > maxTotalValue_ || expiresAt_ <= block.timestamp
        ) revert InvalidConfiguration();
        owner = msg.sender;
        executor = executor_;
        maxValuePerCall = maxValuePerCall_;
        maxTotalValue = maxTotalValue_;
        expiresAt = expiresAt_;
        for (uint256 i; i < targets.length; ++i) {
            if (targets[i] == address(0)) revert InvalidConfiguration();
            allowedTarget[targets[i]] = true;
        }
        for (uint256 i; i < selectors.length; ++i) {
            if (selectors[i] == bytes4(0)) revert InvalidConfiguration();
            allowedSelector[selectors[i]] = true;
        }
    }

    function consume(
        bytes32 intentId,
        address target,
        bytes4 selector,
        uint256 value
    ) external returns (bool) {
        if (msg.sender != executor) revert Unauthorized();
        if (revoked) revert PolicyRevoked();
        if (block.timestamp >= expiresAt) revert PolicyExpired();
        if (!allowedTarget[target]) revert TargetDenied();
        if (!allowedSelector[selector]) revert SelectorDenied();
        if (value > maxValuePerCall || totalConsumed + value > maxTotalValue) revert ValueCapExceeded();
        if (consumedIntent[intentId]) revert DuplicateIntent();
        consumedIntent[intentId] = true;
        totalConsumed += value;
        emit IntentConsumed(intentId, target, selector, value);
        return true;
    }

    function revoke() external {
        if (msg.sender != owner) revert Unauthorized();
        revoked = true;
        emit Revoked(msg.sender);
    }
}
