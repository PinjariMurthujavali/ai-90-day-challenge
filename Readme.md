# Day 50: Kubernetes Clusters Setup

## What changed from Day 48-49

Days 48-49 got the app running in containers, locally, with
`docker compose up`. That's still **one machine**. If it dies,
everything dies.

A Kubernetes **cluster** is a group of machines (nodes) that a control
plane treats as one pool of compute. You describe the *desired state*
("I want 2 copies of chatbot-api always running") in YAML, and
Kubernetes continuously works to make reality match that — restarting
crashed Pods, rescheduling them onto healthy nodes, load-balancing
traffic across whichever replicas are currently up.

## Files in this folder

| File | What it does |
|---|---|
| `namespace.yaml` | Isolates every resource below under `ai-chatbot` |
| `secret.example.yaml` | Template for API keys — copy to `secret.yaml`, fill in, never commit |
| `api-deployment.yaml` | Runs 2 replicas of the main api container, self-healing |
| `api-service.yaml` | Stable internal address that load-balances across the api Pods |
| `analytics-deployment.yaml` | Same idea for the Day 41 analytics microservice |
| `analytics-service-svc.yaml` | Stable internal address for analytics-service |

## Try it locally (free, no cloud account needed)

1. Install a local cluster tool — **kind** is fastest to set up:
   ```
   # https://kind.sigs.k8s.io/docs/user/quick-start/#installation
   kind create cluster --name chatbot-cluster
   ```

2. Build the same images Day 48's Dockerfiles already define:
   ```
   docker build -f Dockerfile.api -t chatbot-api:latest .
   docker build -f Dockerfile.analytics -t analytics-service:latest .
   ```

3. Load them into the kind cluster (kind can't pull local-only images otherwise):
   ```
   kind load docker-image chatbot-api:latest --name chatbot-cluster
   kind load docker-image analytics-service:latest --name chatbot-cluster
   ```

4. Create your real secret (never commit this file):
   ```
   cp k8s/secret.example.yaml k8s/secret.yaml
   # edit k8s/secret.yaml with your real GROQ/Turso values
   ```

5. Apply everything:
   ```
   kubectl apply -f k8s/namespace.yaml
   kubectl apply -f k8s/secret.yaml
   kubectl apply -f k8s/api-deployment.yaml
   kubectl apply -f k8s/api-service.yaml
   kubectl apply -f k8s/analytics-deployment.yaml
   kubectl apply -f k8s/analytics-service-svc.yaml
   ```

6. Check it's alive:
   ```
   kubectl get pods -n ai-chatbot
   kubectl get svc -n ai-chatbot
   ```

7. Prove self-healing — delete a Pod and watch Kubernetes replace it:
   ```
   kubectl delete pod -n ai-chatbot -l app=chatbot-api --field-selector status.phase=Running -o name | head -1 | xargs kubectl delete -n ai-chatbot
   kubectl get pods -n ai-chatbot -w
   ```

## What's next

- **Day 51:** Kubernetes Deployments & Scaling — rolling updates, `kubectl scale`, HorizontalPodAutoscaler
- **Day 52:** Services & Networking — Ingress, so the api is reachable from outside the cluster
- **Day 53:** StatefulSets & Persistent Volumes — for stateful storage instead of Turso
- **Day 54:** Helm Charts — package all of this into one installable chart
