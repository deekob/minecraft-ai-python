import pytest
from server.minecraftStack import MinecraftStack

@pytest.fixture
def stack():
    return MinecraftStack(scope, "TestMinecraftStack", env={"region": "us-west-2"})

def test_minecraft_server_task_definition_ecr_image(stack):
    task_definition = stack.minecraft_server_task_definition
    container = task_definition.default_container
    assert container.image.repository_uri == "123456789012.dkr.ecr.us-west-2.amazonaws.com/my-repository"
    assert container.image.tag == "latest"
