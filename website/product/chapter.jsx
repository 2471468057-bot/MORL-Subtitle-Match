import React, { useRef } from "react";
import { Icon } from "./icons.jsx";
import { useReveal } from "./motion.js";

// One section, one idea. Headline (key phrase in the section's ink) and lede on
// the left, three short points on the right, then one full-width demonstration.
// Every demonstration uses the same frame size, so sections share one rhythm.
export function Section({ id, ink, title, lede, points, tone = false, reduced, children, className = "" }) {
  const root = useRef();
  useReveal(root, reduced);
  return (
    <section id={id} ref={root} className={"sec" + (tone ? " tone" : "") + (className ? " " + className : "")} style={{ "--ch": ink }} aria-labelledby={id + "-title"}>
      <div className="wrap">
        <header className="sec-head" data-reveal>
          <div className="sec-main">
            <h2 className="sec-title" id={id + "-title"}>
              {title}
            </h2>
            <p className="sec-lede">{lede}</p>
          </div>
          {points && (
            <ul className="sec-points">
              {points.map(([icon, head, text]) => (
                <li key={head}>
                  <Icon name={icon} size={20} />
                  <b>{head}</b>
                  <span>{text}</span>
                </li>
              ))}
            </ul>
          )}
        </header>
        {children && (
          <div className="sec-body" data-reveal style={{ "--i": 1 }}>
            {children}
          </div>
        )}
      </div>
    </section>
  );
}
