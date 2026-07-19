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
RESOURCE_GROUP="rg-ontology-builder"
LOCATION="eastus"
ACR_NAME="ontologybuilder"
ENVIRONMENT_NAME="ontology-builder-env"
LOG_ANALYTICS_WORKSPACE="ontology-builder-logs"

BACKEND_APP="ontology-backend"
FRONTEND_APP="ontology-frontend"

# Persistent storage (Azure Files) for the backend's SQLite DB, session JSONs, and
# generated YAML — all under /app/deployment. Storage account names must be
# 3-24 chars, lowercase alphanumeric only.
STORAGE_ACCOUNT="ontologybuilderstore"
FILE_SHARE="ontology-data"
STORAGE_MOUNT="ontology-storage"        # ACA env storage name
MOUNT_PATH="/app/deployment"            # where the volume mounts inside the backend

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
# az group create \
#   --name "$RESOURCE_GROUP" \
#   --location "$LOCATION" \
#   --output none

# ─── Step 2: Azure Container Registry ────────────────────────────────────────
echo "▶ Step 2: Creating Azure Container Registry..."
# az acr create \
#   --resource-group "$RESOURCE_GROUP" \
#   --name "$ACR_NAME" \
#   --sku Basic \
#   --admin-enabled true \
#   --output none

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

# ─── Step 4b: Persistent storage (Azure Files) ───────────────────────────────
# The backend writes its SQLite DB, session JSONs, and generated YAML under
# /app/deployment. Back that path with an Azure Files share so it survives
# restarts/redeploys. NOTE: SQLite over SMB requires a single writer — the backend
# is pinned to one replica below, and the app uses a DELETE (non-WAL) journal.
echo "▶ Step 4b: Creating Azure Files storage..."

az storage account create \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --sku Standard_LRS \
  --kind StorageV2 \
  --output none 2>/dev/null || true

STORAGE_KEY=$(az storage account keys list \
  --account-name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --query "[0].value" -o tsv)

az storage share create \
  --name "$FILE_SHARE" \
  --account-name "$STORAGE_ACCOUNT" \
  --account-key "$STORAGE_KEY" \
  --quota 5 \
  --output none 2>/dev/null || true

# Register the share with the Container Apps environment (idempotent).
az containerapp env storage set \
  --name "$ENVIRONMENT_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --storage-name "$STORAGE_MOUNT" \
  --azure-file-account-name "$STORAGE_ACCOUNT" \
  --azure-file-account-key "$STORAGE_KEY" \
  --azure-file-share-name "$FILE_SHARE" \
  --access-mode ReadWrite \
  --output none

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
  --max-replicas 1 \
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

# ─── Step 5b: Mount the Azure Files share into the backend ───────────────────
# The core `containerapp` CLI has no volume-mount flag, so patch via YAML: fetch
# the current app definition, inject the volume + volumeMount + single-replica
# scale, and apply. Idempotent (re-applying the same mount is a no-op).
echo "▶ Step 5b: Mounting persistent volume at $MOUNT_PATH..."

# JSON is valid YAML, so we fetch/patch/apply as JSON using only Python's stdlib
# (no PyYAML dependency on the deploy machine); `az containerapp update --yaml`
# accepts the JSON file.
BACKEND_DEF="$(mktemp -t ontology-backend-XXXX).json"
az containerapp show \
  --name "$BACKEND_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --output json > "$BACKEND_DEF"

python3 - "$BACKEND_DEF" "$STORAGE_MOUNT" "$MOUNT_PATH" <<'PYEOF'
import sys, json
path, storage_name, mount_path = sys.argv[1], sys.argv[2], sys.argv[3]
with open(path) as f:
    doc = json.load(f)
tmpl = doc.setdefault("properties", {}).setdefault("template", {})
# Single replica (SQLite single-writer requirement).
scale = tmpl.setdefault("scale", {}) or {}
scale["minReplicas"] = 1
scale["maxReplicas"] = 1
tmpl["scale"] = scale
# Volume backed by the ACA env Azure Files storage.
vols = [v for v in (tmpl.get("volumes") or []) if v.get("name") != "ontology-data-vol"]
vols.append({"name": "ontology-data-vol", "storageType": "AzureFile", "storageName": storage_name})
tmpl["volumes"] = vols
# Mount it into the (single) container at the deployment path.
containers = tmpl.get("containers") or []
if containers:
    c = containers[0]
    mounts = [m for m in (c.get("volumeMounts") or []) if m.get("volumeName") != "ontology-data-vol"]
    mounts.append({"volumeName": "ontology-data-vol", "mountPath": mount_path})
    c["volumeMounts"] = mounts
with open(path, "w") as f:
    json.dump(doc, f, indent=2)
PYEOF

az containerapp update \
  --name "$BACKEND_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --yaml "$BACKEND_DEF" \
  --output none
rm -f "$BACKEND_DEF"

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
