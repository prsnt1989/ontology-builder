#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# Ontology Builder — Redeploy (rebuild & update container images)
#
# Use after code changes to push new images and roll the container apps.
#
# Usage:
#   ./redeploy.sh            # redeploy both services
#   ./redeploy.sh backend    # redeploy backend only
#   ./redeploy.sh frontend   # redeploy frontend only
###############################################################################

RESOURCE_GROUP="rg-onotology-builder"
ACR_NAME="ontologybuilder"
BACKEND_APP="ontology-backend"
FRONTEND_APP="ontology-frontend"

TARGET="${1:-all}"

# Load .env so backend secrets/credentials can be refreshed on redeploy.
ENV_FILE=".env"
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
else
  echo "WARN: $ENV_FILE not found — backend secrets/credentials will not be refreshed."
fi

ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)
TAG="$(date +%Y%m%d-%H%M%S)"

echo "═══════════════════════════════════════════════════════════════════════"
echo "  Ontology Builder — Redeploy"
echo "═══════════════════════════════════════════════════════════════════════"
echo "  ACR:    $ACR_LOGIN_SERVER"
echo "  Tag:    $TAG"
echo "  Target: $TARGET"
echo ""

az acr login --name "$ACR_NAME"

# ─── Backend ─────────────────────────────────────────────────────────────────
if [[ "$TARGET" == "all" || "$TARGET" == "backend" ]]; then
  echo "▶ Building backend..."
  docker build --platform linux/amd64 \
    -t "$ACR_LOGIN_SERVER/$BACKEND_APP:$TAG" \
    -t "$ACR_LOGIN_SERVER/$BACKEND_APP:latest" \
    -f docker/backend/Dockerfile .

  echo "  Pushing backend image..."
  docker push "$ACR_LOGIN_SERVER/$BACKEND_APP:$TAG"
  docker push "$ACR_LOGIN_SERVER/$BACKEND_APP:latest"

  echo "  Updating container app..."
  az containerapp update \
    --name "$BACKEND_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --image "$ACR_LOGIN_SERVER/$BACKEND_APP:$TAG" \
    --output none

  # Refresh secret + env vars from .env so credential changes take effect.
  if [ -f "$ENV_FILE" ] && [ -n "${AZURE_OPENAI_API_KEY:-}" ]; then
    echo "  Refreshing backend secret & credentials..."
    az containerapp secret set \
      --name "$BACKEND_APP" \
      --resource-group "$RESOURCE_GROUP" \
      --secrets "azure-openai-key=$AZURE_OPENAI_API_KEY" \
      --output none

    az containerapp update \
      --name "$BACKEND_APP" \
      --resource-group "$RESOURCE_GROUP" \
      --set-env-vars \
        "AZURE_OPENAI_ENDPOINT=$AZURE_OPENAI_ENDPOINT" \
        "AZURE_OPENAI_API_KEY=secretref:azure-openai-key" \
        "AZURE_OPENAI_DEPLOYMENT=${AZURE_OPENAI_DEPLOYMENT:-gpt-4o}" \
        "AZURE_OPENAI_API_VERSION=${AZURE_OPENAI_API_VERSION:-2025-03-01-preview}" \
        "CORS_ORIGINS=*" \
      --output none
  fi

  echo "  ✓ Backend deployed"
  echo ""
fi

# ─── Frontend ────────────────────────────────────────────────────────────────
if [[ "$TARGET" == "all" || "$TARGET" == "frontend" ]]; then
  echo "▶ Building frontend..."
  docker build --platform linux/amd64 \
    -t "$ACR_LOGIN_SERVER/$FRONTEND_APP:$TAG" \
    -t "$ACR_LOGIN_SERVER/$FRONTEND_APP:latest" \
    -f docker/frontend/Dockerfile .

  echo "  Pushing frontend image..."
  docker push "$ACR_LOGIN_SERVER/$FRONTEND_APP:$TAG"
  docker push "$ACR_LOGIN_SERVER/$FRONTEND_APP:latest"

  echo "  Updating container app..."
  az containerapp update \
    --name "$FRONTEND_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --image "$ACR_LOGIN_SERVER/$FRONTEND_APP:$TAG" \
    --output none

  echo "  ✓ Frontend deployed"
  echo ""
fi

# ─── Done ────────────────────────────────────────────────────────────────────
FRONTEND_FQDN=$(az containerapp show \
  --name "$FRONTEND_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --query "properties.configuration.ingress.fqdn" -o tsv)

echo "═══════════════════════════════════════════════════════════════════════"
echo "  ✓ Redeploy complete!   Tag: $TAG"
echo ""
echo "  App URL: https://$FRONTEND_FQDN"
echo ""
echo "  View logs:"
echo "    az containerapp logs show -n $BACKEND_APP -g $RESOURCE_GROUP --follow"
echo "═══════════════════════════════════════════════════════════════════════"
