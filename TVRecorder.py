from mlibs.mhttp import HTTP
from mlibs.mjsonc import JsonCParser, JsonCArray, JsonCNode
from mlibs.mlogger import Logger

from time import time, sleep
import re # Regex
from sys import stderr
from datetime import datetime
from subprocess import Popen, PIPE
import os
from sys import platform


"""
    JSON Configue format:
    "<continion>":<value>
    Type of comparaison:
        date:
            "06/25/2020",
            "/25/2020",
            "//2020",
            "06//2020",
            "06/25",
            "06",
            {
                "dayofweek": <dayofweek comparaison or number comparaison>,
                "dayofmonth": <number comparaison>,
                "month": <month comparaison or number comparaison>,
                "year": <number comparaison>
            }
            {
                "min": "",
                "max": ""
            }
            ["","",""]
        dayofweek:
            "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
            "mon", "tue", "wed", "thu", "fri", "sat", "sun"
            0    , 1    , 2    , 3    , 4    , 5    , 6
        month:
            "january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"
            "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"
            0    , 1    , 2    , 3    , 4    , 5    , 6    , 7    , 8    , 9    , 10   , 11
        time:
            "12:30:59",
            ":30:59",
            "::59",
            "12::59",
            "12:30",
            "12",
            {
                "hour": <number comparaison>,
                "minute": <number comparaison>,
                "second": <number comparaison>
            }
            {
                "min": "",
                "max": ""
            }
            ["","",""]
        number:
            16,
            [4,3,57,21]
            {"min":13,"max":64}
        string:
            "test" (default is total)
            {"match":"regex","value":"/test/"}
            {"match":"ignorecase","value":"hELLo wOrlD !"}
            {"match":"total","value":"Total Match With Case"}
            {"match":"total","value":"Match words ignore case"}
        logicop:
            A list of conditions. Ex:
            "or":[
                {"contition1": "myvalue"},
                {"contition1": "myvalue2"},
                {"contition2": 16}
            ]
            Or a dict of conditions but can't have two same condition key. Ex:
            "or":{
                "contition1": "myvalue",
                "contition2": 16
            }

    List of conditions:
        "title": <string>
        "channel": <string> or <number>
        "channel_name": <string>
        "channel_shrtname": <string>
        "channel_number: <number>
        "date": <date>
        "time": <time>
        "timestamp": <number> (in seconds)
        "endtime": <time>
        "endtimestamp": <number> (in seconds)
        "subtitle": <string> 
        "episode": <number>
        "season": <number>
        "duration": <time>
        "or": <logicop>
        "nor": <logicop>
        "and": <logicop>
        "nand": <logicop>
        "xor": <logicop>
        "xnor": <logicop>

    "conditions" field has same properties than "and" condition

    Filename ('filename') placeholders:
        %default% : Work only on programe config part and refer to the default "filename" defined by "default": { ... } or by Python if not set
        %episode% : Episode number
        %season% : Season number
        %title% : Title
        %subtitle% : Sub-title
        %ext% : "ts"
    
    Record directory ('record_dir') placeholders:
        %default% : Work only on programe config part and refer to the default "record_dir" defined by "default": { ... } or by Python if not set
        %episode% : Episode number
        %season% : Season number
        %title% : Title
        %subtitle% : Sub-title

    Config file example:
    {
        "default":{
            "filename": "%title% - %subtitle%.%ext%",
            "record_dir": "D:/Perso/videos/",
            "replace_file": false,
            "ffmpeg": {
                "args": ["-c","copy","-copyts","-map","0","-b:v","900k","-r","60"],
                "path": "ffmpeg"
            }
        },

        "programs":[
            {
                "filename": "%title% - %subtitle% | ep%episode% s%season%.%ext%",
                "record_dir": "%default%/doctorwho",
                "replace_file": true,
                "ffmpeg": {
                    "args": ["-c","copy","-copyts","-map","0","-b:v","900k","-r","60","-y"]
                }

                "conditions":{
                    "or":{
                        "title":    {"match": "partial", "value":["Doctor Who","DoctorWho"]},
                        "subtitle": {"match": "partial", "value":["Doctor Who","DoctorWho"]}
                    }
                }
            },

            {
                "filename": "%title% - %subtitle%.%ext%",
                "record_dir": "%default%",

                "conditions":{
                    "channel": "TF1",
                    "time": {
                        "min": "19:50",
                        "max": "20:10"
                    }
                }
            }
        ]
    }
"""


# Setup logger
logger = Logger()
logger.useAsDefault()
logger.openFile("log.txt")
#logger.allowColor(True) # Force colors


