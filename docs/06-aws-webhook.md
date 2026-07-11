# AWS Lambda webhook receiver

`infra/template.yaml` deploys the NightForge webhook receiver as AWS Lambda + API Gateway + DynamoDB.

Security properties:

- GitHub `X-Hub-Signature-256` is verified before any receipt or GitHub API action.
- `delivery_id` is the DynamoDB partition key and is written with
  `attribute_not_exists(delivery_id)`. A replay receives `200` and causes no second state transition.
- The Lambda accepts only `POST /webhook`, `ping`, and `check_suite` payloads of at most 1 MiB.
- DynamoDB uses on-demand billing and server-side encryption.
- GitHub access uses a dedicated fine-grained token in Lambda environment variables; the runtime never requires the `gh` CLI.

Prerequisites:

- AWS SAM CLI configured with a deployment-capable AWS profile.
- An opted-in NightForge repository.
- A dedicated fine-grained GitHub token limited to that repository with:
  - Issues: Read and write
  - Pull requests: Read
- A random webhook secret. Do not put either secret in source control or shell history.

Validate and deploy:

```bash
cd /home/je/project/nightforge
sam validate --template-file infra/template.yaml
sam build --template-file infra/template.yaml
sam deploy --guided \
  --stack-name nightforge-webhook \
  --parameter-overrides \
    GitHubRepository=hangang907-png/nightforge \
    GitHubWebhookSecret='set-interactively' \
    GitHubToken='set-interactively'
```

After deployment, retrieve the endpoint and configure GitHub:

```bash
aws cloudformation describe-stacks --stack-name nightforge-webhook \
  --query "Stacks[0].Outputs[?OutputKey=='WebhookUrl'].OutputValue" --output text
```

In GitHub repository settings → Webhooks, add that URL with:

- Content type: `application/json`
- Secret: the exact `GitHubWebhookSecret` deployment parameter
- Events: **Check suites** (the GitHub `ping` event is accepted during setup)
- Active: enabled

GitHub's `check_suite` events are then mapped into ticket labels only when the related PR body contains `Ticket Issue: #<number>`.

Operational check:

```bash
aws logs tail /aws/lambda/nightforge-webhook-WebhookFunction --follow
```

Do not rotate a GitHub webhook secret by editing the template. Update the CloudFormation parameter and GitHub webhook configuration together, then send a signed `ping` test.
