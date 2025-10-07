# Kubernetes Deployment for HealthtechParseMatch

This directory contains Kubernetes manifests for deploying the HealthtechParseMatch application to a Kubernetes cluster.

## Prerequisites

- Kubernetes cluster (v1.19+)
- kubectl configured to access your cluster
- Docker registry access (for pulling images)

## Components

### Core Application
- `deployment.yaml` - Main application deployment with 2 replicas
- `service.yaml` - ClusterIP service for internal access
- `configmap.yaml` - Configuration values
- `secret.yaml` - Sensitive configuration (passwords, API keys)

### Dependencies (Not Included)
You'll also need to deploy:
- PostgreSQL database
- Redpanda (Kafka-compatible) message broker
- Prometheus (monitoring)
- Grafana (dashboards)

## Quick Start

1. **Build and push your Docker image:**
   ```bash
   docker build -t your-registry/healthtech-api:latest .
   docker push your-registry/healthtech-api:latest
   ```

2. **Update the image reference in `deployment.yaml`:**
   ```yaml
   image: your-registry/healthtech-api:latest
   ```

3. **Apply the manifests:**
   ```bash
   kubectl apply -f k8s/
   ```

4. **Check deployment status:**
   ```bash
   kubectl get pods
   kubectl get services
   ```

## Configuration

### Environment Variables
- `DATABASE_URL`: PostgreSQL connection string
- `KAFKA_BOOTSTRAP_SERVERS`: Redpanda/Kafka brokers
- `ENVIRONMENT`: Runtime environment (production/staging/dev)

### Secrets
Update `secret.yaml` with your actual secrets:
```bash
# Encode secrets to base64
echo -n "your-password" | base64
```

### Scaling
Adjust replica count in `deployment.yaml`:
```yaml
spec:
  replicas: 3  # Scale as needed
```

## Health Checks

The deployment includes:
- **Liveness Probe**: `/health/check` - restarts container if unhealthy
- **Readiness Probe**: `/health/check` - removes from service if not ready
- **Resource Limits**: CPU 100m-500m, Memory 128Mi-512Mi

## Production Considerations

1. **Ingress**: Add Ingress resource for external access
2. **TLS**: Configure SSL certificates
3. **Persistent Volumes**: Use PVCs for logs and data persistence
4. **RBAC**: Configure proper service accounts and permissions
5. **Network Policies**: Restrict pod-to-pod communication
6. **Monitoring**: Integrate with Prometheus Operator
7. **Backup**: Set up database backups

## Troubleshooting

```bash
# Check pod status
kubectl describe pod <pod-name>

# View logs
kubectl logs <pod-name>

# Check service endpoints
kubectl get endpoints

# Debug with temporary pod
kubectl run debug --image=busybox --rm -it -- sh
```
