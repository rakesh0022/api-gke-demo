# GKE Microservices Architecture – Notes

## Goal

Build a **production-ready microservices architecture on Google Kubernetes Engine (GKE)** using **Gateway API** (not legacy Ingress) to achieve:

* Path-based routing for multiple microservices
* Central traffic management (routing, retries, timeouts)
* Future-ready hooks for auth, rate limiting, and policy controls
* Compatibility with Google Cloud Load Balancer, Cloud Armor, and CDN

---

## High-Level Architecture (Current)

```
Client
  │
  ▼
Global External HTTPS Load Balancer (created by GKE Gateway API)
  │
  ▼
GKE Gateway (gke-l7-global-external-managed)
  │
  ▼
HTTPRoute (path-based routing)
  │
  ▼
Kubernetes Services (NEG-backed)
  │
  ▼
Pods (Microservices)
```

---

## What We Have Implemented

### 1. GKE Cluster

* **Type**: GKE Standard (VPC-native)
* **Gateway API**: Enabled
* **HttpLoadBalancing addon**: Enabled

---

### 2. Gateway (Production)

* **Gateway Name**: `prod-gateway`
* **Namespace**: `prod-app`
* **GatewayClass**: `gke-l7-global-external-managed`
* **Protocol**: HTTPS (TLS Termination at LB)
* **Public IP (auto-assigned by Gateway)**:

  * `136.110.129.148`
* **Hostname (temporary)**:

  * `136.110.129.148.nip.io`

> Note: Gateway API does **not reuse existing Ingress static IPs**. It always creates a new Google-managed external LB.

---

### 3. TLS / SSL

* **Certificate Type**: Google-managed SSL certificate
* **Configured using**:

  ```yaml
  tls:
    mode: Terminate
    options:
      networking.gke.io/pre-shared-certs: prod-gateway-cert
  ```
* **Domain used**: `136.110.129.148.nip.io`

> ManagedCertificate CRD is **not supported** by Gateway API. Certificates must be created via `gcloud compute ssl-certificates`.

---

**Containerization & Routing (Current State)**

**Production Docker Image (Implemented)**

All microservices now run on a single production-grade Docker image built using a multi-stage Go build.

Image characteristics

Language: Go 1.21

Multi-stage build

Final image: gcr.io/distroless/base-debian12

No shell, no package manager

Static binary only

Docker build strategy

Stage 1: Build Go binary using golang:1.21-alpine

Stage 2: Copy binary into distroless runtime image

Artifact Registry image

us-central1-docker.pkg.dev/rakesh-project-480508/my-repo/microservice-base:1.1


All microservices reuse this image. Service differentiation is achieved via routing, not separate images.

Gateway API Routing (Finalized)

A single HTTPRoute now handles routing for all microservices using path-based routing with URL rewriting.

HTTPRoute

Name: microservices-route

Namespace: prod-app

Gateway: prod-gateway

Hostname: 136.110.129.148.nip.io

Routing rules

External Path	Backend Service	Internal Path
/users	user-svc	/
/orders	order-svc	/
/payments	payment-svc	/

URL rewrite (required and supported)

Each rule uses a Gateway API–supported URLRewrite filter:

filters:
- type: URLRewrite
  urlRewrite:
    path:
      type: ReplacePrefixMatch
      replacePrefixMatch: /


This ensures:

Clean external APIs (/users, /orders, /payments)

Simple backend services that only serve /

No service-side path parsing

This configuration is fully supported by GKE Gateway API and validated against Google documentation.

Current Request Flow
Client
  │
  ▼
https://136.110.129.148.nip.io
  │
  ▼
Global External HTTPS Load Balancer (GKE-managed)
  │
  ▼
GKE Gateway (Gateway API)
  │
  ▼
HTTPRoute (path match + rewrite)
  │
  ├── /users     → user-svc     → user-app Pods
  ├── /orders    → order-svc    → order-app Pods
  └── /payments  → payment-svc  → payment-app Pods

Verification
curl https://136.110.129.148.nip.io/users
curl https://136.110.129.148.nip.io/orders
curl https://136.110.129.148.nip.io/payments


Each request:

Hits a different Kubernetes Service

Reaches different Pods

Uses the same hardened container image

Key Outcome

✅ True microservice routing

✅ No legacy Ingress

✅ No unsupported Gateway features

✅ Production-grade containers

✅ Clean separation of routing and service logic

At this point, the data plane is solid.
Next phases can focus purely on traffic policies (timeouts, retries), auth, and rate limiting—without touching the foundation.

### 4. Microservices Deployed

All services run in namespace: `prod-app`

