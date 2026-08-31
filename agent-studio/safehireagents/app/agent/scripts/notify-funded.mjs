import { envLocalPath, loadEnv } from "@bnbagent/studio-runtime/config";

const PLATFORM_AGENT_ID = "01M19F53Z2SRN65TBHKWXY1K54";
const TOKEN_URL = "https://bnbagent-api.bnbchain.world/v1/oauth/token";
const A2A_URL = `https://bnbagent-api.bnbchain.world/v1/rt/${PLATFORM_AGENT_ID}/a2a`;
const JOB_ID = Number(process.env.SAFEHIRE_JOB_ID);

if (!Number.isSafeInteger(JOB_ID) || JOB_ID <= 0) {
  throw new Error("SAFEHIRE_JOB_ID must be a positive integer");
}
const confirmation = `JOB_${JOB_ID}_BSC_TESTNET`;
if (process.env.CONFIRM_NOTIFY_FUNDED !== confirmation) {
  throw new Error(
    `Refusing to notify without CONFIRM_NOTIFY_FUNDED=${confirmation}`,
  );
}

loadEnv(envLocalPath());
const clientId = process.env.BNB_INVOKE_CLIENT_ID;
const clientSecret = process.env.BNB_INVOKE_CLIENT_SECRET;
if (!clientId || !clientSecret) {
  throw new Error("Buyer invoke client credentials are not configured");
}

const tokenResponse = await fetch(TOKEN_URL, {
  method: "POST",
  headers: { "content-type": "application/x-www-form-urlencoded" },
  body: new URLSearchParams({
    grant_type: "client_credentials",
    client_id: clientId,
    client_secret: clientSecret,
    scope: `invoke:${PLATFORM_AGENT_ID}`,
  }),
  signal: AbortSignal.timeout(30_000),
});
if (!tokenResponse.ok) {
  throw new Error(`OAuth token request failed with HTTP ${tokenResponse.status}`);
}
const tokenPayload = await tokenResponse.json();
if (!tokenPayload.access_token) throw new Error("OAuth response has no access token");

const requestId = `safehire-funded-${JOB_ID}-${Date.now()}`;
const response = await fetch(A2A_URL, {
  method: "POST",
  headers: {
    authorization: `Bearer ${tokenPayload.access_token}`,
    "content-type": "application/json",
  },
  body: JSON.stringify({
    jsonrpc: "2.0",
    id: requestId,
    method: "message/send",
    params: {
      message: {
        messageId: requestId,
        role: "user",
        parts: [{ kind: "data", data: { skill: "notify_funded", job_id: JOB_ID } }],
      },
    },
  }),
  signal: AbortSignal.timeout(90_000),
});
if (!response.ok) {
  throw new Error(`Remote notify_funded failed with HTTP ${response.status}`);
}
const payload = await response.json();

function findAck(value) {
  if (typeof value === "string") {
    try {
      return findAck(JSON.parse(value));
    } catch {
      return null;
    }
  }
  if (!value || typeof value !== "object") return null;
  if (
    ["accepted", "rejected", "retry"].includes(String(value.status)) &&
    (value.job_id === undefined || Number(value.job_id) === JOB_ID)
  ) {
    return value;
  }
  for (const nested of Object.values(value)) {
    const ack = findAck(nested);
    if (ack) return ack;
  }
  return null;
}

if (payload.error) {
  throw new Error(`Remote Agent returned JSON-RPC error ${payload.error.code ?? "unknown"}`);
}
const ack = findAck(payload);
if (!ack) throw new Error("Remote Agent response did not contain a notify_funded acknowledgement");
if (ack.status !== "accepted") {
  throw new Error(`Remote Agent did not accept job ${JOB_ID}: ${ack.status}`);
}

process.stdout.write(
  `Remote Agent accepted funded job ${JOB_ID}; delivery is running asynchronously.\n`,
);
