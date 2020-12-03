FROM debian:buster-slim

USER root

RUN apt-get clean -y && apt-get update -y && \
    apt-get install --no-install-recommends -y python3-pip python3-setuptools python3-dev build-essential && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN pip3 install argparse prometheus_client
RUN pip3 install IPy
RUN pip3 install geoip2

RUN apt-get update -y && apt-get install -y tcpdump

COPY network-output-exporter.py /usr/bin/network-output-exporter.py
COPY GeoLite2-Country.mmdb /opt/GeoLite2-Country.mmdb
RUN chmod +x /usr/bin/network-output-exporter.py
CMD /usr/bin/network-output-exporter.py

EXPOSE 8000
