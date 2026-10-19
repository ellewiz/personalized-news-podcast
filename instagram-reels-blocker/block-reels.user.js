// ==UserScript==
// @name         Block Instagram Reels
// @description  Hides Reels everywhere on instagram.com and bounces /reels/ URLs back to the home feed.
// @version      1.0.0
// @match        https://www.instagram.com/*
// @run-at       document-start
// @noframes
// ==/UserScript==

(function () {
  "use strict";

  const REEL_PATH = /^\/(reels?)(\/|$)/;

  // 1. Redirect any direct Reels URL (typed, tapped from a DM link, etc.).
  function bounceIfReel() {
    if (REEL_PATH.test(location.pathname)) {
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

  // 2. Hide Reels UI: nav tab, profile tab, and Reels showing up in the feed.
  const css = `
    a[href="/reels/"],
    a[href^="/reels/"],
    a[href$="/reels/"],
    a[href*="/reel/"] { display: none !important; }

    /* Feed posts that are Reels */
    article:has(a[href*="/reel/"]),
    div[role="presentation"]:has(> article a[href*="/reel/"]) { display: none !important; }

    /* Reels shared in DMs and suggested-reel tiles */
    div:has(> a[href*="/reel/"]) { display: none !important; }
  `;

  function injectCss() {
    if (document.getElementById("block-reels-style")) return;
    const style = document.createElement("style");
    style.id = "block-reels-style";
    style.textContent = css;
    (document.head || document.documentElement).appendChild(style);
  }
  injectCss();
  document.addEventListener("DOMContentLoaded", injectCss);
})();
