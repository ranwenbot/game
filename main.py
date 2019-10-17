from config import BOTNAME,BOTTOKEN,DEBUG,PROXY,PY

from api import GetUserInfo,ChangeUserInfo

import requests
reqChange=requests.Session()
reqSender=requests.Session()
reqUpdater=requests.Session()
reqCallback=requests.Session()
req=requests.Session()
if len(PROXY)>0:
    reqChange.proxies={"http":PROXY,"https":PROXY}
    reqSender.proxies={"http":PROXY,"https":PROXY}
    reqUpdater.proxies={"http":PROXY,"https":PROXY}
    reqCallback.proxies={"http":PROXY,"https":PROXY}
    req.proxies={"http":PROXY,"https":PROXY}

import time
import threading
import json
import re


if DEBUG:
    import sys
    import traceback


HELPMESSAGE='''帮助
/help 帮助
/blackjack 21点
/horse 赛马
/dice 骰子
/bet 金额|百分比|sh 下注(不支持小数)
例: /bet 10 或 /bet 10%
'''



def MakeRequest(method,data="",robj=req):
    if data=="":
        r=robj.get("https://api.telegram.org/bot"+BOTTOKEN+"/"+method)
    else:
        r=robj.post("https://api.telegram.org/bot"+BOTTOKEN+"/"+method,data=data)
    resans=json.loads(r.text)
    if resans["ok"]!=True:
        logger.error(r.text)
    return resans



import logging
logging.basicConfig(level = logging.ERROR,format = '[%(asctime)s][%(levelname)s]: %(message)s')
#logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger()


# Telegram Bot

ChangeQueue=[]
ChangeLock=threading.Lock()
def ServiceChange():
    global ChangeQueue
    try:
        f=open("BotUpdateID")
        LastID=int(f.read())
        f.close()
    except:
        LastID=0
    while True:
        try:
            res=MakeRequest("getUpdates",{"offset":str(LastID+1),"allowed_updates":"[\"message\",\"callback_query\"]","timeout":10},robj=reqChange)
            if DEBUG:
                print("MKREQ ",res)
            if res["ok"]==True:
                #print(res)
                lis=res["result"]
                ChangeLock.acquire()
                ChangeQueue=ChangeQueue+lis
                ChangeLock.release()
                if len(lis)>0:
                    LastID=lis[-1]["update_id"]
                    f=open("BotUpdateID","w")
                    f.write(str(LastID))
                    f.close()
        except:
            logger.error("Change")
        time.sleep(0.2)

SenderQueue=[]
SenderLock=threading.Lock()
SendReqIDMap={}
SendReqIDTot=-1
def ServiceSender():#TODO: rate limit
    global SenderQueue,SendReqIDMap
    while True:
        try:
            sttime=time.time()
            SenderLock.acquire()
            todolis=SenderQueue*1
            SenderQueue.clear()
            SenderLock.release()
            for it in todolis:
                resarr={"text":it["text"],"chat_id":it["chat_id"]}
                if "reply_markup" in it:
                    resarr["reply_markup"]=json.dumps(it["reply_markup"])
                if "reply_to_message_id" in it:
                    resarr["reply_to_message_id"]=it["reply_to_message_id"]
                #print(resarr)
                ret=MakeRequest("sendMessage",resarr,robj=reqSender)
                if "reqid" in it:
                    SendReqIDMap[it["reqid"]]=ret["result"]["message_id"]
                if DEBUG:
                    print("SEND ",resarr)
            edtime=time.time()
            net=max(0.1-edtime+sttime,0)
            time.sleep(net)
        except:
            logger.error("Sender")
            time.sleep(0.1)

UpdaterQueue=[]
UpdaterLock=threading.Lock()
def ServiceUpdater():#TODO: merge & rate limit
    global UpdaterQueue
    while True:
        try:
            sttime=time.time()
            UpdaterLock.acquire()
            todolis=UpdaterQueue*1
            UpdaterQueue.clear()
            UpdaterLock.release()
            for it in todolis:
                resarr={"text":it["text"],"chat_id":it["chat_id"],"message_id":it["message_id"]}
                if "reply_markup" in it:
                    resarr["reply_markup"]=json.dumps(it["reply_markup"])
                MakeRequest("editMessageText",resarr,robj=reqUpdater)
            edtime=time.time()
            net=max(0.1-edtime+sttime,0)
            time.sleep(net)
        except:
            logger.error("Updater")
            time.sleep(0.1)

