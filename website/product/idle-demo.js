import { useEffect, useRef, useState } from "react";
import { mayDemonstrate } from "./demo.js";

// Time-based demonstrations run only in their own visible, idle surface.
// Interaction cancels the pending beat synchronously; a later idle resume never resets data.
export function useIdleDemo(
  root,
  { reduced, suspended = false, idleMs = 12000, onBeat, onPause },
) {
  const [status, setStatus] = useState("waiting");
  const callbacks = useRef({ onBeat, onPause });
  callbacks.current = { onBeat, onPause };
  const api = useRef({});
  useEffect(() => {
    const host = root.current;
    if (!host) return;
    let timer,
      visible = false,
      occupied = false,
      focused = false,
      lastInput = 0,
      stopped = false;
    const allowed = () =>
      mayDemonstrate({
        visible,
        occupied,
        focused,
        reduced,
        suspended,
        hidden: document.hidden,
      });
    const cancel = (reason) => {
      clearTimeout(timer);
      callbacks.current.onPause?.(reason);
    };
    const schedule = (delay = 650) => {
      clearTimeout(timer);
      if (!allowed() || stopped) {
        setStatus(
          reduced
            ? "reduced"
            : suspended || occupied || focused
              ? "manual"
              : stopped
                ? "complete"
                : "waiting",
        );
        return;
      }
      const idleWait = Math.max(0, idleMs - (Date.now() - lastInput));
      setStatus(idleWait ? "idle" : "running");
      timer = setTimeout(
        () => {
          if (!allowed()) return;
          const duration = callbacks.current.onBeat();
          if (duration === null) {
            stopped = true;
            setStatus("complete");
            return;
          }
          schedule(duration);
        },
        Math.max(delay, idleWait),
      );
    };
    const pause = () => {
      lastInput = Date.now();
      stopped = false;
      cancel("input");
      setStatus("manual");
      schedule();
    };
    const enter = (e) => {
      if (e.pointerType === "mouse" && (Math.abs(e.movementX) + Math.abs(e.movementY) > 1)) {
        occupied = true;
        pause();
      }
    };
    const leave = () => {
      occupied = false;
      schedule();
    };
    const protectsFocus = (target) =>
      !!target?.matches?.(
        ':focus-visible, input, textarea, select, [contenteditable="true"]',
      );
    const focusIn = (e) => {
      focused = protectsFocus(e.target);
      pause();
    };
    const focusOut = (e) => {
      focused =
        host.contains(e.relatedTarget) && protectsFocus(e.relatedTarget);
      schedule();
    };
    const key = () => {
      focused = true;
      pause();
    };
    const visibility = () => {
      if (document.hidden) cancel("offscreen");
      schedule();
    };
    const scroll = () => {
      lastInput = Date.now();
      cancel("scroll");
      schedule();
    };
    const observer = new IntersectionObserver(
      ([entry]) => {
        visible = entry.isIntersecting;
        if (!visible) cancel("offscreen");
        schedule();
      },
      { threshold: 0, rootMargin: "-120px 0px -90px 0px" },
    );
    observer.observe(host);
    host.addEventListener("pointermove", enter);
    host.addEventListener("pointerleave", leave);
    host.addEventListener("pointerdown", pause);
    host.addEventListener("keydown", key);
    host.addEventListener("focusin", focusIn);
    host.addEventListener("focusout", focusOut);
    document.addEventListener("visibilitychange", visibility);
    window.addEventListener("scroll", scroll, { passive: true });
    window.addEventListener("wheel", scroll, { passive: true });
    window.addEventListener("touchmove", scroll, { passive: true });
    api.current = {
      pause,
      resume: () => {
        stopped = false;
        lastInput = 0;
        schedule();
      },
    };
    return () => {
      clearTimeout(timer);
      observer.disconnect();
      host.removeEventListener("pointermove", enter);
      host.removeEventListener("pointerleave", leave);
      host.removeEventListener("pointerdown", pause);
      host.removeEventListener("keydown", key);
      host.removeEventListener("focusin", focusIn);
      host.removeEventListener("focusout", focusOut);
      document.removeEventListener("visibilitychange", visibility);
      window.removeEventListener("scroll", scroll);
      window.removeEventListener("wheel", scroll);
      window.removeEventListener("touchmove", scroll);
    };
  }, [root, reduced, suspended, idleMs]);
  return {
    status,
    pause: () => api.current.pause?.(),
    resume: () => api.current.resume?.(),
  };
}
