const CHAIN_ID_HEX = "0x61";
const BSC_TESTNET_EXPLORER = "https://testnet.bscscan.com";

const state = {
  owner: null,
  plan: null,
  transactions: [],
  activeTransaction: null,
  results: [],
};

const byId = (id) => document.getElementById(id);

let toastTimer;
function toast(message, error = false) {
  const element = byId("toast");
  element.textContent = message;
  element.classList.toggle("error", error);
  element.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => element.classList.remove("show"), 5000);
}

function short(value, head = 10, tail = 8) {
  const text = String(value ?? "");
  return text.length > head + tail + 2 ? `${text.slice(0, head)}…${text.slice(-tail)}` : text;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail || body.message || `HTTP ${response.status}`);
  return body;
}

async function ensureBscTestnet() {
  const chainId = await ethereum.request({ method: "eth_chainId" });
  if (chainId === CHAIN_ID_HEX) return;
  try {
    await ethereum.request({ method: "wallet_switchEthereumChain", params: [{ chainId: CHAIN_ID_HEX }] });
  } catch (error) {
    if (error.code !== 4902) throw error;
    await ethereum.request({
      method: "wallet_addEthereumChain",
      params: [{
        chainId: CHAIN_ID_HEX,
        chainName: "BNB Smart Chain Testnet",
        nativeCurrency: { name: "tBNB", symbol: "tBNB", decimals: 18 },
        rpcUrls: ["https://data-seed-prebsc-1-s1.bnbchain.org:8545"],
        blockExplorerUrls: [BSC_TESTNET_EXPLORER],
      }],
    });
  }
}

function currentStep() {
  return state.transactions[state.results.length] || null;
}

function displayName(transaction) {
  return transaction.contract_name === "FundAgentWallet" ? "Agent wallet with 0.05 tBNB" : transaction.contract_name;
}

function walletTransaction(transaction) {
  const request = { from: state.owner, value: transaction.value || "0x0" };
  if (transaction.to) request.to = transaction.to;
  if (transaction.data) request.data = transaction.data;
  return request;
}

function setStepStatus(contractName, status, label) {
  const row = document.querySelector(`[data-step="${contractName}"]`);
  row.classList.toggle("active", status === "active");
  row.classList.toggle("done", status === "done");
  row.querySelector("small").innerHTML = label;
}

async function waitForReceipt(txHash) {
  const deadline = Date.now() + 5 * 60 * 1000;
  while (Date.now() < deadline) {
    const receipt = await ethereum.request({ method: "eth_getTransactionReceipt", params: [txHash] });
    if (receipt) return receipt;
    await new Promise((resolve) => setTimeout(resolve, 3000));
  }
  throw new Error("Receipt was not confirmed within 5 minutes. Check BscScan before retrying.");
}

async function estimateNext() {
  const next = currentStep();
  if (!next || !state.owner) return;
  try {
    const [gasHex, priceHex] = await Promise.all([
      ethereum.request({ method: "eth_estimateGas", params: [walletTransaction(next)] }),
      ethereum.request({ method: "eth_gasPrice" }),
    ]);
    const feeWei = BigInt(gasHex) * BigInt(priceHex);
    byId("estimatedGas").textContent = `${(Number(feeWei) / 1e18).toFixed(6)} tBNB maximum estimate`;
  } catch {
    byId("estimatedGas").textContent = "Wallet will show the final testnet gas";
  }
}

async function preparePolicy(registryAddress) {
  const expiresAt = Math.floor(Date.now() / 1000) + 7 * 24 * 60 * 60;
  return api("/api/dev/contracts/scoped-policy-plan", {
    method: "POST",
    body: JSON.stringify({ owner: state.owner, registry_address: registryAddress, expires_at: expiresAt }),
  });
}

async function connectWallet() {
  if (!window.ethereum) {
    toast("No EVM wallet was found in Chrome.", true);
    return;
  }
  try {
    const accounts = await ethereum.request({ method: "eth_requestAccounts" });
    if (!accounts?.[0]) throw new Error("Wallet returned no account");
    await ensureBscTestnet();
    state.owner = accounts[0];
    state.plan = await api("/api/dev/contracts/deployment-plan");
    state.transactions = [state.plan.funding, ...state.plan.transactions];
    byId("deployer").textContent = state.owner;
    byId("deployNetwork").textContent = "BSC Testnet · ready";
    byId("deployDot").className = "dot ok";
    byId("connectDeployWallet").textContent = short(state.owner);
    setStepStatus("FundAgentWallet", "active", "Ready to send 0.05 tBNB");
    byId("deployNext").disabled = false;
    byId("deployNext").textContent = "Fund Agent wallet with 0.05 tBNB";
    await estimateNext();
  } catch (error) {
    toast(`Wallet connection stopped: ${error.message}`, true);
  }
}