CallbackQueue=[]
CallbackLock=threading.Lock()
def ServiceCallback():#TODO: merge
    global CallbackQueue
    while True:
        try:
            sttime=time.time()
            CallbackLock.acquire()
            todolis=CallbackQueue*1
            CallbackQueue.clear()
            CallbackLock.release()
            for it in todolis:
                resarr={"callback_query_id":it["id"]}
                if "text" in it:
                    resarr["text"]=it["text"]
                if "alert" in it:
                    resarr["show_alert"]=it["alert"]
                MakeRequest("answerCallbackQuery",resarr,robj=reqUpdater)
            edtime=time.time()
            net=max(0.1-edtime+sttime,0)
            time.sleep(net)
        except:
            logger.error("Callback")
            time.sleep(0.1)

def GetChange():
    global ChangeQueue
    ChangeLock.acquire()
    ret=ChangeQueue*1
    ChangeQueue.clear()
    ChangeLock.release()
    return ret

def SendMessage(text,chatid,reply=0,button={},reqid=0):
    global SenderQueue
    obj={"text":text,"chat_id":chatid}
    if len(button)!=0:
        obj["reply_markup"]=button
    if reply!=0:
        obj["reply_to_message_id"]=reply
    if reqid!=0:
        obj["reqid"]=reqid
    SenderLock.acquire()
    SenderQueue.append(obj)
    SenderLock.release()

def UpdateMessage(text,chatid,messid,button={}):
    global UpdaterQueue
    obj={"text":text,"chat_id":chatid,"message_id":messid}
    if len(button)!=0:
        obj["reply_markup"]=button
    UpdaterLock.acquire()
    flag=False
    for i in UpdaterQueue:
        if i["chat_id"]==chatid and i["message_id"]==messid:
            flag=True
            i["text"]=text
            if len(button)!=0:
                i["reply_markup"]=button
            elif "reply_markup" in i:
                i.pop("reply_markup")
            flag=True
    if not flag:
        UpdaterQueue.append(obj)
    UpdaterLock.release()

def AnswerCallback(callbackid,text="",isalert=False):
    global CallbackQueue
    obj={"id":callbackid}
    if len(text)!=0:
        obj["text"]=text
    if isalert:
        obj["alert"]=True
    CallbackLock.acquire()
    CallbackQueue.append(obj)
    CallbackLock.release()


ObjThreadServiceChange=threading.Thread(target=ServiceChange)
ObjThreadServiceChange.start()
ObjThreadServiceSender=threading.Thread(target=ServiceSender)
ObjThreadServiceSender.start()
ObjThreadServiceUpdater=threading.Thread(target=ServiceUpdater)
ObjThreadServiceUpdater.start()
ObjThreadServiceCallback=threading.Thread(target=ServiceCallback)
ObjThreadServiceCallback.start()



# Bot end

# Game Obj
class GameDiceObj(object):
    def __init__(self,userlist):
        self.player=userlist
        self.playerst={}
        for i in userlist:
            self.playerst[i]=0#0:pending 1:xiao 2:da 3:wei
        self.NeedUpdate=True
        self.NeedEnd=False
        self.lastime=time.time()
    
    def GenMess(self):
        info=["?","小","大","围"]
        mess="骰子"
        for i in self.player:
            mess+="\n"+self.player[i]["name"]+"("+str(self.player[i]["money"])+"): "+info[self.playerst[i]]
        return mess

    def GenButton(self,chatid):
        return [[{"text":"小","callback_data":str(chatid)+"+s"},
    {"text":"围","callback_data":str(chatid)+"+m"},
    {"text":"大","callback_data":str(chatid)+"+l"}
    ],
    [{"text":"强制结束","callback_data":str(chatid)+"+E"}]]

    def UserCmd(self,uid,action):
        if action=="E":
            if time.time()-self.lastime>15:
                self.NeedEnd=True
            return
        if self.NeedEnd:
            return
        if not uid in self.player:
            return
        if self.playerst[uid]!=0:
            return
        self.NeedUpdate=True
        if action=="s":
            self.playerst[uid]=1
        elif action=="l":
            self.playerst[uid]=2
        else:
            self.playerst[uid]=3
        self.lastime=time.time()
        return
    
    def NextTick(self):
        sfg=True
        for i in self.playerst:
            if self.playerst[i]==0:
                sfg=False
        self.NeedEnd|=sfg
    
    def EndGame(self):
        info=["?","小","大","围"]
        res=[]
        rdl=__import__("random")
        res.append(rdl.randint(1,6))
        res.append(rdl.randint(1,6))
        res.append(rdl.randint(1,6))
        typ=1
        if res[0]==res[1] and res[1]==res[2]:
            typ=3
        elif sum(res)>=11:
            typ=2
        mess="骰子"
        mess+="\n🎲"+str(res[0])+" 🎲"+str(res[1])+" 🎲"+str(res[2])
        user={}
        for i in self.player:
            ob={"mess":info[self.playerst[i]]}
            if self.playerst[i]==0:
                ob["money"]=self.player[i]["money"]
            elif self.playerst[i]==typ:
                ob["money"]=self.player[i]["money"]*2
                if typ==3:
                    ob["money"]=self.player[i]["money"]*24
            else:
                ob["money"]=0
            user[i]=ob
        return (mess,user)


