import json

import pulumi
import pulumi_docker_build as docker_build
import pulumi_gcp as gcp

from deps import nixdeps


class Deployer:
    @staticmethod
    def list_locations() -> list[str]:
        return filter(
            lambda l: l != "me-central2", gcp.cloudrun.get_locations().locations
        )

    def __init__(self, calling_service_account: gcp.serviceaccount.Account):
        self.calling_service_account = calling_service_account

        # Import the provider's configuration settings.
        gcp_config = pulumi.Config("gcp")
        self.project = gcp_config.require("project")

    def make_function(self, location: str) -> pulumi.Output[str]:
        registry = gcp.artifactregistry.Repository(
            f"ping-{location}-docker",
            format="DOCKER",
            cleanup_policies=[
                gcp.artifactregistry.RepositoryCleanupPolicyArgs(
                    id="delete untagged",
                    action="DELETE",
                    condition=gcp.artifactregistry.RepositoryCleanupPolicyConditionArgs(
                        tag_state="UNTAGGED"
                    ),
                )
            ],
            location=location,
            project=self.project,
            repository_id="pinger",
            mode="STANDARD_REPOSITORY",
        )
        # Create a container image for the service.
        with open(nixdeps["gcp.imageDetails"]) as f:
            image_details = json.load(f)
        image = docker_build.Index(
            f"image-{location}",
            sources=[f"{image_details['name']}:{image_details['tag']}"],
            tag=f"{location}-docker.pkg.dev/{self.project}/pinger/pinger",
        )
        service_account = gcp.serviceaccount.Account(
            f"ping-{location}", account_id=f"ping-{location}"
        )
        # Create a Cloud Run service definition.
        service = gcp.cloudrunv2.Service(
            f"ping-{location}",
            name=f"ping-{location}",
            location=location,
            project=self.project,
            template=gcp.cloudrunv2.ServiceTemplateArgs(
                service_account=service_account.email,
                containers=[
                    gcp.cloudrunv2.ServiceTemplateContainerArgs(
                        image=image.ref,
                        resources=gcp.cloudrunv2.ServiceTemplateContainerResourcesArgs(
                            cpu_idle=True,
                            limits=dict(
                                memory="128Mi",
                                cpu="1",
                            ),
                        ),
                    ),
                ],
                max_instance_request_concurrency=50,
                scaling=gcp.cloudrunv2.ServiceTemplateScalingArgs(max_instance_count=1),
            ),
            custom_audiences=["pinger"],
        )

        # Create an IAM member to make the service publicly accessible.
        gcp.cloudrunv2.ServiceIamBinding(
            f"invoker-{location}",
            name=service.name,
            location=location,
            members=[self.calling_service_account.member],
            role="roles/run.invoker",
        )
        return service.uri

    def finish(self):
        pass
