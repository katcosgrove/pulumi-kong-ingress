"""A Python Pulumi program"""

import pulumi
import pulumi_digitalocean as do
import pulumi_kubernetes as k8s

# Get config values to define what our cluster looks like.
config = pulumi.Config();
clusterName = config.require('cluster-name'); # "my-cluster"
clusterRegion = config.require('region'); # "nyc3"
nodePoolName = config.require('node-pool-name'); # "my-cluster-pool"
nodeSize = config.require('node-size'); # "s-1vcpu-2gb"
nodeCount = config.require('node-count'); # "4"
nodeTag = config.require('tag'); # "matty-workshop"

# Grab the latest version available from DigitalOcean.
ver = do.get_kubernetes_versions()

# Provision a Kubernetes cluster.
cluster = do.KubernetesCluster(
    clusterName,
    region=clusterRegion,
    version=ver.latest_version,
    node_pool=do.KubernetesClusterNodePoolArgs(
        name=nodePoolName, 
        size=nodeSize, 
        node_count=config.get_int('node-count'),
        tags=[nodeTag]
    ),
)

# Set up a Kubernetes provider.
k8s_provider = k8s.Provider(
    "do-k8s",
    kubeconfig=cluster.kube_configs.apply(lambda c: c[0].raw_config),
    opts=pulumi.ResourceOptions(parent=cluster),
)

ns = k8s.core.v1.Namespace(
    "platform",
    metadata=k8s.meta.v1.ObjectMetaArgs(name="platform"),
    opts=pulumi.ResourceOptions(provider=k8s_provider, parent=k8s_provider),
)

# Little helper function to apply a transformation to the Kong Helm chart.
def remove_status(obj, opts):
    if obj["kind"] == "CustomResourceDefinition":
        del obj["status"]

# Deploying Kong via Helm chart.
kong_ingress = k8s.helm.v3.Chart(
    "kong-ingress",
    k8s.helm.v3.ChartOpts(
        namespace=ns.metadata.name,
        chart="kong",
        fetch_opts=k8s.helm.v3.FetchOpts(
            repo="https://charts.konghq.com/"
        ),
        transformations=[remove_status],
    ),
    opts=pulumi.ResourceOptions(provider=k8s_provider, parent=ns),
)

# Getting the Kong resource we've deployed and exporting its IP address.
svc = kong_ingress.get_resource('v1/Service', "platform/kong-ingress-kong-proxy")
pulumi.export("url", svc.status.apply(lambda s: s.load_balancer.ingress[0].ip))
