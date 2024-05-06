import logging
from mcrcon import MCRcon
import os

# Configure logging
logging.basicConfig(filename='/rcon/logs/logfile.log', level=logging.INFO, 
                    format='%(asctime)s:%(levelname)s:%(message)s')

server = '10.0.149.21'
port = os.environ['MINECRAFT_SERVER_PORT_RCON']
password = os.environ['RCON_PASSWORD']

try:
    with MCRcon(server, password, port=int(port)) as mcr:
        resp = mcr.command("/time set noon")
        logging.info(resp)  # Log the response from the server
        print(resp)  # This will also output to console, can be useful for debugging
except Exception as e:
    logging.error("Failed to execute RCON command", exc_info=True)  # Log the exception

