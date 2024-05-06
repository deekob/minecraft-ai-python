from aws_cdk import Stack, Duration, CfnOutput
import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_ecs as ecs
import aws_cdk.aws_ecs_patterns as ecs_patterns
import aws_cdk.aws_secretsmanager as secretsmanager
from constructs import Construct
from aws_cdk import aws_iam as iam
from aws_cdk import aws_elasticloadbalancingv2 as elbv2


#create a python CDK stack that extends cdk.Stack
class MinecraftStack (Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The bot container...
        repo_ecr = "590183852924.dkr.ecr.us-west-2.amazonaws.com"
        repo_name = "minecraft-bot"
        repo_tag = "0.1.4-3"

        server_port = 25565
        server_port_rcon = 25575
        bot_username = "Claude"
        agent_alias_id = "DCFT5Y8L8Z"
        agent_id = "DEHCT5KPAE"


# ######################################################
# Create VPC and networking

        # VPC
        minecraft_vpc = ec2.Vpc(
            self, 
            "MinecraftVPC",
            max_azs=2,
            nat_gateways=1
        )

        # Security Group
        minecraft_security_group = ec2.SecurityGroup(
            self,
            "MinecraftServerSecurityGroup",
            vpc=minecraft_vpc,
            description="Security group for Minecraft server",
            allow_all_outbound=True
        )

        # Add security group rules
        minecraft_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(server_port),
            description="Allow inbound TCP traffic on minecraft port"
        )

        # Add security group rules
        minecraft_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(server_port_rcon),
            description="Allow inbound TCP traffic on minecraft rcon"
        )

# ######################################################
# Create ECS Cluster

        # ECS Cluster
        cluster = ecs.Cluster(
            self,
            "MinecraftServerCluster",
            vpc=minecraft_vpc
        )

# ######################################################
# Create Minecraft Task

        # ECS Task Definition
        task_definition = ecs.FargateTaskDefinition(
            self, "MinecraftServerTaskDefinition",
            cpu=4096,
            memory_limit_mib=16384,
        )
        
        rcon_secret = secretsmanager.Secret.from_secret_name_v2(self, "RconPassword", "minecraft/rcon-password")

        container = task_definition.add_container(
            "minecraft-server",
            image=ecs.ContainerImage.from_registry("itzg/minecraft-server:latest"),
            logging=ecs.LogDriver.aws_logs(stream_prefix="minecraft"),
            port_mappings=[
                ecs.PortMapping(
                    container_port=server_port,
                    host_port=server_port,
                    protocol=ecs.Protocol.TCP
                ),
                ecs.PortMapping(
                    container_port=server_port_rcon,
                    host_port=server_port_rcon,
                    protocol=ecs.Protocol.TCP
                )
            ],
            environment={
                "EULA": "TRUE",
                "VERSION": "1.20.1",
                "SERVER_PORT": str(server_port),
                "RCON_PORT": str(server_port_rcon),
                "MODE": "creative",
                "DIFFICULTY": "peaceful",
                "ONLINE_MODE": "FALSE",
                "ALLOW_CHEATS": "TRUE",
                "LEVEL_TYPE": "FLAT",
                "ALLOW_FLIGHT": "TRUE",
            },
            secrets={
                "RCON_PASSWORD": ecs.Secret.from_secrets_manager(rcon_secret)
            },
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", f"netstat -an | grep {server_port} > /dev/null || exit 1"],
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                retries=3,
                start_period=Duration.seconds(300)  # 5 minutes
            )
        )
      
        mount_points=[
            ecs.MountPoint(
                read_only = False,
                container_path="/data",
                source_volume="minecraft-data"
            )
        ]
        
        container.mount_point=mount_points

        task_definition.add_volume(
            name="minecraft-data"
        )

        minecraft_service = ecs_patterns.NetworkLoadBalancedFargateService(
            self, "MinecraftServerService",
            cluster=cluster,
            task_definition=task_definition,
            desired_count=1,
            public_load_balancer=True,
            listener_port=server_port,
            assign_public_ip=False,
            health_check_grace_period=Duration.minutes(5),
            security_groups=[minecraft_security_group]  # Add this line to include your security group
        )

