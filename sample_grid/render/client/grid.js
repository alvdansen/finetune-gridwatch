/* Phase-1 client JS — theme/density toggle + sticky-shadow cue. Vanilla, no
   dependency, MUST run from file:// with no server. Phase 1 renders live=False,
   so there is deliberately no live-reload / no server wiring here (that arrives
   in Phase 4). The dark/comfortable defaults live in the CSS :root, so a
   JS-disabled page still renders correctly — this script only adds the toggle
   and the scroll-shadow polish. */
(function () {
  "use strict";
  var root = document.documentElement;
  var STORE = { theme: "sg-theme", density: "sg-density" };

  // Restore the persisted theme/density (if any) on load.
  Object.keys(STORE).forEach(function (key) {
    var saved = null;
    try { saved = localStorage.getItem(STORE[key]); } catch (e) {}
    if (saved) root.setAttribute("data-" + key, saved);
  });

  // Reflect the active value on every segment of a group via aria-pressed.
  function syncPressed(key) {
    var current = root.getAttribute("data-" + key);
    var segs = document.querySelectorAll('[data-set^="' + key + ':"]');
    for (var i = 0; i < segs.length; i++) {
      var value = segs[i].getAttribute("data-set").split(":")[1];
      segs[i].setAttribute("aria-pressed", String(value === current));
    }
  }
  syncPressed("theme");
  syncPressed("density");

  // Wire each [data-set="key:value"] button: set the attribute, persist, sync.
  document.querySelectorAll("[data-set]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var parts = btn.getAttribute("data-set").split(":");
      var key = parts[0], value = parts[1];
      root.setAttribute("data-" + key, value);
      try { localStorage.setItem(STORE[key], value); } catch (e) {}
      syncPressed(key);
    });
  });

  // Sticky-shadow cue: toggle .is-scrolled-x / .is-scrolled-y on the scroll
  // container once content scrolls under the headers. Only as a motion-safe
  // enhancement; the always-on hairline is the CSS-only fallback.
  if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: no-preference)").matches) {
    var scroller = document.querySelector(".grid-scroll");
    if (scroller) {
      var ticking = false;
      var update = function () {
        scroller.classList.toggle("is-scrolled-y", scroller.scrollTop > 0);
        scroller.classList.toggle("is-scrolled-x", scroller.scrollLeft > 0);
        ticking = false;
      };
      scroller.addEventListener("scroll", function () {
        if (!ticking) { ticking = true; requestAnimationFrame(update); }
      });
    }
  }
})();
