from mcrcon import MCRcon
import os

server = '10.0.149.21'
port = os.environ['MINECRAFT_SERVER_PORT_RCON']
password = os.environ['RCON_PASSWORD']

with MCRcon(server, password, port=int(port)) as mcr:
	resp = mcr.command("/op mikegchambers")
	print(resp)
	resp = mcr.command("/op deekob")
	print(resp)