import { envLocalPath, loadEnv } from "@bnbagent/studio-runtime/config";
import { get8183Client } from "@bnbagent/studio-runtime/erc8183";
import { getWallet } from "@bnbagent/studio-runtime/wallet";

const JOB_ID = 807n;
const EXPECTED_BUYER = "0xe144264e2b71ec885cb10a10c6881b45fdf54f5f";
const EXPECTED_AGENT = "0x7ca564102be3c107eda9075f490a9bb1bb74daed";
const EXPECTED_BUDGET = 100000000000000000n;

if (process.env.CONFIRM_EXPIRED_REFUND !== "JOB_807_TO_ORIGINAL_BUYER") {
  throw new Error(
    "Refusing to send without CONFIRM_EXPIRED_REFUND=JOB_807_TO_ORIGINAL_BUYER",
  );
}

loadEnv(envLocalPath());
const wallet = getWallet();
if (wallet.address.toLowerCase() !== EXPECTED_AGENT) {
  throw new Error("Refusing to use an unexpected refund-trigger wallet");
}

const client = await get8183Client("bsc-testnet");
const job = await client.getJob(JOB_ID);
if (String(job.client).toLowerCase() !== EXPECTED_BUYER) {
  throw new Error("Refusing: refund recipient is not the approved buyer");
}
if (BigInt(job.budget) !== EXPECTED_BUDGET) {
  throw new Error("Refusing: escrow budget is not exactly 0.1 U");
}
if (Number(job.status) !== 1) {
  throw new Error(`Refusing: job status is ${String(job.status)}, expected FUNDED`);
}
if (BigInt(job.expiredAt) > BigInt(Math.floor(Date.now() / 1000))) {
  throw new Error("Refusing: job has not expired yet");
}

const result = await client.claimRefund(JOB_ID);
const transactionHash = result?.transactionHash ?? result?.txHash ?? result?.hash;
if (!transactionHash) throw new Error("Refund returned no transaction hash");
process.stdout.write(
  `${JSON.stringify(
    {
      network: "bsc-testnet",
      job_id: Number(JOB_ID),
      refund_recipient: EXPECTED_BUYER,
      refunded_u: "0.1",
      transaction_hash: transactionHash,
    },
    null,
    2,
  )}\n`,
);
