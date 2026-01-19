# BGP AI Agent

A Python-based BGP speaker with an AI-powered Network Analyst that can answer natural language questions about the network state.

## Disclaimer

This is a proof of concept and should not be used in production. It only supports IPv4 unicast.

## Setup

### Prerequisites
- [uv](https://github.com/astral-sh/uv) package manager

### Installation

```bash
# Clone the repository
git clone https://github.com/stiltzkin10/bgp-ai-agent.git
cd bgp-ai-agent

# Install dependencies
uv sync
```

### Configuration

1. Create peer configuration files (see `examples/peer1.yaml` and `examples/peer2.yaml`)
2. For the AI agent, create a `.env` file with your Gemini API key:
   ```
   GEMINI_API_KEY=your_api_key_here
   ```

## Running

### Start the BGP Speaker

```bash
uv run main.py examples/peer1.yaml
```

The example peer1.yaml and peer2.yaml can be used to start two BGP speakers on the same machine. They will peer with each other.

Start two terminals and run:

```bash
uv run python main.py examples/peer1.yaml
```

and 

```bash
uv run python main.py examples/peer2.yaml
```

## Use the CLI Tool

```
uv run bgpctl.py --socket /tmp/bgp_agent_peer1.sock show neighbors
```

### Show received routes

```
uv run bgpctl.py --socket /tmp/bgp_agent_peer1.sock show routes received
```

### Show advertised routes
```
uv run bgpctl.py --socket /tmp/bgp_agent_peer1.sock show routes advertised
```

## Run the AI Network Analyst

```bash
uv run bgp_agent.py --socket /tmp/bgp_agent_peer1.sock
```

Example questions:
- "How many neighbors do I have?"
- "Are there any peers not in ESTABLISHED state?"
- "What routes am I receiving from 172.17.0.2?"
- "Can I summarize any prefixes?"

