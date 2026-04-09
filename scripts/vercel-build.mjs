#!/usr/bin/env node

import path from "node:path";
import { spawnSync } from "node:child_process";

const DEFAULT_PRODUCTION_BASE_URL = "https://bbnotes.vercel.app/";

function normalizeBaseUrl(value) {
  const trimmed = value.trim();
  if (!trimmed) {
    return DEFAULT_PRODUCTION_BASE_URL;
  }

  const withProtocol = /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
  return withProtocol.endsWith("/") ? withProtocol : `${withProtocol}/`;
}

function resolveBaseUrl(env = process.env) {
  const explicit = env.SUMMARIZER_SITE_BASE_URL;
  if (explicit) {
    return normalizeBaseUrl(explicit);
  }

  if (env.VERCEL === "1") {
    if (env.VERCEL_ENV === "production" && env.VERCEL_PROJECT_PRODUCTION_URL) {
      return normalizeBaseUrl(env.VERCEL_PROJECT_PRODUCTION_URL);
    }
    if (env.VERCEL_BRANCH_URL) {
      return normalizeBaseUrl(env.VERCEL_BRANCH_URL);
    }
    if (env.VERCEL_URL) {
      return normalizeBaseUrl(env.VERCEL_URL);
    }
    if (env.VERCEL_PROJECT_PRODUCTION_URL) {
      return normalizeBaseUrl(env.VERCEL_PROJECT_PRODUCTION_URL);
    }
  }

  return DEFAULT_PRODUCTION_BASE_URL;
}

function runOrExit(command, args, options = {}) {
  const result = spawnSync(command, args, {
    stdio: "inherit",
    ...options,
  });

  if (result.error) {
    throw result.error;
  }
  if (typeof result.status === "number" && result.status !== 0) {
    process.exit(result.status);
  }
}

const projectRoot = process.cwd();
const hugoCacheDir = process.env.HUGO_CACHEDIR || path.join(projectRoot, ".hugo_cache");
const baseUrl = resolveBaseUrl(process.env);

console.log(`[vercel-build] Hugo baseURL: ${baseUrl}`);

runOrExit(
  "hugo",
  ["--source", "blog", "--destination", "public", "--gc", "--minify", "--baseURL", baseUrl],
  {
    cwd: projectRoot,
    env: {
      ...process.env,
      HUGO_CACHEDIR: hugoCacheDir,
    },
  },
);

runOrExit("node", ["scripts/build-search-index.mjs"], {
  cwd: projectRoot,
  env: {
    ...process.env,
    OUTPUT_DIR: "blog/public",
  },
});
