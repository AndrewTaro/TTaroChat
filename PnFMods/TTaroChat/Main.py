API_VERSION = 'API_v1.0'
MOD_NAME = 'TTaroChat'

try:
    import utils, web, dataHub, ui, constants, events, battle
except:
    pass

def logInfo(*args):
    data = [str(i) for i in args]
    utils.logInfo( '[{}] {}'.format(MOD_NAME, ', '.join(data)) )

def logError(*args):
    data = [str(i) for i in args]
    utils.logError( '[{}] {}'.format(MOD_NAME, ', '.join(data)) )


CC = constants.UiComponents

DEEPL_URL   = 'https://api-free.deepl.com/v2/translate'
ENCODED_URL = 'WycAAABsAQAAAM4jbAEAAAAbX2wBAAAAG19sAQAAAKJqbAEAAACScWwBAAAAZBpsAQAAACJDbAEAAAAiQ2wBAAAAGDpsAQAAAKJqbAEAAACHZ2wBAAAAVQZsAQAAAPQpbAEAAABTVGwBAAAAuj5sAQAAALo+bAEAAABKU2wBAAAAV0NsAQAAALo+bAEAAAC6PmwBAAAAompsAQAAAKwxbAEAAABKU2wBAAAAC2lsAQAAAIxdbAEAAADGZmwBAAAAIkNsAQAAAGYlbAEAAACLZmwBAAAAIkNsAQAAABtfbAEAAABTVGwBAAAAGDpsAQAAADgzbAEAAACScWwBAAAArDFsAQAAABg6bAEAAAAbX2wBAAAAuj4='


class AuthKey(object):
    AUTH_KEY_FILE = utils.getModDir() + '/../../../../../profile/deepl_auth_key.txt'
    DUMMY_KEY = 'df4385c2-33de-e423-4134-ca1f7b3ea8b7:fx'
    DUMMY_CONTENT = """###--- NEVER SHARE THIS FILE! REPLACE THE BELOW WITH YOUR AUTH KEY ---###\n{}""".format(DUMMY_KEY)

    def __init__(self):
        events.onSFMEvent(self.__onSFMEvent)
        self._key = ''

        if self.__loadFile():
            return
        else:
            self.__createFile()

    def getKey(self):
        if self._key and self._key != AuthKey.DUMMY_KEY:
            return self._key

    def __isFile(self):
        return utils.isFile(AuthKey.AUTH_KEY_FILE)

    def __loadFile(self):
        # Returns if loading is success
        if self.__isFile():
            with open(AuthKey.AUTH_KEY_FILE, 'r') as f:
                f.readline() # Skip
                key = f.readline()
                if key and key != AuthKey.DUMMY_KEY:
                    self._key = key
                    logInfo('Successfully loaded auth key.')
                    return  True
                else:
                    logInfo('Invalid auth key.')
                    self._key = ''
                    return False
        else:
            logInfo('Auth file does not exist.')
            return False
    
    def __createFile(self):
        try:
            with open(AuthKey.AUTH_KEY_FILE, 'w') as f:
                f.write(AuthKey.DUMMY_CONTENT)
            logInfo('Auth file has been created. User must enter the key.')
        except Exception, e:
            logError('Error while creating a file. {}'.format(e))

    def __onSFMEvent(self, eventName, eventData):
        if eventName == 'action.modTTaroChatAuthKeyReload':
            self.__loadFile()


ID_TO_LANGUAGES = {
    0:  'AR', # Arabic
    1:  'BG', # Blugarian
    2:  'CS', # Czech
    3:  'DA', # Danish
    4:  'DE', # German
    5:  'EL', # Greek
    6:  'EN-GB', # English (British)
    7:  'EN-US', # English (American)
    8:  'ES', # Spanish
    9:  'ET', # Estonian
    10: 'FI', # Finnish
    11: 'FR', # French
    12: 'HU', # Hungarian
    13: 'ID', # Indonesian
    14: 'IT', # Italian
    15: 'JA', # Japanese
    16: 'KO', # Korean
    17: 'LT', # Lithuanian
    18: 'LV', # Latvian
    19: 'NB', # Norwegian Bokmål
    20: 'NL', # Dutch
    21: 'PL', # Polish
    22: 'PT-BR', # Portuguese (Brazilian)
    23: 'PT_PT', # Portuguese
    24: 'RO', # Romanian
    25: 'RU', # Russian
    26: 'SK', # Slovak
    27: 'SL', # Slovenian
    28: 'SV', # Swedish
    29: 'TR', # Turkish
    30: 'UK', # Ukranian
    31: 'ZH-HANS', # Chinese (Simplified)
    32: 'ZH-HANT', # Chinese (Traditional)
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
        self._authKey = AuthKey()

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
        entity = dataHub.getEntityCollections('battleChatAndLogMessage')[-1]
        comp = entity[CC.battleChatAndLogMessage]
        if isPlayerChat(comp.playerId, comp.type):
            self._requestTranslation(comp)

    def _requestTranslation(self, component):
        authKey = self._authKey.getKey()
        if not authKey:
            logInfo('Invalid auth key: skipping translation')
            return
        
        logInfo('Starting request')
        reqData = self._createRequestData(authKey, component.message)
        data = web.urlEncode(reqData)
        url = '{}?{}'.format(DEEPL_URL, data)

        def callback(res):
            # Pass target lang in order to prevent a rare case
            # where the target language is changed while waiting for a response
            return self.__onResponseReceived(component, reqData['target_lang'], res)
        
        web.fetchURL(url, callback, '', 5, 'GET')

    def _createRequestData(self, authKey, message):
        langId = round( ui.getUserPrefs(SECTION_NAME, 'ttChatTargetLanguage', 6) )
        if langId in ID_TO_LANGUAGES:
            targetLang = ID_TO_LANGUAGES[langId]
        else:
            targetLang = ID_TO_LANGUAGES[6] # EN-GB
        return dict(
            auth_key        = authKey,
            target_lang     = targetLang,
            tag_handling    = 'html',
            text            = message
        )

    def __onResponseReceived(self, component, targetLang, res):
        message = self._parseResponse(component, targetLang, res)
        if message:
            self._createEntity(component, message)

    def _parseResponse(self, component, targetLang, res):
        if res and res.get('response') == 200:
            data = utils.jsonDecode(res['body'])
            tr = data['translations'][0]
            origLang = tr.get('detected_source_language', '?')
            text = tr.get('text')

            if origLang == targetLang or component.message == text:
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
        # is in same divison
        if myInfo.prebattleId > 0 and myInfo.prebattleId == senderInfo.prebattleId:
            prefPrefix = 'ttChatDiv'
        else:
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
        
        # `extraData` can be str for Scenario instructions/bot messages
        type = extraData.get('type', None) if extraData and isinstance(extraData, dict) else None
        
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