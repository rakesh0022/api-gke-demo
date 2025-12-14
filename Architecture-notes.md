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

## Next Planned Steps

1. Create a **custom Docker image** with service-specific responses
2. Update deployments to use the new image
3. Add advanced HTTPRoute rules
4. Introduce supported traffic policies (timeouts, retries)
5. Re-evaluate API Gateway vs GKE Gateway roles

---

## Key Takeaway

This architecture is:

* Production-aligned
* Gateway API–native
* Future-proof for service mesh–like controls
* Cleanly separated from deprecated Ingress patterns

No hacks. No unsupported fields. No surprises.
