from aws_cdk import Stack, Duration, CfnOutput
import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_ecs as ecs
import aws_cdk.aws_ecs_patterns as ecs_patterns
import aws_cdk.aws_secretsmanager as secretsmanager
from constructs import Construct
from aws_cdk import aws_iam as iam

#create a python CDK stack that extends cdk.Stack
class MinecraftStack (Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

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
            connection=ec2.Port.tcp(25565),
            description="Allow inbound TCP traffic on port 25565"
        )

        # ECS Cluster
        cluster = ecs.Cluster(
            self,
            "MinecraftServerCluster",
            vpc=minecraft_vpc
        )

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
                    container_port=25565,
                    host_port=25565,
                    protocol=ecs.Protocol.TCP
                ),
                ecs.PortMapping(
                    container_port=25575,
                    host_port=25575,
                    protocol=ecs.Protocol.TCP
                )
            ],
            environment={
                "EULA": "TRUE",
                "VERSION": "1.20.1",
                "SERVER_PORT": "25565",
                "RCON_PORT": "25575",
                "MODE": "creative",
                "DIFFICULTY": "peaceful",
                "ONLINE_MODE": "FALSE",
            },
            secrets={
                "RCON_PASSWORD": ecs.Secret.from_secrets_manager(rcon_secret)
            },
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "netstat -an | grep 25565 > /dev/null || exit 1"],
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
            listener_port=25565,
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

        # Update the Node.js task definition to use the IAM role
        nodejs_task_definition = ecs.FargateTaskDefinition(
            self, "NodeJsTaskDefinition",
            cpu=256,
            memory_limit_mib=512,
            task_role=nodejs_task_role,  # Set the task role for the task definition
            # compatibility=ecs.Compatibility.EC2
        )

        health_check = ecs.HealthCheck(
            interval=Duration.minutes(1),
            timeout=Duration.seconds(30),
            retries=3,
            start_period=Duration.seconds(300),  # 5 minutes
            command=["CMD-SHELL", "echo 'foo' || exit 1"]
        )

        nodejs_container = nodejs_task_definition.add_container(
            "nodejs-container",
            image=ecs.ContainerImage.from_registry("amazonlinux:latest"),
            logging=ecs.LogDriver.aws_logs(stream_prefix="amazonlinux"),
            health_check=health_check,
            command=[
                "sh",
                "-c",
                "echo 'Installing Node.js and Python packages...'",
                "yum install -y nodejs python3 git",
                "python3 -m ensurepip --upgrade",
                "git clone https://github.com/deekob/minecraft-ai-python.git",
                "pip3 install -r requirements.txt",
                f"export MINECRAFT_NLB_DNS_NAME={minecraft_service.load_balancer.load_balancer_dns_name}", 
                "python3 ./index.py" # && tail -f /dev/null"
            ],
        )

        nodejs_container.add_port_mappings(
            ecs.PortMapping(container_port=3000, host_port=3000, protocol=ecs.Protocol.TCP)
        )

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


# #######################################################

        CfnOutput(
            self,
            "MineCraft Service",
            value=f"{minecraft_service.load_balancer.load_balancer_dns_name}:25565",
            description="Access minecraft from your client"
        )