def loads(data):
    parser = JsonCParser()
    parser.parse(data)
    parser.finialize()
    return parser.root


default_filename = "%title% - %subtitle%.%ext%"
default_record_dir = "./"
quality_weight = {'8k':6, '4k':5, 'hd':4, 'sd':3, 'ld':2, 'auto':1}

def error(msg, errcode=-1, fatal=True):
    print("Error: " + msg, file=stderr)
    if fatal: exit(errcode)

def frmtTime(timestamp):
    return datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")

def closeFFmpeg(process):
    if process.poll() == None:
        process.stdin.write(b'q')
        process.stdin.flush()
def startProcess(cmd, newconsole=False):
    if newconsole and platform == "win32":
        from subprocess import CREATE_NEW_CONSOLE
        return Popen(cmd, creationflags=CREATE_NEW_CONSOLE, stdin=PIPE)
    else:
        if platform == "win32": return Popen(cmd, stdin=PIPE)
        return Popen(cmd, stdin=PIPE, shell=True)


_str_seps = [' ','\t','\n','-',',',' ',':',';','/','\\','.','_','#','~','*','-','+','?','&','"','\'','`','|','{','}','(',')','[',']','@','=','§','!','?','$','%','^','<','>']
_str_rem = ['\r']
_str_repaccents = {}
# Voir le fichier "accents_dictionary.txt" dans "Text File" sur le Bureau


