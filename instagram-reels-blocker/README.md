# Instagram Reels blocker (iPhone Safari)

A free userscript that hides Reels on instagram.com and redirects `/reels/` links to the home feed. A single Reel link opened from outside Instagram (for example from a DM in Beeper) still plays; moving on to any other Reel bounces you home.

## Install

1. Install the free **Userscripts** app by quoid from the App Store.
2. Open it once and pick a folder (iCloud Drive works) to hold your scripts.
3. iOS Settings > Apps > Safari > Extensions > turn on **Userscripts**, and allow it on all websites (or just instagram.com).
4. Copy `block-reels.user.js` into that folder.
5. Open https://www.instagram.com in Safari. Tap the "aA" button in the address bar, then Userscripts, to confirm the script is active.

## Limits

- The official Instagram app cannot be modified. Delete it or keep it off your home screen, and use Safari (add the site to your home screen for an app-like icon).
- Instagram changes its page structure often, so the feed-hiding selectors may need occasional tweaks. The URL redirect is the sturdy part.
- Reels sent to you in DMs through Beeper are outside this script's reach.

## Other scripts in this folder

- `facebook-friends-first.user.js`: opens the friends-only chronological feed, redirects Reels and Watch to the home page, and hides Reels, group posts, suggested posts, sponsored posts, People you may know, and the "Open app" bar. Toggles are in the `CONFIG` block at the top. Facebook obfuscates its markup, so the hiding works from visible labels and links and will need occasional fixes. It is untested against the live site.
- `reddit-old-layout.user.js`: sends reddit.com to old.reddit.com and bounces r/popular and r/all to your own home feed. Toggles are in the `CONFIG` block.

Install each one the same way as the Reels script: open its raw GitHub URL in Safari and install it from the Userscripts menu, or copy the file into your Userscripts folder.
