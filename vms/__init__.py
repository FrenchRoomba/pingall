import pulumi
import pulumi_gcp as pgcp

def do(home_region):
    vms_pulumi_state = pgcp.storage.Bucket(
        "pingall-vms-pulumi-state",
        location=home_region,
        soft_delete_policy=pgcp.storage.BucketSoftDeletePolicyArgs(retention_duration_seconds=0),
    )

    vms_pulumi_state.url
