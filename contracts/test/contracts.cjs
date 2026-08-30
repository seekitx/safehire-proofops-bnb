const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("SafeHire contracts", function () {
  it("registers an agent once and keeps owner control", async function () {
    const [owner, other] = await ethers.getSigners();
    const registry = await (await ethers.getContractFactory("AgentRegistry")).deploy();
    const agentId = ethers.id("lp-guardian");
    const metadataHash = ethers.id("metadata-v1");
    await expect(registry.register(agentId, 0, "https://agents.example/lp", metadataHash))
      .to.emit(registry, "AgentRegistered")
      .withArgs(agentId, owner.address, 0, "https://agents.example/lp", metadataHash);
    await expect(
      registry.connect(other).update(agentId, "https://evil.example", metadataHash, true)
    ).to.be.revertedWithCustomError(registry, "Unauthorized");
    await expect(
      registry.register(agentId, 0, "https://agents.example/lp", metadataHash)
    ).to.be.revertedWithCustomError(registry, "AgentAlreadyExists");
  });

  it("enforces target, selector, caps, replay protection and revoke", async function () {
    const [owner, executor, target, denied] = await ethers.getSigners();
    const now = (await ethers.provider.getBlock("latest")).timestamp;
    const selector = "0x12345678";
    const policy = await (await ethers.getContractFactory("ScopedExecutionPolicy")).deploy(
      executor.address,
      [target.address],
      [selector],
      10,
      20,
      now + 3600
    );
    const intentId = ethers.id("intent-1");
    await expect(policy.connect(executor).consume(intentId, denied.address, selector, 1))
      .to.be.revertedWithCustomError(policy, "TargetDenied");
    await expect(policy.connect(executor).consume(intentId, target.address, selector, 10))
      .to.emit(policy, "IntentConsumed");
    await expect(policy.connect(executor).consume(intentId, target.address, selector, 1))
      .to.be.revertedWithCustomError(policy, "DuplicateIntent");
    await expect(policy.connect(owner).revoke()).to.emit(policy, "Revoked");
    await expect(policy.connect(executor).consume(ethers.id("intent-2"), target.address, selector, 1))
      .to.be.revertedWithCustomError(policy, "PolicyRevoked");
  });

  it("anchors only increasing, non-empty evidence roots", async function () {
    const anchor = await (await ethers.getContractFactory("EvidenceAnchor")).deploy();
    const root = ethers.id("ledger-head-1");
    await expect(anchor.anchor(1, root, "ipfs://evidence-1"))
      .to.emit(anchor, "EvidenceAnchored")
      .withArgs(1, root, "ipfs://evidence-1");
    await expect(anchor.anchor(1, ethers.id("new"), "ipfs://evidence-2"))
      .to.be.revertedWithCustomError(anchor, "InvalidSequence");
    await expect(anchor.anchor(2, ethers.ZeroHash, "ipfs://evidence-2"))
      .to.be.revertedWithCustomError(anchor, "EmptyRoot");
  });
});
