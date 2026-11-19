# reel-autopilot

Turns short JSON scripts into 9:16 Instagram Reels (animated text, mock Google search, AI voiceover) and posts them to Instagram on a schedule with GitHub Actions.

```
reels/*.json  ──push──▶  Preview workflow renders MP4s  ──you watch, set "approved"──▶
Publish workflow (Mon/Wed/Fri 6:45 pm IST) posts the next approved Reel and marks it "posted"
```

Nothing is posted unless you've set its status to `"approved"`.

## Day-to-day

1. **Add a Reel**: copy a file in `reels/` and edit it (format below). Keep `"status": "draft"`. Push.
2. **Watch it**: open the **Actions** tab → **Preview Reels** run → download `reel-previews` (MP4s inside).
3. **Approve**: change `"status": "draft"` to `"status": "approved"` and push.
4. **It posts** on the next scheduled run, oldest file name first. The file is updated to `"posted"` with the Instagram link.

To post right away: **Actions → Publish next Reel → Run workflow** (optionally with a Reel id, or tick *dry run* to only build).

To change the days or time, edit the `cron` line in `.github/workflows/publish.yml` (it's in UTC; IST = UTC + 5:30).

## One-time setup

### 1. Instagram professional account
In the Instagram app: **Settings → Account type and tools → Switch to professional account**. Creator or Business both work. Personal accounts can't post through the API.

### 2. Meta app and access token (Instagram Login, no Facebook Page needed)
1. Go to <https://developers.facebook.com/apps> → **Create app**. Pick the Instagram use case (managing messages and content on Instagram).
2. In the app dashboard open **Instagram → API setup with Instagram login**.
3. Under **Generate access tokens**, click **Add account** and log in with your Instagram account. If asked, accept the tester invite in Instagram (**Settings → Website permissions → Apps and websites → Tester invites**).
4. Copy the **access token** and the **Instagram user ID** shown next to your account.

The app can stay in Development mode: it only needs to post to your own account, which has a role on the app. App Review is only needed to post for other people.

### 3. Supabase bucket (temporary public link for each video)
With Instagram Login, Meta takes videos by public URL, so each Reel is uploaded to a public bucket, fetched by Instagram, then deleted.
1. Create a free project at <https://supabase.com>.
2. **Storage → New bucket** → name it `reels`, tick **Public bucket**.
3. **Project Settings → API**: copy the **Project URL** and the **service_role** key.

### 4. GitHub secrets
Repo **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Value |
|---|---|
| `IG_USER_ID` | Instagram user ID from step 2 |
| `IG_ACCESS_TOKEN` | access token from step 2 |
| `SUPABASE_URL` | Supabase Project URL |
| `SUPABASE_SERVICE_KEY` | Supabase service_role key |
| `GH_PAT` | fine-grained GitHub token for this repo only, with **Secrets: Read and write** (lets the token-renewal job save the renewed token) |

Then run **Actions → Publish next Reel → Run workflow** with *dry run* ticked to check the build, and **Renew Instagram token → Run workflow** to check the token.

### Alternative: Facebook Login (no Supabase)
If your Instagram account is linked to a Facebook Page, you can use a Page access token instead. Videos are then uploaded straight to Meta, so Supabase isn't needed. Add a repository **variable** `IG_LOGIN` = `facebook`, set `IG_USER_ID` to the Instagram business account ID and `IG_ACCESS_TOKEN` to the Page token. Page tokens made from a long-lived user token don't expire, so the renewal job switches itself off.

## Reel format

```jsonc
{
  "status": "draft",               // draft → approved → posted
  "voice": "am_michael",           // Kokoro voice (am_adam, bm_george, af_heart, ...)
  "speed": 1.08,
  "caption": "Instagram caption with #hashtags",
  "scenes": [ ... ]
}
```

Every scene has a `say` list: one voiceover line per *beat*. Each beat's text appears when its line starts speaking. `""` is a silent beat. Scenes stretch to fit the voice.

| type | fields | beats (`say` lines) |
|---|---|---|
| `statement` | `eyebrow`, `lines` (white), `accent` (lime) | 1: lines · 2: accent |
| `search` | `query`, `results` (3× `[name, sub, stars]`), `you` `{name, sub, rank}`, `punch` (red) | 1: typing · 2: punch |
| `list` | `kind` `"bad"` (red ✕) or `"good"` (lime ✓), `title`, `accent`, `items` | 1: title · then one per item |
| `rank_up` | `query`, `results`, `you` `{name, sub, stars, from_rank}`, `lines`, `accent` | 1: climb · 2: lines · 3: accent |
| `cta` | `lines`, `button`, `sub` | 1: lines · 2: button |

Keep lines short: text shrinks to fit, but 2–3 words per line reads best on a phone.

## Run locally

```bash
brew install ffmpeg            # or apt install ffmpeg
pip install -r requirements.txt
python -m reelgen.build reels/001-invisible-on-google.json            # → out/001-invisible-on-google.mp4
python -m reelgen.build reels/001-invisible-on-google.json --stills   # quick layout check, no voice
```

The voice model (~350 MB) downloads into `models/` on first use.

## Notes

- Instagram allows 100 API posts per 24 hours; this posts at most one per run.
- Music from Instagram's library can't be added through the API. The voiceover counts as original audio.
- Fonts: Inter Display, SIL Open Font License (`assets/fonts/OFL.txt`). Voice: [Kokoro](https://github.com/thewh1teagle/kokoro-onnx), Apache 2.0.
