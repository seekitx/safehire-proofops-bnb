import fs from "node:fs";
import path from "node:path";

const input = await new Promise((resolve, reject) => {
  let value = "";
  process.stdin.setEncoding("utf8");
  process.stdin.on("data", (chunk) => {
    value += chunk;
  });
  process.stdin.on("end", () => resolve(value));
  process.stdin.on("error", reject);
});

const payload = JSON.parse(input);

function findValue(value, names) {
  if (!value || typeof value !== "object") return null;
  for (const [key, nested] of Object.entries(value)) {
    if (names.has(key) && typeof nested === "string" && nested.length > 0) {
      return nested;
    }
  }
  for (const nested of Object.values(value)) {
    const found = findValue(nested, names);
    if (found) return found;
  }
  return null;
}

const clientId = findValue(payload, new Set(["client_id", "clientId"]));
const clientSecret = findValue(
  payload,
  new Set(["client_secret", "clientSecret"]),
);
if (!clientId || !clientSecret) {
  throw new Error("Invoke-client response did not contain both credential fields");
}

const envPath = path.join(process.cwd(), ".studio", ".env.local");
const original = fs.existsSync(envPath) ? fs.readFileSync(envPath, "utf8") : "";
const updates = new Map([
  ["BNB_INVOKE_CLIENT_ID", clientId],
  ["BNB_INVOKE_CLIENT_SECRET", clientSecret],
]);
const seen = new Set();
const lines = original.split(/\r?\n/).map((line) => {
  const match = line.match(/^([A-Z][A-Z0-9_]*)=/);
  if (!match || !updates.has(match[1])) return line;
  seen.add(match[1]);
  return `${match[1]}=${JSON.stringify(updates.get(match[1]))}`;
});
for (const [key, value] of updates) {
  if (!seen.has(key)) lines.push(`${key}=${JSON.stringify(value)}`);
}
fs.writeFileSync(envPath, `${lines.filter((line, index) => line || index < lines.length - 1).join("\n")}\n`, {
  mode: 0o600,
});
fs.chmodSync(envPath, 0o600);
process.stdout.write("Stored buyer invoke client credentials in .studio/.env.local (values hidden).\n");