class ProgrameConds:
    def __init__(self, config, configparserclass):
        self.data = config
        self.conditions_conf = self.data['conditions'] if 'conditions' in self.data else []
        
        self.filename = config['filename'].replace("%default%", configparserclass.d_filename) if 'filename' in config else configparserclass.d_filename
        self.record_dir = config['record_dir'].replace("%default%", configparserclass.d_record_dir) if 'record_dir' in config else configparserclass.d_record_dir
        self.replace_file = config['replace_file'] if 'replace_file' in config else configparserclass.d_replace_file
        self.ffmpeg_path = configparserclass.d_ffmpeg_path
        self.ffmpeg_args = configparserclass.d_ffmpeg_args

        if 'ffmpeg' in config:
            ffmpeg_conf = config['ffmpeg']
            if 'path' in ffmpeg_conf: self.ffmpeg_path = ffmpeg_conf['path']
            if 'args' in ffmpeg_conf: self.ffmpeg_args = ffmpeg_conf['args']
        
    def processPlaceholders(self, pgrm):
        self.filename   = self.filename  .replace("%season%", str(pgrm['season'])).replace("%episode%", str(pgrm['episode'])).replace("%title%", str(pgrm['title'])).replace("%subtitle%", str(pgrm['subtitle'])).replace("%ext%",'ts')
        self.record_dir = self.record_dir.replace("%season%", str(pgrm['season'])).replace("%episode%", str(pgrm['episode'])).replace("%title%", str(pgrm['title'])).replace("%subtitle%", str(pgrm['subtitle']))
    
    def parseStrDate(self, strd):
        elems = strd.split('/')
        nbelems = len(elems)
        try:
            if nbelems == 1:
                return {"day": int(elems[0]) if (elems[0]!="") else None, "month": None, "year": None}
            elif nbelems == 2:
                return {"day": int(elems[0]) if (elems[0]!="") else None, "month": int(elems[1]) if (elems[1]!="") else None, "year": None}
            elif nbelems == 3:
                return {"day": int(elems[0]) if (elems[0]!="") else None, "month": int(elems[1]) if (elems[1]!="") else None, "year": int(elems[2]) if (elems[2]!="") else None}
            else:
                return None
        except ValueError:
            return None

    def parseStrTime(self, strt):
        elems = strt.split(':')
        nbelems = len(elems)
        try:
            if nbelems == 1:
                return {"hour": int(elems[0]) if (elems[0]!="") else None, "min": None, "sec": None}
            elif nbelems == 2:
                return {"hour": int(elems[0]) if (elems[0]!="") else None, "min": int(elems[1]) if (elems[1]!="") else None, "sec": None}
            elif nbelems == 3:
                return {"hour": int(elems[0]) if (elems[0]!="") else None, "min": int(elems[1]) if (elems[1]!="") else None, "sec": int(elems[2]) if (elems[2]!="") else None}
            else:
                return None
        except ValueError:
            return None

    def strCutToWords(self, a):
        last_is_sep = False
        tmpstr = ""
        words = []
        for c in a:
            if c in _str_seps:
                if not last_is_sep:
                    last_is_sep = True
                    words.append(tmpstr)
                    tmpstr = ""
            else:
                tmpstr += c
                last_is_sep = False
        if tmpstr != "": words.append(tmpstr)
        return words

    def strRemCharsets(self, a, char_list):
        out = ""
        for c in a:
            if not c in char_list: out += c
        return out
    
    def strRepCharsets(self, a, dic):
        out = ""
        for c in a:
            if c in dic: out += dic[c]
            else: out += c
        return out

    def cmpStrPartial(self, str1, str2):
        str2arr = str2 if type(str2) == JsonCArray else [str2]
        for s in str2arr:
            words1 = self.strCutToWords(self.strRepCharsets(self.strRemCharsets(str1.lower(), _str_rem), _str_repaccents))
            words2 = self.strCutToWords(self.strRepCharsets(self.strRemCharsets(   s.lower(), _str_rem), _str_repaccents))
            if len(words1) < 1 or len(words2) < 1: return False

            finded = True
            for word in words1:
                if not word in words2:
                    finded = False; break
            if finded: return True

            finded = True
            for word in words2:
                if not word in words1:
                    finded = False; break
            if finded: return True

        return False

    def cmpStrRegex(self, a, regex):
        regexarr = regex if type(regex) == JsonCArray else [regex]
        for r in regexarr:
            if re.compile(regex).match(a): return True
        return False

    def cmpStrIngnorecase(self, str1, str2):
        str2arr = str2 if type(str2) == JsonCArray else [str2]
        str1 = str1.lower()
        for s in str2arr:
            if str1 == s.lower(): return True
        return False
    
    def cmpTimeEqual(self, t1, t2):
        return (t1['hour']==t2['hour'] or t1['hour']==None or t2['hour']==None) and (t1['min']==t2['min'] or t1['min']==None or t2['min']==None) and (t1['sec']==t2['sec'] or t1['sec']==None or t2['sec']==None)
    def cmpTimeLowerEqual(self, t1, t2):
        return ( t1['hour']<=t2['hour']) or ((t1['hour']==t2['hour'] or t1['hour']==None or t2['hour']==None) and ( t1['min' ]<=t2['min' ] or ((t1['min' ]==t2['min' ] or t1['min' ]==None or t2['min' ]==None) and ( t1['sec' ]<=t2['sec' ] or t1['sec' ]==None or t2['sec' ]==None))))
    def cmpTimeUpperEqual(self, t1, t2):
        return ( t1['hour']>=t2['hour']) or ((t1['hour']==t2['hour'] or t1['hour']==None or t2['hour']==None) and ( t1['min' ]>=t2['min' ] or ((t1['min' ]==t2['min' ] or t1['min' ]==None or t2['min' ]==None) and ( t1['sec' ]>=t2['sec' ] or t1['sec' ]==None or t2['sec' ]==None))))

    def cmpDateEqual(self, d1, d2):
        return (d1['day']==d2['day'] or d1['day']==None or d2['day']==None) and (d1['month']==d2['month'] or d1['month']==None or d2['month']==None) and (d1['year']==d2['year'] or d1['year']==None or d2['year']==None)
    def cmpDateLowerEqual(self, d1, d2):
        return ( d1['year' ]<=d2['year' ]) or ((d1['year' ]==d2['year' ] or d1['year' ]==None or d2['year' ]==None) and ( d1['month']<=d2['month'] or ((d1['month']==d2['month'] or d1['month']==None or d2['month']==None) and ( d1['day'  ]<=d2['day'  ] or d1['day'  ]==None or d2['day'  ]==None))))
    def cmpDateUpperEqual(self, d1, d2):
        return ( d1['year' ]>=d2['year' ]) or ((d1['year' ]==d2['year' ] or d1['year' ]==None or d2['year' ]==None) and ( d1['month']>=d2['month'] or ((d1['month']==d2['month'] or d1['month']==None or d2['month']==None) and ( d1['day'  ]>=d2['day'  ] or d1['day'  ]==None or d2['day'  ]==None))))

    def conditionNumber(self, obj, v):
        t = type(obj)
        if t == int:
            return obj == v
        elif t == str and obj.lower() == "nan":
            return v == None
        elif t == JsonCArray:
            return v in t
        else:
            if 'min' in obj and v < obj['min']: return False
            if 'max' in obj and v > obj['max']: return False
            return True

    def conditionString(self, obj, v):
        t = type(obj)
        if t == str:
            return v == obj
        elif t == JsonCArray:
            return v in obj
        else:
            t = obj['match'].lower() if 'match' in obj else 'total'
            if   t == 'total': return v == obj['value']
            elif t == 'partial': return self.cmpStrPartial(v, obj['value'])
            elif t == 'ignorecase': return self.cmpStrIngnorecase(v, obj['value'])
            elif t == 'regex': return self.cmpStrRegex(v, obj['value'])

    def conditionTime(self, value, objdata):
        if type(value) == str:
            return self.cmpTimeEqual(objdata, self.parseStrTime(value))
        else:
            if 'min' in value:
                minv = value['min']
                if type(minv) == str:
                    if not self.cmpTimeUpperEqual(objdata, self.parseStrTime(minv)): return False
                else:
                    if not self.cmpTimeUpperEqual(objdata, minv): return False
            if 'max' in value:
                maxv = value['max']
                if type(maxv) == str:
                    if not self.cmpTimeLowerEqual(objdata, self.parseStrTime(maxv)): return False
                else:
                    if not self.cmpTimeLowerEqual(objdata, maxv): return False
            
            if 'hour' in value:
                if not self.conditionNumber(value['hour'], objdata['hour']): return False
            if 'minute' in value:
                if not self.conditionNumber(value['minute'], objdata['min']): return False
            if 'second' in value:
                if not self.conditionNumber(value['second'], objdata['sec']): return False
            
            return True

    def conditionDate(self, value, objdata):
        if type(value) == str:
            return self.cmpTimeEqual(objdata, self.parseStrDate(value))
        else:
            if 'min' in value:
                minv = value['min']
                if type(minv) == str:
                    if not self.cmpDateUpperEqual(objdata, self.parseStrDate(minv)): return False
                else:
                    if not self.cmpDateUpperEqual(objdata, minv): return False
            if 'max' in value:
                maxv = value['max']
                if type(maxv) == str:
                    if not self.cmpDateLowerEqual(objdata, self.parseStrDate(maxv)): return False
                else:
                    if not self.cmpDateLowerEqual(objdata, maxv): return False
            
            if 'day' in value:
                if not self.conditionNumber(value['day'], objdata['day']): return False
            if 'month' in value:
                if not self.conditionNumber(value['month'], objdata['month']): return False
            if 'year' in value:
                if not self.conditionNumber(value['year'], objdata['year']): return False
            
            return True


    def checkCondition(self, kl, value, objdata):
        if   kl == "or":
            if type(value) == JsonCArray:
                for e in value:
                    if self._checkConditionsOr(e, objdata): return True
                return False
            else: return self._checkConditionsOr(value, objdata)
        elif kl == "and":
            if type(value) == JsonCArray:
                for e in value:
                    if not self._checkConditionsAnd(e, objdata): return False
                return True
            else: return self._checkConditionsAnd(value, objdata)
        elif kl == "nor":
            if type(value) == JsonCArray:
                for e in value:
                    if self._checkConditionsNor(e, objdata): return False
                return True
            else: return self._checkConditionsNor(value, objdata)
        elif kl == "nand":
            if type(value) == JsonCArray:
                for e in value:
                    if not self._checkConditionsNand(e, objdata): return True
                return False
            else: return self._checkConditionsNand(value, objdata)
        elif kl == "xor":
            if type(value) == JsonCArray:
                c = 0
                for e in value:
                    c += self._checkConditionsXor(e, objdata)
                return c%2
            else: return self._checkConditionsXor(value, objdata)
        elif kl == "xnor":
            if type(value) == JsonCArray:
                c = 1
                for e in value:
                    c += self._checkConditionsXnor(e, objdata)
                return c%2
            else: return self._checkConditionsXnor(value, objdata)
        elif kl == "time":
            return self.conditionTime(value, objdata['time'])
        elif kl == "endtime":
            return self.conditionTime(value, objdata['endtime'])
        elif kl == "date":
            return self.conditionDate(value, objdata['date'])
        elif kl == "timestamp":
            return self.conditionNumber(value, objdata['timestamp'])
        elif kl == "endtimestamp":
            return self.conditionNumber(value, objdata['endtimestamp'])
        elif kl == "duration":
            return self.conditionTime(value, objdata['duration'])
        elif kl == "episode":
            return self.conditionNumber(value, objdata['episode'])
        elif kl == "season":
            return self.conditionNumber(value, objdata['season'])
        elif kl == "title":
            return self.conditionString(value, objdata['title'])
        elif kl == "subtitle":
            return self.conditionString(value, objdata['subtitle'])
        elif kl == "channel":
            if type(value) == int: return value == objdata['channel_number']
            else: return self.conditionString(value, objdata['channel_name'])
        elif kl == "channel_name":
            return self.conditionString(value, objdata['channel_name'])
        elif kl == "channel_number":
            return self.conditionNumber(value, objdata['channel_number'])
        elif kl == "channel_shrtname":
            return self.conditionString(value, objdata['channel_shrtname'])
        else:
            error("unknow condition \"" + kl + "\"", fatal=False)
            return None

    def _checkConditionsAnd(self, conditions, objdata):
        for k in conditions.keys():
            if not self.checkCondition(k.lower(), conditions[k], objdata): return False
        return True
    def _checkConditionsOr(self, conditions, objdata):
        for k in conditions.keys():
            if self.checkCondition(k.lower(), conditions[k], objdata): return True
        return False
    def _checkConditionsNand(self, conditions, objdata):
        for k in conditions.keys():
            if not self.checkCondition(k.lower(), conditions[k], objdata): return True
        return False
    def _checkConditionsNor(self, conditions, objdata):
        for k in conditions.keys():
            if self.checkCondition(k.lower(), conditions[k], objdata): return False
        return True
    def _checkConditionsXor(self, conditions, objdata):
        c = 0
        for k in conditions.keys():
            c += self.checkCondition(k.lower(), conditions[k], objdata)
        return c%2
    def _checkConditionsXnor(self, conditions, objdata):
        c = 1
        for k in conditions.keys():
            c += self.checkCondition(k.lower(), conditions[k], objdata)
        return c%2

    def checkConditions(self, objdata):
        if type(self.conditions_conf) == JsonCArray:
            for e in self.conditions_conf:
                if not self._checkConditionsAnd(e, objdata): return False
            return True
        elif type(self.conditions_conf) == JsonCNode:
            return self._checkConditionsAnd(self.conditions_conf, objdata)
        else:
            raise AttributeError("Invalide first argument (must be a dictionary or a list)")


