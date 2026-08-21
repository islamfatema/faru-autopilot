# Faru Autopilot

Generates and publishes short-form videos to three YouTube channels on a schedule,
using GitHub Actions.

| Channel | Folder | Schedule |
|---|---|---|
| History That Explains the World | `autopilot_history` | 5 runs/day, 2 videos each |
| FaRu Facts | `autopilot_fun` | 5 runs/day, 2 videos each |
| Rise With Fate | `autopilot_us` | 5 runs/day, 2 videos each |

`analytics/` pulls each channel's real view counts daily, normalises them to
views-per-day, and writes `winners_<channel>.json`. The generators read that file
and weight their topic rotation 2:1 toward the tags that are actually performing.

Everything is built with free tooling: edge-tts for voice, Pollinations for AI
images, Pexels for stock footage, ffmpeg for compositing.

## Secrets required

These are set in **Settings -> Secrets and variables -> Actions**. They are never
stored in this repository.

| Secret | Used by |
|---|---|
| `YT_REFRESH_TOKEN_HISTORY` | history shorts + documentaries |
| `YT_REFRESH_TOKEN` | FaRu Facts shorts |
| `YT_REFRESH_TOKEN_US` | Rise With Fate shorts |

## Why this repository is public

GitHub gives unlimited free Actions minutes to public repositories, and only
2,000 per month to private ones. Posting 10 videos a day needs far more than
that. No credentials live here - the OAuth tokens are repository secrets, and
the subscription, payment and API code lives in a separate private repository.
