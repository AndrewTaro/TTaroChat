API_VERSION = 'API_v1.0'
MOD_NAME = 'TTaroChat'

try:
    import utils, web, dataHub, ui, constants, events, battle
except:
    pass

import xml
ET =  xml.etree.ElementTree

import TTaroPrefs

def logInfo(*args):
    data = [str(i) for i in args]
    utils.logInfo( '[{}] {}'.format(MOD_NAME, ', '.join(data)) )

def logError(*args):
    data = [str(i) for i in args]
    utils.logError( '[{}] {}'.format(MOD_NAME, ', '.join(data)) )


CC = constants.UiComponents

EXPORT_URL   = 'http://localhost:5000/wowschat'
ENCODED_URL = 'Wx4AAABsAQAAAM4jbAEAAAAbX2wBAAAAG19sAQAAAKJqbAEAAABkGmwBAAAAIkNsAQAAACJDbAEAAACsMWwBAAAAjF1sAQAAAAtpbAEAAAAYOmwBAAAArDFsAQAAAM4jbAEAAACMXWwBAAAAknFsAQAAABtfbAEAAABkGmwBAAAA1yxsAQAAAF9MbAEAAABfTGwBAAAAX0xsAQAAACJDbAEAAADLNGwBAAAAjF1sAQAAAMs0bAEAAACScWwBAAAAC2lsAQAAAM4jbAEAAAAYOmwBAAAAG18='

ACHIEVEMENT_CHAT_TYPE = constants.TypeClientSystemChatMessages.ACHIEVEMENT_EARNED
SYSTEM_CHAT_SENDER_IDS = constants.SystemChatSenderIds.ALL
SYSTEM_CHAT_TYPES = constants.TypeClientSystemChatMessages.ALL + constants.TypeSystemChatMessages.ALL

QuickCommandType = constants.QuickCommandType
COMMAND_TYPE_TO_MESSAGE_KIND = {
    QuickCommandType.QUICK_GOOD_GAME    : 'WellDone',
    QuickCommandType.QUICK_GOOD_LUCK    : 'GoodLuck',
    QuickCommandType.QUICK_CARAMBA      : 'WTF',
    QuickCommandType.QUICK_AYE_AYE      : 'Affirmitive',
    QuickCommandType.QUICK_NO_WAY       : 'Negative',
    QuickCommandType.BACK               : 'GetBack',
    QuickCommandType.NEED_SMOKE         : 'NeedSmoke',
    QuickCommandType.QUICK_NEED_SUPPORT : 'NeedSupport',
    QuickCommandType.NEED_AIR_DEFENCE   : 'NeedAirDefense',
    QuickCommandType.NEED_VISION        : 'NeedSpotting',
}

RPF_MESSAGE_TO_DIRECTION = {
	'RPF: N~NNE':  1,
	'RPF: NNE~NE': 2,
	'RPF: NE~ENE': 3,
	'RPF: ENE~E':  4,
	'RPF: E~ESE':  5,
	'RPF: ESE~SE': 6,
	'RPF: SE~SSE': 7,
	'RPF: SSE~S':  8,
	'RPF: S~SSW':  9,
	'RPF: SSW~SW': 10,
	'RPF: SW~WSW': 11,
	'RPF: WSW~W':  12,
	'RPF: W~WNW':  13,
	'RPF: WNW~NW': 14,
	'RPF: NW~NNW': 15,
	'RPF: NNW~N':  16,
    'RPF: None':   -1,
}


# shortName -> full dotted key, from chat.schema.json.  Visibility short names are
# '<relation>.<kind>', kind being a COMMAND_TYPE_TO_MESSAGE_KIND value or 'Chats'/'Achievements'.
#
# EVERY schema key is spelled out.  The old code built one by concatenation
# ('ttChat' + relation + kind + 'Visible'), and the new leaves are NOT a transform of the kind
# names: 'WTF' became 'Wtf' and 'NeedAirDefense' became 'NeedAirSupport'.  Composing the SHORT
# name stays safe -- that half is ours -- but a composed schema key resolves to nothing, silently.
#
# Only 18 of the 3x12 relation/kind combinations carry a setting.  A missing one means "no control
# for this", which __isMessageVisible answers True for, exactly as the old default did.
PREF_KEYS = {
    'exportChat':          'ttChat.exportChat',

    'ally.Chats':          'ttChat.ally.showChats',
    'ally.Achievements':   'ttChat.ally.showAchievements',
    'ally.WellDone':       'ttChat.ally.showWellDone',
    'ally.GoodLuck':       'ttChat.ally.showGoodLuck',
    'ally.WTF':            'ttChat.ally.showWtf',
    'ally.Affirmitive':    'ttChat.ally.showAffirmative',
    'ally.Negative':       'ttChat.ally.showNegative',
    'ally.GetBack':        'ttChat.ally.showGetBack',
    'ally.NeedSmoke':      'ttChat.ally.showNeedSmoke',
    'ally.NeedSupport':    'ttChat.ally.showNeedSupport',
    'ally.NeedAirDefense': 'ttChat.ally.showNeedAirSupport',
    'ally.NeedSpotting':   'ttChat.ally.showNeedSpotting',

    'enemy.Chats':         'ttChat.enemy.showChats',
    'enemy.Achievements':  'ttChat.enemy.showAchievements',
    'enemy.WellDone':      'ttChat.enemy.showWellDone',
    'enemy.GoodLuck':      'ttChat.enemy.showGoodLuck',
    'enemy.WTF':           'ttChat.enemy.showWtf',

    'div.Achievements':    'ttChat.div.showAchievements',
}

