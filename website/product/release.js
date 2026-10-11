// Newest published installer, asked once per page from /api/release
// (functions/api/release.js). null while loading, offline or on error, so the
// page keeps its build-time version; { available: false } before any release.
import { useEffect, useState } from "react";
import { RELEASE_API, VERSION } from "./data.js";

let request;
const load = () =>
  (request ??= fetch(RELEASE_API, { headers: { accept: "application/json" } })
    .then((r) => (r.ok ? r.json() : null))
    .then((j) => (j && typeof j.available === "boolean" ? j : null))
    .catch(() => null));

export function useLatestRelease() {
  const [rel, setRel] = useState(null);
  useEffect(() => {
    if (!RELEASE_API) return;
    let live = true;
    load().then((r) => live && setRel(r));
    return () => {
      live = false;
    };
  }, []);
  return rel;
}

export const releaseVersion = (rel) => (rel?.available ? rel.version : VERSION);

// 1009166375 -> "962 MB"
export function bytesLabel(bytes) {
  if (!bytes) return "";
  const mb = bytes / 1048576;
  return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${Math.round(mb)} MB`;
}
