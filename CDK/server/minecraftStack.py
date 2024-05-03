from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,  CfnOutput, Stack,
    Duration,
    aws_secretsmanager as secretsmanager
)

from constructs import Construct

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
                "DIFFICULTY": "peaceful"
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


        CfnOutput(
            self,
            "MineCraft Service",
            value=f"{minecraft_service.load_balancer.load_balancer_dns_name}:25565",
            description="Access minecraft from your client"
        )