class GameHorseObj(object):
    def __init__(self,userlist):
        self.player=userlist
        self.playerst={}
        self.horsest={}#(dis,st)
        for i in userlist:
            self.playerst[i]=0#ma id
        self.NeedUpdate=True
        self.NeedEnd=False
        self.lastime=time.time()
        self.status=0#0xuanma 1jiesuan
        self.NeedStart=False
        self.rdlib=__import__("random").SystemRandom()
        self.sm={}
    
    def GenMess(self):
        info="?------"
        if self.status==0:
            mess="选马"
            for i in self.player:
                mess+="\n"+self.player[i]["name"]+"("+str(self.player[i]["money"])+"): 🐴"+info[self.playerst[i]]
            return mess
        else:
            mst=["🏇","☠️","🐎"]
            mess="赛马"
            for i in self.horsest:
                tx=" "*max(50-self.horsest[i][0],0)
                tx+=mst[self.horsest[i][1]]
                tx+=str(i)
                mess+="\n"+tx
            return mess

    def GenButton(self,chatid):
        if self.status==0:
            return [[{"text":"🐴1","callback_data":str(chatid)+"+1"},
                    {"text":"🐴2","callback_data":str(chatid)+"+2"},
                    {"text":"🐴3","callback_data":str(chatid)+"+3"}
                    ],
                    [{"text":"🐴4","callback_data":str(chatid)+"+4"},
                    {"text":"🐴5","callback_data":str(chatid)+"+5"},
                    {"text":"🐴6","callback_data":str(chatid)+"+6"}
                    ],
                    [{"text":"强制开始","callback_data":str(chatid)+"+E"}]]
        else:
            return [[{"text":"火箭加速","callback_data":str(chatid)+"+H"},
                    {"text":"快马加鞭","callback_data":str(chatid)+"+B"}
                    ]]

    def UserCmd(self,uid,action):
        mst="马死摔"
        if action=="E":
            if time.time()-self.lastime>15:
                self.NeedStart=True
            return
        if not uid in self.player:
            return
        if self.status==0:
            if self.playerst[uid]!=0:
                return
            if not re.match("^[1-6]$",action):
                return
            self.NeedUpdate=True
            self.playerst[uid]=int(action)
            self.lastime=time.time()
            fafa=True
            for i in self.playerst:
                if self.playerst[i]==0:
                    fafa=False
            self.NeedStart|=fafa
        else:
            maid=self.playerst[uid]
            if maid==0:
                return
            if self.horsest[maid][1]!=0:
                return ("你🐴"+mst[self.horsest[maid][1]]+"了",True)
            if action=='H':
                dis=min(50,16+self.horsest[maid][0])
                ff=self.rdlib.randint(0,1)
                gst=0
                if ff==1:
                    gst=1
                self.horsest[maid]=(dis,gst)
            if action=='B':
                dis=min(50,8+self.horsest[maid][0])
                ff=self.rdlib.randint(0,2)
                gst=0
                if ff==2:
                    gst=2
                self.horsest[maid]=(dis,gst)
            return
        return
    
    def NextTick(self):
        if self.status==0:
            if self.NeedStart==False:
                return
            for i in range(1,7):
                self.horsest[i]=(0,0)
                self.sm[i]=0
            self.status=1
            return
        else:
            self.NeedUpdate=True
            for i in self.horsest:
                if self.horsest[i][1]==0:
                    dis=self.rdlib.randint(3,6)
                    dis=min(50,dis+self.horsest[i][0])
                    self.horsest[i]=(dis,self.horsest[i][1])
                    self.sm[i]=0
                    if dis==50:
                        self.NeedEnd=True
                elif self.horsest[i][1]==2:
                    self.sm[i]+=1
                    if self.sm[i]==5:
                        self.horsest[i]=(self.horsest[i][0],0)
            return
    
    def EndGame(self):
        mess="赛马"
        mst=["🏇","☠️","🐎"]
        info="?123456"
        for i in self.horsest:
            tx=" "*max(50-self.horsest[i][0],0)
            tx+=mst[self.horsest[i][1]]
            tx+=str(i)
            mess+="\n"+tx
        user={}
        for i in self.player:
            ob={"mess":"🐴"+info[self.playerst[i]]}
            if self.playerst[i]==0:
                ob["money"]=self.player[i]["money"]
            elif self.horsest[self.playerst[i]][0]==50 and self.horsest[self.playerst[i]][1]==0:
                ob["money"]=self.player[i]["money"]*2
            else:
                ob["money"]=0
            user[i]=ob
        return (mess,user)


