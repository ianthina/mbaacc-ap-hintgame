from typing import Optional
from .gameHandler import *
import asyncio
import colorama
import random
from CommonClient import (
	CommonContext,
	ClientCommandProcessor,
	get_base_parser,
	logger,
	server_loop,
	gui_enabled,
)
import traceback

class mbaaClientProcessor(ClientCommandProcessor):
    pass

class mbaaContext(CommonContext):
    def make_gui(self):
            ui = super().make_gui()
            ui.base_title = f"{DISPLAY_NAME} Client"
            return ui

    def __init__(self, server_address: Optional[str], password: Optional[str]) -> None:
            super().__init__(server_address, password)
            self.game = ""
            self.items_handling = 0b000
            self.command_processor = mbaaClientProcessor
            self.tags = ["HintGame"]
            self.reset()

    def reset(self):
        self.is_connected = False
        self.handler = None
        self.inError = False
        self.currentStreak = 0
        self.currentRoundStreak = 0
        self.usefulQueue = 0
        self.progressionQueue = 0
        self.otherQueue = 0
        self.hints = []

    async def server_auth(self, password_requested: bool = False):
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    def on_package(self, cmd: str, args: dict):
        """
        Manage the package received from the server
        """
        if cmd == "Connected":
            self.is_connected = True            

        if cmd == "PrintJSON":
            if args['type'] == "Hint":
                item = args['item']
                if item.player == self.slot:
                    self.hints.append(item.location)

        if cmd == "Retrieved":
            retrievedKeys = args['keys']
            if f"_read_hints_{self.team}_{self.slot}" in retrievedKeys:
                hints = retrievedKeys[f"_read_hints_{self.team}_{self.slot}"]
                for hint in hints:
                    if hint['finding_player'] == self.slot:
                        self.hints.append(hint['location'])

        if cmd == "LocationInfo":
            locs = args['locations']
            locs_unhinted = []
            for loc in locs:
                if not loc.location in self.hints:
                    locs_unhinted.append(loc)
            loc_candidates = random.sample(locs_unhinted, k=min(100,len(locs_unhinted)))
            if self.progressionQueue:
                logger.info("Preparing to send a progression hint...")
                self.progressionQueue -= 1
                self.hintProgression(loc_candidates)
            elif self.usefulQueue:
                logger.info("Preparing to send a useful hint...")
                self.usefulQueue -= 1
                self.hintUseful(loc_candidates)
            elif self.otherQueue:
                logger.info("Preparing to send a chaff hint...")
                self.otherQueue -= 1
                self.hintOther(loc_candidates)

    def client_recieved_initial_server_data(self):
        """
		This method waits until the client finishes the initial conversation with the server.
		This means:
			- All LocationInfo packages recieved - requested only if patch files dont exist.
			- DataPackage package recieved (id_to_name maps and name_to_id maps are popualted)
			- Connection package recieved (slot number populated)
			- RoomInfo package recieved (seed name populated)
		"""
        return self.is_connected

    async def wait_for_initial_connection_info(self):
        """
		This method waits until the client finishes the initial conversation with the server.
	    See client_recieved_initial_server_data for wait requirements.
		"""
        if self.client_recieved_initial_server_data():
            return
        
        logger.info("Waiting for connect from server...")
        while not self.client_recieved_initial_server_data() and not self.exit_event.is_set():
            await asyncio.sleep(1)

    def hintOther(self, scouts):
        loc_candidates = []
        loc_result = None
        for loc in scouts:
            if not (loc.flags & 0b011):
                loc_candidates.append(loc)
        if len(loc_candidates):
            loc_result = random.choice(loc_candidates)
        elif len(scouts):
            loc_result = random.choice(scouts)
        if loc_result:
            logger.info("Sent a chaff hint.")
            asyncio.create_task(self.send_msgs([{"cmd": "CreateHints", "locations": [loc_result.location]}]))
            return
        logger.info("No items found.")

    def hintUseful(self, scouts):
        loc_candidates = []
        loc_result = None
        for loc in scouts:
            if (loc.flags & 0b011):
                loc_candidates.append(loc)
        if len(loc_candidates):
            loc_result = random.choice(loc_candidates)
        if loc_result:
            logger.info("Sent a useful hint.")
            asyncio.create_task(self.send_msgs([{"cmd": "CreateHints", "locations": [loc_result.location]}]))
            return
        logger.info("No useful hints found...")
        self.hintOther(scouts)

    def hintProgression(self, scouts):
        loc_candidates = []
        loc_result = None
        for loc in scouts:
            if (loc.flags & 0b001):
                loc_candidates.append(loc)
        if len(loc_candidates):
            loc_result = random.choice(loc_candidates)
        if loc_result:
            logger.info("Sent a progression hint.")
            asyncio.create_task(self.send_msgs([{"cmd": "CreateHints", "locations": [loc_result.location]}]))
            return
        logger.info("No progression hints found...")
        self.hintUseful(scouts)

    async def roundHint(self):
        try:
            hintQuality = (self.currentRoundStreak * 10) + (self.currentStreak * self.handler.getMaxRounds() * 2) + 20
            if (random.randint(0, 99) < hintQuality):
                self.usefulQueue += 1
            else:
                self.otherQueue += 1
            await self.send_msgs([{"cmd": "LocationScouts","locations": list(self.missing_locations)[:100]}])
        except Exception as e:
            logger.error(f"Hint ERROR: {e}")
            logger.error(traceback.format_exc())
            self.inError = True

    async def winHint(self):
        try:
            hintQuality = (self.currentRoundStreak * 10) + (self.currentStreak * self.handler.getMaxRounds() * 2) + 15
            hintRoll = random.randint(0, 99)
            if (hintRoll < hintQuality):
                self.progressionQueue += 1
            elif (hintRoll < (hintQuality * 2)):
                self.usefulQueue += 1
            else:
                self.otherQueue += 1
            await self.send_msgs([{"cmd": "LocationScouts","locations": list(self.missing_locations)[:100]}])
        except Exception as e:
            logger.error(f"Hint ERROR: {e}")
            logger.error(traceback.format_exc())
            self.inError = True

    async def main_loop(self):
        try:
            currentWins = 0
            currentLosses = 0
            currentWonRounds = 0
            currentLostRounds = 0
            while not self.exit_event.is_set() and self.handler.pm and self.handler.cccaster and not self.inError:
                newWins = self.handler.getWins()
                newLosses = self.handler.getLosses()
                newWonRounds = self.handler.getWonRounds()
                newLostRounds = self.handler.getLostRounds()

                if newLostRounds > currentLostRounds:
                    if self.currentRoundStreak > 0:
                        self.currentRoundStreak = 0
                        logger.info(f"Round lost. Streak reset.")
                if newLosses > currentLosses:
                    if self.currentStreak > 0:
                        self.currentStreak = 0
                        logger.info(f"Match lost. Streak reset.")

                if newWonRounds > currentWonRounds:
                    self.currentRoundStreak += 1
                    logger.info(f"Round won. Streak: {self.currentRoundStreak}.")
                    logger.info(f"Round {newWonRounds} out of {self.handler.getMaxRounds()}")
                    if not newWonRounds == self.handler.getMaxRounds():
                        asyncio.create_task(self.roundHint())
                if newWins > currentWins:
                    self.currentStreak += 1
                    asyncio.create_task(self.winHint())
                    logger.info(f"Match won. Streak: {self.currentStreak}.")

                currentWins = newWins if newWins >= currentWins else 0
                currentLosses = newLosses if newLosses >= currentLosses else 0
                currentWonRounds = newWonRounds if newWonRounds >= currentWonRounds else 0
                currentLostRounds = newLostRounds if newLostRounds >= currentLostRounds else 0
                await asyncio.sleep(0.2)
        except Exception as e:
            logger.error(f"Main ERROR: {e}")
            logger.error(traceback.format_exc())
            self.inError = True
         
    async def connect_to_game(self):
        """
        Connect the client to the game process
        """
        self.handler = None

        while not self.handler:
            try:
                self.handler = gameHandler()
            except Exception as e:
                await asyncio.sleep(2)

    async def reconnect_to_game(self):
        """
        Reconnect to client to the game process without resetting everything
        """

        while not self.handler.pm or not self.handler.cccaster:
            try:
                self.handler.reconnect()
            except Exception as e:
                await asyncio.sleep(2)

