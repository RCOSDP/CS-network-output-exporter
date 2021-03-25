## How to use

### Set environment variables
- `NOE_PORT`: Port where the metrics will be exposed (default: `9000`)
- `NOE_METRICS_PREFIX`: Prefix to be added into the metrics names (default: `noe`)
- `NOE_INTERFACE`: Name of interface to be supervised (default: `127.0.0.1`)

### To execute by Docker

```
docker build --tag network-output-exporter .
docker run -it --rm network-output-exporter bash test.sh # for testing
docker run -it --rm network-output-exporter
```

## DockerHub

https://hub.docker.com/r/lmeval/network_output_exporter

## Credit

Thanks to [Zane Claes's project](https://github.com/zaneclaes/network-traffic-metrics)
    for the base concept of this exporter.

This product includes GeoLite2 data created by MaxMind, available from https://www.maxmind.com.
