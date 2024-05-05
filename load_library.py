from javascript import require, On

print("Loading javascript libraries for the first time.")

mineflayer = require('mineflayer')
pathfinder = require('mineflayer-pathfinder')
collectblock = require('mineflayer-collectblock')

print("Libraries should be cached now...")
