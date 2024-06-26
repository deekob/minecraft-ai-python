"""
This module connects to a Minecraft server and sets up a bot with the ability
to interact with the game world and chat with an AI agent.

The main components are:
- Initializing a Minecraft bot using the mineflayer library
- Loading the pathfinder plugin for navigation
- Creating a BedrockBot instance to handle communication with the AI agent
- Defining event handlers for when the bot spawns and receives chat messages

The bot listens for chat messages and sends them to the BedrockBot instance,
which communicates with the AI agent and processes the agent's responses.
"""

import asyncio
import uuid
from javascript import require, On
from bedrock_agent import BedrockBot
import os

minecraft_server_dns_name = os.environ['MINECRAFT_NLB_DNS_NAME']
minecraft_server_port = os.environ['MINECRAFT_SERVER_PORT']
minecraft_bot_username = os.environ['MINECRAFT_BOT_USERNAME']
agent_alias_id = os.environ['AGENT_ALIAS_ID']
agent_id = os.environ['AGENT_ID']

# minecraft_server_dns_name = 'localhost'
# minecraft_server_port = 25565
# minecraft_bot_username = "Claude"
# agent_alias_id = 'DCFT5Y8L8Z'
# agent_id = 'DEHCT5KPAE'

session_uuid_string = uuid.uuid4().hex

mineflayer = require('mineflayer')
pathfinder = require('mineflayer-pathfinder')
# collectblock = require('mineflayer-collectblock')

bot = mineflayer.createBot({
  'host': minecraft_server_dns_name,
  'port': minecraft_server_port,
  'username':minecraft_bot_username,
  'verbose': True,
  'checkTimeoutInterval': 60 * 10000,
})

bot.loadPlugin(pathfinder.pathfinder)
# bot.loadPlugin(collectblock.plugin)
mcData = require('minecraft-data')(bot.version)

bedrockAgent = BedrockBot(bot, pathfinder)
bedrockAgent.agentAliasId = agent_alias_id
bedrockAgent.agentId = agent_id
bedrockAgent.session_id = session_uuid_string

@On(bot, 'spawn')
def spawn(*args):
    """
    Event handler for when the bot spawns in the game world.
    Prints a message to indicate the bot has spawned.
    """
    print("I spawned 👋")

@On(bot, "chat")
def handle(this, player_name, message, *args):
    """
    Event handler for when the bot receives a chat message.

    Args:
        player_name (str): The name of the player who sent the message.
        message (str): The chat message received.

    If the message is from the bot itself, it is ignored. Otherwise, the
    message is sent to the BedrockBot instance for processing.
    """
    if player_name == bot.username:
        # This is a chat from the bot itself, so do nothing...
        return
    else:
        # Send the message to the bedrockAgent object to connect to Agents for Amazon Bedrock.
        asyncio.run(bedrockAgent.chat_with_agent(f"{player_name} says: {message}"))
