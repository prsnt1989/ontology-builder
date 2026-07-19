#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# Ontology Builder — Azure Deployment Script
#
# Prerequisites:
#   - Azure CLI installed and logged in:  az login
#   - Docker installed and running (builds linux/amd64 images from a Mac)
#   - .env file configured at the repo root (Azure OpenAI credentials)
#
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh
#
# What this script does:
#   1. Creates the Azure resource group (if not exists)
#   2. Creates the Azure Container Registry (ACR)
#   3. Builds & pushes the backend + frontend Docker images to ACR
#   4. Creates the Container Apps environment (with Log Analytics)
#   5. Deploys backend (internal) and frontend (external) as Container Apps
#   6. Wires env vars + the Azure OpenAI key as a Container App secret
#   7. Prints the public URL
###############################################################################

# ─── Configuration ───────────────────────────────────────────────────────────
RESOURCE_GROUP="rg-onotology-builder"
LOCATION="eastus"
ACR_NAME="ontologybuilder"
ENVIRONMENT_NAME="ontology-builder-env"
LOG_ANALYTICS_WORKSPACE="ontology-builder-logs"

BACKEND_APP="ontology-backend"
FRONTEND_APP="ontology-frontend"

# Load Azure OpenAI credentials from the repo-root .env.
# `set -a` + source reads values verbatim (endpoints/keys may contain '=' or '/').
ENV_FILE=".env"
if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: $ENV_FILE not found. Copy .env.example to .env and fill in values."
  exit 1
fi
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${AZURE_OPENAI_ENDPOINT:?AZURE_OPENAI_ENDPOINT not set in .env}"
: "${AZURE_OPENAI_API_KEY:?AZURE_OPENAI_API_KEY not set in .env}"
AZURE_OPENAI_DEPLOYMENT="${AZURE_OPENAI_DEPLOYMENT:-gpt-4o}"
AZURE_OPENAI_API_VERSION="${AZURE_OPENAI_API_VERSION:-2025-03-01-preview}"

echo "═══════════════════════════════════════════════════════════════════════"
echo "  Ontology Builder — Azure Deployment"
echo "═══════════════════════════════════════════════════════════════════════"
echo ""
echo "  Resource Group:  $RESOURCE_GROUP"
echo "  Location:        $LOCATION"
echo "  ACR:             $ACR_NAME"
echo ""

# ─── Step 1: Resource Group ──────────────────────────────────────────────────
echo "▶ Step 1: Creating resource group..."
az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --output none

# ─── Step 2: Azure Container Registry ────────────────────────────────────────
echo "▶ Step 2: Creating Azure Container Registry..."
az acr create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$ACR_NAME" \
  --sku Basic \
  --admin-enabled true \
  --output none

ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)
ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --query "passwords[0].value" -o tsv)

echo "  ACR Login Server: $ACR_LOGIN_SERVER"

# ─── Step 3: Build & Push Docker Images ──────────────────────────────────────
echo "▶ Step 3: Building and pushing Docker images..."
az acr login --name "$ACR_NAME"

echo "  Building backend..."
docker build --platform linux/amd64 \
  -t "$ACR_LOGIN_SERVER/$BACKEND_APP:latest" \
  -f docker/backend/Dockerfile .

echo "  Building frontend..."
docker build --platform linux/amd64 \
  -t "$ACR_LOGIN_SERVER/$FRONTEND_APP:latest" \
  -f docker/frontend/Dockerfile .

echo "  Pushing images..."
docker push "$ACR_LOGIN_SERVER/$BACKEND_APP:latest"
docker push "$ACR_LOGIN_SERVER/$FRONTEND_APP:latest"

# ─── Step 4: Log Analytics & Container Apps Environment ──────────────────────
echo "▶ Step 4: Creating Container Apps environment..."

az monitor log-analytics workspace create \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$LOG_ANALYTICS_WORKSPACE" \
  --location "$LOCATION" \
  --output none 2>/dev/null || true