class GameBlackJackObj(object):
    def __init__(self,userlist):
        self.vall=[0,1,2,3,4,5,6,7,8,9,10,10,10,10]
        self.Redst=["x","A","2","3","4","5","6","7","8","9","10","J","Q","K"]
        self.player=userlist
        self.playerst={}
        self.playerok={}
        self.NeedUpdate=True
        self.NeedEnd=False
        self.lastime=time.time()
        self.rdlib=__import__("random").SystemRandom()
        self.zjst=[self.rdlib.randint(1,13),self.rdlib.randint(1,13)]
        while self.cal(self.zjst)[1]<17:
            self.zjst.append(self.rdlib.randint(1,13))
        for i in userlist:
            self.playerst[i]=[self.rdlib.randint(1,13),self.rdlib.randint(1,13)]
            self.playerok[i]=0
            if self.cal(self.playerst[i])[1]==21:
                self.playerok[i]=2
    
    def cal(self,arr):
        ret=[0,0]
        for i in arr:
            ret[1]+=self.vall[i]
            if i==1:
                ret[0]+=1
        if ret[1]<=11 and ret[0]>0:
            ret[1]+=10
        return tuple(ret)

    def arr2str(self,arr):
        st=""
        for i in arr:
            st+=self.Redst[i]+" "
        return st

    def GenMess(self):
        mess="21点"
        sta=["未完成","已完成","黑杰克","爆炸"]
        mess+="\n庄家: "+self.Redst[self.zjst[0]]+" "+self.Redst[self.zjst[1]]
        for i in self.player:
            mess+="\n"+self.player[i]["name"]+"("+str(self.player[i]["money"])+"): "+self.arr2str(self.playerst[i])+sta[self.playerok[i]]
        return mess

    def GenButton(self,chatid):
        return [[{"text":"要牌","callback_data":str(chatid)+"+Y"},
                {"text":"完成","callback_data":str(chatid)+"+N"}
                ],
                [{"text":"强制结束","callback_data":str(chatid)+"+E"}]]

    def UserCmd(self,uid,action):
        if action=="E":
            if time.time()-self.lastime>15:
                self.NeedEnd=True
            return
        if self.NeedEnd:
            return
        if not uid in self.player:
            return
        if self.playerok[uid]!=0:
            return
        if action=='Y':
            self.playerst[uid].append(self.rdlib.randint(1,13))
            cc=self.cal(self.playerst[uid])
            if cc[1]>21:
                self.playerok[uid]=3
        if action=='N':
            self.playerok[uid]=1
        self.NeedUpdate=True
        self.lastime=time.time()
        return
    
    def NextTick(self):
        nmsl=True
        for i in self.playerok:
            if self.playerok[i]==0:
                nmsl=False
        self.NeedEnd|=nmsl
        return
    
    def EndGame(self):
        mess="21点"
        sta=["失败","胜利","黑杰克","爆炸","平局"]
        mess+="\n庄家: "+self.arr2str(self.zjst)
        user={}
        zjd=self.cal(self.zjst)
        for i in self.player:
            ob={"mess":self.arr2str(self.playerst[i])}
            nmsl=self.playerok[i]
            if self.playerok[i]==3:
                ob["money"]=0
            elif self.playerok[i]==2:
                ob["money"]=int(self.player[i]["money"]*2.5)
            else:
                if zjd[1]>21 or self.cal(self.playerst[i])[1]>zjd[1]:
                    ob["money"]=self.player[i]["money"]*2
                    nmsl=1
                elif self.cal(self.playerst[i])[1]==zjd[1]:
                    ob["money"]=self.player[i]["money"]
                    nmsl=4
                else:
                    ob["money"]=0
                    nmsl=0
            ob["mess"]+=sta[nmsl]
            user[i]=ob
        return (mess,user)


