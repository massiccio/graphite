# Setup of Graphite and Diamond

Environment: CentOS 6.8
Metrics to be sent to port TCP 2003

Requirements and notes:
- All commands require super user privileges  
- Ensure that iptables is disabled or that the appropriate firewall rules are in place
- If not needed, disable SELinux, see /etc/sysconfig/selinux
- The following tutorial discusses how to deploy a basic graphite setup. Secutiry aspects and scaling issues are not covered.

Expected result:
- The host storing metrics runs graphite, carbon, grafana and mysql.
- diamond runs on every machine that needs to be monitored, sending metrics to carbon

## MySQL configuration

Graphite uses a database to store a few things. We will use Oracle MySQL 5.7 for this. 
Install MySQL 5.7

``` bash
$ wget http://dev.mysql.com/get/mysql57-community-release-el6-7.noarch.rpm
$ yum localinstall mysql57-community-release-el6-7.noarch.rpm
$ yum install mysql-community-server
$ yum install MySQL-python
$ yum-complete-transaction
$ service mysqld start
```


Oracle MySQL 5.7 uses the validate_password plugin, which we will uninstall.
MySQL setup

``` bash
$ grep -i temporary /var/log/mysqld.log
2016-10-25T10:24:08.036990Z 1 [Note] A temporary password is generated for root@localhost: jizYLyvEE4!e
2016-10-25T10:24:12.295338Z 0 [Note] InnoDB: Creating shared tablespace for temporary tables
2016-10-25T10:24:14.208065Z 0 [Note] InnoDB: Removed temporary tablespace data file: "ibtmp1"
2016-10-25T10:24:15.330033Z 0 [Note] InnoDB: Creating shared tablespace for temporary tables
```

``` bash
$ mysql -uroot -p
<enter the password store in /var/log/mysqld.log, e.g. "jizYLyvEE4!e" in the example above)
  
ALTER USER 'root'@'localhost' IDENTIFIED BY 'MyNewPass123!';
uninstall plugin validate_password;
SET PASSWORD FOR 'root'@'localhost' = PASSWORD('');
exit
```

From now on, the mysql console can be accessed from localhost with the command mysql -uroot
 
## Create Graphite database

``` bash
$ mysql -uroot
mysql> create database graphite;
Query OK, 1 row affected (0.00 sec)
mysql> GRANT ALL PRIVILEGES ON graphite.* TO 'graphite'@'localhost' IDENTIFIED BY 'graphite';
Query OK, 0 rows affected, 1 warning (0.00 sec)
mysql> flush privileges;
Query OK, 0 rows affected (0.00 sec)
exit
```

## Graphite-web setup
 
Install graphite and related packages:

``` bash
$ yum install pycairo Django14 python-ldap python-memcached python-sqlite2 bitmap bitmap-fonts-compat python-devel python-crypto pyOpenSSL gcc python-zope-filesystem python-zope-interface git gcc-c++ zlib-static python-txamqp python-setuptools python-psycopg2 mod_wsgi
 
$ yum install build-essential graphite-web python-carbon graphite-web-selinux python-dev apache2 libapache2-mod-wsgi libpq-dev python-psycopg2
```
 
The following step involves configuring the graphite web-app

## Graphite setup

``` bash
$ vim /etc/graphite-web/local_settings.py
```

``` bash
# Set time zone, e.g.
TIME_ZONE = 'Europe/Rome'
  
# Enable debug on exceptions
DEBUG = True
 
# Fix paths where needed
GRAPHITE_ROOT = '/usr/share/graphite'
CONF_DIR = '/etc/graphite-web'
STORAGE_DIR = '/var/lib/graphite'
CONTENT_DIR = '/usr/share/graphite/webapp/content'
DASHBOARD_CONF = '/etc/graphite-web/dashboard.conf'
GRAPHTEMPLATES_CONF = '/etc/graphite-web/graphTemplates.conf'
WHISPER_DIR = '/var/lib/graphite/whisper'
LOG_DIR = '/var/log/graphite/'  # Ensure that this directory is created and has the correct access rights (apache:apache)
INDEX_FILE = '/var/lib/graphite/index'  # Search index file
 
# Add database configuration for Django 
DATABASES = {
 'default': {
 'NAME': 'graphite',
 'ENGINE': 'django.db.backends.mysql',
 'USER': 'graphite',
 'PASSWORD': 'graphite',
 }
}
# Everything else can be removed
```