# ######################################################
# Create an IAM role for the Node.js container

        nodejs_task_role = iam.Role(
            self, "NodeJsTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            description="IAM role for Node.js Fargate task"
        )

        # Define the custom policy document allowing Bedrock runtime access
        bedrock_policy_document = iam.PolicyDocument(
            statements=[
                iam.PolicyStatement(
                    actions=[
                        "bedrock:Invoke*"
                    ],
                    resources=["*"],  # Adjust the resource ARN as needed
                    effect=iam.Effect.ALLOW
                )
            ]
        )

        # Create an IAM policy using the custom policy document
        bedrock_policy = iam.Policy(
            self, "BedrockPolicy",
            policy_name="BedrockRuntimeAccessPolicy",
            document=bedrock_policy_document
        )

        # Attach the custom policy to the IAM role
        nodejs_task_role.attach_inline_policy(bedrock_policy)

# ######################################################
# Create Amazon ECS task execution IAM role

        nodejs_task_execution_role = iam.Role(
            self, "NodeJsTaskExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            description="IAM role for Node.js Fargate task execution"
        )

        nodejs_task_execution_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy"))

# ######################################################
# Create Task...

        # Update the Node.js task definition to use the IAM role
        nodejs_task_definition = ecs.FargateTaskDefinition(
            self, "NodeJsTaskDefinition",
            cpu=256,
            memory_limit_mib=512,
            task_role=nodejs_task_role,
            execution_role=nodejs_task_execution_role
        )

        health_check = ecs.HealthCheck(
            interval=Duration.minutes(1),
            timeout=Duration.seconds(30),
            retries=3,
            start_period=Duration.minutes(1),
            command=["CMD-SHELL", "echo 'foo' || exit 0"]
        )

        nodejs_container = nodejs_task_definition.add_container(
            "nodejs-container",
            # image=ecs.ContainerImage.from_registry("amazonlinux:latest"),
            image=ecs.ContainerImage.from_registry(f"{repo_ecr}/{repo_name}:{repo_tag}"),
            logging=ecs.LogDriver.aws_logs(stream_prefix="nodejs_container"),
            health_check=health_check,
            environment={
                "MINECRAFT_NLB_DNS_NAME": f"{minecraft_service.load_balancer.load_balancer_dns_name}",
                "MINECRAFT_SERVER_PORT" : str(server_port),
                "MINECRAFT_BOT_USERNAME" : bot_username,
                "AGENT_ALIAS_ID" : agent_alias_id,
                "AGENT_ID" : agent_id,
            }
        )

        nodejs_container.add_port_mappings(
            ecs.PortMapping(container_port=3000, host_port=3000, protocol=ecs.Protocol.TCP)
        )

# ######################################################
# Create security group....

        nodejs_security_group = ec2.SecurityGroup(
            self,
            "NodeJsSecurityGroup",
            vpc=minecraft_vpc,
            description="Security group for Node.js service",
            allow_all_outbound=True
        )

        # Create the Node.js service without a load balancer and with the new security group
        nodejs_service = ecs.FargateService(
            self, "NodeJsService",
            cluster=cluster,
            task_definition=nodejs_task_definition,
            desired_count=1,
            security_groups=[nodejs_security_group],  # Use the dedicated security group
            assign_public_ip=False,
            enable_execute_command=True
        )

#####################################################################
#####################################################################
# ######################################################
# Create an IAM role for the rcon container

        rcon_task_role = iam.Role(
            self, "RconTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            description="IAM role for rcon Fargate task"
        )

        # Define the custom policy document allowing Bedrock runtime access
        rcon_policy_document = iam.PolicyDocument(
            statements=[
                iam.PolicyStatement(
                    actions=[
                        "bedrock:Invoke*"
                    ],
                    resources=["*"],  # Adjust the resource ARN as needed
                    effect=iam.Effect.ALLOW
                ),
                # add managed policy for ecs access
                iam.PolicyStatement(
                    actions=[
                        "ecs:*"
                    ],
                    resources=["*"],  # Adjust the resource ARN as needed
                    effect=iam.Effect.ALLOW
                )
            ]
        )

        # Create an IAM policy using the custom policy document
        rcon_policy = iam.Policy(
            self, "RconPolicy",
            policy_name="RconPolicy",
            document=rcon_policy_document
        )

        # Attach the custom policy to the IAM role
        rcon_task_role.attach_inline_policy(rcon_policy)

