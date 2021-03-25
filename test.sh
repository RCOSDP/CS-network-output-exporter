network_output_exporter.py &
PID=$!

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

function red {
    printf "${RED}$@${NC}\n"
}

function green {
    printf "${GREEN}$@${NC}\n"
}

echo Network output exporter started on $PID

sleep 2 # wait booting of the exporter

echo "dummy" | nc -q0 example.com 80 > /dev/null

echo "The first packet has been sent..."

sleep 2 # wait for metrics retrieval

FIRST_METRICS=$(curl -sS 'http://localhost:9000')

PACKETS_1=$(echo "$FIRST_METRICS"  | grep ^noe_packets | rev | cut -d ' ' -f 1 | rev 2> /dev/null)
BYTES_1=$(echo "$FIRST_METRICS"  | grep ^noe_bytes | rev | cut -d ' ' -f 1 | rev 2> /dev/null)
echo First packet count: $PACKETS_1
echo First byte count: $BYTES_1

if test -z $PACKETS_1; then
    echo $(red "Test failed!: metrics 'noe_packets' is absent")
    exit -1
fi

if test -z $BYTES_1; then
    echo $(red "Test failed!: metrics 'noe_bytes' is absent")
    exit -1
fi

echo "dummy" | nc -q0 example.com 80 > /dev/null

echo "The second dummy packet has been sent..."

sleep 2 # wait for metrics retrieval

SECOND_METRICS=$(curl -sS 'http://localhost:9000')

PACKETS_2=$(echo "$SECOND_METRICS" | grep ^noe_packets | rev | cut -d ' ' -f 1 | rev)
BYTES_2=$(echo "$SECOND_METRICS" | grep ^noe_bytes | rev | cut -d ' ' -f 1 | rev)

echo Second packet count: $PACKETS_2
echo Second byte count: $BYTES_2

PACKETS_DIFF=`echo $PACKETS_2 - $PACKETS_1 | bc -l`
BYTES_DIFF=`echo $BYTES_2 - $BYTES_1 | bc -l`
PACKETS_DIFF=${PACKETS_DIFF%.*} # convert to int
BYTES_DIFF=${BYTES_DIFF%.*} # convert to int

echo Packet count difference: $PACKETS_DIFF
echo Byte count difference: $BYTES_DIFF

if test $PACKETS_DIFF -le 0; then
    echo $(red "Test failed!: metrics 'noe_packets' did not increase")
    exit -1
fi

if test $BYTES_DIFF -le 0; then
    echo $(red "Test failed!: metrics 'noe_bytes' did not increase")
    exit -1
fi

echo $(green "Test succeeded!")

kill $PID
