const MAX_PAYLOAD_BYTES = 1_048_576;
const DELIVERY_ID = /^[A-Za-z0-9_-]{1,128}$/;
const ALLOWED_EVENTS = new Set(["check_suite", "ping"]);
const TICKET_LINK = /Ticket Issue:\s*#([1-9][0-9]*)/i;
const TICKET_TRANSITIONS = {
  "state:open": new Set(["state:claimed"]),
  "state:claimed": new Set(["state:open", "state:submitted"]),
  "state:submitted": new Set(["state:verifying"]),
  "state:verifying": new Set(["state:accepted", "state:rejected"]),
  "state:rejected": new Set(["state:claimed"]),
  "state:accepted": new Set(),
};

function json(document, status = 200) {
  return new Response(JSON.stringify(document), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function hex(bytes) {
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function sha256(payload) {
  return hex(new Uint8Array(await crypto.subtle.digest("SHA-256", payload)));
}

async function validSignature(payload, signature, secret) {
  if (!signature?.startsWith("sha256=")) return false;
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["verify"],
  );
  const provided = signature.slice("sha256=".length);
  if (!/^[a-f0-9]{64}$/i.test(provided)) return false;
  const bytes = Uint8Array.from(provided.match(/../g), (pair) => Number.parseInt(pair, 16));
  return crypto.subtle.verify("HMAC", key, bytes, payload);
}

function targetForCheckSuite(payload) {
  const suite = payload.check_suite ?? {};
  const pulls = suite.pull_requests ?? [];
  if (pulls.length !== 1 || !Number.isInteger(pulls[0]?.number)) {
    throw new Error("check suite must reference exactly one pull request");
  }
  if (["requested", "rerequested"].includes(payload.action)) return { pullNumber: pulls[0].number, target: "state:verifying" };
  if (payload.action === "completed") {
    return { pullNumber: pulls[0].number, target: suite.conclusion === "success" ? "state:accepted" : "state:rejected" };
  }
  throw new Error(`unsupported check_suite action: ${payload.action}`);
}

async function github(env, path, options = {}) {
  const response = await (env.FETCH ?? fetch)(`https://api.github.com${path}`, {
    ...options,
    headers: {
      accept: "application/vnd.github+json",
      authorization: `Bearer ${env.NIGHTFORGE_GITHUB_TOKEN}`,
      "x-github-api-version": "2022-11-28",
      ...(options.body ? { "content-type": "application/json" } : {}),
    },
  });
  if (!response.ok) throw new Error(`GitHub API request failed: ${response.status}`);
  return response.json();
}

async function processCheckSuite(env, payload) {
  const { pullNumber, target } = targetForCheckSuite(payload);
  const repository = env.NIGHTFORGE_GITHUB_REPOSITORY;
  if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repository ?? "")) throw new Error("invalid GitHub repository configuration");
  const pull = await github(env, `/repos/${repository}/pulls/${pullNumber}`);
  const match = TICKET_LINK.exec(pull.body ?? "");
  if (!match) throw new Error("pull request does not link a ticket issue");
  const issueNumber = Number(match[1]);
  const issue = await github(env, `/repos/${repository}/issues/${issueNumber}`);
  const labels = issue.labels.map((label) => typeof label === "string" ? label : label.name);
  const states = labels.filter((label) => label.startsWith("state:"));
  if (!labels.includes("kind:ticket") || states.length !== 1) throw new Error("ticket has invalid NightForge labels");
  if (!TICKET_TRANSITIONS[states[0]]?.has(target)) throw new Error(`invalid ticket transition: ${states[0]} -> ${target}`);
  const retained = labels.filter((label) => !label.startsWith("state:"));
  await github(env, `/repos/${repository}/issues/${issueNumber}`, {
    method: "PATCH",
    body: JSON.stringify({ labels: [...retained, target] }),
  });
  return { pullNumber, issueNumber, target };
}

async function receiveWebhook(request, env) {
  if (request.method !== "POST" || new URL(request.url).pathname !== "/webhook") return json({ error: "not found" }, 404);
  const payload = await request.arrayBuffer();
  if (payload.byteLength > MAX_PAYLOAD_BYTES) return json({ error: "webhook payload is too large" }, 400);
  const deliveryId = request.headers.get("x-github-delivery") ?? "";
  const event = request.headers.get("x-github-event") ?? "";
  if (!DELIVERY_ID.test(deliveryId)) return json({ error: "invalid GitHub delivery ID" }, 400);
  if (!ALLOWED_EVENTS.has(event)) return json({ error: `unsupported webhook event: ${event}` }, 400);
  if (!await validSignature(payload, request.headers.get("x-hub-signature-256"), env.NIGHTFORGE_WEBHOOK_SECRET)) {
    return json({ error: "invalid GitHub webhook signature" }, 400);
  }
  const payloadText = new TextDecoder().decode(payload);
  const payloadHash = await sha256(payload);
  const result = await env.DELIVERIES.prepare(
    "INSERT OR IGNORE INTO deliveries (delivery_id, event, payload_sha256, status) VALUES (?, ?, ?, 'pending')",
  ).bind(deliveryId, event, payloadHash).run();
  if (result.meta.changes === 0) return json({ accepted: false, delivery_id: deliveryId, duplicate: true }, 200);
  if (event === "check_suite") await env.GITHUB_EVENTS.send({ delivery_id: deliveryId, event, payload: payloadText, payload_sha256: payloadHash });
  return json({ accepted: true, delivery_id: deliveryId }, 202);
}

async function consumeQueue(batch, env) {
  for (const message of batch.messages) {
    const envelope = typeof message.body === "string" ? JSON.parse(message.body) : message.body;
    try {
      if (envelope.event === "check_suite") await processCheckSuite(env, JSON.parse(envelope.payload));
      await env.DELIVERIES.prepare("UPDATE deliveries SET status = 'processed', processed_at = CURRENT_TIMESTAMP, error = NULL WHERE delivery_id = ?")
        .bind(envelope.delivery_id).run();
      message.ack();
    } catch (error) {
      await env.DELIVERIES.prepare("UPDATE deliveries SET status = 'failed', error = ? WHERE delivery_id = ?")
        .bind(String(error.message ?? error), envelope.delivery_id).run();
      message.retry();
    }
  }
}

export default { fetch: receiveWebhook, queue: consumeQueue };
