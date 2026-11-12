#!/usr/bin/env bash
# Run a command in the live test VM (forwarded port 2222) through bash, whatever the login shell is. Test-only credentials.
b64=$(printf '%s' "$*" | base64 -w0)
exec sshpass -p sunshine ssh -p 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR sunshine@localhost "bash -c \"\$(echo $b64 | base64 -d)\""
