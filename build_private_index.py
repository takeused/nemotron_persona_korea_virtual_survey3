"""Build one password-gated index containing all HTML reports."""
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
REPORTS = [
    ("report_all.html", "\ud1b5\ud569 \uacb0\uacfc", "Q1~Q30 \ud1b5\ud569 \ud45c"),
    ("report_compare.html", "\uc2e4\uc81c\uc870\uc0ac \ube44\uad50", "\uc7ac\ud604\uc131\u00b7\uac1c\uc120 \ub85c\ub4dc\ub9f5"),
    ("report_findings.html", "\uc5f0\uad6c \uc885\ud569", "\ud575\uc2ec \ubc1c\uacac\uacfc \uc2dc\uc0ac\uc810"),
    ("report_phase1.html", "1\ucc28 \uacb0\uacfc", "Q1~Q13"),
    ("report_phase2.html", "2\ucc28 \uacb0\uacfc", "Q14~Q30"),
]


def fnv1a(value: str) -> str:
    h = 2166136261
    for ch in value:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return f"{h:08x}"


def main() -> None:
    # This is a convenience privacy barrier for a local file, not encryption.
    password_hash = fnv1a("ndmi8041!")
    tabs = []
    panes = []
    for i, (filename, label, description) in enumerate(REPORTS):
        report = (OUT / filename).read_text(encoding="utf-8")
        srcdoc = escape(report, quote=True)
        active = " active" if i == 0 else ""
        tabs.append(
            f'<button class="tab{active}" data-target="report-{i}">'
            f"<span>{escape(label)}</span><small>{escape(description)}</small></button>"
        )
        panes.append(
            f'<section id="report-{i}" class="report-pane{active}">'
            f'<iframe title="{escape(label)}" srcdoc="{srcdoc}"></iframe></section>'
        )

    html = f'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>\uac00\uc0c1 \uc124\ubb38\uc870\uc0ac - \ube44\uacf5\uac1c \ubcf4\uace0\uc11c</title>
<style>
:root {{ color-scheme: light; font-family: "Malgun Gothic", system-ui, sans-serif; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: #eef1f5; color: #17202a; }}
#gate {{ position: fixed; inset: 0; display: grid; place-items: center; background: #17202a; z-index: 10; }}
.card {{ width: min(420px, calc(100vw - 32px)); padding: 30px; border-radius: 16px; background: white; box-shadow: 0 16px 50px #0006; }}
.card h1 {{ margin: 0 0 8px; font-size: 22px; }}
.card p {{ color: #5d6975; font-size: 14px; line-height: 1.6; }}
.card input {{ width: 100%; padding: 12px; border: 1px solid #c8d0d8; border-radius: 8px; font-size: 16px; }}
.card button {{ width: 100%; margin-top: 12px; padding: 12px; border: 0; border-radius: 8px; background: #155eef; color: white; font-weight: 700; cursor: pointer; }}
#error {{ min-height: 20px; margin-top: 8px; color: #c62828; font-size: 13px; }}
#app {{ display: none; min-height: 100vh; }}
header {{ padding: 22px 28px 14px; background: white; border-bottom: 1px solid #d8dee6; }}
header h1 {{ margin: 0 0 5px; font-size: 24px; }}
header p {{ margin: 0; color: #66717d; font-size: 13px; }}
.tabs {{ display: flex; gap: 8px; flex-wrap: wrap; padding: 14px 28px; background: #f8fafc; border-bottom: 1px solid #d8dee6; }}
.tab {{ display: flex; flex-direction: column; align-items: flex-start; gap: 3px; padding: 10px 14px; border: 1px solid #cbd5e1; border-radius: 9px; background: white; color: #334155; cursor: pointer; }}
.tab small {{ color: #718096; }}
.tab.active {{ border-color: #155eef; background: #eaf1ff; color: #0b4acb; }}
.report-pane {{ display: none; padding: 16px 20px 28px; }}
.report-pane.active {{ display: block; }}
iframe {{ display: block; width: 100%; min-height: calc(100vh - 170px); border: 0; border-radius: 8px; background: white; box-shadow: 0 2px 10px #17202a18; }}
@media (max-width: 700px) {{ header, .tabs {{ padding-left: 14px; padding-right: 14px; }} .report-pane {{ padding: 10px 0 20px; }} iframe {{ min-height: calc(100vh - 230px); border-radius: 0; }} }}
</style>
</head>
<body>
<div id="gate">
  <form class="card" id="login">
    <h1>\ube44\uacf5\uac1c \ubcf4\uace0\uc11c</h1>
    <p>\uac00\uc0c1 \uc124\ubb38\uc870\uc0ac \ubcf4\uace0\uc11c\ub97c \uc5f4\ub824\uba74 \ube44\ubc00\ubc88\ud638\ub97c \uc785\ub825\ud558\uc138\uc694.</p>
    <input id="password" type="password" autocomplete="current-password" autofocus>
    <button type="submit">\uc5f4\uae30</button>
    <div id="error" aria-live="polite"></div>
  </form>
</div>
<main id="app">
  <header><h1>\uac00\uc0c1 \uc124\ubb38\uc870\uc0ac \ubcf4\uace0\uc11c \ubaa9\ub85d</h1><p>\ube44\ubc00\ubc88\ud638\ub85c \ubcf4\ud638\ub418\uba70, \uc6d0\ubcf8 HTML 5\uac1c\uac00 \uc774 \ud30c\uc77c\uc5d0 \ud3ec\ud568\ub418\uc5b4 \uc788\uc2b5\ub2c8\ub2e4.</p></header>
  <nav class="tabs" aria-label="\ubcf4\uace0\uc11c \uc120\ud0dd">{"".join(tabs)}</nav>
  {"".join(panes)}
</main>
<script>
const PASSWORD_HASH = "{password_hash}";
const gate = document.getElementById("gate");
const app = document.getElementById("app");
function hash(value) {{
  let h = 2166136261;
  for (const ch of value) {{ h ^= ch.codePointAt(0); h = Math.imul(h, 16777619) >>> 0; }}
  return h.toString(16).padStart(8, "0");
}}
function unlock() {{ gate.style.display = "none"; app.style.display = "block"; }}
if (sessionStorage.getItem("private-report-unlocked") === PASSWORD_HASH) unlock();
document.getElementById("login").addEventListener("submit", (event) => {{
  event.preventDefault();
  const value = document.getElementById("password").value;
  if (hash(value) === PASSWORD_HASH) {{ sessionStorage.setItem("private-report-unlocked", PASSWORD_HASH); unlock(); }}
  else {{ document.getElementById("error").textContent = "\ube44\ubc00\ubc88\ud638\uac00 \uc62c\ubc14\ub974\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4."; }}
}});
document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => {{
  document.querySelectorAll(".tab, .report-pane").forEach((el) => el.classList.remove("active"));
  tab.classList.add("active");
  document.getElementById(tab.dataset.target).classList.add("active");
}}));
</script>
</body>
</html>
'''
    (OUT / "index.html").write_text(html, encoding="utf-8")
    print(f"created {OUT / 'index.html'} ({len(REPORTS)} reports)")


if __name__ == "__main__":
    main()