## Apache setup

``` bash
$ /usr/lib/python2.6/site-packages/graphite/manage.py syncdb
# You will be asked to create a superuser. Go ahead and do so.
# Username/password: root/root
  
$ vim /usr/lib/python2.6/site-packages/graphite/app_settings.py
# Comment the line containing
ADMIN_MEDIA_PREFIX = '/media/'
 
$ vim /usr/lib/python2.6/site-packages/graphite/settings.py
# change the value of the SECRET_KEY variable
# Change the permission for webapp storage to httpd user
$ mkdir /var/lib/graphite
$ chcon -R -h -t httpd_sys_content_t /var/lib/graphite # SELinux
$ chown -R apache:apache /var/lib/graphite
$ mkdir /var/lib/graphite/whisper
$ chown -R carbon:carbon /var/lib/graphite/whisper # Important step!
 
  
$ vim /etc/httpd/conf.d/graphite-web.conf
  
<VirtualHost *:8080>
    ServerName graphite-web
    DocumentRoot "/usr/share/graphite/webapp"
    ErrorLog /var/log/httpd/graphite-web-error.log
    CustomLog /var/log/httpd/graphite-web-access.log common
    LogLevel warn
    WSGIScriptAlias / /usr/share/graphite/graphite-web.wsgi
    WSGIImportScript /usr/share/graphite/graphite-web.wsgi process-group=%{GLOBAL} application-group=%{GLOBAL}
    <Location "/content/">
        SetHandler None
    </Location>
    Alias /media/ "/usr/lib/python2.6/site-packages/django/contrib/admin/media/"
    <Location "/media/">
        SetHandler None
    </Location>
</VirtualHost>
```

``` bash
$ vim /etc/httpd/conf/httpd.conf 
# Add the port where graphite will be listening (port 80 will be used by grafana)
Listen 8080
# Enable keep alive
KeepAlive On
# Add the ServerName directive in order to suppress the warning, "httpd: Could not reliably determine the server's fully qualified domain name", e.g.
ServerName myhost.mydomain.com
```

``` bash
# start the apache service
$ service httpd start
```

## Carbon setup
Carbon is the daemon listening for metrics (default: TCP port 2003) and writing them to disk.

carbon configuration
``` bash
$ vim /etc/carbon/carbon.conf
```

``` bash
# Add the following
STORAGE_DIR	= /var/lib/graphite/
LOCAL_DATA_DIR = /var/lib/graphite/whisper/
WHITELISTS_DIR = /var/lib/graphite/lists/
CONF_DIR   	= /etc/carbon/
LOG_DIR    	= /var/log/carbon/
PID_DIR    	= /var/run/
 
# Modify the following
# The daemon will drop privileges to the carbon user on startup.
# The carbon user must all write access to the /var/lib/graphite/whisper directory (see above)
USER = carbon
# Increase limits to fully utilise the available disk IOPS 
MAX_UPDATES_PER_SECOND = 3000
MAX_CREATES_PER_MINUTE = 15000
```


Configure the schemas (e.g., how often graphite expects a certain metric to be updated, and for how long it the data will be stored for).
Note: disk space is allocated at file creation (one metric -> one file)!
``` bash
$ vim /etc/carbon/storage-schemas.conf
 
# Current configuration
[graphite-debug]
pattern = ^graphite\.
retentions = 1s:1d
 
[mysql_size]
pattern = ^mysql\.
retentions = 10m:1y
 
[servers]
pattern = ^servers\.
retentions = 1m:43200,5m:95040
 
[default_1min_for_1day]
pattern = .*
retentions = 1m:1d
```

Start the carbon daemon
``` bash
$ service carbon-cache start
```

Verify that the daemon is listening on port 2003
``` bash
$ netstat -anp | grep 2003
tcp    	0  	0 0.0.0.0:2003            	0.0.0.0:*               	LISTEN  	18651/python2.6
```

