// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title SafeHire Evidence Anchor
/// @notice Anchors append-only evidence ledger heads on BSC.
/// @dev The event is the primary immutable audit artifact. This reference is not audited.
contract EvidenceAnchor {
    address public immutable owner;
    bytes32 public latestRoot;
    uint64 public latestSequence;

    event EvidenceAnchored(uint64 indexed sequence, bytes32 indexed root, string uri);

    error Unauthorized();
    error InvalidSequence();
    error EmptyRoot();
    error InvalidUri();

    constructor() {
        owner = msg.sender;
    }

    function anchor(uint64 sequence, bytes32 root, string calldata uri) external {
        if (msg.sender != owner) revert Unauthorized();
        if (sequence <= latestSequence) revert InvalidSequence();
        if (root == bytes32(0)) revert EmptyRoot();
        if (bytes(uri).length == 0 || bytes(uri).length > 512) revert InvalidUri();
        latestSequence = sequence;
        latestRoot = root;
        emit EvidenceAnchored(sequence, root, uri);
    }
}
