#!/bin/bash
# This container stays alive so the dashboard can docker-exec tcpdump into it.
# tcpdump runs with --net=host --privileged to see the bridge interface.
exec sleep infinity
