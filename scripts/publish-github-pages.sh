#!/usr/bin/env bash
set -euo pipefail

REPO="amrsalahsap-droid/VeriScope"
SITE_URL="https://amrsalahsap-droid.github.io/VeriScope/"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKTREE="${ROOT}"

cd "$ROOT"

# Recover from a broken or missing git checkout (common after tarball extract).
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Initializing git worktree from GitHub..."
  TMP="$(mktemp -d)"
  git clone "https://github.com/${REPO}.git" "$TMP/repo"
  for path in README.md docs/index.html docs/_config.yml .github/workflows/pages.yml scripts/publish-github-pages.sh; do
    if [[ -f "${ROOT}/${path}" ]]; then
      mkdir -p "$TMP/repo/$(dirname "$path")"
      cp "${ROOT}/${path}" "$TMP/repo/${path}"
    fi
  done
  WORKTREE="$TMP/repo"
  cd "$WORKTREE"
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "Installing GitHub CLI..."
  brew install gh
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "Log in to GitHub first:"
  gh auth login --hostname github.com --git-protocol https --web --scopes repo,workflow,read:org
fi

echo "Checking push access to ${REPO}..."
gh api "repos/${REPO}" --jq '.permissions.push'

git add README.md docs/index.html docs/_config.yml .github/workflows/pages.yml scripts/publish-github-pages.sh
git commit -m "$(cat <<'EOF'
Add public GitHub Pages site and project README.

Publish a discoverable landing page and enable automated Pages deployment.
EOF
)" || echo "Nothing new to commit."

git push -u origin main

echo "Enabling GitHub Pages..."
gh api -X POST "repos/${REPO}/pages" \
  -f build_type=workflow \
  -f source[branch]=main \
  -f source[path]=/docs 2>/dev/null || \
gh api -X PUT "repos/${REPO}/pages" \
  -f build_type=workflow \
  -f source[branch]=main \
  -f source[path]=/docs

gh api -X PATCH "repos/${REPO}" \
  -f description='Regression intelligence for engineering teams — recommend exactly what to test and explain why.' \
  -f homepage="${SITE_URL}" \
  -F 'topics[]=regression-testing' \
  -F 'topics[]=testing' \
  -F 'topics[]=github' \
  -F 'topics[]=python' \
  -F 'topics[]=nextjs'

echo
echo "Done."
echo "Repository: https://github.com/${REPO}"
echo "Public site:  ${SITE_URL}"
echo "Pages may take 1-2 minutes to become live after the workflow finishes."
