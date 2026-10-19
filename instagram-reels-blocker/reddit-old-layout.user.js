// ==UserScript==
// @name         Reddit: old layout, no discovery feeds
// @description  Sends Reddit to old.reddit.com and bounces r/popular and r/all back to your own home feed.
// @version      1.0.0
// @match        https://www.reddit.com/*
// @match        https://old.reddit.com/*
// @run-at       document-start
// @noframes
// ==/UserScript==

(function () {
  "use strict";

  const CONFIG = {
    useOldReddit: false,
    blockPopularAndAll: true,
  };

  const { hostname, pathname, search, hash } = location;

  if (CONFIG.useOldReddit && hostname === "www.reddit.com") {
    location.replace("https://old.reddit.com" + pathname + search + hash);
    return;
  }

  if (CONFIG.blockPopularAndAll && /^\/r\/(popular|all)(\/|$)/i.test(pathname)) {
    location.replace("/");
  }
})();
