#!/bin/bash
set -euo pipefail

bash scripts/cloudflare-build.sh

npx wrangler versions upload --config wrangler.jsonc --assets=./dist
