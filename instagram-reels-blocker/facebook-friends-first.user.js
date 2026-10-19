// ==UserScript==
// @name         Facebook: friends first
// @description  Removes Reels, Watch, and suggested/promoted posts from Facebook and prefers the chronological feed.
// @version      1.0.0
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
    preferChronological: true,
    hideSuggestedPosts: true,
  };

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
    if (CONFIG.preferChronological && pathname === "/" && !search.includes("sk=")) {
      // Once per tab session, so a Facebook rewrite of the URL can't cause a loop.
      try {
        if (sessionStorage.getItem("fb-chrono-done")) return;
        sessionStorage.setItem("fb-chrono-done", "1");
      } catch (e) {
        return;
      }
      location.replace("/?sk=h_chr");
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

  // 3. Hide junk posts in the feed. Facebook's class names are scrambled, so
  // match on the visible header text of each post instead.
  const JUNK_HEADER =
    /(^|\n)\s*(Suggested for you|Sponsored|People you may know|Reels and short videos|Suggested groups?|Suggested pages?)\s*(\n|$)/i;

  function sweep() {
    const posts = document.querySelectorAll('[role="article"]:not([data-fff-checked])');
    for (const post of posts) {
      const text = post.innerText || "";
      if (text.length < 50) continue; // not rendered yet, check again later
      post.setAttribute("data-fff-checked", "1");
      const isReel = post.querySelector('a[href*="/reel/"]');
      const isJunk = CONFIG.hideSuggestedPosts && JUNK_HEADER.test(text.slice(0, 500));
      if (isReel || isJunk) post.style.display = "none";
    }
  }

  let queued = false;
  function schedule() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      sweep();
    });
  }
  new MutationObserver(schedule).observe(document.documentElement, {
    childList: true,
    subtree: true,
  });
})();
