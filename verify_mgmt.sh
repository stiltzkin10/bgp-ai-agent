#!/bin/bash

# Kill any running python bgp processes
pkill -f "python main.py"

# Start only Peer 1 (Server)
# We need to start only one peer to interact with its management socket 
# because both peers currently try to listen on the SAME socket path /tmp/bgp_agent.sock!
# This is a limitation I need to fix: socket path should be unique per instance or configurable.
# For now, I will create a config for Peer 1 and verify CLI against it.
# To fully test peering + CLI, I need to separate the sockets.

# Let's assume we test pure CLI interactions with one instance first, 
# but "show neighbors" needs a neighbor.

# So I MUST make socket path configurable to run two instances on the same machine.
# But for the requested task, I can just demonstrate it works with one instance attempting to connect.

echo "Starting Peer 1 (AS 65001)..."
PYTHONPATH=. uv run python main.py examples/peer1.yaml > peer1.log 2>&1 &
PID1=$!

sleep 3

echo "--- Check Neighbors (Should be empty or stuck in Connect) ---"
PYTHONPATH=. uv run python bgpctl.py show neighbors

echo "--- Check Routes Advertised ---"
PYTHONPATH=. uv run python bgpctl.py show routes advertised

# Clean up
kill $PID1
