const fs = require("node:fs");
const path = require("node:path");
const hre = require("hardhat");

function required(name) {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required`);
  return value;
}

async function deploy(factoryName, args = []) {
  const factory = await hre.ethers.getContractFactory(factoryName);
  const contract = await factory.deploy(...args);
  await contract.waitForDeployment();
  const deployment = contract.deploymentTransaction();
  if (!deployment) throw new Error(`${factoryName} deployment transaction is missing`);
  const receipt = await deployment.wait();
  if (!receipt || receipt.status !== 1) throw new Error(`${factoryName} deployment failed`);
  return {
    address: await contract.getAddress(),
    deployment_tx_hash: deployment.hash,
    block_number: receipt.blockNumber,
  };
}

async function main() {
  const network = await hre.ethers.provider.getNetwork();
  if (Number(network.chainId) !== 97) throw new Error("Deployment is restricted to BSC Testnet (chain id 97)");
  const [deployer] = await hre.ethers.getSigners();
  if (!deployer) throw new Error("BSC_DEPLOYER_PRIVATE_KEY is not configured");

  const executor = required("POLICY_EXECUTOR");
  const target = required("POLICY_TARGET");
  const selector = required("POLICY_SELECTOR");
  const maxPerCallWei = BigInt(process.env.POLICY_MAX_PER_CALL_WEI || "0");
  const maxTotalWei = BigInt(process.env.POLICY_MAX_TOTAL_WEI || "0");
  const ttlSeconds = Number(process.env.POLICY_TTL_SECONDS || "3600");
  if (maxPerCallWei > maxTotalWei) throw new Error("POLICY_MAX_PER_CALL_WEI cannot exceed POLICY_MAX_TOTAL_WEI");
  if (!/^0x[0-9a-fA-F]{8}$/.test(selector) || selector === "0x00000000") {
    throw new Error("POLICY_SELECTOR must be a non-zero bytes4 hex value");
  }
  const latest = await hre.ethers.provider.getBlock("latest");
  const expiresAt = BigInt(latest.timestamp + ttlSeconds);

  const contracts = {
    AgentRegistry: await deploy("AgentRegistry"),
    ScopedExecutionPolicy: await deploy("ScopedExecutionPolicy", [
      executor,
      [target],
      [selector],
      maxPerCallWei,
      maxTotalWei,
      expiresAt,
    ]),
    EvidenceAnchor: await deploy("EvidenceAnchor"),
  };

  const output = path.resolve(__dirname, "..", "deployments", "bsc-testnet.json");
  if (fs.existsSync(output) && process.env.OVERWRITE_DEPLOYMENT !== "true") {
    throw new Error(`Refusing to overwrite ${output}; set OVERWRITE_DEPLOYMENT=true after reviewing the existing evidence`);
  }
  const record = {
    schema_version: "1.0",
    chain_id: 97,
    network: "bsc-testnet",
    deployer: deployer.address,
    observed_at: new Date().toISOString(),
    contracts,
  };
  fs.writeFileSync(output, `${JSON.stringify(record, null, 2)}\n`, { encoding: "utf8", mode: 0o600 });
  process.stdout.write(`${output}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.message}\n`);
  process.exitCode = 1;
});
