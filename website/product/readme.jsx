// Fixed scenes for README media, built from the same components as the page.
// The README GIFs in docs/assets/readme were recorded from the 2026-09-30
// scenes and have not been re-recorded with these components.
import React from "react";
import { createRoot } from "react-dom/client";
import { ReviewDemo, ProofreadDemo, GlossaryDemo, TimingDemo, ExportDemo } from "./features.jsx";
import "./tokens.css";
import "./readme.css";

const SCENES = {
  "speaker-tracks": TimingDemo,
  "word-split": TimingDemo,
  "candidate-review": ReviewDemo,
  proofread: ProofreadDemo,
  glossary: GlossaryDemo,
  export: ExportDemo,
};
const scene = new URLSearchParams(location.search).get("scene") || "speaker-tracks";
const Scene = SCENES[scene] || TimingDemo;
createRoot(document.getElementById("root")).render(
  <main className={"readme-stage scene-" + scene} data-scene={scene}>
    <Scene reduced />
  </main>,
);
