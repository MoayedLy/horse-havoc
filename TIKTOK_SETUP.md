# TikTok Content Posting API & Multi-Channel Deployment Guide

This guide details how to configure automated TikTok publishing for **HORSE HAVOC**, including official Developer Portal credential setup, chunked video upload workflows, and instant aggregator fallbacks.

---

## 1. System Architecture: Simultaneous Dispatch

When `auto_run.py` runs, it renders the 1080x1920 (9:16) short video, creates viral metadata, and dispatches to **YouTube Shorts** and **TikTok** simultaneously:
- **YouTube Shorts**: Uploads via OAuth 2.0 with `token.json`
- **TikTok**: Uploads via official TikTok Content Posting API v2 (or configured aggregator fallbacks)
- **Telegram / Discord**: Mobile notification backup with direct download link

---

## 2. Keys Required from TikTok Developer Portal

To enable direct posting via the official API, create an app in the [TikTok Developer Portal](https://developers.tiktok.com):

| Key Name | Where to find it | `.env` Variable | Description |
| :--- | :--- | :--- | :--- |
| **Client Key** | App Details -> App Credentials | `TIKTOK_CLIENT_KEY` | Public app identifier. |
| **Client Secret** | App Details -> App Credentials | `TIKTOK_CLIENT_SECRET` | Secret key used to sign OAuth requests. |
| **User Access Token** | Tools -> Access Token Generator or OAuth | `TIKTOK_ACCESS_TOKEN` | Bearer token granting `video.publish` permission. |
| **Privacy Level** | Settings | `TIKTOK_PRIVACY_LEVEL` | `PUBLIC_TO_EVERYONE`, `MUTUAL_FOLLOW_FRIENDS`, or `SELF_ONLY`. |

---

## 3. Step-by-Step Developer Portal Setup

### Step 1: Register as a TikTok Developer
1. Go to [developers.tiktok.com](https://developers.tiktok.com) and log in with your TikTok account.
2. Complete your developer registration.

### Step 2: Create a New App
1. Go to **Manage Apps** -> Click **Create an App**.
2. Set the App Name to `Horse Havoc Studio` (or your chosen brand name).
3. Select App Type: **Web / Desktop / Server**.

### Step 3: Add the Content Posting API Product
1. Under **Add Products**, select **Content Posting API**.
2. Select the required Scopes:
   - `video.upload` (initiating video chunk upload)
   - `video.publish` (publishing to creator's feed)
   - `user.info.basic` (read account profile info)

### Step 4: Generate Your Access Token
> **Note on Sandbox Mode**: During Development / Sandbox mode (before app submission approval):
> - You can immediately generate a **Developer Access Token** in your app sandbox or via the OAuth redirect flow.
> - TikTok enforces `privacy_level: "SELF_ONLY"` (Private video) during development testing so you can verify uploads without public view.
> - Once your app review is approved, set `TIKTOK_PRIVACY_LEVEL=PUBLIC_TO_EVERYONE` in `.env` to publish public TikToks.

---

## 4. Alternative Instant Fallbacks (No Developer Review Delay)

If your TikTok Developer App is pending approval, you can post immediately using one of the 3 built-in fallbacks in `publisher.py`:

### Fallback 1: Ayrshare API (Recommended)
[Ayrshare](https://www.ayrshare.com) has pre-approved enterprise TikTok API access:
1. Connect your TikTok account on Ayrshare.
2. Add your API key to `.env`:
   ```env
   AYRSHARE_API_KEY=your_ayrshare_api_key_here
   ```
3. `publisher.py` will automatically upload the video file and post to TikTok.

### Fallback 2: Buffer API
1. Connect your TikTok account in [Buffer](https://buffer.com).
2. Add your Buffer access token and profile ID to `.env`:
   ```env
   BUFFER_ACCESS_TOKEN=your_buffer_token_here
   BUFFER_PROFILE_ID=your_buffer_profile_id_here
   ```

### Fallback 3: Make.com / Zapier / n8n Webhook
1. Create a webhook trigger in Make or Zapier that accepts a multipart video file and posts it to TikTok.
2. Add the webhook URL to `.env`:
   ```env
   TIKTOK_WEBHOOK_URL=https://hook.eu1.make.com/your_webhook_id
   ```

---

## 5. CLI Usage & Platform Toggles

Run simultaneous or individual platform uploads directly from the command line:

```bash
# 1. Full automated match published to BOTH YouTube Shorts & TikTok simultaneously
python auto_run.py

# 2. Publish to YouTube Shorts only (skip TikTok)
python auto_run.py --no-tiktok

# 3. Publish to TikTok only (skip YouTube Shorts)
python auto_run.py --no-youtube

# 4. Fast 10-second test match with live upload
python auto_run.py --test --live-upload

# 5. Direct standalone TikTok upload test with existing video
python publisher.py --tiktok -v final_short.mp4
```

