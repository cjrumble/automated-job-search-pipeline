/**
 * Netlify Function: trigger
 *
 * Receives form data from the frontend, validates/sanitizes inputs,
 * and calls the GitHub Actions workflow_dispatch API to run the pipeline
 * with the user's custom parameters.
 *
 * Required Netlify env vars:
 *   GITHUB_TOKEN  — a GitHub Personal Access Token with the `workflow` scope
 *   GITHUB_OWNER  — your GitHub username (e.g. "cjrumble")
 *   GITHUB_REPO   — your repo name   (e.g. "automated-job-search-pipeline")
 */

const ALLOWED_ORIGIN = process.env.ALLOWED_ORIGIN || '*';

// Only printable ASCII, no shell-special characters
const SAFE_TEXT_RE = /^[\x20-\x7E]{1,200}$/;
// Comma-separated slugs: letters, digits, hyphens
const SLUG_LIST_RE = /^[a-z0-9][a-z0-9-]*(,[a-z0-9][a-z0-9-]*)*$/i;

function sanitize(value) {
  return (value || '').toString().trim().slice(0, 200);
}

function isValidText(value) {
  return SAFE_TEXT_RE.test(value);
}

function isValidSlugList(value) {
  if (!value) return true;
  return SLUG_LIST_RE.test(value);
}

exports.handler = async (event) => {
  const corsHeaders = {
    'Access-Control-Allow-Origin': ALLOWED_ORIGIN,
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };

  // Handle CORS preflight
  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 204, headers: corsHeaders, body: '' };
  }

  if (event.httpMethod !== 'POST') {
    return {
      statusCode: 405,
      headers: corsHeaders,
      body: JSON.stringify({ error: 'Method not allowed.' }),
    };
  }

  // ── Parse body ────────────────────────────────────────────────────────────
  let body;
  try {
    body = JSON.parse(event.body || '{}');
  } catch {
    return {
      statusCode: 400,
      headers: corsHeaders,
      body: JSON.stringify({ error: 'Invalid JSON body.' }),
    };
  }

  const role        = sanitize(body.target_role);
  const location    = sanitize(body.target_location);
  const greenhouse  = sanitize(body.greenhouse_companies);
  const lever       = sanitize(body.lever_companies);

  // ── Validate ──────────────────────────────────────────────────────────────
  if (!role || !isValidText(role)) {
    return {
      statusCode: 400,
      headers: corsHeaders,
      body: JSON.stringify({ error: 'target_role is required and must be plain text (max 200 chars).' }),
    };
  }

  if (!location || !isValidText(location)) {
    return {
      statusCode: 400,
      headers: corsHeaders,
      body: JSON.stringify({ error: 'target_location is required and must be plain text (max 200 chars).' }),
    };
  }

  if (greenhouse && !isValidSlugList(greenhouse)) {
    return {
      statusCode: 400,
      headers: corsHeaders,
      body: JSON.stringify({ error: 'greenhouse_companies must be comma-separated slugs (letters, digits, hyphens).' }),
    };
  }

  if (lever && !isValidSlugList(lever)) {
    return {
      statusCode: 400,
      headers: corsHeaders,
      body: JSON.stringify({ error: 'lever_companies must be comma-separated slugs (letters, digits, hyphens).' }),
    };
  }

  // ── GitHub env ────────────────────────────────────────────────────────────
  const token = process.env.GITHUB_TOKEN;
  const owner = process.env.GITHUB_OWNER;
  const repo  = process.env.GITHUB_REPO;

  if (!token || !owner || !repo) {
    console.error('[trigger] Missing GITHUB_TOKEN, GITHUB_OWNER, or GITHUB_REPO env vars.');
    return {
      statusCode: 500,
      headers: corsHeaders,
      body: JSON.stringify({ error: 'Server misconfiguration — contact the site owner.' }),
    };
  }

  // ── Dispatch workflow ─────────────────────────────────────────────────────
  const url = `https://api.github.com/repos/${owner}/${repo}/actions/workflows/daily_pipeline.yml/dispatches`;

  const ghRes = await fetch(url, {
    method: 'POST',
    headers: {
      Accept:        'application/vnd.github+json',
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      'X-GitHub-Api-Version': '2022-11-28',
    },
    body: JSON.stringify({
      ref: 'main',
      inputs: {
        target_role:          role,
        target_location:      location,
        greenhouse_companies: greenhouse || '',
        lever_companies:      lever || '',
      },
    }),
  });

  if (ghRes.status === 204) {
    return {
      statusCode: 200,
      headers: corsHeaders,
      body: JSON.stringify({ ok: true }),
    };
  }

  const ghBody = await ghRes.text();
  console.error(`[trigger] GitHub API error ${ghRes.status}: ${ghBody}`);

  return {
    statusCode: 502,
    headers: corsHeaders,
    body: JSON.stringify({
      error: `GitHub API returned ${ghRes.status}. Check that GITHUB_TOKEN has the "workflow" scope.`,
    }),
  };
};