async def game_watcher(ctx: mbaaContext):
    """
    Client loop, watching the game process.
    Start the different loops once connected that will handle the game.
    It will also attempt to reconnect if the connection to the game is lost.
    
    :mbaaContext ctx: The client context instance.
    """

    await ctx.wait_for_initial_connection_info()

    while not ctx.exit_event.is_set():
        if not ctx.server:
            ctx.reset()
            await ctx.wait_for_initial_connection_info()
            
        if ctx.handler is None and not ctx.inError:
            logger.info(f"Waiting for connection to {SHORT_NAME}...")
            asyncio.create_task(ctx.connect_to_game())
            while(ctx.handler is None and not ctx.exit_event.is_set()):
                await asyncio.sleep(1)

        if ctx.inError:
            logger.info(f"Connection lost. Waiting for connection to {SHORT_NAME}...")
            ctx.handler.pm = None
            ctx.handler.cccaster = None

            asyncio.create_task(ctx.reconnect_to_game())
            await asyncio.sleep(1)
            while(ctx.handler.pm is None and ctx.handler.cccaster is None and not ctx.exit_event.is_set()):
                await asyncio.sleep(1)

        if ctx.handler and ctx.handler.pm and ctx.handler.cccaster:
            ctx.inError = False
            logger.info(f"{SHORT_NAME} process found. Starting loop...")

            loops = []
            loops.append(asyncio.create_task(ctx.main_loop()))

            while not ctx.exit_event.is_set() and ctx.server and not ctx.inError:
                await asyncio.sleep(1)

            for loop in loops:
                try:
                    loop.cancel()
                except:
                    pass

def launch():
	"""
	Launch a client instance (wrapper / args parser)
	"""
	async def main(args):
		"""
		Launch a client instance (threaded)
		"""
		ctx = mbaaContext(args.connect, args.password)
		ctx.server_task = asyncio.create_task(server_loop(ctx))
		if gui_enabled:
			ctx.run_gui()
		ctx.run_cli()
		watcher = asyncio.create_task(
			game_watcher(ctx),
			name="GameProgressionWatcher"
		)
		await ctx.exit_event.wait()
		await watcher
		await ctx.shutdown()

	parser = get_base_parser(description=SHORT_NAME+" Client")
	args, _ = parser.parse_known_args()

	colorama.init()
	asyncio.run(main(args))
	colorama.deinit()