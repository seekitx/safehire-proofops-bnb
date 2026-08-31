import { AgentEndpoint, ERC8004Agent, resolveNetwork } from "@bnbagent/sdk";
import { envLocalPath, loadEnv } from "@bnbagent/studio-runtime/config";
import { getWallet } from "@bnbagent/studio-runtime/wallet";

const EXPECTED_ENDPOINT =
  "https://bnbagent-api.bnbchain.world/v1/rt/01M19F53Z2SRN65TBHKWXY1K54/.well-known/agent-card.json";

if (process.env.CONFIRM_DIRECT_ERC8004_REGISTER !== "BSC_TESTNET_ONLY") {
  throw new Error(
    "Refusing to register without CONFIRM_DIRECT_ERC8004_REGISTER=BSC_TESTNET_ONLY",
  );
}

const endpoint = process.env.SAFEHIRE_PUBLIC_AGENT_ENDPOINT;
if (endpoint !== EXPECTED_ENDPOINT) {
  throw new Error("Refusing to register an unexpected public Agent endpoint");
}

loadEnv(envLocalPath());

const wallet = getWallet();
const network = {
  ...resolveNetwork("bsc-testnet"),
  usePaymaster: false,
};
const agent = await ERC8004Agent.create({ walletProvider: wallet, network });
const agentUri = agent.generateAgentUri({
  name: "SafeHire ProofOps",
  description:
    "Evidence-first DeFi agent marketplace with ERC-8183 paid hiring on BSC Testnet.",
  endpoints: [
    new AgentEndpoint({
      name: "A2A",
      endpoint,
      version: "0.3.0",
      capabilities: ["negotiate", "notify_funded"],
    }),
  ],
  supportedTrust: ["reputation", "crypto-economic"],
});

const result = await agent.registerAgent(agentUri);
process.stdout.write(
  `${JSON.stringify(
    {
      chain_id: network.chainId,
      network: "bsc-testnet",
      registry: agent.contractAddress,
      owner: agent.walletAddress,
      agent_id: result.agentId,
      registration_tx_hash: result.transactionHash,
      endpoint,
    },
    null,
    2,
  )}\n`,
);
