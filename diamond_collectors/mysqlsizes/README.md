Extra collectors for Diamond, https://github.com/python-diamond/Diamond

Instructions for CentOS

- Place the collector in /usr/share/diamond/collectors
- Enable the collector by adding the following in /etc/diamond/diamond.conf

[[MySQLSizeCollector]]
enabled = True
# no need to gather statistics more frequently
interval = 600
host = localhost
user = stats
password = stats
path_prefix = mysql

- Restart the Diamond daemon:
service diamond restart