# ######################################################
# Create Amazon ECS task execution IAM role

        rcon_task_execution_role = iam.Role(
            self, "RconTaskExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            description="IAM role for rcon Fargate task execution"
        )

        rcon_task_execution_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy"))


# ######################################################
# Create Task...

        # Update the rcon task definition to use the IAM role
        rcon_task_definition = ecs.FargateTaskDefinition(
            self, "RconTaskDefinition",
            cpu=256,
            memory_limit_mib=512,
            task_role=rcon_task_role,
            execution_role=rcon_task_execution_role
        )

        rcon_health_check = ecs.HealthCheck(
            interval=Duration.minutes(1),
            timeout=Duration.seconds(30),
            retries=3,
            start_period=Duration.minutes(1),
            command=["CMD-SHELL", "echo 'foo' || exit 0"]
        )

        rcon_container = rcon_task_definition.add_container(
            "rcon-container",
            image=ecs.ContainerImage.from_registry("amazonlinux:latest"),
            logging=ecs.LogDriver.aws_logs(stream_prefix="rcon"),
            health_check=rcon_health_check,
            environment={
                "MINECRAFT_NLB_DNS_NAME": f"{minecraft_service.load_balancer.load_balancer_dns_name}",
                "MINECRAFT_SERVER_PORT" : str(server_port),
                "MINECRAFT_SERVER_PORT_RCON" : str(server_port_rcon),
                "MINECRAFT_BOT_USERNAME" : bot_username,
                "AGENT_ALIAS_ID" : agent_alias_id,
                "AGENT_ID" : agent_id,
            },
            secrets={
                "RCON_PASSWORD": ecs.Secret.from_secrets_manager(rcon_secret)
            },
            command=[
                "sh",
                "-c",
                "tail -f /dev/null"
            ]
        )

        rcon_container.add_port_mappings(
            ecs.PortMapping(container_port=3000, host_port=3000, protocol=ecs.Protocol.TCP)
        )

# ######################################################
# Create security group....

        rcon_security_group = ec2.SecurityGroup(
            self,
            "RconSecurityGroup",
            vpc=minecraft_vpc,
            description="Security group for Rcon service",
            allow_all_outbound=True
        )

        # Create the rcon service without a load balancer and with the new security group
        rcon_service = ecs.FargateService(
            self, "RconService",
            cluster=cluster,
            task_definition=rcon_task_definition,
            desired_count=1,
            security_groups=[rcon_security_group],  # Use the dedicated security group
            assign_public_ip=False,
            enable_execute_command=True
        )



# #######################################################

        server_connection_link = f"""aws ecs execute-command \
    --cluster {cluster.cluster_name} \
    --task {nodejs_service.task_definition.task_definition_arn}/XXXXXXXXXXX \
    --container nodejs-container \
    --interactive \
    --command "/bin/sh"
"""
        
        rcon_connection_link = f"""aws ecs execute-command \
    --cluster {cluster.cluster_name} \
    --task {rcon_service.task_definition.task_definition_arn}/XXXXXXXXXXX \
    --container rcon-container \
    --interactive \
    --command "/bin/sh"
"""

        CfnOutput(
            self,
            "Server Connection",
            value=f"{server_connection_link}",
            description="Connect to the node container"
        )

        CfnOutput(
            self,
            "Rcon Connection",
            value=f"{rcon_connection_link}",
            description="Connect to the node container"
        )

        CfnOutput(
            self,
            "MineCraft Service",
            value=f"{minecraft_service.load_balancer.load_balancer_dns_name}:{server_port}",
            description="Access minecraft from your client"
        )