# GKE Cluster Lifecycle Automation

This document provides:

1. A **shell script** to recreate the entire GKE microservices + Gateway API setup
2. Clear separation of **automated vs manual steps**
3. Commands to **tear down** resources to save cost

The goal is **repeatable, safe recreation** without guessing.

---

## 1. What This Automation Covers

### Automated by Script

* GKE cluster creation
* Enable required GCP APIs
* Namespace creation
* Deployments & Services (all microservices)
* Gateway API resources (Gateway + HTTPRoute)
* NEG-backed services

### Manual (One-Time / External)

* Artifact Registry repo creation
* Docker image build & push
* Google-managed SSL certificate creation
* Domain (nip.io or real domain) decision

Reason: These resources are **project-level** or **image-level**, not cluster-scoped.

---

## 2. Tear-Down Script (Cost Saving)

Use this when you are done and want **zero cluster cost**.

```bash
#!/bin/bash

PROJECT_ID="rakesh-project-480508"
CLUSTER_NAME="prod-gke-cluster"
REGION="us-central1"

set -e

echo "Deleting GKE cluster: $CLUSTER_NAME"
gcloud container clusters delete $CLUSTER_NAME \
  --region $REGION \
  --project $PROJECT_ID \
  --quiet

echo "Cluster deleted successfully"
```

> This deletes **everything inside the cluster** (Gateway, Services, Pods, LBs).

---

## 3. Full Create Script (End-to-End – Reviewed & Corrected)

Below is the **corrected automation flow**, aligned with how GKE Gateway actually works.

### Important Corrections (Read This First)

1. **The cluster is created only once**

   * Earlier confusion was due to explanation, not an actual second `create` command
   * This script creates the cluster **exactly one time**

2. **Gateway creation ≠ fully finished LB setup**

   * Gateway creation triggers LB provisioning **asynchronously**
   * The external IP is allocated **after** Gateway becomes `Programmed`

3. **SSL certificate CANNOT be fully automated**

   * We must first:

     * Wait for Gateway LB IP
     * Derive `nip.io` hostname
     * Create Google-managed SSL cert
     * Update Gateway to reference the cert

Because of this, the script is intentionally split into **automated** and **manual-intervention checkpoints**.

---

### Script: `scripts/create-cluster.sh`

```bash
#!/bin/bash
set -e

# -----------------------------
# Config
# -----------------------------
PROJECT_ID="rakesh-project-480508"
REGION="us-central1"
CLUSTER_NAME="prod-gke-cluster"
NAMESPACE="prod-app"
NODE_COUNT=2
MACHINE_TYPE="e2-standard-4"

# -----------------------------
# Enable Required APIs
# -----------------------------

echo "Enabling required GCP APIs"
gcloud services enable \
  container.googleapis.com \
  compute.googleapis.com \
  iam.googleapis.com \
  networkservices.googleapis.com \
  networksecurity.googleapis.com \
  certificatemanager.googleapis.com \
  --project $PROJECT_ID

# -----------------------------
# Create GKE Cluster (ONCE)
# -----------------------------

echo "Creating GKE cluster"

gcloud container clusters create $CLUSTER_NAME \
  --project $PROJECT_ID \
  --region $REGION \
  --num-nodes $NODE_COUNT \
  --machine-type $MACHINE_TYPE \
  --enable-ip-alias \
  --enable-dataplane-v2 \
  --enable-autorepair \
  --enable-autoupgrade \
  --release-channel regular \
  --workload-pool="$PROJECT_ID.svc.id.goog"

# -----------------------------
# Fetch Credentials
# -----------------------------

gcloud container clusters get-credentials $CLUSTER_NAME \
  --region $REGION \
  --project $PROJECT_ID

# -----------------------------
# Enable Gateway API CRDs
# -----------------------------

kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/gateway-api/v1.0.0/config/crd/standard/gateway.networking.k8s.io_gateways.yaml
kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/gateway-api/v1.0.0/config/crd/standard/gateway.networking.k8s.io_httproutes.yaml

# -----------------------------
# Create Namespace
# -----------------------------

kubectl create namespace $NAMESPACE || true

# -----------------------------
# Deploy Workloads & Services
# -----------------------------

echo "Deploying microservices"

kubectl apply -n $NAMESPACE -f k8s/demo-deployment.yaml
kubectl apply -n $NAMESPACE -f k8s/microservice-a.yaml
kubectl apply -n $NAMESPACE -f k8s/microservice-b.yaml
kubectl apply -n $NAMESPACE -f k8s/microservice-c.yaml

# -----------------------------
# Deploy Gateway (NO TLS YET)
# -----------------------------

echo "Deploying Gateway without TLS"

kubectl apply -n $NAMESPACE -f k8s/gateway.yaml
kubectl apply -n $NAMESPACE -f k8s/httproute.yaml

# -----------------------------
# Wait for Gateway LB IP
# -----------------------------

echo "Waiting for Gateway to be Programmed"

kubectl wait gateway prod-gateway \
  -n $NAMESPACE \
  --for=condition=Programmed \
  --timeout=20m

echo "Gateway created successfully"

echo "NEXT MANUAL STEP REQUIRED:"
echo "1. Get Gateway IP"
echo "2. Create SSL certificate"
echo "3. Patch Gateway with cert"
```

