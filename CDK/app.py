#!/usr/bin/env python3
import aws_cdk as cdk
#import Minecraft stack from a file called minecraft.py in a subfolder server
from server.minecraftStack import MinecraftStack  

app = cdk.App()
MinecraftStack(app, "MinecraftStack",
   
    env=cdk.Environment(account='590183852924', region='us-west-2'),
    )

app.synth()