class ConfigParser:
    def __init__(self, filename, fp=None):
        self.filename = filename

        if fp == None or fp.closed:
            fp = open(filename, "r")
            self.data = loads(fp.read())
            fp.close()
        else:
            self.data = loads(fp.read())
        
        self.d_filename = default_filename
        self.d_record_dir = default_record_dir
        self.d_replace_file = False
        self.d_ffmpeg_path = "ffmpeg"
        self.d_ffmpeg_args = []

        if 'default' in self.data:
            dflt = self.data['default']
            if 'filename' in dflt: self.d_filename = dflt['filename']
            if 'record_dir' in dflt: self.d_record_dir = dflt['record_dir']
            if 'replace_file' in dflt: self.d_replace_file = dflt['replace_file']
            if 'ffmpeg' in dflt:
                conf_ffmpeg = dflt['ffmpeg']
                if 'path' in conf_ffmpeg: self.d_ffmpeg_path = conf_ffmpeg['path']
                if 'args' in conf_ffmpeg: self.d_ffmpeg_args = conf_ffmpeg['args']
        
        self.programconds_list = []
        if 'programs' in self.data:
            for p in self.data['programs']:
                self.programconds_list.append( ProgrameConds(p, self) )

    def getDatas(self):
        return self.data
    
    def getProgramesDatas(self):
        return self.data["programes"]
    
    def getPrograms(self):
        return self.programconds_list

    def get(self, *path):
        last_data = self.data
        for p in path:
            if not p in last_data: return None
            last_data = last_data[p]
        return last_data
    
    def checkConditions(self, objdata):
        for pc in self.programconds_list:
            if pc.checkConditions(objdata): return pc
        return None