LOG_ANALYTICS_ID=$(az monitor log-analytics workspace show \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$LOG_ANALYTICS_WORKSPACE" \
  --query customerId -o tsv)

LOG_ANALYTICS_KEY=$(az monitor log-analytics workspace get-shared-keys \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$LOG_ANALYTICS_WORKSPACE" \
  --query primarySharedKey -o tsv)

az containerapp env create \
  --name "$ENVIRONMENT_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --logs-workspace-id "$LOG_ANALYTICS_ID" \
  --logs-workspace-key "$LOG_ANALYTICS_KEY" \
  --output none 2>/dev/null || true

# ─── Step 5: Deploy Backend (internal ingress) ───────────────────────────────
echo "▶ Step 5: Deploying backend container app..."

az containerapp create \
  --name "$BACKEND_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$ENVIRONMENT_NAME" \
  --image "$ACR_LOGIN_SERVER/$BACKEND_APP:latest" \
  --registry-server "$ACR_LOGIN_SERVER" \
  --registry-username "$ACR_NAME" \
  --registry-password "$ACR_PASSWORD" \
  --target-port 8005 \
  --ingress internal \
  --min-replicas 1 \
  --max-replicas 3 \
  --cpu 1.0 \
  --memory 2.0Gi \
  --secrets "azure-openai-key=$AZURE_OPENAI_API_KEY" \
  --env-vars \
    "AZURE_OPENAI_ENDPOINT=$AZURE_OPENAI_ENDPOINT" \
    "AZURE_OPENAI_API_KEY=secretref:azure-openai-key" \
    "AZURE_OPENAI_DEPLOYMENT=$AZURE_OPENAI_DEPLOYMENT" \
    "AZURE_OPENAI_API_VERSION=$AZURE_OPENAI_API_VERSION" \
    "CORS_ORIGINS=*" \
  --output none 2>/dev/null || \
az containerapp update \
  --name "$BACKEND_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --image "$ACR_LOGIN_SERVER/$BACKEND_APP:latest" \
  --output none

BACKEND_FQDN=$(az containerapp show \
  --name "$BACKEND_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --query "properties.configuration.ingress.fqdn" -o tsv)

echo "  Backend FQDN: $BACKEND_FQDN (internal)"

# ─── Step 6: Deploy Frontend (external ingress) ──────────────────────────────
echo "▶ Step 6: Deploying frontend container app..."

# nginx proxies /api → the backend. Within a Container Apps environment an
# internal app is reachable by its name; we pass the full internal FQDN to be safe.
az containerapp create \
  --name "$FRONTEND_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$ENVIRONMENT_NAME" \
  --image "$ACR_LOGIN_SERVER/$FRONTEND_APP:latest" \
  --registry-server "$ACR_LOGIN_SERVER" \
  --registry-username "$ACR_NAME" \
  --registry-password "$ACR_PASSWORD" \
  --target-port 80 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 3 \
  --cpu 0.5 \
  --memory 1.0Gi \
  --env-vars \
    "BACKEND_HOST=$BACKEND_FQDN" \
    "BACKEND_PORT=443" \
  --output none 2>/dev/null || \
az containerapp update \
  --name "$FRONTEND_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --image "$ACR_LOGIN_SERVER/$FRONTEND_APP:latest" \
  --set-env-vars \
    "BACKEND_HOST=$BACKEND_FQDN" \
    "BACKEND_PORT=443" \
  --output none

FRONTEND_FQDN=$(az containerapp show \
  --name "$FRONTEND_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --query "properties.configuration.ingress.fqdn" -o tsv)

# ─── Done ────────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "  ✓ Deployment complete!"
echo "═══════════════════════════════════════════════════════════════════════"
echo ""
echo "  Frontend URL:  https://$FRONTEND_FQDN"
echo "  Backend URL:   https://$BACKEND_FQDN  (internal)"
echo ""
echo "  View logs:"
echo "    az containerapp logs show -n $BACKEND_APP -g $RESOURCE_GROUP --follow"
echo "    az containerapp logs show -n $FRONTEND_APP -g $RESOURCE_GROUP --follow"
echo ""
echo "  Redeploy after code changes:"
echo "    ./redeploy.sh            # both services"
echo "    ./redeploy.sh backend    # backend only"
echo "    ./redeploy.sh frontend   # frontend only"
echo ""
echo "═══════════════════════════════════════════════════════════════════════"
