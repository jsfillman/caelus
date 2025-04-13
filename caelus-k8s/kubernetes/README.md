# Kubernetes Deployment for Caelus K8s

This directory contains Kubernetes manifests for deploying Caelus K8s in a Kubernetes cluster.

## Components

- **Controller**: Single pod that handles MIDI input, OSC control messages, and mixes audio from workers
- **Workers**: Multiple pods for polyphony, each generating one note at a time

## Deployment Steps

### 1. Build Docker Images

```bash
# Build controller image
docker build -t caelus-controller:latest -f kubernetes/Dockerfile .

# Build worker image (same code base, different startup command)
docker build -t caelus-worker:latest -f kubernetes/Dockerfile .
```

### 2. Deploy to Kubernetes

```bash
# Deploy workers
kubectl apply -f kubernetes/worker-deployment.yaml

# Deploy controller
kubectl apply -f kubernetes/controller-deployment.yaml
```

### 3. Verify Deployment

```bash
# Check pods
kubectl get pods -l app=caelus

# Check services
kubectl get svc -l app=caelus
```

## Accessing the Controller

The controller exposes two services:

- OSC server on port 30800 (NodePort)
- RTP receiver on port 30500 (NodePort)

To access the controller from outside the cluster, use the IP address of any Kubernetes node and the NodePort.

## Scaling

To adjust polyphony, scale the number of worker replicas:

```bash
kubectl scale deployment caelus-worker --replicas=16
```