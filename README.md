# reel-autopilot

Turns short JSON scripts into 9:16 Instagram Reels (animated text, mock Google search, AI voiceover) and posts them to Instagram on a schedule. GitHub Actions renders each Reel, GitHub Pages hosts the MP4, and Buffer publishes it.

```
reels/*.json  ──push──▶  Preview workflow renders MP4s  ──you watch, set "approved"──▶
Publish workflow (daily 6:45 pm IST): build → GitHub Pages → Buffer → Instagram → mark "posted"
```

Nothing is posted unless you've set its status to `"approved"`.

## Day-to-day

1. **Add a Reel**: copy a file in `reels/` and edit it (format below). Keep `"status": "draft"`. Push.
2. **Watch it**: open the **Actions** tab → **Preview Reels** run → download `reel-previews` (MP4s inside).
3. **Approve**: change `"status": "draft"` to `"status": "approved"` and push.
4. **It posts** on the next scheduled run, oldest file name first. The file is updated to `"posted"` with the Instagram link.

Statuses: `draft` → `approved` → `posted`. Two others can appear: `submitted` (Buffer accepted it but hadn't finished publishing when the job stopped waiting; check Buffer) and `failed` (Buffer reported an error, saved in the file's `error` field; fix it and set `approved` again to retry).

To post right away: **Actions → Publish next Reel → Run workflow** (optionally with a Reel id, or tick *dry run* to only build).

To change the days or time, edit the `cron` line in `.github/workflows/publish.yml` (it's in UTC; IST = UTC + 5:30).

## One-time setup (about 10 minutes)

### 1. Instagram professional account
In the Instagram app: **Settings → Account type and tools → Switch to professional account**. Creator or Business both work.

### 2. Buffer
1. Sign up at <https://buffer.com> (the free plan includes one API key) and connect your Instagram account as a channel.
2. **Settings → API** → create a personal API key and copy it.

### 3. GitHub Pages
Repo **Settings → Pages → Build and deployment → Source: GitHub Actions**. That's all: the publish job deploys each Reel's MP4 to `https://<you>.github.io/reel-autopilot/` just before posting, which gives Buffer the direct public link it needs. Pages is free for public repos; a private repo needs a paid GitHub plan for this.

### 4. GitHub secret
Repo **Settings → Secrets and variables → Actions → New repository secret**: `BUFFER_API_KEY` = your Buffer key.

If your Buffer account has more than one Instagram channel, also add a repository **variable** `BUFFER_CHANNEL_ID` (get the id from the next step). With one Instagram channel it's found automatically.

### 5. Check it
1. **Actions → List Buffer channels → Run workflow**: should list your Instagram channel. This confirms the key works.
2. **Actions → Publish next Reel → Run workflow** with *dry run* ticked: confirms the build works.
3. Approve one Reel and run **Publish next Reel** without dry run. It should appear on Instagram within a few minutes.

## Reel format

```jsonc
{
  "status": "draft",               // draft → approved → posted
  "cover_ms": 2600,                // optional: frame used as the Reel's cover, in ms
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

- Posting goes through Buffer's API (`reelgen/buffer.py`). Buffer accepts a post instantly but fetches and publishes the video afterwards, so the job waits until Buffer reports it `sent` before marking it posted.
- Buffer's free plan allows 600 API requests a day; each post uses about 10.
- Music from Instagram's library can't be added through the API. The voiceover counts as original audio.
- Each publish run replaces the Pages site with only the current Reel's MP4, so the site never fills up.
- Fonts: Inter Display, SIL Open Font License (`assets/fonts/OFL.txt`). Voice: [Kokoro](https://github.com/thewh1teagle/kokoro-onnx), Apache 2.0.
