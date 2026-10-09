# Morning Wire data

Feeds Alexandre's Morning Wire page with the newest videos from vetted YouTube channels.

- `scripts/channels.json` lists the channels per topic (YouTube channel IDs).
- `scripts/fetch_videos.py` reads each channel's official YouTube feed and keeps the last 7 days.
- `.github/workflows/fetch-videos.yml` runs it every 3 hours and saves `data/videos.json`.
