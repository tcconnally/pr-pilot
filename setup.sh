#!/bin/bash
# PR Pilot — Quick setup script
# Run after creating the GitHub App and enabling Google Cloud APIs
set -e

echo "=== PR Pilot Setup ==="
echo ""

# ── Prerequisites ──────────────────────────────────────────────────
echo "Before running this script:"
echo "1. Create the GitHub App:"
echo "   https://github.com/settings/apps/new?url=https://raw.githubusercontent.com/tcconnally/pr-pilot/main/app-manifest.yaml"
echo ""
echo "2. After creating the app, note:"
echo "   - App ID (number)"
echo "   - Download the private key (.pem file)"
echo "   - Set a webhook secret"
echo ""
echo "3. Enable Google Cloud APIs:"
echo "   gcloud services enable run.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com aiplatform.googleapis.com"
echo ""
echo "4. Store secrets in Google Cloud Secret Manager:"
echo "   echo -n 'YOUR_GEMINI_API_KEY' | gcloud secrets create gemini-api-key --data-file=-"
echo "   cat your-private-key.pem | gcloud secrets create github-app-private-key --data-file=-"
echo ""

read -p "Press Enter when ready to continue, or Ctrl+C to exit."

# ── Check prerequisites ────────────────────────────────────────────
command -v gcloud >/dev/null 2>&1 || { echo "gcloud CLI not found. Install: https://cloud.google.com/sdk"; exit 1; }
command -v git >/dev/null 2>&1 || { echo "git not found"; exit 1; }

echo ""

# ── Get user input ─────────────────────────────────────────────────
read -p "Google Cloud Project ID: " PROJECT_ID
read -p "GitHub App ID: " GITHUB_APP_ID
read -p "GitHub Webhook Secret: " GITHUB_WEBHOOK_SECRET
read -p "Path to GitHub App private key (.pem): " PEM_PATH

if [ ! -f "$PEM_PATH" ]; then
    echo "Private key not found at: $PEM_PATH"
    exit 1
fi

# ── Set Google Cloud project ───────────────────────────────────────
gcloud config set project "$PROJECT_ID"

# ── Store secrets ──────────────────────────────────────────────────
echo "Storing secrets..."
echo -n "$GITHUB_APP_ID" | gcloud secrets create github-app-id --data-file=- 2>/dev/null || \
    echo -n "$GITHUB_APP_ID" | gcloud secrets versions add github-app-id --data-file=-

cat "$PEM_PATH" | gcloud secrets create github-app-private-key --data-file=- 2>/dev/null || \
    cat "$PEM_PATH" | gcloud secrets versions add github-app-private-key --data-file=-

echo -n "$GITHUB_WEBHOOK_SECRET" | gcloud secrets create github-webhook-secret --data-file=- 2>/dev/null || \
    echo -n "$GITHUB_WEBHOOK_SECRET" | gcloud secrets versions add github-webhook-secret --data-file=-

# ── Create Artifact Registry repo ──────────────────────────────────
echo "Creating Artifact Registry..."
gcloud artifacts repositories create pr-pilot \
    --repository-format=docker \
    --location=us-central1 \
    2>/dev/null || echo "Repository already exists"

# ── Build and deploy ───────────────────────────────────────────────
echo "Building and deploying..."
gcloud builds submit \
    --config cloudbuild.yaml \
    --substitutions _GITHUB_APP_ID="$GITHUB_APP_ID",_GITHUB_WEBHOOK_SECRET="$GITHUB_WEBHOOK_SECRET"

# ── Get deployed URL ───────────────────────────────────────────────
SERVICE_URL=$(gcloud run services describe pr-pilot --region us-central1 --format 'value(status.url)')
echo ""
echo "=== Deployment Complete ==="
echo "Service URL: $SERVICE_URL"
echo "Webhook URL: $SERVICE_URL/webhook/github"
echo ""
echo "Next: Update GitHub App webhook URL to: $SERVICE_URL/webhook/github"
echo "Then install the app on your repos at: https://github.com/apps/pr-pilot"
