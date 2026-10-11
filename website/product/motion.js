import { useEffect, useRef, useState } from "react";

// Chapter-local entry: children marked data-reveal fade up once when seen.
export function useReveal(root, reduced) {
  useEffect(() => {
    const host = root.current;
    if (!host) return;
    const items = [...host.querySelectorAll("[data-reveal]")];
    if (reduced || !("IntersectionObserver" in window)) {
      items.forEach((el) => el.classList.add("is-in"));
      return;
    }
    const ob = new IntersectionObserver(
      (entries) =>
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("is-in");
            ob.unobserve(e.target);
          }
        }),
      { rootMargin: "0px 0px -8% 0px", threshold: 0.12 },
    );
    items.forEach((el) => ob.observe(el));
    return () => ob.disconnect();
  }, [root, reduced]);
}

export function useMedia(query) {
  const [match, set] = useState(() => matchMedia(query).matches);
  useEffect(() => {
    const m = matchMedia(query),
      fn = () => set(m.matches);
    m.addEventListener("change", fn);
    return () => m.removeEventListener("change", fn);
  }, [query]);
  return match;
}

// True while at least `threshold` of the element is on screen.
export function useInView(ref, threshold = 0.3) {
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ob = new IntersectionObserver(([e]) => setSeen(e.isIntersecting), { threshold });
    ob.observe(el);
    return () => ob.disconnect();
  }, [ref, threshold]);
  return seen;
}

// A looping, time-driven demonstration: steps with durations, played only while
// visible and not paused. Reduced motion holds the `still` step.
export function useLoop(ref, durations, { reduced = false, paused = false, still = durations.length - 1 } = {}) {
  const visible = useInView(ref, 0.25);
  const [state, setState] = useState({ step: reduced ? still : 0, ms: 0 });
  const run = visible && !paused && !reduced;
  useEffect(() => {
    if (reduced) return setState({ step: still, ms: 0 });
    if (!run) return;
    let raf,
      last = performance.now();
    const tick = (now) => {
      const dt = document.hidden ? 0 : Math.min(100, now - last);
      last = now;
      setState((s) => {
        let { step, ms } = s;
        ms += dt;
        if (ms >= durations[step]) {
          ms = 0;
          step = (step + 1) % durations.length;
        }
        return { step, ms };
      });
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [run, reduced]);
  return { ...state, running: run, go: (step) => setState({ step, ms: 0 }) };
}
