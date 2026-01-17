#!/bin/bash

# Kill any running python bgp processes
pkill -f "python main.py"

echo "Starting Peer 1 (AS 65001, Socket: /tmp/bgp_agent_peer1.sock)..."
PYTHONPATH=. uv run python main.py examples/peer1.yaml > peer1.log 2>&1 &
PID1=$!

sleep 2

echo "Starting Peer 2 (AS 65002, Socket: /tmp/bgp_agent_peer2.sock)..."
PYTHONPATH=. uv run python main.py examples/peer2.yaml > peer2.log 2>&1 &
PID2=$!

echo "Waiting for session establishment..."
sleep 10

echo "=== PEER 1 STATUS ==="
PYTHONPATH=. uv run python bgpctl.py --socket /tmp/bgp_agent_peer1.sock show neighbors
PYTHONPATH=. uv run python bgpctl.py --socket /tmp/bgp_agent_peer1.sock show routes received

echo "=== PEER 2 STATUS ==="
PYTHONPATH=. uv run python bgpctl.py --socket /tmp/bgp_agent_peer2.sock show neighbors
PYTHONPATH=. uv run python bgpctl.py --socket /tmp/bgp_agent_peer2.sock show routes received

# Cleanup
kill $PID1 $PID2
