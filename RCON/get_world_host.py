import boto3
import json

# Constants: Set these to match your specific environment
CLUSTER_NAME = 'MinecraftStack-MinecraftServerClusterE5F7E9E1-isYIDqj5eWpL'
SERVICE_NAME = 'MinecraftStack-MinecraftServerServiceB09FCDC8-x1P4TO8cu4Dp'

def get_container_ip(cluster_name, service_name):
    # Create a boto3 client for ECS
    ecs_client = boto3.client('ecs')

    # Get the list of tasks running under the specified service and cluster
    tasks_response = ecs_client.list_tasks(
        cluster=cluster_name,
        serviceName=service_name
    )
    task_arns = tasks_response.get('taskArns')
    if not task_arns:
        raise Exception("No tasks found under the specified service.")

    # Describe the task to get container instance ID
    describe_tasks_response = ecs_client.describe_tasks(
        cluster=cluster_name,
        tasks=task_arns
    )
    tasks = describe_tasks_response.get('tasks')
    if not tasks:
        raise Exception("Unable to retrieve task details.")

    details = tasks[0]['attachments'][0]['details']
    for detail in details: 
        if detail['name'] == 'privateIPv4Address':
            return detail['value']
    return False

# Usage
if __name__ == "__main__":
    ip_address = get_container_ip(CLUSTER_NAME, SERVICE_NAME)
    print(f"The IP address of the container is: {ip_address}")

