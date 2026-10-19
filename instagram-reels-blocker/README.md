# Instagram Reels blocker (iPhone Safari)

A free userscript that hides Reels on instagram.com and redirects `/reels/` links to the home feed.

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
