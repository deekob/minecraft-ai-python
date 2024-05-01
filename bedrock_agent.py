import boto3, json, time
import logging, sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)s %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout
)

# class TestPlayerBot:
#     def chat(self, message):
#         self.logger.info(f"pLayerBot says: {message}")

#     def jump(self):
#         self.logger.info(f"pLayerBot is jumping")

class FunctionHandler:

    def __init__(self, playerBot, pathfinder):
        self.logger = logging.getLogger(__name__)
        self.bot = playerBot
        self.pathfinder = pathfinder
        
    """Handles specific actions that can be called dynamically."""
    def action_dig(self, parameters):
        self.logger.info("Digging")
        self.logger.info(parameters)
        return {"message": "Done"}, "REPROMPT"

    def action_jump(self, parameters):
        self.logger.info("Jumping")
        self.logger.info(parameters)
        self.bot.setControlState('jump', True)
        time.sleep(1)
        self.bot.setControlState('jump', False)
        return {"message": "Done"}, "REPROMPT"

    def action_is_raining(self, parameters):
        self.logger.info("Checking if it's raining.")
        self.logger.info(parameters)
        result = self.bot.isRaining
        self.logger.info(result)
        return {"raining": result}, "REPROMPT"
    
    def action_get_time(self, parameters):
        self.logger.info("Getting the time.")
        self.logger.info(parameters)
        # get time in a string format:
        result = time.strftime("%H:%M:%S")
        self.logger.info(result)
        return {"time": result}, "REPROMPT"

    def action_get_player_location(self, parameters):
        # requires the player_name to be set
        self.logger.info("Getting the location.")
        self.logger.info(parameters)
        # get location in a string format:
        player_name = parameters['player_name']
        player = self.bot.players[player_name]
        entity = player.entity
        pos = entity.position
        result = f"x:{pos.x}, y:{pos.y}, z:{pos.z}"
        self.logger.info(result)
        return {"location": result}, "REPROMPT"
    
    def action_move_to_location(self, parameters):
        self.logger.info("Moving to location.")
        self.logger.info(parameters)
        # get location from string into float:
        x = float(parameters['location_x'])
        y = float(parameters['location_y'])
        z = float(parameters['location_z'])
        range_goal = 1
        self.bot.pathfinder.setGoal(self.pathfinder.goals.GoalNear(x, y, z, range_goal))
        return {"message": "En route"}, "REPROMPT"
    
    def action_get_distance_between_to_entities(self, parameters):
        self.logger.info("Getting the distance between to entities.")
        self.logger.info(parameters)

        # This is a bit of a hack, but it works.
        # If the json string contains single quotes replace with double quotes:
        if "'" in parameters['location_1']:
            parameters['location_1'] = parameters['location_1'].replace("'", '"')
        if "'" in parameters['location_2']:
            parameters['location_2'] = parameters['location_2'].replace("'", '"')        

        # get location from json string:
        location_1 = json.loads(parameters['location_1']) # {'x':x,'y':y,'z':z}
        location_2 = json.loads(parameters['location_2']) # {'x':x,'y':y,'z':z}

        # calculate the euclidean distance between the two entities:
        result = ((location_2['x'] - location_1['x']) ** 2 + (location_2['y'] - location_1['y']) ** 2 + (location_2['z'] - location_1['z']) ** 2) ** 0.5
        
        self.logger.info(result)
        return {"distance": result}, "REPROMPT"

    def call_function(self, function_name, parameters):
        """Dynamically calls functions based on function_name."""

        param_dict = {}
        for entry in parameters:
            key = entry.get("name")
            value = entry.get("value")
            param_dict[key] = value

        func = getattr(self, function_name, None)
        if func is None:
            self.logger.exception("Function not found.")
            return {"error": "Function not found"}, "FAILURE"
        return func(param_dict)

class BedrockBot:
    def __init__(self, playerBot, pathfinder):
        self.logger = logging.getLogger(__name__)
        self.bedrock_agent_runtime_client = boto3.client('bedrock-agent-runtime', region_name='us-west-2')
        self.agentAliasId = 'WP6MJQ3RNG'
        self.agentId = 'DEHCT5KPAE'
        self.playerBot = playerBot
        self.function_handler = FunctionHandler(playerBot, pathfinder)
        self.session_id = None

    async def chat_with_agent(self, prompt):

        logging.info("chat_with_agent")
        logging.info(f"prompt: {prompt}")

        response = await self._invoke_agent(input_text=prompt)
        
        return response

    async def _invoke_agent(self, input_text=None, session_state=None):
        
        params = {
            'agentId': self.agentId,
            'agentAliasId': self.agentAliasId,
            'sessionId': self.session_id,
        }
        if input_text:
            params['inputText'] = input_text
        if session_state:
            params['sessionState'] = session_state

        response = self.bedrock_agent_runtime_client.invoke_agent(**params)
        processed_response = await self._process_response(response)
        
        return processed_response

    async def _process_response(self, response):

        self.logger.info("_process_response")

        completion = ""
        return_control_data = None
        
        for event in response.get("completion", []):
            if 'chunk' in event:
                chunk = event.get('chunk')
                if 'bytes' in chunk:
                    completion += chunk['bytes'].decode()
            if 'returnControl' in event:
                return_control_data = event['returnControl']

        if 'returnControl' in response and not return_control_data:
            return_control_data = response['returnControl']

        processed =  {
            "streamed_data": completion,
            "return_control_data": return_control_data
        }

        if processed['streamed_data']:
            logging.info(f"chat_message: {processed['streamed_data']}")
            self.playerBot.chat(processed['streamed_data'])
        
        if processed['return_control_data']:
            logging.info(f"return_control_data: {json.dumps(processed['return_control_data'], indent=2)}")
            await self._handle_return_control(return_control_data)

        return True

    async def _handle_return_control(self, return_control_data):

        self.logger.info("_handle_return_control")
        self.logger.info(f"return_control_data: {json.dumps(return_control_data, indent=2)}")

        functionInvocationInput = return_control_data['invocationInputs'][0]['functionInvocationInput']

        actionGroup = functionInvocationInput['actionGroup']
        function = functionInvocationInput['function']
        parameters = functionInvocationInput['parameters']

        result, responseState = self.function_handler.call_function(function, parameters)

        responseBody = {
            'TEXT': {
                'body': json.dumps(result)
            }
        }

        session_state = {
            'invocationId': return_control_data['invocationId'],
            'returnControlInvocationResults': [
                { 
                    'functionResult' : {
                        'actionGroup': actionGroup,
                        'function': function,
                        'responseBody': responseBody,
                        'responseState': responseState
                    }
                }
            ]
        }

        self.logger.info(f"Session state: {json.dumps(session_state, indent=2)}")

        return await self._invoke_agent(session_state=session_state)

# import asyncio

# def main():
#     playerBot = TestPlayerBot()
#     bot = BedrockBot(playerBot)
#     response = asyncio.run(bot.chat_with_agent("Player 1 says: hello!!", "efjbdkukujgvdhfgurnhjljhcvktkvrrdikdfjbrb"))

# if __name__ == "__main__":
#     main()
