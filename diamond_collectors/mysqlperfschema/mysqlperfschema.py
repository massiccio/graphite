try:
    import MySQLdb
    from MySQLdb import MySQLError
except ImportError:
    MySQLdb = None
import diamond
import re

# Collector querying the performance schema of MySQL.
class MySQLPerfSchemaCollector(diamond.collector.Collector):

    # Query executed when a database is specified, e.g., hosts = root:@localhost:3306/my_db
    _TABLE_STATS = "select object_schema, object_name, count_insert, count_update, count_delete, count_read, count_write, count_star from performance_schema.table_io_waits_summary_by_table where object_schema='{0}'"

    # Query executed when no database is specified, e.g., hosts = root:@localhost:3306/None
    _STATS_ALL_DATABASES = 'select object_schema, object_name, count_insert, count_update, count_delete, count_read, count_write, count_star from performance_schema.table_io_waits_summary_by_table;'

    # Query executed when a database is specified, e.g., hosts = root:@localhost:3306/my_db
    _INDEX_STATS = "select object_schema, object_name, index_name, count_star, count_read, count_write, avg_timer_wait / pow(10, 9) as 'avg_timer_wait_ms', avg_timer_read / pow(10, 9) as 'avg_timer_read_ms', avg_timer_write / pow(10, 9) as 'avg_timer_write_ms' from performance_schema.table_io_waits_summary_by_index_usage where object_schema='{0}'"

    # Query executed when no database is specified, e.g., hosts = root:@localhost:3306/None
    _INDEX_ALL_DATABASES = 'select object_schema, object_name, index_name, count_star, count_read, count_write, avg_timer_wait / pow(10, 9) as "avg_timer_wait_ms", avg_timer_read / pow(10, 9) as "avg_timer_read_ms", avg_timer_write / pow(10, 9) as "avg_timer_write_ms" from performance_schema.table_io_waits_summary_by_index_usage'


    def __init__(self, *args, **kwargs):
        super(MySQLPerfSchemaCollector, self).__init__(*args, **kwargs)
        self.db = None

    # Load configuration
    def process_config(self):
        if self.config['hosts'].__class__.__name__ != 'list':
            self.config['hosts'] = [self.config['hosts']]

        # Move legacy config format to new format
        if 'host' in self.config:
            hoststr = '%s:%s@%s:%s/%s' % (
                self.config['user'],
                self.config['passwd'],
                self.config['host'],
                self.config['port'],
                self.config['db'],
            )
            self.config['hosts'].append(hoststr)

        self.db = None

    # Connect to the database
    def connect(self, params):
        try:
            self.db = MySQLdb.connect(**params)
            self.log.debug('MySQLPerfSchemaCollector: Connected to database.')
        except MySQLError, e:
            self.log.error('MySQLPerfSchemaCollector couldnt connect to database %s', e)
            return False
        return True

    # Disconnect from the database
    def disconnect(self):
        self.db.close()

    # Execute the query
    def get_db_stats(self, query):

        cursor = self.db.cursor(cursorclass=MySQLdb.cursors.DictCursor)
        try:
            cursor.execute(query)
            return cursor.fetchall()
        except MySQLError, e:
            self.log.error('MySQLPerfSchemaCollector could not get performance schema stats', e)
            return ()

    # Parse the results and stores them into a dictionary
    def _get_table_stats(self, query_table_stats):
        metrics = {}

        results = self.get_db_stats(query_table_stats)
        for r in results:
            db = r['object_schema'] # database name
            table = r['object_name'] # table name
            # counters
            metrics['table.total.{0}.{1}'.format(db, table)] = r['count_star']
            metrics['table.reads.{0}.{1}'.format(db, table)] = r['count_read']
            metrics['table.writes.{0}.{1}'.format(db, table)] = r['count_write']
            metrics['table.inserts.{0}.{1}'.format(db, table)] = r['count_insert']
            metrics['table.updates.{0}.{1}'.format(db, table)] = r['count_update']
            metrics['table.deletes.{0}.{1}'.format(db, table)] = r['count_delete']

        return metrics

    def _get_index_stats(self, query_index_stats):
        metrics = {}

        results = self.get_db_stats(query_index_stats)
        for r in results:
            db = r['object_schema'] # database name
            table = r['object_name'] # table name
            index = r['index_name'] #index

            if db == 'performance_schema': # ignore performance schema
                continue

            if index == 'None':
                index = "NO_INDEX_USED"
            # counters
            metrics['index.total.{0}.{1}.{2}'.format(db, table, index)] = r['count_star']
            metrics['index.reads.{0}.{1}.{2}'.format(db, table, index)] = r['count_read']
            metrics['index.writes.{0}.{1}.{2}'.format(db, table, index)] = r['count_write']

        return metrics


    def _publish_stats(self, metrics):

        counter = 0L
        for key, value in metrics.items():
            rate = self.derivative(key, value)
            self.publish(key, rate)
            counter = counter + 1L
            self.log.debug('%s = %d', key, rate)

        self.log.debug('Published %d metrics', counter)

    def get_stats(self, params, query_table_stats, query_index_stats):

        # if unable to connect, return emtpty dict
        if not self.connect(params):
            return {}

        metrics = self._get_table_stats(query_table_stats)
        metrics.update(self._get_index_stats(query_index_stats))

        return metrics

    # Collect the metrics
    def collect(self):

        if MySQLdb is None:
            self.log.error('Unable to import MySQLdb')
            return False

        for host in self.config['hosts']:
            matches = re.search('^([^:]*):([^@]*)@([^:]*):?([^/]*)/([^/]*)/?(.*)', host)

            if not matches:
                self.log.error('Connection string not in required format, skipping: %s', host)
                continue

            params = {}

            params['host'] = matches.group(3)
            try:
                params['port'] = int(matches.group(4))
            except ValueError:
                params['port'] = 3306
            params['db'] = matches.group(5)
            params['user'] = matches.group(1)
            params['passwd'] = matches.group(2)

            # If no database is selected, get data about all databases
            query_table_stats = self._STATS_ALL_DATABASES
            query_index_stats = self._INDEX_ALL_DATABASES

            if params['db'] == 'None':
                del params['db']
                self.log.debug('Database not specified. Querying performance schema data about all schemas.')
                # query all stats
            else:
                query_table_stats = self._TABLE_STATS.format(params['db'])
                query_index_stats = self._INDEX_STATS.format(params['db'])
                self.log.debug('Getting metrics for database: %s', params['db'])

            try:
                metrics = self.get_stats(params, query_table_stats, query_index_stats)
                if len(metrics) == 0:
                    self.log.debug('Empty metric set.')
                else:
                    self.log.debug('Publishing %d metrics', len(metrics))
                    self._publish_stats(metrics)
            except Exception, e:
                try:
                    self.log.error("Error %s", e)
                    self.disconnect()
                except MySQLdb.ProgrammingError:
                    pass
                self.log.error('Collection failed for %s', e)
