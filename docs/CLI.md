# CLI Guide

The CLI is the fastest way to try the swarm in a terminal.

## Run
```bash
. .venv/bin/activate
python -m spds.main
```

## Common options
```bash
python -m spds.main --interactive
python -m spds.main --agent-ids ag-123 ag-456
python -m spds.main --agent-names "Project Manager Alex" "Designer Jordan"
python -m spds.main --swarm-config creative_swarm.json
```

## Sessions
```bash
python -m spds.main sessions list
python -m spds.main sessions show <session-id>
python -m spds.main sessions delete <session-id>
python -m spds.main --session-id <session-id>
python -m spds.main --new-session "My Project Discussion"
```
