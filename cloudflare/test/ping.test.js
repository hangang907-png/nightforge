import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import test from "node:test";

import worker from "../src/worker.js";

test("records an accepted ping as processed without queueing it", async () => {
  const calls = [];
  const payload = "{}";
  const env = {
    NIGHTFORGE_WEBHOOK_SECRET: "secret",
    DELIVERIES: {
      prepare(sql) {
        return {
          bind(...values) {
            calls.push({ sql, values });
            return { run: async () => ({ meta: { changes: 1 } }) };
          },
        };
      },
    },
    GITHUB_EVENTS: { send: async () => assert.fail("ping must not queue") },
  };
  const response = await worker.fetch(new Request("https://nightforge-webhook.oldcatwhite.workers.dev/webhook", {
    method: "POST",
    headers: {
      "x-github-delivery": "ping-processed",
      "x-github-event": "ping",
      "x-hub-signature-256": `sha256=${createHmac("sha256", "secret").update(payload).digest("hex")}`,
    },
    body: payload,
  }), env);

  assert.equal(response.status, 202);
  assert.equal(calls[0].values[3], "processed");
});
