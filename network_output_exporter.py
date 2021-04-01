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

# Parse output from tcpdump and update the Prometheus metrics
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
    key = tuple(labels.items())
    length = int(m.group('length'))

    if key not in packet_dict:
        packet_dict[key] = [(time.time(), length)]
    else:
        packet_dict[key].append((time.time(), length))

def update_packet_dict(now_time):
    global packet_dict
    new_packet_dict = {}
    for labels, time_len_list in packet_dict.items():
        # Drop entries older than one minute
        new_time_len_list = [(t, packet_len) for (t, packet_len) in time_len_list if now_time - t <= 60]
        if len(new_time_len_list) == 0:
            label_values = [v for (k, v) in labels]
            packet_gauge.remove(*label_values)
            throughput_gauge.remove(*label_values)
        else:
            label_dict = dict(labels)
            new_packet_dict[labels] = new_time_len_list
            packet_gauge.labels(**label_dict).set(len(new_time_len_list))
            throughput_gauge.labels(**label_dict).set(sum([packet_len for (_, packet_len) in new_time_len_list]))        
    packet_dict = new_packet_dict

# Run tcpdump and stream the packets out
async def stream_packets(interface):
    p = await asyncio.create_subprocess_exec(
        'tcpdump', '-i', interface, '-v', '-n', '-l', stdout=asyncio.subprocess.PIPE)
    while True:
        update_packet_dict(time.time())
        # When tcpdump is run with -v, it outputs two lines per packet;
        # readuntil ensures that each "line" is actually a parse-able string of output.
        line = await p.stdout.readuntil(b' IP ')
        if len(line) <= 0:
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
    parser.add_argument('--port', '-p', default=int(os.getenv('NOE_PORT', 9000)),
                        help='The Prometheus metrics port.')
    parser.add_argument('--metric_prefix', '-s', default=os.getenv('NOE_METRIC_PREFIX', 'noe'),
                        help='Metric prefix (group) for Prometheus')
    opts = parser.parse_args()

    packet_dict = {}
    packet_gauge = Gauge(f'{opts.metric_prefix}_packets', 'Packets transferred per minute', metric_labels)
    throughput_gauge = Gauge(f'{opts.metric_prefix}_bytes', 'Bytes transferred per minute', metric_labels)
    
    start_http_server(int(opts.port))
    asyncio.run(stream_packets(opts.interface))
