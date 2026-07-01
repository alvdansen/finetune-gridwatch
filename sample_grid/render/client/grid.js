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

  // ── Video player lifecycle (Phase 3, MEDIA-01 / MEDIA-05) ──────────────────
  // IntersectionObserver-gated decoder lifecycle: attach `src` + paint the
  // first-frame poster on ENTER, DETACH `src` to free the WebMediaPlayer on
  // EXIT. Chromium hard-caps live players (75 desktop / 40 mobile) and blacks
  // out cells past the cap, so detaching on exit is MANDATORY for a real 10x8
  // grid. Per-cell click / Space-Enter toggles play-pause of THAT cell (D-03,
  // never all-playing); a rejected play() degrades to the poster + `data-blocked`
  // (D-11), never a dead cell. Freeze-on-frame (D-02): pause/scroll-away holds
  // the current frame, re-enter restores it (Independent), never the poster.
  // Still vanilla and file://-safe: no network calls, no live-reload, no server.
  var PLAY_CAP = 12;
  var FORCE_REJECT = /(?:^|[?&])forceRejectPlay=1(?:&|$)/.test(location.search);

  // window.__players = count of live (attached) decoders — the M5 observable
  // that must stay bounded (well under the browser WebMediaPlayer cap).
  window.__players = 0;

  // PlayerManager owns the currently-playing set + the concurrent-play cap.
  var manager = {
    playing: [], // oldest first, so [0] is the eviction victim
    track: function (cell) { this.untrack(cell); this.playing.push(cell); },
    untrack: function (cell) {
      var i = this.playing.indexOf(cell);
      if (i !== -1) this.playing.splice(i, 1);
    },
    evictOldest: function () { if (this.playing.length) this.playing[0].pause(); }
  };

  function VideoCell(el) {
    this.el = el;
    this.video = el.querySelector("video");
    this.playing = false;
    this.blocked = false;
    this.frozenAt = 0;
    this.attached = false;
  }

  // attach(): paint the first-frame poster via the #t=0.001 data-src fragment
  // and register a live decoder. Idempotent (guards on this.attached).
  VideoCell.prototype.attach = function () {
    var v = this.video;
    if (!v || this.attached) return;
    v.muted = true;
    v.src = this.el.getAttribute("data-src"); // #t=0.001 paints the poster frame
    v.load();
    this.attached = true;
    window.__players++;
    // Independent semantics: restore the remembered frame (D-02), never reset
    // to the poster. (Synced re-sync is Plan 03 — non-"synced" is Independent.)
    if (this.frozenAt > 0 && root.getAttribute("data-sync") !== "synced") {
      var self = this;
      var seek = function () {
        try { v.currentTime = self.frozenAt; } catch (e) {}
        v.removeEventListener("loadedmetadata", seek);
      };
      v.addEventListener("loadedmetadata", seek);
    }
  };

  // detach(): freeze the current frame, then release the WebMediaPlayer.
  VideoCell.prototype.detach = function () {
    var v = this.video;
    if (!v || !this.attached) return;
    this.frozenAt = v.currentTime || this.frozenAt; // D-02 freeze frame
    v.pause();
    v.removeAttribute("src");
    v.load(); // frees the decoder (WebMediaPlayer) — mandatory under the cap
    this.attached = false;
    this.playing = false;
    this.el.classList.remove("is-playing");
    this.el.setAttribute("aria-pressed", "false");
    manager.untrack(this);
    window.__players--;
  };

  // play(): a direct user click on a specific cell is always honored (evicting
  // the oldest if at the concurrent cap); re-assert muted every time so the
  // autoplay policy can never veto a muted, user-gestured start.
  VideoCell.prototype.play = function () {
    var v = this.video;
    if (!v) return;
    if (!this.attached) this.attach();
    if (!this.playing && manager.playing.length >= PLAY_CAP) manager.evictOldest();
    v.muted = true;
    var self = this;
    var settle = function (ok) {
      self.playing = ok;
      self.blocked = !ok;
      if (ok) {
        self.el.classList.add("is-playing");
        self.el.setAttribute("aria-pressed", "true");
        self.el.removeAttribute("data-blocked");
        manager.track(self);
      } else {
        // D-11: keep the poster + ▶ and mark the cell — never a black/dead cell.
        self.el.classList.remove("is-playing");
        self.el.setAttribute("aria-pressed", "false");
        self.el.setAttribute("data-blocked", "");
        manager.untrack(self);
      }
    };
    // Debug hook (manual protocol M1 / future automated): force the poster path.
    if (FORCE_REJECT) { settle(false); return; }
    var p = v.play();
    if (p && typeof p.then === "function") {
      p.then(function () { settle(true); }).catch(function () { settle(false); });
    } else {
      settle(true);
    }
  };

  // pause(): freeze on the current frame — do NOT reset currentTime. The ▶
  // reappears (CSS drops .is-playing).
  VideoCell.prototype.pause = function () {
    var v = this.video;
    if (!v) return;
    v.pause();
    this.playing = false;
    this.el.classList.remove("is-playing");
    this.el.setAttribute("aria-pressed", "false");
    manager.untrack(this);
  };

  VideoCell.prototype.toggle = function () {
    if (this.playing) this.pause(); else this.play();
  };

  var videoCells = document.querySelectorAll("[data-video]");
  if (videoCells.length && "IntersectionObserver" in window) {
    // rootMargin pre-attaches just-off-screen cells so a scrolled-to cell already
    // shows its poster; threshold 0 fires as soon as any pixel enters/leaves.
    var observer = new IntersectionObserver(function (entries) {
      for (var i = 0; i < entries.length; i++) {
        var cell = entries[i].target.__cell;
        if (!cell) continue;
        if (entries[i].isIntersecting) cell.attach();
        else cell.detach();
      }
    }, { rootMargin: "300px 0px", threshold: 0 });

    videoCells.forEach(function (el) {
      var cell = new VideoCell(el);
      el.__cell = cell;
      observer.observe(el);

      // A click anywhere on the cell toggles play/pause of THAT cell — except on
      // the ⧉ pop-out anchor, whose native new-tab navigation must proceed
      // (stopPropagation keeps its click from ever toggling playback).
      var popout = el.querySelector(".cell__popout");
      if (popout) {
        popout.addEventListener("click", function (ev) { ev.stopPropagation(); });
      }
      el.addEventListener("click", function () { cell.toggle(); });

      // Keyboard parity: Space/Enter on the focused cell toggles the same;
      // preventDefault on Space so the page never scrolls under the gesture.
      el.addEventListener("keydown", function (ev) {
        if (ev.key === " " || ev.key === "Enter") {
          if (ev.key === " ") ev.preventDefault();
          cell.toggle();
        }
      });
    });
  }
})();
