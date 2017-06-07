#!/bin/bash
# Note: the above script causes a full GC at every execution, see
# http://netflix.github.io/spectator/en/latest/ext/jvm-gc-causes/#heap_inspection_initiated_gc

# This script parses the output of jmap and sends the resulting data to Graphite
# It assumes there is only one JVM running from a jar file. If that is not the case, the get_total_heap_values() function
# should be modified accordingly.

HOSTNAME=`hostname --short`
GRAPHITE=127.0.0.1
GRAPHITE_PORT=2003

get_total_heap_values()
{
	DATE=`date +%s`
	pid=`jps |grep jar`
        if [[ ! -z "$pid" ]]; then
		echo $pid | cut -d" " -f1| xargs jmap -histo|grep Total|sed 's/\s\+/ /g'|cut -d" " -f2,3,4|
                awk '{print "ngserver.'$HOSTNAME'.heap.total.objects "$1"\nngserver.'$HOSTNAME'.heap.total.object_size_bytes " $2}' | while read line
                do
                        echo $line $DATE | nc $GRAPHITE $GRAPHITE_PORT
                done

                echo $pid | cut -d" " -f1| xargs jmap -histo:live|grep Total|sed 's/\s\+/ /g'|cut -d" " -f2,3,4|
                awk '{print "ngserver.'$HOSTNAME'.heap.total.live_objects "$1"\nngserver.'$HOSTNAME'.heap.total.live_objects_size_bytes " $2}' | while read line
                do
                        echo $line $DATE | nc $GRAPHITE $GRAPHITE_PORT
                done
        fi

}

while true; do
	START=$(date +%s);
        get_total_heap_values
	END=$(date +%s);
	DURATION=$((END-START))
	SLEEP_FOR=$((10-DURATION));
	if [ $SLEEP_FOR > 0 ]; then
		sleep $SLEEP_FOR
	fi
done
