// ==UserScript==
// @name         Facebook: friends first
// @description  Friends-only chronological feed, no Reels/Watch, no suggested or sponsored posts, no "Open app" bar.
// @version      1.1.0
// @match        https://www.facebook.com/*
// @match        https://m.facebook.com/*
// @run-at       document-start
// @noframes
// ==/UserScript==

(function () {
  "use strict";

  // Flip any of these to false to turn that piece off.
  const CONFIG = {
    redirectReels: true,
    redirectWatch: true,
    friendsChronologicalHome: true,
    hideSuggestedPosts: true,
    hideSponsoredPosts: true,
    hideOpenAppBar: true,
  };

  const FRIENDS_FEED = "/?filter=friends&sk=h_chr";

  // 1. Redirects (direct links and in-app navigation).
  function route() {
    const { pathname, search } = location;
    if (CONFIG.redirectReels && /^\/reels?(\/|$)/.test(pathname)) {
      location.replace("/");
      return;
    }
    if (CONFIG.redirectWatch && /^\/watch(\/|$)/.test(pathname)) {
      location.replace("/");
      return;
    }
    if (CONFIG.friendsChronologicalHome && pathname === "/" && !search.includes("sk=")) {
      // Skip if we redirected in the last few seconds, so a Facebook rewrite
      // of the URL can't cause a redirect loop.
      try {
        const last = Number(sessionStorage.getItem("fff-redirected-at") || 0);
        if (Date.now() - last < 5000) return;
        sessionStorage.setItem("fff-redirected-at", String(Date.now()));
      } catch (e) {
        return;
      }
      location.replace(FRIENDS_FEED);
    }
  }
  route();

  for (const method of ["pushState", "replaceState"]) {
    const original = history[method];
    history[method] = function (...args) {
      const result = original.apply(this, args);
      route();
      return result;
    };
  }
  window.addEventListener("popstate", route);

  // 2. Hide menu entries for Reels and Watch.
  const style = document.createElement("style");
  style.textContent = `
    a[href^="/reel"],
    a[href^="/watch"],
    a[href*="/reel/"] { display: none !important; }
  `;
  (document.head || document.documentElement).appendChild(style);

  // 3. Sweep the page for junk. Facebook's class names are scrambled, so
  // match on visible text, link targets, and aria labels instead.
  const JUNK_HEADER =
    /(^|\n)\s*(Suggested for you|People you may know|Reels and short videos|Suggested groups?|Suggested pages?)\s*(\n|$)/i;
  const SPONSORED_TEXT = /(^|\n)\s*Sponsored\s*(\n|$)/i;
  const SPONSORED_MARKERS =
    'a[href*="/ads/about"], a[href*="ads/about"], [aria-label="Sponsored"]';
  const OPEN_APP_TEXT = /^(Open app|Open in app|Open Facebook|Use app|Use the app|Get app|Get the app)$/i;

  function isSponsored(post, head) {
    return SPONSORED_TEXT.test(head) || post.querySelector(SPONSORED_MARKERS) !== null;
  }

  function sweepPosts() {
    const posts = document.querySelectorAll('[role="article"]:not([data-fff-checked])');
    for (const post of posts) {
      const text = post.innerText || "";
      if (text.length < 50) continue; // not rendered yet, check again later
      post.setAttribute("data-fff-checked", "1");
      const head = text.slice(0, 500);
      const hide =
        post.querySelector('a[href*="/reel/"]') ||
        (CONFIG.hideSuggestedPosts && JUNK_HEADER.test(head)) ||
        (CONFIG.hideSponsoredPosts && isSponsored(post, head));
      if (hide) post.style.display = "none";
    }
  }

  // The "Open app" bar is usually a fixed or sticky strip. Find the button by
  // its text, then hide the nearest fixed/sticky ancestor (or the button itself).
  function sweepOpenApp() {
    const candidates = document.querySelectorAll(
      'a:not([data-fff-app]), button:not([data-fff-app]), [role="button"]:not([data-fff-app])'
    );
    for (const el of candidates) {
      el.setAttribute("data-fff-app", "1");
      const label = (el.innerText || el.getAttribute("aria-label") || "").trim();
      if (!label || label.length > 20 || !OPEN_APP_TEXT.test(label)) continue;
      let target = el;
      for (let node = el, depth = 0; node && depth < 10; node = node.parentElement, depth++) {
        const position = getComputedStyle(node).position;
        if (position === "fixed" || position === "sticky") {
          target = node;
          break;
        }
      }
      target.style.display = "none";
    }
  }

  let queued = false;
  function schedule() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      sweepPosts();
      if (CONFIG.hideOpenAppBar) sweepOpenApp();
    });
  }
  new MutationObserver(schedule).observe(document.documentElement, {
    childList: true,
    subtree: true,
  });
})();