async function deployNext() {
  const next = currentStep();
  if (!next || !state.owner || state.activeTransaction) return;
  state.activeTransaction = next.contract_name;
  const button = byId("deployNext");
  button.disabled = true;
  button.textContent = `Confirm ${displayName(next)} in wallet…`;
  setStepStatus(next.contract_name, "active", "Waiting for wallet confirmation");
  try {
    const txHash = await ethereum.request({
      method: "eth_sendTransaction",
      params: [walletTransaction(next)],
    });
    setStepStatus(next.contract_name, "active", `Submitted · <a href="${BSC_TESTNET_EXPLORER}/tx/${txHash}" target="_blank" rel="noreferrer">view transaction</a>`);
    button.textContent = `Confirming ${next.contract_name}…`;
    const receipt = await waitForReceipt(txHash);
    if (receipt.status !== "0x1" || (next.kind !== "funding" && !receipt.contractAddress)) {
      throw new Error(`${displayName(next)} transaction reverted`);
    }
    const result = next.kind === "funding"
      ? {
          kind: "funding",
          contract_name: next.contract_name,
          to: next.to,
          value_wei: next.value_wei,
          tx_hash: txHash,
          block_number: Number.parseInt(receipt.blockNumber, 16),
        }
      : {
          kind: "deployment",
          contract_name: next.contract_name,
          address: receipt.contractAddress,
          deployment_tx_hash: txHash,
          block_number: Number.parseInt(receipt.blockNumber, 16),
        };
    state.results.push(result);
    setStepStatus(next.contract_name, "done", `Confirmed · ${short(result.address || result.tx_hash)}`);

    if (next.contract_name === "EvidenceAnchor") {
      const registry = state.results.find((item) => item.contract_name === "AgentRegistry");
      const policy = await preparePolicy(registry.address);
      state.transactions.push({
        contract_name: policy.contract_name,
        data: policy.data,
        value: policy.value,
        policy: policy.policy,
      });
    }

    const upcoming = currentStep();
    if (upcoming) {
      setStepStatus(upcoming.contract_name, "active", "Ready to estimate and deploy");
      button.textContent = upcoming.kind === "funding"
        ? "Fund Agent wallet with 0.05 tBNB"
        : `Deploy ${upcoming.contract_name}`;
      button.disabled = false;
      await estimateNext();
    } else {
      const policy = state.transactions.find((item) => item.contract_name === "ScopedExecutionPolicy")?.policy;
      const evidence = {
        schema_version: "1.0",
        chain_id: 97,
        network: "bsc-testnet",
        deployer: state.owner,
        observed_at: new Date().toISOString(),
        contracts: Object.fromEntries(state.results.filter((item) => item.kind === "deployment").map((item) => [item.contract_name, {
          address: item.address,
          deployment_tx_hash: item.deployment_tx_hash,
          block_number: item.block_number,
        }])),
        agent_wallet_funding: state.results.find((item) => item.kind === "funding"),
        scoped_policy: policy,
      };
      byId("deploymentJson").textContent = JSON.stringify(evidence, null, 2);
      byId("deployResult").classList.remove("hidden");
      byId("deployResult").scrollIntoView({ behavior: "smooth", block: "start" });
      button.textContent = "Deployment complete";
      byId("estimatedGas").textContent = "All receipts confirmed";
      byId("deployNote").textContent = "No U, USDT or USDC was transferred. Only tBNB gas was spent.";
      toast("All three BSC Testnet deployments were confirmed.");
    }
  } catch (error) {
    button.disabled = false;
    button.textContent = `Retry ${next.contract_name}`;
    setStepStatus(next.contract_name, "active", "Stopped before a successful receipt");
    toast(`Deployment stopped: ${error.message}`, true);
  } finally {
    state.activeTransaction = null;
  }
}

byId("connectDeployWallet").addEventListener("click", connectWallet);
byId("deployNext").addEventListener("click", deployNext);

if (window.ethereum?.on) {
  ethereum.on("accountsChanged", () => location.reload());
  ethereum.on("chainChanged", () => location.reload());
}
