Extra collectors for Diamond, https://github.com/python-diamond/Diamond

Instructions for CentOS

- Place the collector in /usr/share/diamond/collectors
- Enable the collector by adding the following in /etc/diamond/diamond.conf

``` bash
[[MySQLSizeCollector]]
enabled = True
interval = 600 # no need to gather statistics more frequently
host = localhost
user = stats
password = stats
path_prefix = mysql
```

- Restart the Diamond daemon:
``` bash
service diamond restart
```