gPrefs = TTaroPrefs.PrefStore(MOD_NAME, PREF_KEYS)

web.addAllowedUrl(ENCODED_URL)

def isPlayerChat(senderId, type):
    return senderId not in SYSTEM_CHAT_SENDER_IDS and type not in SYSTEM_CHAT_TYPES and not getattr(battle.getPlayerInfo(senderId), 'isBot', False)

class TTaroChatExporter(object):
    def __init__(self):
        self._entityIds = []
        self._chatEntity = None

        events.onBattleShown(self.init)
        events.onBattleQuit(self.kill)

    def init(self, *args):
        chatEntity = dataHub.getSingleEntity('battleChatAndLog')
        if chatEntity:
            chatEntity[CC.battleChatAndLog].evMessageReceived.add(self.__onChatReceived)
            logInfo('Registered event')
            self._chatEntity = chatEntity

    def kill(self, *args):
        if self._chatEntity:
            self._chatEntity[CC.battleChatAndLog].evMessageReceived.remove(self.__onChatReceived)
        try:
            self._clearEntities()
        except:
            pass

    def __onChatReceived(self, component):
        if gPrefs.get('exportChat'):
            entity = dataHub.getEntityCollections('battleChatAndLogMessage')[-1]
            comp = entity[CC.battleChatAndLogMessage]
            if isPlayerChat(comp.playerId, comp.type) and comp.message not in RPF_MESSAGE_TO_DIRECTION:
                self.__exportChat(entity.id, comp)

    def __exportChat(self, entityId, comp):
        logInfo('Exporting chat')
        data = web.urlEncode({'text': comp.message})
        url = '{}?{}'.format(EXPORT_URL, data)

        def callback(res):
            # In case an expernal app returns a response to the exported chat.
            return self.__onResponseReceived(entityId, res)

        web.fetchURL(url, callback, '', 5, 'GET')

    def __onResponseReceived(self, entityId, res):
        if res and res.get('response') == 200:
            message = str(res.get('data'))
            if message:
                self._createEntity(entityId, message)

    def _createEntity(self, entityId, message):
        compId = 'modTTaroChat_{}'.format(entityId)
        ui.addDataComponentWithId(entityId, compId, {'message': message})

        self._entityIds.append(entityId)

    def _clearEntities(self, *args):
        # Check if this is necessary
        for entityId in self._entityIds:
            ui.deleteUiElement(entityId)


class TTaroChatFilter(object):
    def __init__(self):
        battle.activateQuickCommandFilter(MOD_NAME, self.isQuickCommandVisible)
        battle.activateChatMessageFilter(MOD_NAME, self.isChatVisible)

    def __relation(self, senderInfo, myInfo):
        # is in same divison
        if myInfo.prebattleId > 0 and myInfo.prebattleId == senderInfo.prebattleId:
            return 'div'
        return 'ally' if myInfo.teamId == senderInfo.teamId else 'enemy'

    def __isMessageVisible(self, senderInfo, myInfo, kind):
        shortName = self.__relation(senderInfo, myInfo) + '.' + kind
        if shortName not in PREF_KEYS:
            return True
        return bool(gPrefs.get(shortName))

    def isQuickCommandVisible(self, senderId, commandType):
        myInfo = battle.getSelfPlayerInfo()
        sender = battle.getPlayerInfo(senderId)

        # Always show my own quick command or system message
        if not sender or sender.isOwn:
            return True

        if commandType in COMMAND_TYPE_TO_MESSAGE_KIND:
            return self.__isMessageVisible(sender, myInfo, COMMAND_TYPE_TO_MESSAGE_KIND[commandType])

        return True

    def isChatVisible(self, senderId, extraData):
        myInfo = battle.getSelfPlayerInfo()
        sender = battle.getPlayerInfo(senderId)

        # Always show your own achievements and chats
        if sender and sender.isOwn:
            return True

        # `extraData` can be str for Scenario instructions/bot messages
        type = extraData.get('type', None) if extraData and isinstance(extraData, dict) else None

        # Achievement chats
        if type == ACHIEVEMENT_CHAT_TYPE:
            sender = battle.getPlayerInfo(extraData['playerId'])
            kind = 'Achievements'
        # Player chats
        elif isPlayerChat(senderId, type):
            kind = 'Chats'
        else:
            return True

        return self.__isMessageVisible(sender, myInfo, kind)


gTTaroChatExporter = None
gTTaroChatFilter = None

def onPrefsReady():
    # Nothing may subscribe or register before the store resolves.  If it never does, the two
    # filters stay unregistered and the chat behaves exactly as vanilla -- every message shown.
    # That is the right direction to fail for a filter: hiding messages the user never asked to
    # hide is worse than showing ones they did.
    global gTTaroChatExporter, gTTaroChatFilter
    gTTaroChatExporter = TTaroChatExporter()
    gTTaroChatFilter = TTaroChatFilter()

gPrefs.start(onReady=onPrefsReady)
