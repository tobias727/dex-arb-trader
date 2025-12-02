#!/bin/bash
docker build -t tobias875/dex-arb-trader:v1.3.0 .
docker push tobias875/dex-arb-trader:v1.3.0
docker image prune -f
