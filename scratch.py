import sqlite3

conn = sqlite3.connect('server/data/cmp.db')
c = conn.cursor()
c.execute("SELECT sensor_id, hostname, mac_address FROM sensors")
for row in c.fetchall():
    print(row)
conn.close()
