// ==UserScript==
// @name         Facebook: friends first
// @description  Friends-only chronological feed. Hides Reels, Watch, groups, suggested and sponsored posts, and the "Open app" bar.
// @version      1.2.0
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
    hideReelsInFeed: true,
    hideGroupPosts: true,
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

  // 3. Hide feed junk. Facebook's markup is scrambled, so this works from what
  // is visibly on screen: find a telltale label or link, climb to the full-width
  // block that holds it (one "feed unit"), and hide that block.
  const REEL_HREF = /\/reels?(\/|\?|$)/;
  const GROUP_HREF = /\/groups\//;
  const SUGGESTED_LABEL =
    /^(Suggested for you|Suggested|People you may know|Suggested groups?|Suggested pages?|Groups you might like|Pages you may like)$/i;
  const REEL_LABEL = /^(Reels|Reels and short videos)$/i;
  const SPONSORED_LABEL = /^Sponsored$/i;
  // Buttons that only appear on posts from people/groups you are not friends with.
  const STRANGER_BUTTON = /^(Follow|Join|Join group|Add friend)$/i;
  const OPEN_APP_LABEL = /^(Open app|Open in app|Open Facebook|Use app|Use the app|Get app|Get the app)$/i;

  const NEAR_TOP_PX = 180; // labels count only near the top of a post, not in comments
  const retries = new WeakMap();

  function findUnit(el) {
    const minWidth = window.innerWidth * 0.8;
    for (let node = el; node && node !== document.body; node = node.parentElement) {
      const parent = node.parentElement;
      if (!parent) return null;
      const rect = node.getBoundingClientRect();
      if (rect.width >= minWidth && rect.height >= 120 && parent.children.length >= 3) {
        // A unit is one post. Anything huge is probably the whole feed.
        return rect.height <= 3500 && node.innerText.length <= 6000 ? node : null;
      }
    }
    return null;
  }

  function hideUnitOf(el, mustBeNearTop) {
    const unit = findUnit(el);
    if (!unit) {
      // Layout may not be ready yet; try again shortly.
      const tries = retries.get(el) || 0;
      if (tries < 3 && el.isConnected) {
        retries.set(el, tries + 1);
        setTimeout(() => hideUnitOf(el, mustBeNearTop), 800);
      }
      return;
    }
    if (mustBeNearTop) {
      const offset = el.getBoundingClientRect().top - unit.getBoundingClientRect().top;
      if (offset > NEAR_TOP_PX) return;
    }
    unit.style.display = "none";
  }

  function hideOpenAppBar(el) {
    const button = el.closest('a, button, [role="button"]') || el;
    let target = button;
    for (let node = button, depth = 0; node && depth < 10; node = node.parentElement, depth++) {
      const position = getComputedStyle(node).position;
      if (position === "fixed" || position === "sticky") {
        target = node;
        break;
      }
    }
    target.style.display = "none";
  }

  function inspect(el) {
    if (el.tagName === "A") {
      const href = el.getAttribute("href") || "";
      if (CONFIG.hideReelsInFeed && REEL_HREF.test(href)) hideUnitOf(el, false);
      else if (CONFIG.hideGroupPosts && GROUP_HREF.test(href)) hideUnitOf(el, true);
    }
    if (el.childElementCount !== 0) return;
    const text = el.textContent.trim();
    if (!text || text.length > 30) return;
    if (CONFIG.hideReelsInFeed && REEL_LABEL.test(text)) hideUnitOf(el, true);
    else if (CONFIG.hideSuggestedPosts && SUGGESTED_LABEL.test(text)) hideUnitOf(el, true);
    else if (CONFIG.hideSponsoredPosts && SPONSORED_LABEL.test(text)) hideUnitOf(el, true);
    else if (CONFIG.hideSuggestedPosts && STRANGER_BUTTON.test(text)) hideUnitOf(el, true);
    else if (CONFIG.hideOpenAppBar && OPEN_APP_LABEL.test(text)) hideOpenAppBar(el);
  }

  function scan(root) {
    inspect(root);
    for (const el of root.querySelectorAll("*")) inspect(el);
  }

  // Only rescan what changed, not the whole page, to keep scrolling smooth.
  const pending = new Set();
  let queued = false;
  function enqueue(node) {
    const el = node.nodeType === 1 ? node : node.parentElement;
    if (el) pending.add(el);
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      const batch = [...pending];
      pending.clear();
      for (const root of batch) if (root.isConnected) scan(root);
    });
  }

  new MutationObserver((records) => {
    for (const record of records) {
      if (record.type === "characterData") enqueue(record.target);
      for (const node of record.addedNodes) enqueue(node);
    }
  }).observe(document.documentElement, {
    childList: true,
    subtree: true,
    characterData: true,
  });
})();