class FreeboxAPI:
    def __init__(self):
        self.baseurl = "http://192.168.1.254/api/v8/"
        self.http = HTTP()


    def getMillisTimestamp(self):
        return int(time()*1000)


    def getServices(self):
        rep = self.http.request(self.baseurl + "tv/bouquets/?_dc=" + str(self.getMillisTimestamp()))
        if rep["repcode"] != 200: return None
        data = loads(rep["body"].decode())
        if "success" in data and data["success"] == True and "result" in data:
            return data["result"]
        return None


    def getChannels(self):
        rep = self.http.request(self.baseurl + "tv/channels/")
        if rep["repcode"] != 200: return None
        data = loads(rep["body"].decode())

        if "success" in data and data["success"] == True and "result" in data:
            return data["result"]
        return None

    
    def getChannelsLocal(self, service_id=None):
        url = None
        if service_id == None:
            url = self.baseurl + "tv/bouquets/freeboxtv/channels/"
        else:
            url = self.baseurl + "tv/bouquets/" + str(service_id) + "/channels/?_dc=" + str(self.getMillisTimestamp())

        rep = self.http.request(url)
        if rep["repcode"] != 200: return None
        data = loads(rep["body"].decode())

        if "success" in data and data["success"] == True and "result" in data:
            return data["result"]
        return None

    def getChannelsURL(self, service_id=None):
        return self.getChannelsLocal(service_id)


    def getProgrames(self, channel_uuid=None, startdate=None):
        url = None

        if startdate == None:
            startdate = int(time())
            #startdate -= startdate % 3600

        if channel_uuid == None:
            url = self.baseurl + "tv/epg/by_time/" + str(startdate) + "/"
        else:
            url = self.baseurl + "tv/epg/by_channel/" + channel_uuid + "/" + str(startdate) + "/"

        rep = self.http.request(url)
        if rep["repcode"] != 200: return None
        data = loads(rep["body"].decode())

        if "success" in data and data["success"] == True and "result" in data:
            programes = []
            if channel_uuid == None:
                for chnlid, chnldata in data["result"].items():
                    for k, prgm in chnldata.items():
                        try:
                            programes.append({
                                "subtitle":prgm["sub_title"] if "sub_title" in prgm else None,
                                "id":prgm["id"],
                                "duration":prgm["duration"],
                                "desc":prgm["desc"] if "desc" in prgm else None,
                                "date":prgm["date"],
                                "category_name":prgm["category_name"] if "category_name" in prgm else None,
                                "title":prgm["title"],
                                "category":prgm["category"] if "category" in prgm else None,
                                "episode":prgm["episode_number"] if "episode_number" in prgm else None,
                                "season":prgm["season_number"] if "season_number" in prgm else None,
                                "channel_uuid": chnlid
                            })
                        except KeyError: pass
            else:
                for k, prgm in data["result"].items():
                    try:
                        programes.append({
                            "subtitle":prgm["sub_title"] if "sub_title" in prgm else None,
                            "id":prgm["id"],
                            "duration":prgm["duration"],
                            "desc":prgm["desc"] if "desc" in prgm else None,
                            "date":prgm["date"],
                            "category_name":prgm["category_name"] if "category_name" in prgm else None,
                            "title":prgm["title"],
                            "category":prgm["category"] if "category" in prgm else None,
                            "episode":prgm["episode_number"] if "episode_number" in prgm else None,
                            "season":prgm["season_number"] if "season_number" in prgm else None,
                            "channel_uuid": channel_uuid
                        })
                    except KeyError: pass
            #programes.sort(key=lambda x:x["date"])
            return programes
        return None


    def getProgrameInfos(self, programe_id):
        rep = self.http.request(self.baseurl + "tv/epg/programs/" + programe_id + "?_dc=" + str(self.getMillisTimestamp()))
        if rep["repcode"] != 200: return None
        data = loads(rep["body"].decode())
        if "success" in data and data["success"] == True and "result" in data:
            return data["result"]
        return None


