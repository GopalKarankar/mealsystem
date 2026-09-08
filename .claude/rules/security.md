---
# Uncomment and edit `paths` to make this rule load ONLY when Claude touches
# matching files. Without `paths`, it loads at the start of every session and
# costs context on every turn.
# paths:
#   - "api/**/*.py"
#   - "server/**/*.js"
#   - "app/**/*.{js,jsx}"
#   - "src/**/*.{js,jsx}"
---

# Security Rules

Applies to any code you write, modify, or review in this repo.

**Precedence:** if a request conflicts with a rule here, say so *before* writing the code and
propose the secure version. Do not silently comply and leave a `// TODO: security` comment.
If a rule genuinely doesn't apply to the situation, state why in one line and continue.

**Stack** (edit to match the repo):
React / Next.js (JavaScript) · FastAPI (Python) · Express (Node) · MongoDB / MySQL · Qdrant.

---

## 1. Blocking — never produce this

Refuse and explain. These are not judgement calls.

- Secrets in source, config, tests, fixtures, comments, or logs. `.env` is never committed.
- SQL, shell commands, or file paths built by string concatenation/f-strings from user input.
- A user-controlled object passed straight into a Mongo query filter or `$set` document.
- An authorization decision made only in the frontend (hidden buttons, route guards, `if (user.isAdmin)` in React).
- `dangerouslySetInnerHTML` / `innerHTML` with anything not a compile-time constant.
- Disabled TLS verification: `verify=False`, `rejectUnauthorized: false`, `NODE_TLS_REJECT_UNAUTHORIZED=0`.
- Hand-rolled crypto, hand-rolled password hashing, or `==` on secrets.
  Use Argon2id (or bcrypt), `hmac.compare_digest`, `crypto.timingSafeEqual`.
- `eval`, `exec`, `pickle.loads`, `yaml.load` without `SafeLoader`, `child_process.exec` with interpolation.
- `Access-Control-Allow-Origin: *` together with credentials, or reflecting the `Origin` header.
- Returning raw DB documents to a client. Always project/serialize through an explicit response shape.

## 2. Authorization — the one that actually breaks

Most real breaches here are IDOR/BOLA, not injection. Every handler must answer:
**who is the caller, which object, which action.**

- **Deny by default.** A new route with no explicit auth dependency/middleware is a bug, not a default.
- **Filter in the query, don't fetch-then-check.** The ownership predicate belongs in the DB call:

  ```python
  # wrong
  doc = await db.orders.find_one({"_id": oid})
  if doc["user_id"] != user.id: raise HTTPException(403)

  # right — one query, no TOCTOU, no leak via timing/error shape
  doc = await db.orders.find_one({"_id": oid, "user_id": user.id})
  ```

- **Never trust these from the request body:** user id, org/tenant id, role, `is_admin`, price,
  quantity, status, `created_at`. Derive them from the session or the DB.
- **Mass assignment:** whitelist updatable fields explicitly. Never `{**req.body}` into an update.
- Multi-tenant: the tenant filter goes in *every* query, including aggregations, counts, and
  vector search. A shared helper that injects it is better than 40 hand-written filters.
- Admin/internal endpoints get the same server-side checks as public ones. Obscure paths are not auth.

## 3. Input and injection

- Validate at the boundary with a schema (Pydantic / zod), not with ad-hoc `if` checks.
  Type, max length, allowed values, and format — for every field.
- **MongoDB:** reject any user-supplied key starting with `$` or containing `.`, and coerce
  values to their expected primitive type before querying. `{"password": {"$ne": null}}` in a JSON
  body is a working auth bypass against naive handlers.
- **SQL:** parameterized queries only. Table and column names never come from input — map an
  allowlisted key to a constant.
- **Paths:** resolve, then confirm the result is inside the base directory before opening it.
- **SSRF:** any URL that originates from a user (webhooks, image fetch, RAG document loaders,
  "import from URL") must be allowlisted by host, must block private/link-local ranges, and must
  re-check after each redirect.
- **Regex:** no user-supplied patterns; watch for catastrophic backtracking in patterns you write.

## 4. Secrets and config

- Read from environment/secret manager. Validate presence at startup and fail fast, don't
  fall back to a default.
