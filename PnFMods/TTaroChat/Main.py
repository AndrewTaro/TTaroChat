API_VERSION = 'API_v1.0'
MOD_NAME = 'TTaroChat'
LOG_NAME = '{}, ModsAPI'.format(MOD_NAME)

try:
    import utils, web, dataHub, ui, constants, events, battle
except:
    pass

CC = constants.UiComponents

DEEPL_URL   = 'https://api-free.deepl.com/v2/translate'
ENCODED_URL = 'WycAAABsAQAAAM4jbAEAAAAbX2wBAAAAG19sAQAAAKJqbAEAAACScWwBAAAAZBpsAQAAACJDbAEAAAAiQ2wBAAAAGDpsAQAAAKJqbAEAAACHZ2wBAAAAVQZsAQAAAPQpbAEAAABTVGwBAAAAuj5sAQAAALo+bAEAAABKU2wBAAAAV0NsAQAAALo+bAEAAAC6PmwBAAAAompsAQAAAKwxbAEAAABKU2wBAAAAC2lsAQAAAIxdbAEAAADGZmwBAAAAIkNsAQAAAGYlbAEAAACLZmwBAAAAIkNsAQAAABtfbAEAAABTVGwBAAAAGDpsAQAAADgzbAEAAACScWwBAAAArDFsAQAAABg6bAEAAAAbX2wBAAAAuj4='
AUTH_KEY    = 'totallyLegitAuthToken'
TARGET_LANG = 'EN'

BASE_DATA = {
    'auth_key'      : AUTH_KEY,
    'target_lang'   : TARGET_LANG, # ToDo: use prefs
    'tag_handling'  : 'html',
}

ACHIEVEMENT_CHAT_TYPE = constants.TypeClientSystemChatMessages.ACHIEVEMENT_EARNED
SYSTEM_CHAT_SENDER_IDS = constants.SystemChatSenderIds.ALL
SYSTEM_CHAT_TYPES = constants.TypeClientSystemChatMessages.ALL + constants.TypeSystemChatMessages.ALL

QuickCommandType = constants.QuickCommandType
COMMAND_TYPE_TO_PREF_KEY = {
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
SECTION_NAME = 'chatBoxWidth'

web.addAllowedUrl(ENCODED_URL)

def isPlayerChat(senderId, type):
    return senderId not in SYSTEM_CHAT_SENDER_IDS and type not in SYSTEM_CHAT_TYPES


class TTaroChatTranslator(object):
    def __init__(self):
        self._entityIds = []
        self._chatEntity = None

        events.onBattleShown(self.init)
        events.onBattleQuit(self.kill)

    def init(self, *args):
        chatEntity = dataHub.getSingleEntity('battleChatAndLog')
        if chatEntity:
            chatEntity[CC.battleChatAndLog].evMessageReceived.add(self.__onChatReceived)
            utils.logInfo('[{}] {}'.format(MOD_NAME, 'registered event') )
            self._chatEntity = chatEntity

    def kill(self, *args):
        if self._chatEntity:
            self._chatEntity[CC.battleChatAndLog].evMessageReceived.remove(self.__onChatReceived)
        try:
            self._clearEntities()
        except:
            pass

    def __onChatReceived(self, component):
        entity = dataHub.getEntityCollections('battleChatAndLogMessage')[-1]
        comp = entity[CC.battleChatAndLogMessage]
        if isPlayerChat(comp.playerId, comp.type):
            self._requestTranslation(comp)

    def _requestTranslation(self, component):
        utils.logInfo('[{}] {}'.format(MOD_NAME, 'starting request') )
        data = web.urlEncode( dict(BASE_DATA, text=component.message) )
        url = '{}?{}'.format(DEEPL_URL, data)

        def f(res):
            return self.__onResponseReceived(component, res)
        
        web.fetchURL(url, f, '', 5, 'GET')

    def __onResponseReceived(self, component, res):
        message = self._parseResponse(component, res)
        if message:
            self._createEntity(component, message)

    def _parseResponse(self, component, res):
        if res and res.get('response') == 200:
            data = utils.jsonDecode(res['body'])
            tr = data['translations'][0]
            origLang = tr.get('detected_source_language', '?')
            text = tr.get('text')

            if origLang == TARGET_LANG or component.message == text:
                # If Input and Translation are the same language
                # Do not overwrite the chat
                # or the mesasge did not change
                return

            message = '({}) {}'.format(origLang, text)
            return message

    def _createEntity(self, component, message):
        compId = 'modTTaroChat_{}'.format(component.id)
        entityId = ui.createUiElement()
        ui.addDataComponentWithId(entityId, compId, {'message': message})

        self._entityIds.append(entityId)

    def _clearEntities(self, *args):
        for entityId in self._entityIds:
            ui.deleteUiElement(entityId)


gTTaroChatTranslator = TTaroChatTranslator()


class TTaroChatFilter(object):
    def __init__(self):
        battle.activateQuickCommandFilter(MOD_NAME, self.isQuickCommandVisible)
        battle.activateChatMessageFilter(MOD_NAME, self.isChatVisible)

    def __createPrefKey(self, senderInfo, myInfo, type):
        prefPrefix = 'ttChatAlly' if myInfo.teamId == senderInfo.teamId else 'ttChatEnemy'
        return prefPrefix + type + 'Visible'

    def isQuickCommandVisible(self, senderId, commandType):
        myInfo = battle.getSelfPlayerInfo()
        sender = battle.getPlayerInfo(senderId)

        # Always show my own quick command or system message
        if not sender or sender.isOwn:
            return True

        if commandType in COMMAND_TYPE_TO_PREF_KEY:
            prefKey = self.__createPrefKey(sender, myInfo, COMMAND_TYPE_TO_PREF_KEY[commandType])
            isVisible = ui.getUserPrefs(SECTION_NAME, prefKey, True)
            if isVisible is None:
                # getUserPrefs returns None if SECTION_NAME is missing.
                return True
            return bool( round(isVisible) )

        return True
    
    def isChatVisible(self, senderId, extraData):
        myInfo = battle.getSelfPlayerInfo()
        sender = battle.getPlayerInfo(senderId)

        # Always show your own achievements and chats
        if sender and sender.isOwn:
            return True
        
        type = extraData.get('type', None) if extraData else None
        
        # Achievement chats
        if type == ACHIEVEMENT_CHAT_TYPE:
            sender = battle.getPlayerInfo(extraData['playerId'])
            prefName = 'Achievements'
        # Player chats
        elif isPlayerChat(senderId, type):
            prefName = 'Chats'
        else:
            return True
        
        prefKey = self.__createPrefKey(sender, myInfo, prefName)
        isVisible = ui.getUserPrefs(SECTION_NAME, prefKey, True)
        if isVisible is None:
            # getUserPrefs returns None if SECTION_NAME is missing.
            return True
        return bool( round(isVisible) )
    
gTTaroChatFilter = TTaroChatFilter()