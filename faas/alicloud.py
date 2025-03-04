import pulumi
import pulumi_alicloud as alicloud
from deps import nixdeps
import json
import pulumi_gcp as gcp


class Deployer:
    @staticmethod
    def list_locations() -> list[str]:
        # Returns regions that we can't use for whatever reason.
        # return alicloud.get_regions().ids
        return [
            # "cn-qingdao",
            "cn-beijing",
            "cn-huhehaote",
            "cn-zhangjiakou",
            # "cn-shanghai",
            "cn-hongkong",
            "cn-hangzhou",
            "ap-southeast-1",
            "cn-chengdu",
            # "cn-shenzhen",
            "us-west-1",
            "ap-northeast-1",
            "ap-northeast-2",
            "eu-central-1",
            # "ap-south-1",
            "ap-southeast-3",
            "us-east-1",
            #"ap-southeast-2",
            "ap-southeast-5",
            "ap-southeast-7",
            "eu-west-1",
        ]

    def __init__(self, calling_service_account: gcp.serviceaccount.Account):
        self.account_id = alicloud.get_caller_identity().account_id
        # alicloud.ims.OidcProvider(
        #     "google",
        #     issuer_url="https://accounts.google.com",
        #     issuance_limit_time=1,
        #     oidc_provider_name="Google",
        #     client_ids=[
        #         "sts.aliyuncs.com",
        #     ],
        #     fingerprints=["08745487E891C19E3078C1F2A07E452950EF36F6"],
        # )
        # self.ping_service_role = alicloud.ram.Role(
        #     "ping-service-role",
        #     name="ping-service-role",
        #     document=calling_service_account.unique_id.apply(
        #         lambda a_id: json.dumps(
        #             {
        #                 "Version": "1",
        #                 "Statement": [
        #                     {
        #                         "Action": "sts:AssumeRole",
        #                         "Effect": "Allow",
        #                         "Principal": {
        #                             "Federated": "acs:ram::5473371411128805:oidc-provider/Google"
        #                         },
        #                         "Condition": {
        #                             "StringEquals": {
        #                                 "oidc:aud": "sts.aliyuncs.com",
        #                                 "oidc:sub": a_id,
        #                                 "oidc:iss": "accounts.google.com",
        #                             }
        #                         },
        #                     }
        #                 ],
        #             }
        #         ),
        #     ),
        # )

    def make_function(self, location):
        provider = alicloud.Provider(f"alicloud-{location}", region=location)
        provider_url = alicloud_fc_url.Provider(
            f"alicloud-url-{location}", region=location
        )

        opts = pulumi.ResourceOptions(provider=provider)
        opts_url = pulumi.InvokeOptions(provider=provider_url)

        role = alicloud.ram.Role(
            f"pingerFunctionRole-{location}",
            document=json.dumps(
                {
                    "Version": "1",
                    "Statement": [
                        {
                            "Action": "sts:AssumeRole",
                            "Principal": {"Service": ["fc.aliyuncs.com"]},
                            "Effect": "Allow",
                        }
                    ],
                }
            ),
        )

        function_service = alicloud.fc.Service(
            f"fs-pinger-{location}",
            role=role.arn,
            opts=opts,
        )

        function_ = alicloud.fc.Function(
            f"pinger-{location}",
            handler="thiscanbeanystring",
            runtime="custom",
            service=function_service.name,
            filename=nixdeps["alicloud.archive"],
            ca_port=9000,
            opts=opts,
        )

        trigger = alicloud.fc.V3Trigger(
            f"pinger-trigger3-{location}",
            function_name=pulumi.Output.format("{0}${1}", function_service.name, function_.name),
            trigger_type="http",
            trigger_name="httptrigger",
            qualifier="LATEST",
            trigger_config=json.dumps({
                "authType": "anonymous",
                "methods": [
                    "GET",
                ],
            }),
            opts=opts,
        )

        return trigger.http_trigger.url_internet

    def finish(self):
        pass
