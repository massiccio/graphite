Extra collectors for Diamond, https://github.com/python-diamond/Diamond

Instructions for CentOS

- Place the collector in /usr/share/diamond/collectors
- Enable the collector by adding the following in /etc/diamond/diamond.conf

[[MySQLPerfSchemaCollector]]
enabled = True
hosts = root:@localhost:3306/Non

- Restart the Diamond daemon:
service diamond restart