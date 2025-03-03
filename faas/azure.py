import pulumi
import pulumi_azure_native as azure
from deps import nixdeps
import pulumi_gcp as gcp


class Deployer:
    @staticmethod
    def list_locations() -> list[str]:
        # TODO: Get This from the API
        return [
            "eastus",
            "northeurope",
            "westeurope",
            "southeastasia",
            "eastasia",
            "westus",
            "japanwest",
            "japaneast",
            "eastus2",
            "northcentralus",
            "southcentralus",
            "brazilsouth",
            "australiaeast",
            "australiasoutheast",
            "centralus",
            # "eastasia(stage)",
            "centralindia",
            "westindia",
            "southindia",
            "canadacentral",
            "canadaeast",
            "westcentralus",
            "westus2",
            "ukwest",
            "uksouth",
            # "eastus2euap",
            # "centraluseuap",
            # "koreasouth",
            "koreacentral",
            # "francesouth",
            "francecentral",
            # "australiacentral2",
            # "australiacentral",
            "southafricanorth",
            # "southafricawest",
            "switzerlandnorth",
            "germanywestcentral",
            # "germanynorth",
            # "switzerlandwest",
            # "uaecentral",
            "uaenorth",
            # "norwaywest",
            "norwayeast",
            # "brazilsoutheast",
            # "westus3",
            # "jioindiawest",
            # "jioindiacentral",
            "swedencentral",
            # "qatarcentral",
            # "swedensouth",
            # "polandcentral",
            # "italynorth", # ummm umm subscription not found?
            # "israelcentral",
            # "spaincentral",
            # "mexicocentral",
            # "taiwannorth",
            # "taiwannorthwest",
        ]

    def __init__(self, calling_service_account: gcp.serviceaccount.Account):
        self.resource_group = azure.resources.ResourceGroup("pingall")

        self.subscription_id = azure.authorization.get_client_config().subscription_id

    def make_function(self, location: str) -> pulumi.Output[str]:
        code_storage_account = azure.storage.StorageAccount(
            f"pingallcs{location}",
            account_name=f"pingcs{location}",
            resource_group_name=self.resource_group.name,
            sku=azure.storage.SkuArgs(
                name=azure.storage.SkuName.STANDARD_LRS,
            ),
            kind=azure.storage.Kind.STORAGE_V2,
            location=location,
            allow_blob_public_access=False,
            allow_shared_key_access=False,
            minimum_tls_version=azure.storage.MinimumTlsVersion.TLS1_2,
        )

        code_container = azure.storage.BlobContainer(
            f"zips-{location}",
            resource_group_name=self.resource_group.name,
            account_name=code_storage_account.name,
        )

        nix_hash = nixdeps["azure.archive"].split("/")[-1].split("-")[0]

        code_blob = azure.storage.Blob(
            f"zip-{location}-{nix_hash}",
            blob_name=f"{nix_hash}.zip",
            resource_group_name=self.resource_group.name,
            account_name=code_storage_account.name,
            container_name=code_container.name,
            source=pulumi.asset.FileAsset(nixdeps["azure.archive"]),
        )
        app_storage = azure.storage.StorageAccount(
            f"pingsa{location}",
            account_name=f"pingsa{location}",
            resource_group_name=self.resource_group.name,
            sku=azure.storage.SkuArgs(
                name=azure.storage.SkuName.STANDARD_LRS,
            ),
            kind=azure.storage.Kind.STORAGE_V2,
            location=location,
            allow_blob_public_access=False,
            allow_shared_key_access=False,
            minimum_tls_version=azure.storage.MinimumTlsVersion.TLS1_2,
        )
        plan = azure.web.AppServicePlan(
            f"plan{location}",
            resource_group_name=self.resource_group.name,
            sku=azure.web.SkuDescriptionArgs(
                name="Y1",
                tier="Dynamic",
            ),
            reserved=True,
            location=location,
        )

        app = azure.web.WebApp(
            f"ping-{location}",
            location=location,
            resource_group_name=self.resource_group.name,
            server_farm_id=plan.id,
            kind="functionapp,linux",
            https_only=True,
            identity=azure.web.ManagedServiceIdentityArgs(
                type=azure.web.ManagedServiceIdentityType.SYSTEM_ASSIGNED
            ),
            site_config=azure.web.SiteConfigArgs(
                app_settings=[
                    azure.web.NameValuePairArgs(
                        name="FUNCTIONS_EXTENSION_VERSION", value="~4"
                    ),
                    azure.web.NameValuePairArgs(
                        name="FUNCTIONS_WORKER_RUNTIME", value="custom"
                    ),
                    azure.web.NameValuePairArgs(
                        name="AzureWebJobsStorage__accountName",
                        value=app_storage.name,
                    ),
                    azure.web.NameValuePairArgs(
                        name="WEBSITE_RUN_FROM_PACKAGE", value=code_blob.url
                    ),
                ],
                http20_enabled=True,
                ftps_state=azure.web.FtpsState.DISABLED,
                min_tls_version="1.3",
            ),
            opts=pulumi.ResourceOptions(replace_on_changes=["server_farm_id", "kind"]),
        )
        azure.authorization.RoleAssignment(
            f"codeAccessAssignment{location}",
            principal_id=app.identity.principal_id,
            principal_type="ServicePrincipal",
            role_definition_id=f"/subscriptions/{self.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/2a2b9908-6ea1-4ae2-8e65-a410df84e7d1",
            scope=pulumi.Output.format(
                "subscriptions/{2}/resourceGroups/{0}/providers/Microsoft.Storage/storageAccounts/{1}",
                self.resource_group.name,
                code_storage_account.name,
                self.subscription_id,
            ),
        )
        azure.authorization.RoleAssignment(
            f"storageOwnerAssignment{location}",
            principal_id=app.identity.principal_id,
            principal_type="ServicePrincipal",
            role_definition_id=f"/subscriptions/{self.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/b7e6dc6d-f1e8-4753-8033-0f276bb0955b",
            scope=pulumi.Output.format(
                "subscriptions/{2}/resourceGroups/{0}/providers/Microsoft.Storage/storageAccounts/{1}",
                self.resource_group.name,
                app_storage.name,
                self.subscription_id,
            ),
        )
        if location == "australiaeast":
            plan2 = azure.web.AppServicePlan(
                f"planf{location}",
                resource_group_name=self.resource_group.name,
                sku=azure.web.SkuDescriptionArgs(
                    name="FC1",
                    tier="FlexConsumption",
                ),
                reserved=True,
                location=location,
            )

            app2 = azure.web.WebApp(
            f"pingf-{location}",
                location=location,
                resource_group_name=self.resource_group.name,
                server_farm_id=plan.id,
                kind="functionapp,linux",
                https_only=True,
                identity=azure.web.ManagedServiceIdentityArgs(
                    type=azure.web.ManagedServiceIdentityType.SYSTEM_ASSIGNED
                ),
                site_config=azure.web.SiteConfigArgs(
                    app_settings=[
                        azure.web.NameValuePairArgs(
                            name="FUNCTIONS_EXTENSION_VERSION", value="~4"
                        ),
                        azure.web.NameValuePairArgs(
                            name="FUNCTIONS_WORKER_RUNTIME", value="custom"
                        ),
                        azure.web.NameValuePairArgs(
                            name="AzureWebJobsStorage__accountName",
                            value=app_storage.name,
                        ),
                        azure.web.NameValuePairArgs(
                            name="WEBSITE_RUN_FROM_PACKAGE", value=code_blob.url
                        ),
                    ],
                    http20_enabled=True,
                    ftps_state=azure.web.FtpsState.DISABLED,
                    min_tls_version="1.3",
                ),
                opts=pulumi.ResourceOptions(replace_on_changes=["server_farm_id", "kind"]),
            )
        return app.default_host_name.apply(lambda host: f"https://{host}/api/pinger")

    def finish(self):
        pass
