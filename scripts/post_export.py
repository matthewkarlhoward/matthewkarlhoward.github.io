#!/usr/bin/env python3
"""Re-apply local customisations to the exported shinylive app.

``shinylive export`` regenerates everything under ``mor-dms/``, which drops
three things we want to keep:

  1. the Google Analytics tag in ``index.html``
  2. a meaningful ``<title>`` (the export writes "Shiny App")
  3. the filled-in citation on the app's Cite page, for as long as the
     source ``app.R`` still carries the ``{Authors}``/``{Title}`` placeholders

Run it straight after every export::

    python3 scripts/post_export.py

Each step is idempotent and independent: anything already in place is left
alone, and a step that finds nothing to do says so rather than failing. The
exit status is non-zero only if a step was needed but could not be applied,
which means the export changed shape and this script needs updating.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "mor-dms" / "index.html"
APP_JSON = ROOT / "mor-dms" / "app.json"

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

# The Cite panel as the export writes it, and as we want it. The pattern
# spans h3("Paper") through the end of the BibTeX block.
PAPER_BLOCK = re.compile(r'      h3\("Paper"\),.*?sep = "\\n"\)\),', re.S)

CITATION = '''      h3("Paper"),
      p("Howard MK, Fine EJ, Srinivasan K, Richman DD, Freudenberg J, Weinberg Z, ",
        "Rao J, Zou Z, Macdonald C, Rockefeller Grimes P, Varga BR, Fraser JS, ",
        "Von Zastrow M, Majumdar S, Pimentel H, English J, Dror RO, Manglik A, ",
        "Coyote-Maestas W. Distinct activation mechanisms underlie ligand efficacy ",
        "at a GPCR. ", tags$em("bioRxiv"), " (2026). DOI: ",
        tags$a(href = "https://doi.org/10.64898/2026.10.12.758633",
               target = "_blank", rel = "noopener",
               "10.64898/2026.10.12.758633"), "."),
      tags$pre(paste(
        "@article{howard2026efficacy,",
        "  title   = {Distinct activation mechanisms underlie ligand efficacy at a GPCR},",
        "  author  = {Howard, Matthew K. and Fine, Eve J. and Srinivasan, Karthik and",
        "             Richman, Daniel D. and Freudenberg, Jerome and Weinberg, Zara and",
        "             Rao, Jingyou and Zou, Ziyue and Macdonald, Christian and",
        "             Rockefeller Grimes, Patrick and Varga, Balazs R. and",
        "             Fraser, James S. and Von Zastrow, Mark and Majumdar, Susruta and",
        "             Pimentel, Harold and English, Justin and Dror, Ron O. and",
        "             Manglik, Aashish and Coyote-Maestas, Willow},",
        "  journal = {bioRxiv},",
        "  year    = {2026},",
        "  doi     = {10.64898/2026.10.12.758633}",
        "}", sep = "\\n")),'''

EDITOR_NOTE = '''      ),
      p(class = "small-muted",
        "Edit these details in the \u201cCite\u201d nav_panel of app.R when the paper is finalized.")
    )'''


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

    if html != before:
        INDEX.write_text(html, encoding="utf-8")
    print("  index.html: " + "; ".join(notes))
    return True


def patch_citation():
    """Fill the Cite panel placeholders, if the export still has them."""
    files = json.loads(APP_JSON.read_text(encoding="utf-8"))
    changed = False
    seen = False

    for entry in files:
        source = entry.get("content", "")
        if 'h3("Paper")' not in source:
            continue
        seen = True

        match = PAPER_BLOCK.search(source)
        if not match:
            print(f"  FAIL  {entry['name']}: found the Cite panel but not the "
                  "citation block; the export's shape changed")
            return False

        if "{Authors}" not in match.group(0):
            print(f"  app.json ({entry['name']}): citation already filled in")
            continue

        source = source[: match.start()] + CITATION + source[match.end() :]
        source = source.replace(EDITOR_NOTE, "      )\n    )")
        entry["content"] = source
        changed = True
        print(f"  app.json ({entry['name']}): citation filled in")

    if not seen:
        print("  FAIL  app.json: no Cite panel found")
        return False
    if changed:
        # Match the export's own compact encoding so the diff stays small.
        APP_JSON.write_text(
            json.dumps(files, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    return True


def main():
    for path in (INDEX, APP_JSON):
        if not path.exists():
            sys.exit(f"missing {path.relative_to(ROOT)} — run the export first")

    print("Re-applying local customisations to mor-dms/")
    ok = patch_index()
    ok = patch_citation() and ok

    if not ok:
        sys.exit("\nSomething could not be applied — see FAIL above. Fix it by "
                 "hand and update scripts/post_export.py to match the new export.")
    print("Done.")


if __name__ == "__main__":
    main()
