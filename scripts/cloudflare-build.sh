#!/bin/bash
set -euo pipefail

rm -rf dist
mkdir -p dist

cp index.html login.html settings.html statistic.html dist/
cp -R assets css images js dist/

if [ -d data ]; then
  cp -R data dist/
fi
