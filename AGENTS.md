# Repository guidance and project spec

## Purpose and boundaries

- This is the separate Python worker for the Next.js chat app at `C:\Users\umasr\Videos\learnings\next-react`.
- The production process is a Vercel Daemon configured in `vercel.json`, built from `Dockerfile`, and started by `app.worker_main`. Do not rely on a request-driven FastAPI Function to keep the consumer alive.
- `app.main:app` and `/health` remain for local FastAPI development. Daemons do not serve HTTP; check production worker logs in Vercel.
- `app/response_builder.py` returns demo text/chart/table responses. AI/SQL integration is a TODO, not implemented.
- There is no chat-history database. Vercel Queues and Redis Pub/Sub are transient delivery only.

## Message flow and contract

1. Next.js authenticates a Socket.IO client and enqueues `{ messageId, userId, text, createdAt }` to Vercel Queue topic `chat-messages`.
2. `app/queue_worker.py` polls that topic using consumer group `chat-python-worker`. It requires nonempty string `userId`, `messageId`, and `text`.
3. The worker builds a response and POSTs `{ userId, messageId, response }` to `<NEXT_API_BASE_URL>/api/chat/results`, with `Authorization: Bearer <NEXT_CHAT_CALLBACK_SECRET>`.
4. Next.js validates the callback and publishes on Redis channel `chat:responses`; Next.js Socket.IO subscribers emit `chat:response` to the room named by `userId`.

Redis is not the Python input transport. Missing worker receive logs point to the Vercel Queue/Daemon path. Keep `messageId` and `userId` unchanged end to end; `userId` must match the authenticated Next.js Socket.IO room.

## Deployment configuration

- Set `CHAT_QUEUE_REGION` to the same fixed queue region in Next.js and the worker, and to the Vercel Queue resource's region. Both currently default to `iad1`.
- Deploy the worker as a Vercel Daemon using the checked-in `vercel.json` and `Dockerfile`; Daemons are production background processes and do not serve `/health`.
- Leave `VERCEL_QUEUE_TOKEN` unset in Vercel; it overrides SDK OIDC resolution. Never paste a short-lived OIDC token there. The SDK resolves deployment OIDC and supports `VERCEL_OIDC_TOKEN_FILE` for rotating token files. Vercel automatically sets `VERCEL_DEPLOYMENT_ID` to the worker deployment, which will not match the separate Next.js deployment. The worker therefore polls all producer deployment partitions by default; only set the app-specific `CHAT_QUEUE_DEPLOYMENT_ID` when intentionally pinning to one partition.
- Set `NEXT_API_BASE_URL` to the reachable Next.js deployment URL without a trailing slash. `localhost` is only correct when running the apps locally.
- Set the same `NEXT_CHAT_CALLBACK_SECRET` in the worker and Next.js. Next.js also needs `REDIS_URL` for response fan-out.
- Do not run multiple independent worker copies with `chat-python-worker` unless shared consumption is intended. Queue delivery is at least once; handlers must tolerate retries.
- Do not log, copy, or commit secret values. `.env` is local-only; document variable names in `.env.example`.

## Failure isolation

- No `Received chat message ...` in daemon logs: verify the daemon is running, Vercel Queue token/OIDC, topic, matching region, and deployment scope. A Next.js `chat:ack accepted: true` confirms enqueue only.
- Received message but callback failure: verify `NEXT_API_BASE_URL`, network reachability, callback availability, matching callback secret, and Next.js logs. Callback errors are raised so the queue can retry.
- Callback accepted but no browser response: inspect Next.js Redis publisher/subscriber logs, `REDIS_URL`, live Socket.IO subscriber(s), and the same `userId` room. Redis publishes with zero subscribers are treated as failures.

### Local queue setup

- Use the standalone Python Queue devserver for local cross-process queueing. Set `VERCEL_QUEUE_BASE_URL` to its base URL and `VERCEL_QUEUE_TOKEN=local-token` in both local env files.
- Local development does not require cloud OIDC credentials or Redis. Leave the local broker variables unset in Vercel deployments so both SDKs use hosted Vercel Queues and platform-managed credentials.


