# pip install javascript
# conda install nodejs 

from javascript import require, On
import time

mineflayer = require('mineflayer')

bot = mineflayer.createBot({
  'host': 'localhost',
  'port': 54858,
  'username':'Claude',
  'verbose': True,
  'checkTimeoutInterval': 60 * 10000,
})

mcData = require('minecraft-data')(bot.version)


@On(bot, 'spawn')
def spawn(*args):
  print("I spawned 👋")
  

@On(bot, "chat")
def handle(this, player_name, message, *args):
    if player_name == bot.username:
        # This is a chat from the bot itself, so do nothing...
        return
    else:
        # Someone said something...
        bot.setControlState('jump', True)
        bot.chat("Hello, {}!".format(player_name))
        bot.chat("You said: {}".format(message))
        time.sleep(1)
        bot.setControlState('jump', False)