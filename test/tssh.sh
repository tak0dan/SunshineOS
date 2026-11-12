#!/usr/bin/env bash
# Run a command in the installed-system test VM as the test user (port 2222, password testpass123; test-only).
b64=$(printf '%s' "$*" | base64 -w0)
exec sshpass -p testpass123 ssh -p 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR ${TUSER:-tester}@localhost "bash -c \"\$(echo $b64 | base64 -d)\""