GameObjList={
    "dice":{"cmd":"/dice","obj":GameDiceObj,"name":"骰子"},
    "horse":{"cmd":"/horse","obj":GameHorseObj,"name":"赛马"},
    "blackjack":{"cmd":"/blackjack","obj":GameBlackJackObj,"name":"21点"}
}

Cmd2Game={}
for i in GameObjList:
    Cmd2Game[GameObjList[i]["cmd"]]=i

# Game end

def GenBetButton(chatid):
    return [[{"text":"5","callback_data":str(chatid)+"+X5"},
    {"text":"10","callback_data":str(chatid)+"+X10"},
    {"text":"50","callback_data":str(chatid)+"+X50"},
    {"text":"50%","callback_data":str(chatid)+"+X50%"},
    {"text":"sh","callback_data":str(chatid)+"+Xsh"}
    ],
    [{"text":"Start","callback_data":str(chatid)+"+S"},{"text":"余额","callback_data":str(chatid)+"+M"}]]

AliveGame={}

def DoBet(userobj,chatid,st):
    uid=userobj["id"]
    global AliveGame,UserInfo,SendReqIDMap
    if st=="sh":
        st=str(GetUserInfo(uid))
    if re.match("(^[1-9][0-9]{0,1}%$|^100%$)",st):
        fa=int(int(st[:-1])/100.0*GetUserInfo(uid))
        st=str(fa)
    if not re.match("^[1-9][0-9]*$",st):
        return (-1,"无法识别投注金额")
    if not chatid in AliveGame:
        return (-1,"无进行中游戏")
    if not AliveGame[chatid]["status"]==0:
        return (-1,"游戏状态错误")
    mon=int(st)
    if mon>GetUserInfo(uid):
        return (-1,"余额不足")
    ChangeUserInfo(uid,-mon)
    if not uid in AliveGame[chatid]["player"]:
        AliveGame[chatid]["player"][uid]={"money":0,"name":userobj["first_name"]}
    AliveGame[chatid]["player"][uid]["money"]+=mon
    if AliveGame[chatid]["messid"]<0:
        sbsb=AliveGame[chatid]["messid"]
        if not sbsb in SendReqIDMap:
            return (-1,"消息未发出")
        AliveGame[chatid]["messid"]=SendReqIDMap[AliveGame[chatid]["messid"]]
        SendReqIDMap.pop(sbsb)
    typ=AliveGame[chatid]["typ"]
    mess=GameObjList[typ]["name"]+"\n玩家"
    for i in AliveGame[chatid]["player"]:
        mess+="\n"+AliveGame[chatid]["player"][i]["name"]+": "+str(AliveGame[chatid]["player"][i]["money"])+"("+str(GetUserInfo(i))+")"
    UpdateMessage(mess,chatid,AliveGame[chatid]["messid"],button={"inline_keyboard":GenBetButton(chatid)})
    return (0,"下注成功")
    
def StartGame(chatid,typ):
    global AliveGame,SendReqIDTot
    if chatid in AliveGame:
        SendMessage("上一局游戏还未结束 无法新建",chatid)
        return
    obj={"typ":typ,"player":{},"status":0,"messid":SendReqIDTot}
    AliveGame[chatid]=obj
    SendMessage(GameObjList[typ]["name"],chatid,button={"inline_keyboard":GenBetButton(chatid)},reqid=SendReqIDTot)
    SendReqIDTot-=1
    return

def EndGame(chatid):
    global AliveGame
    (mess,chang)=AliveGame[chatid]["game"].EndGame()
    AliveGame[chatid]["game"].NeedUpdate=False
    #player
    for i in chang:
        ChangeUserInfo(i,chang[i]["money"])
        usm=GetUserInfo(i)
        mess+="\n"+AliveGame[chatid]["player"][i]["name"]+"("+str(AliveGame[chatid]["player"][i]["money"])+"): "+chang[i]["mess"]+" +"+str(chang[i]["money"])+"("+str(usm)+")"
    UpdateMessage(mess,chatid,AliveGame[chatid]["messid"])
    return

