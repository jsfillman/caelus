# Get the Node's IP address where workers are running
NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="ExternalIP")].address}')

# Start the controller - note we're specifying worker details explicitly
./caelus controller \
  --workers="${NODE_IP}:30900:1 ${NODE_IP}:30900:1 ${NODE_IP}:30900:1" \
  --use-jack
