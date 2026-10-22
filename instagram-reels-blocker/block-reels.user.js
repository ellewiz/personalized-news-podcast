// ==UserScript==
// @name         Block Instagram Reels
// @description  Hides Reels on instagram.com and bounces /reels/ URLs home. A single Reel link opened from outside Instagram (a DM in Beeper, Messages) still plays.
// @version      1.1.0
// @match        https://www.instagram.com/*
// @run-at       document-start
// @noframes
// ==/UserScript==

(function () {
  "use strict";

  const REEL_PATH = /^\/(reels?)(\/|$)/;
  // /reel/CODE/ or /reels/CODE/, but not the /reels/ feed or /reels/audio/ pages.
  const SINGLE_REEL = /^\/reels?\/(?!audio\/)[^/]+/;

  // A Reel link opened from outside Instagram may play, but only that one.
  // Moving to any other Reel (swiping to the next one, tapping a suggestion)
  // is in-app navigation and gets bounced home.
  let allowedPath = null;
  if (SINGLE_REEL.test(location.pathname) && !/instagram\.com/.test(document.referrer)) {
    allowedPath = location.pathname;
  }

  // Hide Reels UI: nav tab, profile tab, and Reels showing up in the feed.
  // The feed rules are switched off while a shared Reel is open, because they
  // could otherwise hide the player itself.
  const navStyle = document.createElement("style");
  navStyle.id = "block-reels-nav-style";
  navStyle.textContent = `
    a[href="/reels/"],
    a[href^="/reels/"],
    a[href$="/reels/"],
    a[href*="/reel/"] { display: none !important; }
  `;

  const feedStyle = document.createElement("style");
  feedStyle.id = "block-reels-feed-style";
  feedStyle.textContent = `
    /* Feed posts that are Reels */
    article:has(a[href*="/reel/"]),
    div[role="presentation"]:has(> article a[href*="/reel/"]) { display: none !important; }

    /* Reels shared in DMs and suggested-reel tiles */
    div:has(> a[href*="/reel/"]) { display: none !important; }
  `;

  function updateFeedCss() {
    feedStyle.media = location.pathname === allowedPath ? "not all" : "all";
  }

  function bounceIfReel() {
    updateFeedCss();
    if (REEL_PATH.test(location.pathname) && location.pathname !== allowedPath) {
      location.replace("/");
    }
  }
  bounceIfReel();

  // Instagram is a single-page app, so most navigation never reloads the page.
  // Watch history changes as well.
  for (const method of ["pushState", "replaceState"]) {
    const original = history[method];
    history[method] = function (...args) {
      const result = original.apply(this, args);
      bounceIfReel();
      return result;
    };
  }
  window.addEventListener("popstate", bounceIfReel);

  function injectCss() {
    const root = document.head || document.documentElement;
    for (const style of [navStyle, feedStyle]) {
      if (!style.isConnected) root.appendChild(style);
    }
  }
  injectCss();
  document.addEventListener("DOMContentLoaded", injectCss);
})();