---

## 4. Manual Step (MANDATORY – Cannot Be Automated)

### Step 1: Get Gateway IP

```bash
kubectl get gateway prod-gateway -n prod-app -o jsonpath='{.status.addresses[0].value}'
```

Example output:

```
136.110.129.148
```

### Step 2: Create Google Managed SSL Cert

```bash
gcloud compute ssl-certificates create prod-gateway-cert \
  --domains=136.110.129.148.nip.io \
  --global
```

> Wait until cert status becomes `ACTIVE`.

### Step 3: Patch Gateway to Use SSL

```bash
kubectl apply -n prod-app -f k8s/gateway-with-tls.yaml
```

---

## Why This Split Is REQUIRED

| Item            | Reason                      |
| --------------- | --------------------------- |
| Gateway IP      | Allocated asynchronously    |
| nip.io hostname | Depends on actual IP        |
| Managed cert    | Needs real domain           |
| Gateway TLS     | References pre-created cert |

Trying to fully automate this **will break** in real production as well.

---

## Final Truth

This is not a scripting limitation.
This is **how Google Cloud L7 load balancing works**.

You now have a **correct, production-grade lifecycle flow**.bash
#!/bin/bash

set -e

PROJECT_ID="rakesh-project-480508"
REGION="us-central1"
CLUSTER_NAME="prod-gke-cluster"
NAMESPACE="prod-app"

# -----------------------------

# Enable Required APIs

# -----------------------------

echo "Enabling required APIs"
gcloud services enable 
container.googleapis.com 
compute.googleapis.com 
certificatemanager.googleapis.com 
--project $PROJECT_ID

# -----------------------------

# Create GKE Cluster

# -----------------------------

echo "Creating GKE cluster"
gcloud container clusters create $CLUSTER_NAME 
--region $REGION 
--num-nodes 2 
--enable-ip-alias 
--enable-autorepair 
--enable-autoupgrade 
--project $PROJECT_ID

# -----------------------------

# Get Cluster Credentials

# -----------------------------

gcloud container clusters get-credentials $CLUSTER_NAME 
--region $REGION 
--project $PROJECT_ID

# -----------------------------

# Create Namespace

# -----------------------------

kubectl create namespace $NAMESPACE || true

# -----------------------------

# Deploy Microservices

# -----------------------------

echo "Deploying microservices"
kubectl apply -n $NAMESPACE -f k8s/microservice-a.yaml
kubectl apply -n $NAMESPACE -f k8s/microservice-b.yaml
kubectl apply -n $NAMESPACE -f k8s/microservice-c.yaml
kubectl apply -n $NAMESPACE -f k8s/demo-deployment.yaml

# -----------------------------

# Deploy Gateway API Resources

# -----------------------------

echo "Deploying Gateway and HTTPRoute"
kubectl apply -n $NAMESPACE -f k8s/gateway.yaml
kubectl apply -n $NAMESPACE -f k8s/httproute.yaml

# -----------------------------

# Verify

# -----------------------------

echo "Waiting for Gateway to be ready"
kubectl wait gateway prod-gateway 
-n $NAMESPACE 
--for=condition=Programmed 
--timeout=15m

echo "Setup complete"

````

---

## 4. Manual Steps (Required)

These **must be done once per project**.

### 4.1 Artifact Registry
```bash
gcloud artifacts repositories create microservices \
  --repository-format=docker \
  --location=us-central1
````

### 4.2 Build & Push Image

```bash
docker build -t us-central1-docker.pkg.dev/$PROJECT_ID/microservices/app:v1 .
docker push us-central1-docker.pkg.dev/$PROJECT_ID/microservices/app:v1
```

### 4.3 SSL Certificate (Gateway)

```bash
gcloud compute ssl-certificates create prod-gateway-cert \
  --domains=136.110.129.148.nip.io \
  --global
```

> Certificate provisioning may take **10–20 minutes**.

---

## 5. How to Recreate Everything (Quick Guide)

```bash
# 1. Create cluster + deploy everything
bash scripts/create-cluster.sh

# 2. Verify
kubectl get gateway -n prod-app
kubectl get httproute -n prod-app
curl https://<gateway-ip>.nip.io

# 3. Delete when done
bash scripts/delete-cluster.sh
```

---

## 6. Design Principles

* No legacy Ingress
* No unsupported BackendConfig/GCPBackendPolicy fields
* Gateway API only
* Everything reproducible

---

## Final Note

This setup is intentionally **boring and deterministic**.
That is exactly what you want in production.

Next layers (auth, rate limit, circuit breaker) will build **on top**, not replace this.
