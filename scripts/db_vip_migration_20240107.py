import sqlite3
import json
import datetime
conn = sqlite3.connect('../bfchat_data/bot.db')

cur = conn.cursor()
old_vips = conn.execute('SELECT * FROM servervips').fetchall()
with open('../bfchat_data/vip_copy.json', 'w') as f:
    json.dump(old_vips, f)
conn.execute('DROP TABLE servervips')
conn.execute("""
CREATE TABLE servervips (
	serverid INTEGER NOT NULL, 
	pid BIGINT NOT NULL, 
	originid VARCHAR,
    days INTEGER,
    permanent BOOLEAN NOT NULL,
    start_date DATETIME,
	enabled BOOLEAN NOT NULL, 
    priority INTEGER NOT NULL,
	PRIMARY KEY (serverid, pid), 
	FOREIGN KEY(serverid) REFERENCES servers (serverid)
)
""")
for vip in old_vips:
    expire = datetime.datetime.fromisoformat(vip[3])
    days = max((expire - datetime.datetime.now()).days, 0)
    conn.execute('INSERT INTO servervips (serverid, pid, originid, days, permanent, start_date, enabled, priority) VALUES (?, ?, ?, ?, ?, ?, ?, ?);',
                 [vip[0], vip[1], vip[2], days, days>=3650, datetime.datetime.now(), vip[4], 1])
cur.connection.commit()
cur.close()