"""Port the legacy Jinja-era stylesheets into the React app.

`style.css` is the shared design system and stays global. Every other sheet was
loaded by exactly one page, so the same class name means different things in
two of them (`.stat-card` in dashboard.css and company-dashboard.css, `.tag` in
four). In an SPA all CSS is one bundle, so each page sheet is emitted scoped
under a `.pg-<name>` wrapper the route renders, which is what keeps one bundle
from turning into the collisions the multipage build never had.
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "backend", "app", "static", "css")
OUT = os.path.join(HERE, "..", "src", "styles", "legacy")

PAGES = [
    "about", "admin", "admin_page", "career_lab", "community", "community_feed",
    "company-dashboard", "company-team", "dashboard", "jobs", "questionnaire",
    "resources", "roadmap", "roadmaps", "userProfile",
]

def strip_comments(t):
    return re.sub(r"/\*.*?\*/", "", t, flags=re.S)


def strip_imports(t):
    """Drop `@import` lines before parsing.

    Two of the sheets `@import` a sibling sheet, which the React side resolves
    by rendering both scopes on the route instead. The third imports a Google
    font whose URL contains `;` (`family=Inter:wght@300;400;…`), and a naive
    statement split on `;` turns that into garbage rules — the font is declared
    once in `styles/index.css` instead.
    """
    return re.sub(r"^\s*@import[^\n]*\n", "", t, flags=re.M)

def split_rules(text):
    """Yield (prelude, body|None) for each top-level rule."""
    out, buf, i, n = [], "", 0, len(text)
    while i < n:
        c = text[i]
        if c == ";" and not buf.strip().startswith("@media") and buf.strip().startswith("@"):
            out.append((buf.strip() + ";", None)); buf = ""; i += 1; continue
        if c == "{":
            depth, j = 1, i + 1
            while j < n and depth:
                if text[j] == "{": depth += 1
                elif text[j] == "}": depth -= 1
                j += 1
            out.append((buf.strip(), text[i + 1:j - 1]))
            buf = ""; i = j; continue
        buf += c; i += 1
    return out

def scope_selector(sel, scope):
    parts = []
    for s in sel.split(","):
        s = " ".join(s.split())
        if not s:
            continue
        if s in (":root", "body", "html"):
            # The sheet was the whole document; in the SPA that document is the
            # page's own wrapper. Leaving these global is how `admin_page.css`
            # would paint every route's body `#0a0e1a`, and how `admin.css`
            # would put `color-scheme: dark` on the whole app.
            parts.append(f".{scope}")
        elif re.match(r"^(body|html)[.:\[]", s):
            # A state class the document carries (`body.modal-open`): still a
            # document-level flag, so it stays one.
            parts.append(s)
        else:
            parts.append(f".{scope} {s}")
    return ",\n".join(parts)

def scope_block(body, scope, kf_names):
    out = []
    for prelude, inner in split_rules(body):
        if inner is None:
            if prelude.startswith("@import"):
                continue
            out.append(prelude)
            continue
        p = " ".join(prelude.split())
        if p.startswith("@keyframes"):
            name = p.split(None, 1)[1].strip()
            kf_names.add(name)
            out.append("@keyframes %s-%s {%s}" % (scope, name, inner))
        elif p.startswith("@"):
            out.append("%s {\n%s\n}" % (p, scope_block(inner, scope, kf_names)))
        else:
            out.append("%s {%s}" % (scope_selector(p, scope), inner))
    return "\n\n".join(out)

def main():
    os.makedirs(os.path.join(OUT, "pages"), exist_ok=True)

    with open(os.path.join(SRC, "style.css"), encoding="utf-8") as fh:
        base = fh.read()
    with open(os.path.join(OUT, "base.css"), "w", encoding="utf-8") as fh:
        fh.write("/* Ported verbatim from backend/app/static/css/style.css. */\n" + base)

    index = ['@import "./base.css";']
    for page in PAGES:
        with open(os.path.join(SRC, page + ".css"), encoding="utf-8") as fh:
            txt = strip_imports(strip_comments(fh.read()))
        scope = "pg-" + page.replace("_", "-").lower()
        kf = set()
        css = scope_block(txt, scope, kf)
        # keyframes were renamed per scope; point this sheet's animations at them
        for name in kf:
            css = re.sub(r"(animation(?:-name)?\s*:[^;}]*?)\b%s\b" % re.escape(name),
                         lambda m: m.group(1) + scope + "-" + name, css)
        header = ("/* Ported from backend/app/static/css/%s.css, scoped under `.%s`. */\n"
                  % (page, scope))
        with open(os.path.join(OUT, "pages", page + ".css"), "w", encoding="utf-8") as fh:
            fh.write(header + css + "\n")
        index.append('@import "./pages/%s.css";' % page)

    with open(os.path.join(OUT, "index.css"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(index) + "\n")
    print("wrote", len(PAGES) + 2, "files")

main()
