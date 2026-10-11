/* Trusted adapter; artwork is statically audited at build time, never user HTML. */
const style = document.createElement("style");
style.textContent = window.artwork.css;
document.head.append(style);
let last = "",
  timeline = null,
  duration = 3;
const esc = (text) =>
  String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
function mount(text, span) {
  timeline?.kill();
  duration = Math.max(0.1, span);
  document.querySelector(".wt-cue").innerHTML = window.artwork.html
    .replaceAll("{{text}}", esc(text))
    .replaceAll("{{words}}", esc(text))
    .replaceAll("{{speaker}}", "")
    .replaceAll("{{translation}}", "");
  const a = window.artwork.appearance,
    el = document.querySelector("#surface");
  el.style.setProperty("--wt-u", "1.111111vh");
  el.style.setProperty("--wt-size", a.fontSize / 10.8 + "vh");
  el.style.setProperty(
    "--wt-font",
    "Microsoft YaHei UI, Microsoft YaHei, sans-serif",
  );
  el.style.setProperty("--wt-color", a.color);
  el.style.setProperty("--wt-weight", a.fontWeight || 700);
  el.style.setProperty("--wt-spacing", a.letterSpacing / 10.8 + "vh");
  el.style.setProperty("--wt-dur", duration + "s");
  // Keep percentage centering independent of MotionSpec x/y offsets.
  const centered = document.querySelector(".crt-screen-text");
  if (centered)
    gsap.set(centered, { xPercent: -50, yPercent: -50, x: 0, y: 0 });
  // Fit current text within the existing artwork, without changing its geometry.
  const lettering = document.querySelector(".main-copy,.crt-screen-text");
  if (lettering) {
    let size = parseFloat(getComputedStyle(lettering).fontSize);
    const limit = centered
      ? centered.parentElement.clientHeight * 0.85
      : lettering.clientHeight;
    while (lettering.scrollHeight > limit + 1 && size > innerHeight / 60) {
      size *= 0.95;
      el.style.setProperty("--wt-size", size + "px");
    }
  }
  timeline = gsap.timeline({ paused: true });
  const spec = window.artwork.motion,
    entry = Math.min(spec.buildMs / 1000, duration * 0.3),
    exit = Math.min(spec.resolveMs / 1000, duration * 0.25);
  for (const t of spec.tracks) {
    const length =
        t.phase === "resolve"
          ? exit
          : t.phase === "breathe"
            ? (t.durationMs || 4000) / 1000
            : entry,
      offset =
        t.phase === "resolve"
          ? duration - exit
          : t.phase === "breathe"
            ? entry
            : 0;
    const nodes = document.querySelectorAll(t.selector);
    if (!nodes.length) continue;
    const from = { ...t.from },
      to = { ...t.to };
    for (const obj of [from, to])
      for (const k of ["x", "y"])
        if (typeof obj[k] === "number") obj[k] *= innerHeight / 1080;
    timeline.fromTo(
      nodes,
      from,
      {
        ...to,
        duration: Math.max(0.001, (t.end - t.start) * length),
        ease: t.ease,
        immediateRender: false,
      },
      offset + t.start * length,
    );
  }
  timeline.seek(0.001);
}
let latest = null;
function display(d) {
  const key = d.text + "|" + d.duration;
  if (last !== key) {
    last = key;
    mount(d.text, d.duration);
  }
  document.body.style.opacity = d.visible === false ? "0" : "1";
  timeline?.seek(d.reduced ? Math.min(0.9, d.duration * 0.45) : Math.max(0, Math.min(d.duration, d.time)), false);
}
window.addEventListener("message", (event) => {
  if (event.source !== parent || event.data?.type !== "2byte-demo-caption")
    return;
  const d = event.data;
  if (
    typeof d.text !== "string" ||
    d.text.length > 500 ||
    !Number.isFinite(d.time) ||
    !Number.isFinite(d.duration)
  )
    return;
  latest = d;
  display(d);
});
window.addEventListener("resize", () => { if(latest){last = "";display(latest);} });
parent.postMessage({ type: "2byte-demo-theme-ready" }, "*");