Verify that carbon listens on port 2003:
``` bash
$ echo "test1.test2 123.2 `date +%s`"|nc 127.0.0.1 2003
```
Verify that the metric has been written to disk
``` bash
$ whisper-dump /var/lib/graphite/whisper/test1/test2.wsp |more
```
Notes:
- Metrics can be removed simply by removing the associated file in /var/lib/graphite/whisper. This can be done at runtime, without restarting the carbon daemon. Upon receiving a metric, the carbon daemon will create the whisper file for that metric if needed.
- The carbon daemon should be restarted whenever the schema is changed (see above).

Point your browser to your_host:8080. You should see the graphite web app and be able to see the metric "test1.test2". Only one point is stored, so you will not see any line.

## Grafana setup
See also http://docs.grafana.org/installation/rpm/

``` bash
# get the latest stable release from https://grafana.com/grafana/download, e.g.
$ wget https://s3-us-west-2.amazonaws.com/grafana-releases/release/grafana-4.2.0-1.x86_64.rpm
$ yum localinstall grafana-4.2.0-1.x86_64.rpm
$ vim /etc/httpd/conf.d/grafana.conf
<VirtualHost *:80>
        ProxyPreserveHost On
        ProxyPass / http://127.0.0.1:3000/
        ProxyPassReverse / http://127.0.0.1:3000/
        ServerName <YOUR_HOST>  # replace with hostname!
</VirtualHost>
```

Check that apache listens on port 80, e.g., in /etc/httpd/conf/httpd.conf you must have
``` bash
Listen 80
```

Edit the grafana configuration file
``` bash
$ vim /etc/grafana/grafana.ini
# see also http://docs.grafana.org/installation/configuration/
  
# The public facing domain name used to access grafana from a browser
domain = graphite
# enable gzip
enable_gzip = true

security]
# The following two settings can be disabled after creating another admin user
# default admin user, created on startup
admin_user = admin
# default admin password, can be changed before first start of grafana,  or in profile settings
admin_password = admin
 
[analytics]
reporting_enabled = false
check_for_updates = true
 
[users]
# disable user signup / registration
allow_sign_up = false
# Allow non admin users to create organizations
allow_org_create = false
 
[auth.anonymous]
# enable anonymous access
enabled = true
# specify organization name that should be used for unauthenticated users
org_name = Main Org.
# specify role for unauthenticated users
org_role = Viewer
 
[log]
level = warn
 
[metrics]
enabled       	= true
interval_seconds  = 60
```

Finally, restart both grafana and apache
``` bash
$ service grafana-server restart
$ service httpd restart
```

Open your browser and type the server IP in the address bar. Click on "sign up" and create the user, then login add add a graphite datasource.

## Events

Events can be created as follows and visualized from within grafana, see http://docs.grafana.org/reference/annotations/

``` bash
$ curl -X POST "http://<graphite-url>/events/" -d '{ "what": "Start perfclient", "tags": "perfclient", "when": 1480698180, "data": "Start test with settings: numclients 10000, login rate 40" }'
```

Alternatively, they can be created at this url http://graphite:8080/admin/events/event/ (replace host name and port if needed). If you have followed the instructions above, the username/password are root/root.

## Diamond setup

Having prepared the infrastructure to store and visualize metrics, we now need to collect metrics. This is done by the diamond daemon, see http://diamond.readthedocs.io/en/latest/
The following steps need to be carried out on every machine that needs to be monitored.

``` bash
$ yum -y update
$ yum install -y epel-release python-devel gcc vim
$ yum install -y python-pip
$ pip install --upgrade pip
$ pip install diamond
```

Next, copy [this](https://github.com/massiccio/graphite/blob/master/configuration_files/etc/diamond/diamond.conf) configuration file  to /etc/diamond/diamond.conf and [this](https://github.com/massiccio/graphite/blob/master/configuration_files/etc/init.d/diamond) init script to /etc/init.d/diamond (this step works  on CentOS 7 as well). Customize as needed the IP address of the graphite host (see GraphiteHandler section) and the collectors to be run (e.g., enable the MySQL collectors if needed). Extra DB collectors can be added if needed.
They should be stored in /usr/share/diamond/collectors/ and configured in /etc/diamond/diamond.conf

Finally, create the missing directory, setup diamond to be run as a service and start the daemon:
``` bash
$ mkdir /etc/diamond
$ mkdir /var/log/diamond
$ chkconfig --add /etc/init.d/diamond
$ chkconfig --list |grep diamond # check that the service starts at least for levels 3, 4, and 5
$ service diamond start
```
