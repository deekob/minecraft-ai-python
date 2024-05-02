from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,  CfnOutput, Stack
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
            memory_limit_mib=8192,
        )
        
        container = task_definition.add_container(
            "minecraft-server",
            image=ecs.ContainerImage.from_registry("itzg/minecraft-server"),
            logging=ecs.LogDriver.aws_logs(stream_prefix="minecraft"),
            port_mappings=[
                ecs.PortMapping(
                    container_port=25565,
                    host_port=25565,
                    protocol=ecs.Protocol.TCP
                )
            ],
            environment = {
                "EULA": "TRUE",
                "VERSION":"1.19.3"
            })
      
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

        minecraft_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "MinecraftServerService",
            cluster=cluster,
            task_definition=task_definition,
            desired_count=1,
            public_load_balancer=True,
            listener_port=25565,
            assign_public_ip=True
        )

        CfnOutput(
            self,
            "MineCraft Service",
            value=f"http://{minecraft_service.load_balancer.load_balancer_dns_name}",
            description="Access minecraft from your client"
        )