FROM debian:buster-slim

USER root

RUN apt-get clean -y && apt-get update -y && \
    apt-get install --no-install-recommends -y python3-pip python3-setuptools python3-dev build-essential

RUN apt-get install -y curl netcat bc

RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN pip3 install argparse prometheus_client
RUN pip3 install IPy
RUN pip3 install geoip2

RUN apt-get update -y && apt-get install -y tcpdump

COPY network_output_exporter.py /usr/bin/network_output_exporter.py
COPY test.sh /usr/bin/test.sh
COPY GeoLite2-Country.mmdb /opt/GeoLite2-Country.mmdb
RUN chmod +x /usr/bin/network_output_exporter.py
RUN chmod +x /usr/bin/test.sh
CMD /usr/bin/network_output_exporter.py

EXPOSE 8000
