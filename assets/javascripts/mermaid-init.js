// Load mermaid.js + auto-init on every page.
// Pinned to v11 (current stable). The superfences mermaid handler
// emits <div class="mermaid"> blocks that mermaid.init() scans.
//
// Re-runs on every Material instant-navigation page swap so
// diagrams render on client-side route changes, not just hard
// loads.

(function() {
  function loadMermaid(cb) {
    if (window.mermaid) { cb(); return; }
    var s = document.createElement("script");
    s.src = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js";
    s.onload = function() {
      window.mermaid.initialize({
        startOnLoad: false,
        theme: "default",
        flowchart: { useMaxWidth: true, htmlLabels: true },
        sequence: { useMaxWidth: true }
      });
      cb();
    };
    document.head.appendChild(s);
  }

  function render() {
    loadMermaid(function() {
      var nodes = document.querySelectorAll("div.mermaid:not([data-processed])");
      if (nodes.length > 0) {
        window.mermaid.run({ nodes: nodes });
      }
    });
  }

  // Initial page load
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", render);
  } else {
    render();
  }

  // Material instant-navigation: re-render on route change
  if (typeof document$ !== "undefined") {
    document$.subscribe(render);
  }
})();