def UpdateGame(chatid):
    AliveGame[chatid]["game"].NeedUpdate=False
    mess=AliveGame[chatid]["game"].GenMess()
    but={"inline_keyboard":AliveGame[chatid]["game"].GenButton(chatid)}
    UpdateMessage(mess,chatid,AliveGame[chatid]["messid"],button=but)
    return

def DoCommand(obj):
    if not "text" in obj:
        return
    txt=obj["text"]
    if len(txt)<1 or txt[0]!='/':
        return
    cmdall=txt.split(' ')
    cmd=cmdall[0]
    if cmd.find("@")!=-1:
        botname=cmd[cmd.find("@"):]
        if botname!="@"+BOTNAME:
            return
        cmd=cmd.replace("@"+BOTNAME,"")
    
    if cmd=="/help" or cmd=="/start":
        SendMessage(HELPMESSAGE,obj["chat"]["id"])
    if cmd in Cmd2Game:
        StartGame(obj["chat"]["id"],Cmd2Game[cmd])
    if cmd=="/bet":
        if len(cmdall)>1:
            res=DoBet(obj["from"],obj["chat"]["id"],cmdall[1])
            if res[0]==0:
                retx="成功 "
            else:
                retx="错误 "
            retx+=res[1]
            SendMessage(retx,obj["chat"]["id"],reply=obj["message_id"])
    if cmd=='/del':
        global AliveGame
        if obj["chat"]["id"] in AliveGame:
            AliveGame.pop(obj["chat"]["id"])
            SendMessage("已重置",obj["chat"]["id"])
    
    if PY:
        if cmd=='/py':
            mm=__import__("random").randint(-100,1000)
            GetUserInfo(obj["from"]["id"])
            ChangeUserInfo(obj["from"]["id"],mm)
            SendMessage("pyed: "+str(mm),obj["chat"]["id"],reply=obj["message_id"])
    return

def DoButton(obj):
    global AliveGame
    if (not "data" in obj) or len(obj["data"])<1:
        return
    dat=obj["data"].split('+')
    if len(dat)<2 or (not re.match("^[-]*[1-9][0-9]*$",dat[0])):
        AnswerCallback(obj["id"],"非法请求")
        return
    cid=int(dat[0])
    if not cid in AliveGame:
        AnswerCallback(obj["id"],"无进行中的游戏")
        return
    txt=dat[1]
    if AliveGame[cid]["status"]==0:
        if txt[0]=='X':
            res=DoBet(obj["from"],cid,txt[1:])
            sta=False
            if res[0]==0:
                retx="成功 "
            else:
                retx="错误 "
                sta=True
            retx+=res[1]
            AnswerCallback(obj["id"],retx,isalert=sta)
        elif txt[0]=='M':
            AnswerCallback(obj["id"],"余额: "+str(GetUserInfo(obj["from"]["id"])),isalert=True)
        elif txt[0]=='S':
            AliveGame[cid]["game"]=GameObjList[AliveGame[cid]["typ"]]["obj"](AliveGame[cid]["player"])
            AliveGame[cid]["status"]=1
            AnswerCallback(obj["id"])
    else:
        ret=AliveGame[cid]["game"].UserCmd(obj["from"]["id"],txt)
        if ret is None:
            AnswerCallback(obj["id"])
        else:
            AnswerCallback(obj["id"],ret[0],ret[1])
    return

def DoChange(cz):
    if "message" in cz:
        DoCommand(cz["message"])
    elif "callback_query" in cz:
        DoButton(cz["callback_query"])
    return


def ThErr():
    ex_type, ex_val, ex_stack = sys.exc_info()
    print(ex_type)
    print(ex_val)
    for stack in traceback.extract_tb(ex_stack):
        print(stack)

#main


while True:
    sttime=time.time()
    ch=GetChange()
    #print(ch)
    for cz in ch:
        DoChange(cz)
    nend=[]
    for i in AliveGame:
        if "game" in AliveGame[i]:
            try:
                AliveGame[i]["game"].NextTick()
                if AliveGame[i]["game"].NeedEnd:
                    EndGame(i)
                    nend.append(i)
                if AliveGame[i]["game"].NeedUpdate:
                    UpdateGame(i)
            except:
                logger.error("Update Game")
                if DEBUG:
                    ThErr()
    for i in nend:
        AliveGame.pop(i)
    edtime=time.time()
    if DEBUG:
        print(edtime-sttime)
    net=max(2-edtime+sttime,0)
    time.sleep(net)
