# Minecraft 1.20.1 (for the protocol version that works with mineflayer)

# pip install javascript
# conda install nodejs 

import asyncio, uuid
from javascript import require, On
from bedrock_agent import BedrockBot
import time

session_uuid_string = uuid.uuid4().hex

mineflayer = require('mineflayer')
pathfinder = require('mineflayer-pathfinder')

bot = mineflayer.createBot({
  'host': 'localhost',
  'port': 58871,
  'username':'Claude',
  'verbose': True,
  'checkTimeoutInterval': 60 * 10000,
})

bot.loadPlugin(pathfinder.pathfinder)
mcData = require('minecraft-data')(bot.version)

bedrockAgent = BedrockBot(bot, pathfinder)
bedrockAgent.agentAliasId = 'YLNUCCP5XS'
bedrockAgent.agentId = 'DEHCT5KPAE'
bedrockAgent.session_id = session_uuid_string

@On(bot, 'spawn')
def spawn(*args):
  print("I spawned 👋")
  
@On(bot, "chat")
def handle(this, player_name, message, *args):
    if player_name == bot.username:
        # This is a chat from the bot itself, so do nothing...
        return
    else:
        # Send the message to the bedrockAgent object to connect to Agents for Amazon Bedrock. 
        asyncio.run(bedrockAgent.chat_with_agent(f"{player_name} says: {message}"))
