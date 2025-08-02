import pulumi
import pulumi_aws as aws
from deps import nixdeps
import json
import pulumi_gcp as gcp
import pulumi_std as std
import socket


class Deployer:
    apigws = []
    lambdas = []

    @staticmethod
    def list_locations() -> list[str]:
        return aws.get_regions().names

    def __init__(self, calling_service_account: gcp.serviceaccount.Account):
        self.account_id = aws.get_caller_identity().account_id
        calling_service_account.unique_id
        self.ping_service_role = aws.iam.Role(
            "ping-service-role",
            name="ping-service-role",
            assume_role_policy=calling_service_account.unique_id.apply(
                lambda a_id: json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Principal": {"Federated": "accounts.google.com"},
                                "Action": "sts:AssumeRoleWithWebIdentity",
                                "Condition": {
                                    "StringEquals": {
                                        "accounts.google.com:aud": a_id,
                                        "accounts.google.com:oaud": "sts.amazonaws.com",
                                        "accounts.google.com:sub": a_id,
                                    }
                                },
                            }
                        ],
                    }
                ),
            ),
        )

    def make_function(self, location: str):
        role = aws.iam.Role(
            f"pingerLambdaRole-{location}",
            assume_role_policy=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Action": "sts:AssumeRole",
                            "Principal": {"Service": "lambda.amazonaws.com"},
                            "Effect": "Allow",
                        }
                    ],
                }
            ),
        )

        lambda_layer = aws.lambda_.LayerVersion(
            f"lambda_adapter-{location}",
            code=pulumi.FileArchive(nixdeps["aws.adapter-archive"]),
            layer_name="lambda_adapter_layer",
            compatible_runtimes=["provided.al2023"],
            region=location,
        )

        lambda_ = aws.lambda_.Function(
            f"pinger-{location}",
            role=role.arn,
            runtime="provided.al2023",
            handler="pinger",
            code=pulumi.asset.FileArchive(nixdeps["aws.archive"]),
            layers=[lambda_layer.arn],
            environment=aws.lambda_.FunctionEnvironmentArgs(
                variables={"AWS_LAMBDA_EXEC_WRAPPER": "/opt/bootstrap"}
            ),
            region=location,
        )

        lambda_logging = aws.iam.Policy(
            f"lambdaLogging-{location}",
            path="/",
            description="IAM policy for logging from a lambda",
            policy=pulumi.Output.json_dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": "logs:CreateLogGroup",
                            "Resource": f"arn:aws:logs:{location}:{self.account_id}:*",
                        },
                        {
                            "Action": [
                                "logs:CreateLogStream",
                                "logs:PutLogEvents",
                            ],
                            "Resource": lambda_.name.apply(
                                lambda name: f"arn:aws:logs:{location}:{self.account_id}:log-group:/aws/lambda/{name}:*"
                            ),
                            "Effect": "Allow",
                        },
                    ],
                }
            ),
        )
        aws.iam.RolePolicyAttachment(
            f"lambdaLogs-{location}",
            role=role.name,
            policy_arn=lambda_logging.arn,
        )

        try:
            socket.getaddrinfo(f"a.lambda-url.{location}.on.aws", 443)
            function_url_suport = True
        except socket.gaierror:
            function_url_suport = False

        if not function_url_suport:
            apigw = aws.apigateway.RestApi(
                f"restApiGateway-{location}",
                endpoint_configuration=aws.apigateway.RestApiEndpointConfigurationArgs(
                    types="REGIONAL"
                ),
                region=location,
            )
            resource = aws.apigateway.Resource(
                f"resource-{location}",
                rest_api=apigw.id,
                parent_id=apigw.root_resource_id,
                path_part="{proxy+}",
                region=location,
            )
            method = aws.apigateway.Method(
                f"method-{location}",
                rest_api=apigw.id,
                resource_id=resource.id,
                http_method="ANY",
                authorization="AWS_IAM",
                region=location,
            )
            integration = aws.apigateway.Integration(
                f"integration-{location}",
                rest_api=apigw.id,
                resource_id=resource.id,
                http_method=method.http_method,
                type="AWS_PROXY",
                integration_http_method="POST",
                uri=lambda_.invoke_arn,
                region=location,
            )
            method_root = aws.apigateway.Method(
                f"method-root-{location}",
                rest_api=apigw.id,
                resource_id=apigw.root_resource_id,
                http_method="ANY",
                authorization="AWS_IAM",
                region=location,
            )
            integration_root = aws.apigateway.Integration(
                f"integration-root-{location}",
                rest_api=apigw.id,
                resource_id=apigw.root_resource_id,
                http_method=method.http_method,
                type="AWS_PROXY",
                integration_http_method="POST",
                uri=lambda_.invoke_arn,
                region=location,
            )
            deployment = aws.apigateway.Deployment(
                f"deployment-{location}",
                rest_api=apigw.id,
                triggers={
                    "redeployment": std.sha1_output(
                        input=pulumi.Output.json_dumps(
                            [
                                resource.id,
                                method.id,
                                integration.id,
                                method_root.id,
                                integration_root.id,
                            ]
                        )
                    ).apply(lambda invoke: invoke.result),
                },
                region=location,
            )
            stage = aws.apigateway.Stage(
                f"stage-{location}",
                stage_name="test",
                deployment=deployment.id,
                rest_api=apigw.id,
                region=location,
            )
            aws.lambda_.Permission(
                f"allowApiGateway-{location}",
                statement_id="AllowAPIGatewayInvoke",
                action="lambda:InvokeFunction",
                function=lambda_.name,
                principal="apigateway.amazonaws.com",
                source_arn=pulumi.Output.format("{0}/*/*", apigw.execution_arn),
                region=location,
            )
            url = stage.invoke_url
            self.apigws.append(apigw)
        else:
            url = aws.lambda_.FunctionUrl(
                f"woof-{location}",
                function_name=lambda_.arn,
                authorization_type="AWS_IAM",
                region=location,
            ).function_url
            self.lambdas.append(lambda_)
        return url

    def finish(self):
        invoke_policy = aws.iam.Policy(
            "lambdaInvoke",
            path="/",
            description="IAM policy for invoking the pinger lambda",
            policy=pulumi.Output.json_dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Action": [
                                "execute-api:Invoke",
                                "lambda:InvokeFunctionUrl",
                            ],
                            "Effect": "Allow",
                            "Resource": [
                                pulumi.Output.format("{0}/*/*", apigw.execution_arn)
                                for apigw in self.apigws
                            ]
                            + [lambda_.arn for lambda_ in self.lambdas],
                        }
                    ],
                }
            ),
        )
        aws.iam.RolePolicyAttachment(
            "lambdaInvokeAttach",
            role=self.ping_service_role.name,
            policy_arn=invoke_policy.arn,
        )
