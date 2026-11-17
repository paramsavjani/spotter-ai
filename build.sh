#!/usr/bin/env bash
# Build step for a single-service deploy (Render, Railway, ...):
# installs the backend, builds the React app and puts it where Django serves it from.
set -e
pip install -r backend/requirements.txt
cd frontend
npm ci
npm run build
rm -rf ../backend/frontend_build
cp -r dist ../backend/frontend_build
