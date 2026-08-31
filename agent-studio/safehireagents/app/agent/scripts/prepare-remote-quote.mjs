import fs from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";

import { ERC8183Client } from "@bnbagent/sdk";
import {
  buildJobDescription,
  verifyQuoteSignature,
} from "@bnbagent/sdk/erc8183";
import { envLocalPath, loadEnv } from "@bnbagent/studio-runtime/config";
import { erc8183Network } from "@bnbagent/studio-runtime/erc8183";

const PLATFORM_AGENT_ID = "01M19F53Z2SRN65TBHKWXY1K54";
const TOKEN_URL = "https://bnbagent-api.bnbchain.world/v1/oauth/token";
const A2A_URL = `https://bnbagent-api.bnbchain.world/v1/rt/${PLATFORM_AGENT_ID}/a2a`;
const PROVIDER = "0x7ca564102be3C107EdA9075F490a9bB1bb74daED";
const EXPECTED_PRICE = "100000000000000000";
const projectRoot = path.resolve(process.cwd(), "../../../..");

const defaultTaskDefinition = {
  task_description:
    "Review a bounded BSC Testnet DeFi action and return risk gates, evidence references, and a safe execution recommendation.",
  terms: {
    deliverables:
      "A concise risk assessment with explicit allow, deny, and evidence conditions.",
    quality_standards:
      "Use BSC Testnet evidence only, label unknown data, and never claim an unverified execution.",
    success_criteria: [
      "State the risk decision.",
      "Cite the supporting evidence.",
      "List every required human confirmation.",
    ],
  },
};

function loadTaskDefinition() {
  const rawPath = process.env.SAFEHIRE_TASK_FILE?.trim();
  if (!rawPath) {
    return { definition: defaultTaskDefinition, sourcePath: null, sourceSha256: null };
  }

  const candidate = path.resolve(projectRoot, rawPath);
  const relative = path.relative(projectRoot, candidate);
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    throw new Error("SAFEHIRE_TASK_FILE must stay inside the SafeHire project root");
  }
  const stat = fs.statSync(candidate);
  if (!stat.isFile() || stat.size === 0) {
    throw new Error("SAFEHIRE_TASK_FILE must point to a non-empty JSON file");
  }
  const raw = fs.readFileSync(candidate, "utf8");
  const parsed = JSON.parse(raw);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("TermiX task definition must be a JSON object");
  }
  const taskDescription = String(parsed.task_description ?? "").trim();
  const terms = parsed.terms;
  if (taskDescription.length < 40) {
    throw new Error("task_description must contain at least 40 characters");
  }
  if (!terms || typeof terms !== "object" || Array.isArray(terms)) {
    throw new Error("task terms must be an object");
  }
  for (const key of ["deliverables", "quality_standards"]) {
    if (String(terms[key] ?? "").trim().length < 20) {
      throw new Error(`terms.${key} must contain at least 20 characters`);
    }
  }
  if (
    !Array.isArray(terms.success_criteria) ||
    terms.success_criteria.length < 2 ||
    terms.success_criteria.some((item) => String(item).trim().length < 8)
  ) {
    throw new Error("terms.success_criteria must contain at least two specific items");
  }
  return {
    definition: { task_description: taskDescription, terms },
    sourcePath: relative,
    sourceSha256: createHash("sha256").update(raw, "utf8").digest("hex"),
  };
}

loadEnv(envLocalPath());
const clientId = process.env.BNB_INVOKE_CLIENT_ID;
const clientSecret = process.env.BNB_INVOKE_CLIENT_SECRET;
if (!clientId || !clientSecret) {
  throw new Error("Buyer invoke client credentials are not configured");
}

const tokenBody = new URLSearchParams({
  grant_type: "client_credentials",
  client_id: clientId,
  client_secret: clientSecret,
  scope: `invoke:${PLATFORM_AGENT_ID}`,
});
const tokenResponse = await fetch(TOKEN_URL, {
  method: "POST",
  headers: { "content-type": "application/x-www-form-urlencoded" },
  body: tokenBody,
  signal: AbortSignal.timeout(30_000),
});
if (!tokenResponse.ok) {
  throw new Error(`OAuth token request failed with HTTP ${tokenResponse.status}`);
}
const tokenPayload = await tokenResponse.json();
if (!tokenPayload.access_token) throw new Error("OAuth response has no access token");

