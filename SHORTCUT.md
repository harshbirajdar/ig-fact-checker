# iOS Shortcut setup

The iOS Shortcut is the "button" users press from Instagram's share sheet. It POSTs the shared Instagram URL to your backend and renders the HTML verdict card using Quick Look.

There are two ways to set this up:

- **Easy path** — install the author's shortcut template via iCloud link, then change one URL. Best for anyone who doesn't want to fiddle with Shortcuts internals.
- **DIY path** — build it from scratch following the action list. Best if the iCloud template is unavailable, if you want to understand the plumbing, or if you're on a restricted iOS build that blocks third-party shortcut downloads.

Both paths end in the same working Shortcut.

---

## Easy path — install the template

> **Note:** this template points at the author's backend. You **must** change the URL in step 2 to point at your own Cloud Run service, otherwise your checks will hit someone else's API quota.

1. **On your iPhone**, tap this link: **(iCloud link to be added by maintainer — see footnote)**
2. iOS opens the Shortcut preview. Tap **Add Shortcut**.
3. Open the Shortcuts app → find **Fact Check** → tap the **(i)** info icon at the top.
4. Tap the **Get Contents of** action → change the URL to your own Cloud Run URL from step 6 of [README.md](README.md) self-hosting, then append `/check?url=`. It should look like:
   `https://fact-check-xxxxxx-uc.a.run.app/check?url=`
5. Save. Done.

**Test it:** open Instagram → any public reel → paper-plane → Share to… → your Shortcut should appear near the top of the row.

> Maintainer note: if you haven't exported your Shortcut's iCloud link yet, open the Shortcut → "…" menu → **Share** → **Copy iCloud Link** → paste it into this file in a PR. Once there, the easy path actually works.

---

## DIY path — build from scratch

Takes about 5 minutes in the Shortcuts app on iPhone.

### Actions (in order)

1. **Get URLs from Input**
   - Input source: **Share Sheet**
   - Accept types: **URLs** (uncheck everything else)

2. **URL Encode** — encodes the IG URL so it can be safely appended to a query string.
   - Input: **Provided Input** (the URL from step 1)
   - Output variable name: `EncodedURL` (auto)

3. **Text**
   - Content: `https://fact-check-xxxxxx-uc.a.run.app/check?url=`
   - Replace `xxxxxx` with your Cloud Run service suffix. Found in the deploy output (step 6 of the self-hosting guide).

4. **Combine Text** (implicit — the next action concatenates the Text block with the URL Encoded variable)

   Alternatively, use a single **Text** action with inline variable:
   - Content: `https://fact-check-xxxxxx-uc.a.run.app/check?url=` `{URL Encoded}`

5. **Get Contents of URL**
   - URL: the combined text from step 4
   - Method: **GET**
   - Headers: none
   - Request body: none
   - Timeout: 30 sec (under "Advanced")

6. **Quick Look**
   - Input: the response from step 5

### Shortcut settings

- Tap the "..." menu → **Details** →
  - **Show in Share Sheet:** ✅ ON
  - **Accepted types:** **URLs** only (uncheck the rest)
  - **Show Action Button:** optional (places it in Action Button options on iPhone 15 Pro+)
- Name the shortcut **Fact Check**.
- Pick an icon + color — this is what shows up in Instagram's share sheet.

### Common mistakes

| Symptom | Likely cause |
|---|---|
| Shortcut doesn't appear in Instagram's share sheet | "Show in Share Sheet" is off, OR "Accepted types" doesn't include URLs |
| Empty/white Quick Look | Request hit the server but response was empty or non-HTML. Check Cloud Run logs. |
| "Sorry, unable to process!" | Either the IG URL is private/deleted, IG rate-limited your server's IP, or backend had a genuine error. See PRD §5.7. |
| Redirect to Safari instead of Quick Look | You used **Open URL** instead of **Get Contents of URL**. Rebuild action 5. |
| "The operation couldn't be completed" (iOS error) | Usually a timeout. Raise the timeout on action 5 or check that your Cloud Run service is up. |

---

## What the Shortcut actually sends

For debugging, here's the exact HTTP request your Cloud Run service will see:

```
GET /check?url=https%3A%2F%2Fwww.instagram.com%2Fp%2FSHORTCODE%2F HTTP/1.1
Host: fact-check-xxxxxx-uc.a.run.app
User-Agent: <iOS default>
```

No auth header, no body. The backend extracts the shortcode from the `url` query param and runs the pipeline.

If you want to add a shared-secret token (recommended for any instance shared with more than a handful of people), add a **Headers** entry in action 5:

```
Authorization: Bearer <your-random-secret>
```

…and validate it server-side in `backend/main.py`. Not wired up in the default codebase — small change to add.
