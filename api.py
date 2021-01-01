#MEM

# UserInfo={}
# def GetUserInfo(uid):
#     global UserInfo
#     if not uid in UserInfo:
#         UserInfo[uid]=1000
#     return UserInfo[uid]

# def ChangeUserInfo(uid,mon):
#     global UserInfo
#     UserInfo[uid]+=mon

#SQLITE

import sqlite3

UserInfo={}

conn=sqlite3.connect("user.db")

conn.execute('''CREATE TABLE IF NOT EXISTS `user` (
 `uid` INT NOT NULL,
 `money` INT NOT NULL)''')
conn.commit()

##init

resa=conn.execute('''
SELECT * FROM `user`
''')

for i in resa:
    UserInfo[i[0]]=i[1]

def GetUserInfo(uid):
    global UserInfo
    if not uid in UserInfo:
        UserInfo[uid]=1000
        conn.execute('''
        INSERT INTO `user` VALUES(?,?)
        ''',(uid,1000))
        conn.commit()
    return UserInfo[uid]

def ChangeUserInfo(uid,mon):
    global UserInfo
    UserInfo[uid]+=mon
    if UserInfo[uid]>0:
        UserInfo[uid]%=(2**63)
    conn.execute('''
    UPDATE `user` set money=? where uid=?
    ''',(UserInfo[uid],uid))
    conn.commit()

