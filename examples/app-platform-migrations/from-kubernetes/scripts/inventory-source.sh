#!/bin/bash
set -euo pipefail
export_dir=${1:?Usage: inventory-source.sh /secure/source-inventory}
umask 077
mkdir "$export_dir"
# Use the customer's selected kubeconfig/context. Output can contain credentials.
kubectl version -o json > "$export_dir/kubernetes-version.json"
kubectl api-resources -o wide > "$export_dir/api-resources.txt"
kubectl -n portal get deployments,statefulsets,daemonsets,replicasets,pods,services,ingresses,cronjobs,jobs,configmaps,secrets,persistentvolumeclaims,serviceaccounts,rolebindings,roles,horizontalpodautoscalers,networkpolicies -o json > "$export_dir/namespace.json"
kubectl get persistentvolumes,storageclasses,nodes -o json > "$export_dir/storage-and-nodes.json"
kubectl get customresourcedefinitions -o json > "$export_dir/custom-resource-definitions.json"
# Custom resource instances and external owners depend on the discovered platform.
echo 'Core source inventory saved. Record discovered custom resources and external reconciliation owners separately.'
