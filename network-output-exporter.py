#!/usr/bin/env python3
import subprocess, time, re, socket, argparse, os, asyncio, sys
from prometheus_client import Counter, start_http_server, Gauge

metric_labels = ['src_pod', 'src_user', 'src_org', 'dst_ip', 'dst_proto', 'dst_country']

# Given an IP or FQDN, extract the domain name to be used as server/client.
def extract_domain(string):
    parts = string.split('.')
    l = len(parts)
    if l == 4 and all(p.isnumeric() for p in parts): return string # IP Address
    return '.'.join(parts[l-2:]) if l > 2 else string

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
        print('[SKIP] ' + line.replace("\n", "\t"))
        return
    metric_labels = ['src_pod', 'src_user', 'src_org', 'dst_ip', 'dst_proto', 'dst_country']
    labels = {
        'src_pod': 'dummy_pod', # TODO
        'src_user': 'dummy_user', # TODO
        'src_org': 'dummy_org', # TODO
        'dst_ip': extract_domain(m.group('dst')),
        'dst_proto': m.group('proto').lower() + '/' + m.group('dstp'),
        'dst_country': 'Japan' # TODO
    }
    
    packets.labels(**labels).inc()
    throughput.labels(**labels).inc(int(m.group('length')))
    # TODO recet gauges to zero on every minute

# Run tcpdump and stream the packets out
async def stream_packets():
    p = await asyncio.create_subprocess_exec(
        'tcpdump', '-i', opts.interface, '-v', '-n', '-l', opts.filters,
        stdout=asyncio.subprocess.PIPE)
    while True:
        # When tcpdump is run with -v, it outputs two lines per packet;
        # readuntil ensures that each "line" is actually a parse-able string of output.
        line = await p.stdout.readuntil(b' IP ')
        print(line)
        if len(line) <= 0:
            print(f'No output from tcpdump... waiting.')
            time.sleep(1)
            continue
        try:
            parse_packet(line.decode('utf-8'))
        except BaseException as e:
            print(f'Failed to parse line "{line}" because: {e}')

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--interface', '-i', default=os.getenv('NOE_INTERFACE', 'eth0'),
        help='The network interface to monitor.')
    parser.add_argument('--port', '-p', default=int(os.getenv('NOE_PORT', 8000)),
        help='The Prometheus metrics port.')
    parser.add_argument('--metric_prefix', '-s', default=os.getenv('NOE_METRIC_PREFIX', 'ntm'),
        help='Metric prefix (group) for Prometheus')
    parser.add_argument('filters', nargs='?', default=os.getenv('NOE_FILTERS', ''),
        help='The TCPdump filters, e.g., "src net 192.168.1.1/24"')
    opts = parser.parse_args()

    packets = Gauge(f'{opts.metric_prefix}_packets', 'Packets transferred', metric_labels)
    throughput = Gauge(f'{opts.metric_prefix}_bytes', 'Bytes transferred', metric_labels)
    
    start_http_server(int(opts.port))
    asyncio.run(stream_packets())
