import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import test from "node:test";

import worker from "../src/worker.js";

const encoder = new TextEncoder();

function signature(payload, secret = "webhook-secret") {
  return `sha256=${createHmac("sha256", secret).update(payload).digest("hex")}`;
}

function request(payload, headers = {}) {
  return new Request("https://nightforge.example/webhook", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-github-delivery": "delivery-1",
      "x-github-event": "check_suite",
      "x-hub-signature-256": signature(payload),
      ...headers,
    },
    body: payload,
  });
}

function fakeDb(changes = 1) {
  const calls = [];
  return {
    calls,
    prepare(sql) {
      return {
        bind(...values) {
          calls.push({ sql, values });
          return { run: async () => ({ meta: { changes } }) };
        },
      };
    },
  };
}

test("accepts a signed check_suite once and enqueues its receipt", async () => {
  const payload = JSON.stringify({ action: "requested", check_suite: { pull_requests: [{ number: 8 }] } });
  const sent = [];
  const env = {
    NIGHTFORGE_WEBHOOK_SECRET: "webhook-secret",
    DELIVERIES: fakeDb(),
    GITHUB_EVENTS: { send: async (message) => sent.push(message) },
  };

  const response = await worker.fetch(request(payload), env);

  assert.equal(response.status, 202);
  assert.deepEqual(await response.json(), { accepted: true, delivery_id: "delivery-1" });
  assert.equal(sent.length, 1);
  assert.deepEqual(sent[0], {
    delivery_id: "delivery-1",
    event: "check_suite",
    payload,
    payload_sha256: "1b476d77d08316c4f3071e7218083e7f6e357b59e52f2a4251dd504022f02dd3",
  });
});

test("does not enqueue a duplicate delivery", async () => {
  const payload = JSON.stringify({ zen: "keep it logically awesome" });
  const sent = [];
  const env = {
    NIGHTFORGE_WEBHOOK_SECRET: "webhook-secret",
    DELIVERIES: fakeDb(0),
    GITHUB_EVENTS: { send: async (message) => sent.push(message) },
  };

  const response = await worker.fetch(request(payload, { "x-github-event": "ping" }), env);

  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { accepted: false, delivery_id: "delivery-1", duplicate: true });
  assert.deepEqual(sent, []);
});

test("rejects an invalid GitHub signature before persistence", async () => {
  const env = {
    NIGHTFORGE_WEBHOOK_SECRET: "webhook-secret",
    DELIVERIES: fakeDb(),
    GITHUB_EVENTS: { send: async () => assert.fail("queue must not be called") },
  };

  const response = await worker.fetch(request("{}", { "x-hub-signature-256": "sha256=invalid" }), env);

  assert.equal(response.status, 400);
  assert.deepEqual(await response.json(), { error: "invalid GitHub webhook signature" });
  assert.deepEqual(env.DELIVERIES.calls, []);
});

test("queue consumer transitions the linked ticket after a successful check suite", async () => {
  const calls = [];
  const githubFetch = async (url, options = {}) => {
    calls.push({ url: String(url), options });
    if (String(url).endsWith("/pulls/8")) {
      return Response.json({ body: "Ticket Issue: #19" });
    }
    if (String(url).endsWith("/issues/19") && !options.method) {
      return Response.json({ labels: [{ name: "kind:ticket" }, { name: "state:verifying" }] });
    }
    if (String(url).endsWith("/issues/19") && options.method === "PATCH") {
      return Response.json({ number: 19 });
    }
    return new Response("unexpected request", { status: 500 });
  };
  const body = JSON.stringify({
    action: "completed",
    check_suite: { conclusion: "success", pull_requests: [{ number: 8 }] },
  });
  const outcomes = [];
  const event = {
    messages: [{
      body: { event: "check_suite", payload: body },
      ack() { outcomes.push("ack"); },
      retry() { outcomes.push("retry"); },
    }],
  };
  await worker.queue(event, {
    NIGHTFORGE_GITHUB_REPOSITORY: "owner/repo",
    NIGHTFORGE_GITHUB_TOKEN: "github-token",
    DELIVERIES: fakeDb(),
    FETCH: githubFetch,
  });
  assert.deepEqual(outcomes, ["ack"]);

  const update = calls.find((entry) => entry.options.method === "PATCH");
  assert.ok(update, JSON.stringify(calls));
  assert.deepEqual(JSON.parse(update.options.body), { labels: ["kind:ticket", "state:accepted"] });
});
