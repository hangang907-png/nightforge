# Cloudflare webhook deployment

NightForge can run its public GitHub webhook without AWS, a VM, or a custom domain.

Runtime:

- Cloudflare Worker: verifies `X-Hub-Signature-256`, validates the 1 MiB payload ceiling, and immediately returns `202`.
- Cloudflare D1: one immutable `delivery_id` receipt per GitHub delivery. `INSERT OR IGNORE` makes retries idempotent.
- Cloudflare Queue: separates GitHub's webhook deadline from the GitHub API state transition. Failed work retries up to five times.
- `workers.dev`: avoids custom-domain registration and renewal.
- GitHub Actions: runs the Python and Worker test suites, then validates the Worker deployment bundle.

The Worker only accepts `POST /webhook` and the `ping`/`check_suite` event allowlist. It queues `check_suite`; `ping` is persisted and acknowledged but has no state mutation.

## One-time setup

```bash
cd /home/je/project/nightforge/cloudflare
npm ci
npx wrangler login
npx wrangler queues create nightforge-github-events
npx wrangler d1 create nightforge-deliveries
```

Copy the returned D1 UUID into `wrangler.toml` as `database_id`. Then create the schema:

```bash
npx wrangler d1 execute nightforge-deliveries --remote --file=schema.sql
```

Set runtime secrets. Use a dedicated fine-grained GitHub token limited to the opted-in repository: Issues read/write and Pull requests read. Do not commit either secret.

```bash
npx wrangler secret put NIGHTFORGE_WEBHOOK_SECRET
npx wrangler secret put NIGHTFORGE_GITHUB_TOKEN
npx wrangler deploy
```

The deploy output provides a URL such as `https://nightforge-webhook.<account>.workers.dev`. In the GitHub repository's Settings → Webhooks, add:

- Payload URL: `https://nightforge-webhook.<account>.workers.dev/webhook`
- Content type: `application/json`
- Secret: exactly `NIGHTFORGE_WEBHOOK_SECRET`
- Events: **Check suites**
- Active: enabled

GitHub sends a signed `ping` during creation. Verify the D1 receipt:

```bash
npx wrangler d1 execute nightforge-deliveries --remote \
  --command "SELECT delivery_id, event, status, received_at FROM deliveries ORDER BY received_at DESC LIMIT 10"
```

## Zero-touch safeguards

- Set a Cloudflare Workers CPU limit and account billing notification before deployment.
- Use `workers.dev`; no DNS or domain renewal dependency exists.
- Review the GitHub token expiration date. The current adapter supports a fine-grained token for parity with the AWS adapter; migrate to a GitHub App installation token before unattended operation beyond the token's lifetime.
- A Queue message that cannot transition a ticket is marked `failed` in D1 and retried five times. Inspect failures with the query above.
- Do not delete receipt rows while GitHub might still retry the delivery. Keep at least 30 days; add a retention Cron cleanup only after real traffic is observed.

## Local verification

```bash
npm test
npx wrangler deploy --dry-run
```

Official references:

- Workers pricing and CPU limits: https://developers.cloudflare.com/workers/platform/pricing/
- D1: https://developers.cloudflare.com/d1/
- Queues: https://developers.cloudflare.com/queues/
- GitHub webhook security: https://docs.github.com/webhooks/using-webhooks/validating-webhook-deliveries