- `NEXT_PUBLIC_*` and `VITE_*` are **public** — they are inlined into the bundle. Never a server key.
- If you find a secret that was committed, say so explicitly and recommend rotation. Deleting the
  line does not remove it from git history.
- Never print a secret value, even when debugging.

## 5. Sessions, cookies, CSRF, CORS

- Cookies: `HttpOnly`, `Secure`, `SameSite=Lax` (`Strict` for admin surfaces), explicit `Max-Age`,
  narrow `Path`/`Domain`.
- Prefer cookie sessions over storing JWTs in `localStorage`. If a token must live in JS, justify it.
- Rotate the session id on login and on privilege change. Invalidate server-side on logout and on
  password change — a stateless JWT that can't be revoked is a design decision, not a detail.
- CORS: explicit origin list from config. Never wildcard with `credentials: true`.
- CSRF protection is required wherever the browser attaches credentials automatically.
  `SameSite` alone is insufficient across subdomains and for `Lax` + top-level POST edge cases.

## 6. Output, errors, headers

- Rely on framework escaping. Reach for sanitization (DOMPurify) only when rendering raw HTML is
  a real product requirement, and sanitize on render, not on save.
- CSP without `unsafe-inline` / `unsafe-eval`; use nonces or hashes. Also set `HSTS`,
  `X-Content-Type-Options: nosniff`, `Referrer-Policy`.
- Client errors: generic message + correlation id. Details go to logs. No stack traces, no driver
  errors, no distinction between "no such user" and "wrong password" in login responses.

## 7. Rate limiting and account flows

- Rate limit login, signup, OTP, password reset, search, and any LLM-backed endpoint —
  keyed per account **and** per IP.
- Password reset / email verification tokens: cryptographically random, stored hashed, single-use,
  short TTL, invalidated on use and on password change.
- Enumeration: signup, reset, and login must respond identically for existing and non-existing accounts.

## 8. File uploads

- Cap size before reading the body. Allowlist by sniffed content type, not by extension or the
  client-supplied MIME.
- Store under a generated name, outside the web root, ideally on a separate origin/bucket.
- Serve with `Content-Disposition` and a fixed content type. Uploaded files are never executed.

## 9. LLM, RAG, and agent code

- Retrieved chunks, tool results, and model output are **untrusted input**. They must never reach a
  shell, a DB query, `eval`, or an outbound HTTP call without the same validation you'd apply to a
  request body.
- The tenant/ACL filter belongs inside the vector search (e.g. a Qdrant `filter`), not applied to
  results afterwards — post-filtering still leaks via scores, counts, and latency.
- Don't embed or index secrets/PII that the caller isn't allowed to retrieve. The vector store
  inherits the access model of whatever you put in it.
- Rendering model output as HTML/markdown: sanitize it. Markdown image and link URLs are an
  exfiltration channel.
- Give agent tools the narrowest scope that works; prefer separate read and write credentials.

## 10. Dependencies

- Lockfile committed, versions pinned. Don't add a dependency for something the stdlib does.
- Verify a package actually exists and is the canonical one before importing it — do not invent
  package names.
- Flag known-vulnerable versions when you notice them; don't propose wholesale replacements
  without a concrete reason.

## 11. Logging

- **Never log:** passwords, tokens, cookies, `Authorization` headers, OTPs, full card numbers,
  or raw request bodies on auth routes.
- **Do log:** authn success/failure with user id + IP, authz denials, admin actions, rate-limit
  trips, and payment state changes — with a correlation id.

## 12. Out of scope — flag, don't implement

Raise these as findings; do not fabricate config for them:
WAF/CDN/DDoS, backup and restore testing, key rotation infrastructure, encryption at rest,
penetration testing, SIEM. If a change depends on one of these, say so and stop.

---

## Definition of done for a security-relevant diff

Before reporting completion, confirm:

1. Every new endpoint has authentication **and** an object-level authorization check.
2. Every user input is schema-validated; every query is parameterized or field-filtered.
3. No new secret, no new `console.log`/`print` of sensitive data.
4. Errors return a generic message; details only to logs.
5. State the residual risk in one or two lines. Do not claim the change is "secure".

<!-- Note for maintainers: this file is context, not enforcement. Claude can be argued out of it.
     For hard blocks (e.g. forbidding `.env` reads), use a PreToolUse hook or permissions.deny. -->
