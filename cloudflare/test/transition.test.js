import assert from "node:assert/strict";
import test from "node:test";

import worker from "../src/worker.js";

function fakeDb() {
  return {
    prepare() {
      return { bind: () => ({ run: async () => ({ meta: { changes: 1 } }) }) };
    },
  };
}

test("queue consumer retries instead of skipping an invalid ticket state transition", async () => {
  const calls = [];
  const githubFetch = async (url, options = {}) => {
    calls.push({ url: String(url), options });
    if (String(url).endsWith("/pulls/8")) return Response.json({ body: "Ticket Issue: #19" });
    if (String(url).endsWith("/issues/19")) return Response.json({ labels: [{ name: "kind:ticket" }, { name: "state:accepted" }] });
    return new Response("unexpected request", { status: 500 });
  };
  const outcomes = [];
  await worker.queue({
    messages: [{
      body: { event: "check_suite", payload: JSON.stringify({ action: "completed", check_suite: { conclusion: "success", pull_requests: [{ number: 8 }] } }) },
      ack() { outcomes.push("ack"); },
      retry() { outcomes.push("retry"); },
    }],
  }, {
    NIGHTFORGE_GITHUB_REPOSITORY: "owner/repo",
    NIGHTFORGE_GITHUB_TOKEN: "github-token",
    DELIVERIES: fakeDb(),
    FETCH: githubFetch,
  });

  assert.deepEqual(outcomes, ["retry"]);
  assert.equal(calls.filter((entry) => entry.options.method === "PATCH").length, 0);
});
