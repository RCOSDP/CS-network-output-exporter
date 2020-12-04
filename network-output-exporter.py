#!/usr/bin/env python3
import subprocess, time, re, socket, argparse, os, asyncio, sys
import urllib
import socket
import geoip2.database
from IPy import IP
from prometheus_client import Counter, start_http_server, Gauge

metric_labels = ['src_pod', 'src_user', 'src_org', 'dst_ip', 'dst_proto', 'dst_country', 'dst_continent']

geo_reader = geoip2.database.Reader('/opt/GeoLite2-Country.mmdb')


host_name = os.environ.get('HOSTNAME')
if host_name is None:
    host_name = socket.gethostname()
src_pod = host_name
try:
    host_name = urllib.parse.unquote(host_name.replace('-', '%')).partition('%')[2].rpartition('%')[0]
    (src_user, _, src_org) = host_name.partition('@')
except Exception as e:
    src_user = 'Unknown'
    src_org = 'Unknown'
    
# Helper for building regex.
def re_param(name, pattern):
    return f'(?P<{name}>{pattern})'

# Pre-compile regex for matching tcpdump output:
pattern = '.*' + '.*'.join([
    'proto ' + re_param('proto', '\w+') + ' ',
    'length ' + re_param('length', '\d+'),
    '\n\s*' + re_param('src', '[\w\d\.-]+') + '\.' + re_param('srcp', '[\w\d-]+') +
    ' > ' +
    re_param('dst', '[\w\d\.-]+') + '\.' + re_param('dstp', '[\w\d-]+'),
]) + '.*'
dump_matcher = re.compile(pattern)

# Parse output from tcpdump and update the Prometheus counters.
def parse_packet(line):
    m = dump_matcher.match(line)
    if not m:
        return
    metric_labels = ['src_pod', 'src_user', 'src_org', 'dst_ip', 'dst_proto', 'dst_country']
    dst_ip = m.group('dst')
    if IP(dst_ip).iptype() != 'PUBLIC':
        return

    proto = m.group('proto').lower()
    if proto != 'icmp':
        proto += '/' + m.group('dstp')
    else:
        dst_ip += '.' + m.group('dstp') # in icmp, dstp matches last part of ip

    try:
        geo_response = geo_reader.country(dst_ip)
        country = geo_response.country.name
        continent = geo_response.continent.name
    except Exception as e:
        country = 'Unknown'
        continent = 'Unknown'

    labels = {
        'src_pod': src_pod,
        'src_user': src_user,
        'src_org': src_org,
        'dst_ip': dst_ip,
        'dst_proto': proto,
        'dst_country': country,
        'dst_continent': continent
    }
    packets.labels(**labels).inc()
    throughput.labels(**labels).inc(int(m.group('length')))

# Run tcpdump and stream the packets out
async def stream_packets():
    p = await asyncio.create_subprocess_exec(
        'tcpdump', '-i', opts.interface, '-v', '-n', '-l', opts.filters,
        stdout=asyncio.subprocess.PIPE)
    start_time = time.time()
    while True:
        if time.time() - start_time > 60:
            packets._metrics.clear()
            throughput._metrics.clear()
            start_time = time.time()
        # When tcpdump is run with -v, it outputs two lines per packet;
        # readuntil ensures that each "line" is actually a parse-able string of output.
        line = await p.stdout.readuntil(b' IP ')
        if len(line) <= 0:
            # print(f'No output from tcpdump... waiting.')
            time.sleep(1)
            continue
        try:
            parse_packet(line.decode('utf-8'))
        except BaseException as e:
            # print(f'Failed to parse line "{line}" because: {e}')
            pass

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--interface', '-i', default=os.getenv('NOE_INTERFACE', 'eth0'),
        help='The network interface to monitor.')
    parser.add_argument('--port', '-p', default=int(os.getenv('NOE_PORT', 8000)),
        help='The Prometheus metrics port.')
    parser.add_argument('--metric_prefix', '-s', default=os.getenv('NOE_METRIC_PREFIX', 'noe'),
        help='Metric prefix (group) for Prometheus')
    parser.add_argument('filters', nargs='?', default=os.getenv('NOE_FILTERS', ''),
        help='The TCPdump filters, e.g., "src net 192.168.1.1/24"')
    opts = parser.parse_args()

    packets = Gauge(f'{opts.metric_prefix}_packets', 'Packets transferred per minute', metric_labels)
    throughput = Gauge(f'{opts.metric_prefix}_bytes', 'Bytes transferred per minute', metric_labels)
    
    start_http_server(int(opts.port))
    asyncio.run(stream_packets())
