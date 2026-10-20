#!/usr/bin/env python3
"""Re-apply local customisations to mor-dms/index.html.

The page under ``mor-dms/`` is generated. ``build_static.R`` in the
mor_dms_analysis repo rewrites ``index.html`` from scratch, which drops three
things we want to keep:

  1. the Google Analytics tag
  2. a meaningful ``<title>`` (the export writes "Shiny App")
  3. the loading overlay, which covers the ~1 minute webR cold start

Run it after any rebuild that touches index.html::

    python3 scripts/post_export.py

Note that ``app.json`` is NOT handled here. Its contents come from
``shiny_app/`` in the mor_dms_analysis repo, and ``shiny_app/sync_site.py``
re-bakes and copies it; edit the app there, not in the bundle.

Each step is idempotent: anything already in place is left alone. The exit
status is non-zero only if a step was needed but could not be applied, which
means the generated page changed shape and this script needs updating.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "mor-dms" / "index.html"

GA_ID = "G-EM3KZWJ426"
TITLE = "\u03bcOR-DMS data browser"

GA_SNIPPET = f"""
    <!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());

      gtag('config', '{GA_ID}');
    </script>
"""

BOOT_STYLE = """    <style>
      #boot-message {
        position: fixed;
        inset: 0;
        z-index: 9999;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 16px;
        padding: 24px;
        text-align: center;
        background: #ffffff;
        color: #2f4f47;
        font-family: system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif;
        transition: opacity 0.4s ease;
      }
      #boot-message .boot-title { font-size: 1.1rem; font-weight: 600; }
      #boot-message .boot-detail {
        font-size: 0.9rem;
        line-height: 1.5;
        max-width: 30rem;
        color: #5a6b66;
      }
      #boot-message .boot-spinner {
        width: 34px;
        height: 34px;
        border: 3px solid #d7e8e2;
        border-top-color: #4aa98e;
        border-radius: 50%;
        animation: boot-spin 0.9s linear infinite;
      }
      @keyframes boot-spin { to { transform: rotate(360deg); } }
      @media (prefers-reduced-motion: reduce) {
        #boot-message .boot-spinner { animation: none; }
      }
    </style>
"""

BOOT_OVERLAY = """
    <div id="boot-message">
      <div class="boot-spinner"></div>
      <div class="boot-title">Starting the μOR-DMS data browser</div>
      <div class="boot-detail" id="boot-detail">
        This app runs R entirely in your browser, so the first load takes
        up to a minute. Nothing is sent to a server.
      </div>
    </div>
    <script>
      (function () {
        var overlay = document.getElementById("boot-message");
        var root = document.getElementById("root");
        if (!overlay || !root) return;

        var dismissed = false;
        function dismiss() {
          if (dismissed) return;
          dismissed = true;
          clearTimeout(slowTimer);
          overlay.style.opacity = "0";
          setTimeout(function () { overlay.remove(); }, 400);
        }

        // The app mounts an iframe into #root; wait for it to finish loading.
        function watch(frame) {
          if (frame.contentDocument &&
              frame.contentDocument.readyState === "complete") dismiss();
          else frame.addEventListener("load", dismiss);
        }

        var existing = root.querySelector("iframe");
        if (existing) {
          watch(existing);
        } else {
          var observer = new MutationObserver(function () {
            var frame = root.querySelector("iframe");
            if (!frame) return;
            observer.disconnect();
            watch(frame);
          });
          observer.observe(root, { childList: true, subtree: true });
        }

        // Reassure anyone on a slow connection rather than leaving them guessing.
        var slowTimer = setTimeout(function () {
          var detail = document.getElementById("boot-detail");
          if (detail && !dismissed) {
            detail.textContent =
              "Still loading — the R runtime is a large download the first " +
              "time. It is cached afterwards, so later visits start quickly.";
          }
        }, 45000);
      })();
    </script>
"""


def patch_index():
    """Add the analytics tag and set the page title."""
    html = INDEX.read_text(encoding="utf-8")
    before = html
    notes = []

    if GA_ID in html:
        notes.append("analytics tag already present")
    else:
        anchor = re.search(r"[ \t]*<title>.*?</title>\n", html, re.S)
        if not anchor:
            print("  FAIL  no <title> to anchor the analytics tag to")
            return False
        html = html[: anchor.end()] + GA_SNIPPET + html[anchor.end() :]
        notes.append("analytics tag added")

    title = re.search(r"<title>(.*?)</title>", html, re.S)
    if not title:
        print("  FAIL  no <title> element")
        return False
    if title.group(1) == TITLE:
        notes.append("title already set")
    else:
        html = html[: title.start(1)] + TITLE + html[title.end(1) :]
        notes.append(f"title set (was {title.group(1)!r})")

    if "boot-message" in html:
        notes.append("loading overlay already present")
    else:
        css = re.search(r'[ \t]*<link rel="stylesheet" href="[^"]*shinylive\.css" />\n', html)
        if not css or not re.search(r'[ \t]*<div[^>]*id="root"></div>\n', html):
            print("  FAIL  no stylesheet link or #root div to anchor the overlay to")
            return False
        html = html[: css.end()] + BOOT_STYLE + html[css.end() :]
        root = re.search(r'[ \t]*<div[^>]*id="root"></div>\n', html)
        html = html[: root.end()] + BOOT_OVERLAY + html[root.end() :]
        notes.append("loading overlay added")

    if html != before:
        INDEX.write_text(html, encoding="utf-8")
    print("  index.html: " + "; ".join(notes))
    return True


def main():
    if not INDEX.exists():
        sys.exit(f"missing {INDEX.relative_to(ROOT)} — run the build first")

    print("Re-applying local customisations to mor-dms/index.html")
    ok = patch_index()

    if not ok:
        sys.exit("\nSomething could not be applied — see FAIL above. Fix it by "
                 "hand and update scripts/post_export.py to match the new page.")
    print("Done.")


if __name__ == "__main__":
    main()
