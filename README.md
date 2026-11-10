# 🚀 Autonomous 28-Day YouTube Shorts Scheduler

Automated, cloud-native daily publishing system for 28 high-retention Roblox story shorts.

Powered by **GitHub Actions** + **YouTube Data API v3**.

---

## ⚡ Architecture

- **Trigger**: Runs automatically every single day at **18:00 UTC** via GitHub Actions cron.
- **Manual Trigger**: Supports `workflow_dispatch` with custom Day selection (`1-28` or `auto`), privacy toggle (`public`, `unlisted`, `private`), and dry-run testing.
- **Self-Tracking**: Automatically marks published entries in `manifest.json` and pushes the updated status back to the repository without triggering recursion (`[skip ci]`).

---

## 📦 Master Video Queue (28 Days)

| Day | Video File | Story Hook | Size | Status |
|:---:|---|---|:---:|:---:|
| **01** | `videos/day_01_stroke_speed.mp4` | Every stroke doubles your speed | 28.8 MB | Queued |
| **02** | `videos/day_02_school_bus.mp4` | School bus with 29 kids but 28 seats | 21.5 MB | Queued |
| **03** | `videos/day_03_town_story.mp4` | In This Town, Every Living Thing Stops | 30.8 MB | Queued |
| **04** | `videos/day_04_town_story.mp4` | One Cereal Box Costs $1,000,000 | 44.2 MB | Queued |
| **05** | `videos/day_05_town_story.mp4` | You Get Paid For Every Tear | 18.4 MB | Queued |
| **06** | `videos/day_06_town_story.mp4` | One Person Gets Erased Daily | 19.0 MB | Queued |
| **07** | `videos/day_07_town_story.mp4` | Poor People Become Invisible | 17.6 MB | Queued |
| **08** | `videos/day_08_town_story.mp4` | Everyone Lives In Glass Rooms | 21.2 MB | Queued |
| **09** | `videos/day_09_town_story.mp4` | Paid For Every Word You Say | 19.7 MB | Queued |
| **10** | `videos/day_10_town_story.mp4` | Everyone Is A Night Monster | 21.7 MB | Queued |
| **11** | `videos/day_11_town_story.mp4` | Enter Any House Once | 20.0 MB | Queued |
| **12** | `videos/day_12_town_story.mp4` | Must Choose One Color | 14.7 MB | Queued |
| **13** | `videos/day_13_town_story.mp4` | Must Choose A Superpower | 17.0 MB | Queued |
| **14** | `videos/day_14_town_story.mp4` | Everyone Lives 1000 Years | 23.5 MB | Queued |
| **15** | `videos/day_15_town_story.mp4` | Touching Ground Costs You | 17.5 MB | Queued |
| **16** | `videos/day_16_town_story.mp4` | Everyone Believes One Lie | 22.2 MB | Queued |
| **17** | `videos/day_17_town_story.mp4` | Nobody Is Allowed To Sleep | 16.7 MB | Queued |
| **18** | `videos/day_18_town_story.mp4` | The Rich Live Above Clouds | 21.9 MB | Queued |
| **19** | `videos/day_19_town_story.mp4` | The Rich Control The Sun | 23.9 MB | Queued |
| **20** | `videos/day_20_town_story.mp4` | Everyone Has A Bounty | 19.3 MB | Queued |
| **21** | `videos/day_21_town_story.mp4` | Everyone Has A Secret Badge | 14.7 MB | Queued |
| **22** | `videos/day_22_town_story.mp4` | Something Different Happens At Midnight | 11.7 MB | Queued |
| **23** | `videos/day_23_town_story.mp4` | The Sun Never Sets | 25.5 MB | Queued |
| **24** | `videos/day_24_rewind_button.mp4` | One rewind button in your whole life | 12.8 MB | Queued |
| **25** | `videos/day_25_fade_away.mp4` | Unmentioned for 24h = fade away | 16.1 MB | Queued |
| **26** | `videos/day_26_turn_gray.mp4` | Grownups slowly turn gray | 21.1 MB | Queued |
| **27** | `videos/day_27_bravest_deed.mp4` | Name is your bravest deed | 16.3 MB | Queued |
| **28** | `videos/day_28_ground_costs_10.mp4` | Touching ground costs $10 every step | 11.8 MB | Queued |

---

## 🔐 Configured GitHub Secrets

Configured directly in the repository settings:
- `YT_CLIENT_ID`: Google Cloud OAuth Client ID
- `YT_CLIENT_SECRET`: Google Cloud OAuth Client Secret
- `YT_REFRESH_TOKEN`: Long-lived OAuth 2.0 Refresh Token

---

## 🛠️ Local Testing

```bash
# Dry run check (validates video file & manifest without uploading)
python publish.py --day auto --dry-run

# Upload specific day
python publish.py --day 1 --privacy unlisted
```
