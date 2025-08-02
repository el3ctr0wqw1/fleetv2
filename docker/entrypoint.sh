#!/bin/bash
set -e

# Start the miner using environment variables for pool and wallet
exec /usr/local/bin/t-rex -a octopus -o "$POOL" -u "$WALLET" --intensity ${INTENSITY:-70} "$@"
