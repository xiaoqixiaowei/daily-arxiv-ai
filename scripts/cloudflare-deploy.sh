#!/bin/bash
set -euo pipefail

bash scripts/cloudflare-build.sh

npx wrangler deploy --config wrangler.jsonc