# Global variables
checked_programes   = {}
channels_endtime    = {}
programes_to_record = []
events_list         = {}
channels_infos      = {}
records_to_stop     = []

# Constants
ID_UPDATE_CHANNEL   = 1
ID_REM_CHECKED_PGRM = 2
ID_START_RECORD     = 3
ID_STOP_RECORD      = 4

# Get channel name by id
def getChannelName(uuid):
    if uuid in channels_infos:
        return channels_infos[uuid]['name']
    else: return uuid

# Calculate the end time of each channel (the endtime of the last programe per channel)
def calcChannelsEndtime(pgrms):
    chnl_endtimes = {}
    curent_time = int(time())
    for p in pgrms:
        chnlid = p['channel_uuid']
        if not chnlid in chnl_endtimes: chnl_endtimes[chnlid] = 0
        et = p['date'] + p['duration']
        if et < curent_time: et = curent_time + 60
        if et > chnl_endtimes[chnlid]: chnl_endtimes[chnlid] = et
    return chnl_endtimes

# Start record of channel
def startRecord(url, endtime, args, output, replace_file, ffmpeg_path):
    outputdir = os.path.dirname(output)
    if not os.path.exists(outputdir) or not os.path.isdir(outputdir): os.makedirs(outputdir)

    if os.path.exists(output) and os.path.isfile(output) and replace_file == False:
        error("file \""+output+"\" already exist and replace_file is false!", fatal=False)
        return None

    args2 = ['"'+ffmpeg_path+'"', '-i', '"'+url+'"']
    args2.extend(args)
    if replace_file: args2.append('-y')
    args2.append('"'+output+'"')
    cmd = ' '.join(args2)
    print('\nExecute command: ' + cmd + '\n')
    return startProcess(cmd, newconsole=True)