const taskSource = loadTaskDefinition();
const task = taskSource.definition.task_description;
const request = {
  jsonrpc: "2.0",
  id: `safehire-${Date.now()}`,
  method: "message/send",
  params: {
    message: {
      messageId: `safehire-message-${Date.now()}`,
      role: "user",
      parts: [
        {
          kind: "data",
          data: {
            skill: "negotiate",
            task_description: task,
            terms: taskSource.definition.terms,
          },
        },
      ],
    },
  },
};
const quoteResponse = await fetch(A2A_URL, {
  method: "POST",
  headers: {
    authorization: `Bearer ${tokenPayload.access_token}`,
    "content-type": "application/json",
  },
  body: JSON.stringify(request),
  signal: AbortSignal.timeout(90_000),
});
if (!quoteResponse.ok) {
  throw new Error(`Remote negotiate failed with HTTP ${quoteResponse.status}`);
}
const responsePayload = await quoteResponse.json();
const outputDir = path.join(projectRoot, ".data", "erc8183");
fs.mkdirSync(outputDir, { recursive: true, mode: 0o700 });

function findEnvelope(value) {
  if (typeof value === "string") {
    try {
      return findEnvelope(JSON.parse(value));
    } catch {
      return null;
    }
  }
  if (!value || typeof value !== "object") return null;
  if (value.negotiation_hash && value.provider_sig) return value;
  for (const nested of Object.values(value)) {
    const found = findEnvelope(nested);
    if (found) return found;
  }
  return null;
}

const envelope = findEnvelope(responsePayload);
if (!envelope) {
  fs.writeFileSync(
    path.join(outputDir, "last-a2a-response.json"),
    `${JSON.stringify(responsePayload, null, 2)}\n`,
    { mode: 0o600 },
  );
  throw new Error(
    "Remote A2A response did not contain a signed quote; response saved locally for structural inspection",
  );
}
const price = String(envelope.response?.terms?.price ?? envelope.price ?? "");
if (price !== EXPECTED_PRICE) {
  throw new Error(`Refusing unexpected quote price ${price || "<missing>"}`);
}
const network = erc8183Network("bsc-testnet");
const client = await ERC8183Client.create({ network });
const description = buildJobDescription(envelope);
const verdict = await verifyQuoteSignature({
  envelope: JSON.parse(description),
  provider: PROVIDER,
  publicClient: client.publicClient,
  expectedVerifyingContract: network.commerceContract,
});
if (!verdict.valid) {
  throw new Error(`Signed quote verification failed: ${verdict.reason}`);
}
const disputeWindowSeconds = Number(await client.policy.disputeWindow());
const expiresAt = Math.floor(Date.now() / 1000) + disputeWindowSeconds + 1800;

fs.writeFileSync(
  path.join(outputDir, "browser-plan.json"),
  `${JSON.stringify(
    {
      schema_version: "1.0",
      network: "bsc-testnet",
      chain_id: 97,
      buyer: "0xe144264e2b71ec885cb10a10c6881b45fdf54f5f",
      provider: PROVIDER,
      price_raw: EXPECTED_PRICE,
      price_u: "0.1",
      task,
      terms: taskSource.definition.terms,
      task_definition_path: taskSource.sourcePath,
      task_definition_sha256: taskSource.sourceSha256,
      description,
      quote: envelope,
      negotiation_hash: envelope.negotiation_hash,
      commerce_address: network.commerceContract,
      router_address: network.routerContract,
      policy_address: network.policyContract,
      token_address: "0xc70B8741B8B07A6d61E54fd4B20f22Fa648E5565",
      expires_at: expiresAt,
      dispute_window_seconds: disputeWindowSeconds,
      endpoint: A2A_URL,
      quote_verified: true,
      prepared_at: new Date().toISOString(),
    },
    null,
    2,
  )}\n`,
  { mode: 0o600 },
);
process.stdout.write(
  `Prepared a verified 0.1 U quote for browser funding (hash ${String(envelope.negotiation_hash).slice(0, 12)}…).\n`,
);
