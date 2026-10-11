import "./tokens.css";
import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { Icon } from "./icons.jsx";
import { Mascot } from "./kit.jsx";
import { ISSUES, RELEASES, VERSION } from "./data.js";
import { useMedia } from "./motion.js";
import { COPY, LANG, LANGS, pageFor, rich } from "./i18n/index.jsx";
import { Hero, Compare } from "./hero.jsx";
import { ReviewFeature, ProofreadFeature, GlossaryFeature, TimingFeature, ExportFeature } from "./features.jsx";
import { ModelsChapter, Download } from "./models.jsx";
import "./site.css";

const NAV = ["compare", "review", "proofread", "glossary", "timing", "export", "models"].map((id) => [id, COPY.nav[id]]);

// Three pages, one per language; each link names its language in that language.
function LangSwitch({ className = "" }) {
  return (
    <nav className={"lang-switch " + className} aria-label={COPY.nav.language}>
      {LANGS.map(([k, label, tag, short]) => (
        <a key={k} href={pageFor(k)} hrefLang={tag} lang={tag} aria-label={label} aria-current={k === LANG ? "page" : undefined}>
          <span className="ls-full">{label}</span>
          <span className="ls-short" aria-hidden="true">{short}</span>
        </a>
      ))}
    </nav>
  );
}

function SiteNav() {
  const [scrolled, setScrolled] = useState(false);
  const [current, setCurrent] = useState(null);
  useEffect(() => {
    const read = () => {
      setScrolled(scrollY > 8);
      let at = null;
      for (const [id] of NAV) {
        const el = document.getElementById(id);
        if (el && el.getBoundingClientRect().top < innerHeight * 0.4) at = id;
      }
      setCurrent(at);
    };
    read();
    addEventListener("scroll", read, { passive: true });
    return () => removeEventListener("scroll", read);
  }, []);
  return (
    <header className={"site-nav" + (scrolled ? " is-scrolled" : "")}>
      <div className="wrap-wide nav-inner">
        <a href="#top" className="nav-brand" aria-label={COPY.nav.home}>
          <Mascot size={34} />
          <b>2ByteASR</b>
          <span lang="zh-CN">兔白字幕</span>
        </a>
        <nav className="nav-sections" aria-label={COPY.nav.sections}>
          {NAV.map(([id, label]) => (
            <a key={id} href={"#" + id} aria-current={current === id ? "true" : undefined}>
              {label}
            </a>
          ))}
        </nav>
        <LangSwitch />
        <a className="btn primary small nav-cta" href="#download">
          {COPY.nav.download}
        </a>
      </div>
    </header>
  );
}

function Footer({ quiet, setQuiet, systemReduced }) {
  return (
    <footer className="site-footer">
      <div className="wrap-wide footer-inner">
        <div className="footer-brand">
          <Mascot size={28} />
          <b>2ByteASR · <span lang="zh-CN">兔白字幕</span></b>
          <span>{VERSION}</span>
        </div>
        <nav aria-label={COPY.footer.label}>
          <a href={RELEASES} target="_blank" rel="noreferrer">{COPY.footer.releases} <Icon name="external" size={13} /></a>
          <a href={ISSUES} target="_blank" rel="noreferrer">{COPY.footer.issues} <Icon name="external" size={13} /></a>
          <a href="./THIRD_PARTY.md">{COPY.footer.thirdParty}</a>
        </nav>
        <label className="motion-toggle">
          <input
            type="checkbox"
            checked={quiet || systemReduced}
            disabled={systemReduced}
            onChange={(e) => setQuiet(e.target.checked)}
          />
          {COPY.footer.motion}{systemReduced ? COPY.footer.followSystem : ""}
        </label>
        <LangSwitch className="footer-lang" />
        <p className="footer-note">{rich(COPY.footer.note)}</p>
      </div>
    </footer>
  );
}

function Page() {
  const systemReduced = useMedia("(prefers-reduced-motion: reduce)");
  const [quiet, setQuiet] = useState(false);
  const reduced = quiet || systemReduced;
  return (
    <div className={reduced ? "reduced" : ""}>
      <a className="skip" href="#content">{COPY.skip}</a>
      <SiteNav />
      <main id="content">
        <Hero reduced={reduced} />
        <Compare reduced={reduced} />
        <ReviewFeature reduced={reduced} />
        <ProofreadFeature reduced={reduced} />
        <GlossaryFeature reduced={reduced} />
        <TimingFeature reduced={reduced} />
        <ExportFeature reduced={reduced} />
        <ModelsChapter reduced={reduced} />
        <Download />
      </main>
      <Footer quiet={quiet} setQuiet={setQuiet} systemReduced={systemReduced} />
    </div>
  );
}

createRoot(document.getElementById("root")).render(<Page />);