# Add programe to record list
def addProgrameToRecord(pgrm, pgrmcond):
    print("Add programe to record: \"%s\" start %s end %s on channel \"%s\"" % (pgrm['title'], frmtTime(pgrm['date']), frmtTime(pgrm['date']+pgrm['duration']), getChannelName(pgrm['channel_uuid'])))

    pgrmcond.processPlaceholders(pgrm)
    output = os.path.normpath(os.path.join(pgrmcond.record_dir, pgrmcond.filename))

    global programes_to_record
    programes_to_record.append((pgrm['id'], pgrm['channel_uuid'], pgrm['date'], pgrm['date']+pgrm['duration'], pgrmcond.ffmpeg_args, output, pgrmcond.replace_file, pgrm['title'], pgrmcond.ffmpeg_path))

# Fore each the list of programe and try to find a condition that match a program
def checkProgrames(pgrms, config):
    global checked_programes

    nb_program_found = 0
    for pgrm in pgrms:
        if not pgrm['id'] in checked_programes:
            #print("Check program \""+(pgrm['title'] if 'title' in pgrm else 'unknow title')+"\"")
            # For each programme make a object "objdata"
            endtimestamp = pgrm['date']+pgrm['duration']
            if endtimestamp > time():
                dt_time = datetime.fromtimestamp(pgrm['date'])
                dt_endtime = datetime.fromtimestamp(endtimestamp)
                duration = pgrm['duration']

                objdata = {
                    'timestamp': pgrm['date'],
                    'endtimestamp': endtimestamp,
                    'title': pgrm['title'] if pgrm['title'] != None else "",
                    'subtitle': pgrm['subtitle'] if pgrm['subtitle'] != None else "",
                    'episode': pgrm['episode'],
                    'season': pgrm['season'],
                    'duration': {'timestamp':pgrm['duration'], 'sec':duration%60, 'min':(duration//60)%60, 'hour':duration//3600},
                    'time': {'hour':dt_time.hour, 'min':dt_time.minute, 'sec':dt_time.second},
                    'endtime': {'hour':dt_endtime.hour, 'min':dt_endtime.minute, 'sec':dt_endtime.second},
                    'date': {'day':dt_time.day, 'month':dt_time.month, 'year':dt_time.year}
                }

                if pgrm['channel_uuid'] in channels_infos:
                    chnl_infos = channels_infos[pgrm['channel_uuid']]
                    objdata['channel_name']     = chnl_infos['name']
                    objdata['channel_number']   = chnl_infos['number']
                    objdata['channel_shrtname'] = chnl_infos['shrtname']
                else:
                    objdata['channel_name']     = ""
                    objdata['channel_number']   = None
                    objdata['channel_shrtname'] = ""

                # For each conditions check if match
                pgrmcond = config.checkConditions(objdata)
                if pgrmcond != None:
                    addProgrameToRecord(pgrm, pgrmcond)
                    nb_program_found += 1
                
                checked_programes[ pgrm['id'] ] = endtimestamp
        #else: error("ID %s in checked_programes"%pgrm['id'], fatal=False)
    return nb_program_found

# Make all nessecary operation on the list of programe (i.e. checkProgrames, calcChannelsEndtime, nextCheckedProgrameToRem, nextProgrameToRecord, nextChannelToUpdate)
def processProgrameList(pgrms):
    global channels_endtime
    #print("Process program list:", pgrms, "\n")

    channels_endtime.update( calcChannelsEndtime(pgrms) )
    #print("channels_endtime: ", channels_endtime, "\n")
    indice = nextChannelToUpdate()
    eventSet(ID_UPDATE_CHANNEL, mainUpdateChannel, channels_endtime[indice]-30, indice)

    if checkProgrames(pgrms, recordconfig) > 0:
        indice = nextProgrameToRecord()
        eventSet(ID_START_RECORD, mainStartRecord, programes_to_record[indice][2]-30, indice)
    
    indice = nextCheckedProgrameToRem()
    if indice != None:
        eventSet(ID_REM_CHECKED_PGRM, mainRemCheckedPrograme, checked_programes[indice], indice)

# Check function to find the more closest action to do
def nextCheckedProgrameToRem():
    minv = None
    key = None
    for k, v in checked_programes.items():
        if minv == None or v < minv:
            minv = v
            key = k
    return key
def nextProgrameToRecord():
    minv = None
    indice = None
    i = 0
    for p in programes_to_record:
        if minv == None or p[3] < minv:
            minv = p[3]
            indice = i
        i += 1
    return indice
def nextRecordToStop():
    minv = None
    indice = None
    i = 0
    for r in records_to_stop:
        if minv == None or r[0] < minv:
            minv = r[0]
            indice = i
        i += 1
    return indice
def nextChannelToUpdate():
    minv = None
    key = None
    for k, v in channels_endtime.items():
        if minv == None or v < minv:
            minv = v
            key = k
    return key

# Function to manage asyncrone events
def eventSet(uid, func, timestamp, arg=None):
    global events_list
    events_list[uid] = (timestamp, func, arg)
    #print("eventSet("+str(uid)+", "+str(func)+", "+str(timestamp)+", "+str(arg)+")  time: "+datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")) # Debug print
def eventDel(uid):
    global events_list
    events_list.pop(uid)
def eventMainloop():
    global events_list
    while len(events_list):
        mint = None
        nexte = None
        nextuid = None
        for uid, e in events_list.items():
            if mint == None or e[0] < mint:
                mint = e[0]
                nexte = e
                nextuid = uid
        
        time_to_wait = mint - time()
        if time_to_wait > 0: sleep(time_to_wait)
        events_list.pop(nextuid)
        nexte[1](nexte[2])

# Main function called in event loop
def mainUpdateChannel(indice):
    print("Update channel: " + getChannelName(indice) + " ; time: " + datetime.fromtimestamp(channels_endtime[indice] + 30).strftime("%H:%M:%S"))
    pgrms = api.getProgrames(indice, channels_endtime[indice] + 30)
    channels_endtime.pop(indice)
    if pgrms == None: pgrms = []
    processProgrameList(pgrms)

def mainRemCheckedPrograme(indice):
    checked_programes.pop(indice)
    indice = nextCheckedProgrameToRem()
    eventSet(ID_REM_CHECKED_PGRM, mainRemCheckedPrograme, checked_programes[indice], indice)

def mainStartRecord(indice):
    pgrm = programes_to_record[indice]
    programes_to_record.pop(indice)

    endtime = pgrm[3] + 30
    #endtime = int(time()) + 20
    if endtime > time():
        url = channels_infos[pgrm[1]]['besturl']
        if url:
            print("Start record of \""+pgrm[7]+"\"")
            process = startRecord(url, endtime, pgrm[4], pgrm[5], pgrm[6], pgrm[8])
            if process:
                records_to_stop.append((endtime, process, pgrm[7]))
                indice = nextRecordToStop()
                eventSet(ID_STOP_RECORD, mainStopRecord, records_to_stop[indice][0], indice)
                sleep(16)
            else: error("failed to start record for channel \""+(channels_infos[pgrm[1]]['name'] if pgrm[1] in channels_infos else pgrm[1])+"\"", fatal=False)
        else: error("no streaming url for channel \""+(channels_infos[pgrm[1]]['name'] if pgrm[1] in channels_infos else pgrm[1])+"\"", fatal=False)

    indice = nextProgrameToRecord()
    if indice != None:
        eventSet(ID_START_RECORD, mainStartRecord, programes_to_record[indice][2]-30, indice)

def mainStopRecord(indice):
    closeFFmpeg(records_to_stop[indice][1])
    print("Stop record of \""+records_to_stop[indice][2]+"\"")
    records_to_stop.pop(indice)

    indice = nextRecordToStop()
    if indice != None:
        eventSet(ID_STOP_RECORD, mainStopRecord, records_to_stop[indice][0], indice)


# Load configuration file
print("Load config\n")
recordconfig = ConfigParser("recordconfig.json")

api = FreeboxAPI()

# Create channel infos dictionary
global_channels = api.getChannels()
local_channels = api.getChannelsLocal()

for chnl in local_channels:
    global_channel = global_channels[chnl["uuid"]]
    besturl = None
    urls = {}
    if 'streams' in chnl:
        bestq = -1
        for s in chnl['streams']:
            q = quality_weight[s['quality']]
            urls[q] = s['rtsp']
            if q > bestq:
                bestq = q
                besturl = s['rtsp']
    channels_infos[chnl["uuid"]] = {'number': chnl['number'], 'shrtname': global_channel['short_name'], 'name': global_channel['name'], 'besturl': besturl, 'urls':urls}


pgrms = api.getProgrames()
if pgrms: processProgrameList(pgrms)

try:
    eventMainloop()
except KeyboardInterrupt:
    pass


# Stop all running records
for r in records_to_stop:
    closeFFmpeg(r[1])
    print("Stop record of \""+r[2]+"\"")


print("\nFinish program")