| Service | Deployment  | Pods | Path       |
| ------- | ----------- | ---- | ---------- |
| demo    | demo-app    | 2    | `/`        |
| user    | user-app    | 2    | `/user`    |
| order   | order-app   | 2    | `/order`   |
| payment | payment-app | 2    | `/payment` |

Each service:

* Uses `gcr.io/google-samples/hello-app:1.0`
* Exposes port `8080`
* Fronted by a ClusterIP Service on port `80`
* NEG enabled using:

  ```yaml
  cloud.google.com/neg: {"exposed_ports":{"80":{}}}
  ```

---

### 5. HTTP Routing (Gateway API)

* **HTTPRoute Name**: `prod-route`
* **Bound Gateway**: `prod-gateway`
* **Routing Type**: PathPrefix

Example behavior:

* `/` → `demo-svc`
* `/user` → `user-svc`
* `/order` → `order-svc`
* `/payment` → `payment-svc`

Routing is stable and reconciled successfully by the Gateway controller.

---

### 6. Cloud Armor

* **Cloud Armor Policy**: Attached successfully
* **Attachment Method**: Directly on backend service (not via GCPBackendPolicy)

> Cloud Armor **is supported** with Gateway API, but configuration is done at the GCP backend-service level.

---

### 7. Cloud CDN (Status)

* CDN was **manually enabled** using `gcloud compute backend-services update --enable-cdn`
* CDN state is **not stable** (auto-disabled by controller)

Reason:

* Gateway API does **not yet fully support declarative CDN control**
* GKE controller may overwrite backend settings

Decision:

* CDN temporarily deprioritized
* Architecture remains compatible for future CDN enablement

---

## What We Explicitly Avoided

* ❌ Legacy `Ingress`
* ❌ `BackendConfig`
* ❌ Unsupported `GCPBackendPolicy.cdn`
* ❌ ManagedCertificate CRD

All removed to stay **100% aligned with current GKE Gateway API support**.

---

## Current Verification

```bash
curl https://136.110.129.148.nip.io
```

Returns:

```
Hello, world!
Version: 1.0.0
Hostname: <pod-name>
```

Each microservice is reachable and load-balanced.

---

## Known Gaps (Next Phases)

### Functional

* All services return identical responses
* Need service-specific responses

### Traffic Policies (Upcoming)

* Request timeouts
* Retries
* Header-based routing
* Rate limiting (via Envoy / future GatewayPolicy)
* Auth (JWT / IAP / mTLS)

---

## Containerization Update (Implemented)

### Custom Docker Image

* A **custom Dockerfile** and HTTP server were created to ensure each microservice returns a **distinct response** (service name, version, pod info).
* The image was built and pushed to **Google Artifact Registry (GAR)**.

Example image pattern:

```
<REGION>-docker.pkg.dev/<PROJECT>/<REPO>/<service-name>:v1
```

Each microservice deployment now:

* Uses the **same base image**
* Is configured via **ENV variables** (SERVICE_NAME, SERVICE_VERSION)
* Produces unique responses per service

This avoids maintaining multiple images while still keeping responses distinguishable.

---

## Deployment Changes

* `demo-app`, `user-app`, `order-app`, and `payment-app` deployments updated

* Image source switched from:

  ```
  gcr.io/google-samples/hello-app:1.0
  ```

  to the custom GAR-hosted image

* No service or HTTPRoute changes were required

---

## Current Verification

Each path now returns a **service-specific response**:

| Path       | Expected Response      |
| ---------- | ---------------------- |
| `/`        | demo service output    |
| `/user`    | user service output    |
| `/order`   | order service output   |
| `/payment` | payment service output |

This confirms:

* Correct HTTPRoute path-based routing
* Correct Service → Pod resolution
* Correct image rollout

---

## Next Planned Steps

1. Apply **traffic policies** using supported Gateway API features

   * Timeouts
   * Retries
2. Introduce **request-based routing** (headers / methods)
3. Add **rate limiting & auth** (Gateway-native or sidecar-based)
4. Prepare for production domain (replace nip.io)

---

Where we go next (no rush, but clear path)

Next logical phase:

Traffic policies (supported only)

Timeouts

Retries

Request matching

Headers

Methods

Auth strategy decision

IAP vs JWT vs external gateway

Rate limiting reality check

What Gateway API can do today

What needs Envoy / service mesh

When you’re ready, say:

“Let’s start traffic policies – timeouts first”

And we’ll do it strictly based on Google-supported fields, no guessing.

## Key Takeaway (Updated)

The platform now supports:

* True microservice differentiation
* Single reusable container image
* Clean promotion to prod-ready traffic governance

The foundation is solid. Next steps focus purely on **policy & control**, not plumbing.
