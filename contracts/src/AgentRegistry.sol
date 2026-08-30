// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title SafeHire Agent Registry
/// @notice Minimal BSC registry for endpoint and metadata commitments.
/// @dev This reference contract is not audited. Metadata remains offchain; only its hash is committed.
contract AgentRegistry {
    enum Category { Rebalancing, GridTrading, YieldOptimisation, HealthFactorMonitoring }

    struct Agent {
        address owner;
        Category category;
        string endpoint;
        bytes32 metadataHash;
        bool active;
        uint64 updatedAt;
    }

    mapping(bytes32 => Agent) private agents;

    event AgentRegistered(
        bytes32 indexed agentId,
        address indexed owner,
        Category indexed category,
        string endpoint,
        bytes32 metadataHash
    );
    event AgentUpdated(bytes32 indexed agentId, string endpoint, bytes32 metadataHash, bool active);

    error Unauthorized();
    error InvalidEndpoint();
    error AgentAlreadyExists();
    error AgentNotFound();
    error InvalidAgentId();

    function register(
        bytes32 agentId,
        Category category,
        string calldata endpoint,
        bytes32 metadataHash
    ) external {
        if (agentId == bytes32(0)) revert InvalidAgentId();
        if (bytes(endpoint).length == 0 || bytes(endpoint).length > 512) revert InvalidEndpoint();
        if (agents[agentId].owner != address(0)) revert AgentAlreadyExists();
        agents[agentId] = Agent({
            owner: msg.sender,
            category: category,
            endpoint: endpoint,
            metadataHash: metadataHash,
            active: true,
            updatedAt: uint64(block.timestamp)
        });
        emit AgentRegistered(agentId, msg.sender, category, endpoint, metadataHash);
    }

    function update(
        bytes32 agentId,
        string calldata endpoint,
        bytes32 metadataHash,
        bool active
    ) external {
        Agent storage agent = agents[agentId];
        if (agent.owner == address(0)) revert AgentNotFound();
        if (agent.owner != msg.sender) revert Unauthorized();
        if (bytes(endpoint).length == 0 || bytes(endpoint).length > 512) revert InvalidEndpoint();
        agent.endpoint = endpoint;
        agent.metadataHash = metadataHash;
        agent.active = active;
        agent.updatedAt = uint64(block.timestamp);
        emit AgentUpdated(agentId, endpoint, metadataHash, active);
    }

    function get(bytes32 agentId) external view returns (Agent memory) {
        Agent memory agent = agents[agentId];
        if (agent.owner == address(0)) revert AgentNotFound();
        return agent;
    }
}
