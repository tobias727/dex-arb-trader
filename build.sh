#!/bin/bash
docker build -t tobias875/dex-arb-trader:latest .
docker push tobias875/dex-arb-trader:latest
docker image prune -f
