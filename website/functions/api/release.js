// SPDX-License-Identifier: GPL-3.0-only
// /api/release -> version and size of the newest published installer, for the
// page's download button. { available: false } until a version is released.
import { latestRelease, summary } from "../../server/latest-release.js";

export async function onRequestGet({ env }) {
  let body;
  try {
    body = summary(await latestRelease(env));
  } catch {
    body = { available: null };
  }
  return new Response(JSON.stringify(body), {
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": body.available === null ? "no-store" : "public, max-age=300",
    },
  });
}
