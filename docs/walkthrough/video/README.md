# Walkthrough Video Artifact

This folder is a lightweight scaffold for generating a product walkthrough video from the public-safe screenshots in `docs/screenshots/`.

The intended flow is Remotion-compatible, but Vantage does not require Remotion as a runtime dependency. Generate the actual video only when preparing release media.

## Storyboard

1. Product microsite: explain what Vantage is.
2. Dashboard overview: show local AI command center state.
3. Setup wizard: show first-run bootstrap snippets.
4. Operator guide drawer: show docs inside the app.

## Suggested Output

```text
dist/media/vantage-walkthrough.mp4
```

## Manual Generation Path

1. Create a temporary Remotion project under `video/` or another ignored build folder.
2. Import `manifest.json`.
3. Render each screenshot as a timed slide with title, subtitle, and zoom/pan motion.
4. Export MP4 for release notes or landing-page embeds.

Keep generated videos out of git unless they are intentionally small release artifacts.
