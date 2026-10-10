import pymem
import pymem.exception
from .Variables import *

class gameHandler:
    def __init__(self):
        #Game memory
        self.pm = pymem.Pymem(GAME_NAME)
        self.addrPlayerRound = [self.pm.base_address+PLAYER_ROUND[0], self.pm.base_address+PLAYER_ROUND[1]]
        self.addrPlayerWins = [self.pm.base_address+PLAYER_WINS[0], self.pm.base_address+PLAYER_WINS[1]]
        self.addrMaxRounds = self.pm.base_address+MAX_ROUND
        #CCCaster Memory
        self.cccaster = pymem.Pymem(CCCASTER_NAME)
        self.addrOtherPlayer = self.cccaster.base_address+OTHER_PLAYER
        

    def reconnect(self):
        self.pm = pymem.Pymem(GAME_NAME)
        self.cccaster = pymem.Pymem(CCCASTER_NAME)

    def getOtherPlayer(self):
        # 0 is offline
        # 1 is hosting? or remote player is player 1?
        # 2 is client? or remote player is player 2?
        # 3 is spectating
        return int.from_bytes(self.cccaster.read_bytes(self.addrOtherPlayer, 1))

    def getPlayer(self):
        # since 0 is offline (assume player 1)
        # since PLAYER_ROUNDS and PLAYER_WINS are 0 indexed and have two entries,
        # we can use binary logic.
        return int(self.getOtherPlayer() == 1)

    def isSpectating(self):
        return int(self.getOtherPlayer() == 3)

    def getPlayerWins(self, player):
        return int.from_bytes(self.pm.read_bytes(self.addrPlayerWins[player], 1))

    def getWins(self):
        if self.isSpectating():
            return 0
        player = self.getPlayer()
        return self.getPlayerWins(player)

    def getLosses(self):
        if self.isSpectating():
            return 0
        player = int(not self.getPlayer())
        return self.getPlayerWins(player)

    def getPlayerRounds(self, player):
        return int.from_bytes(self.pm.read_bytes(self.addrPlayerRound[player], 1))

    def getMaxRounds(self):
        return int.from_bytes(self.pm.read_bytes(self.addrMaxRounds, 1))

    def getWonRounds(self):
        if self.isSpectating():
            return 0
        player = self.getPlayer()
        return self.getPlayerRounds(player)

    def getLostRounds(self):
        if self.isSpectating():
            return 0
        player = int(not self.getPlayer())
        return self.getPlayerRounds(player)

    