#!/usr/bin/env bash
# G6 proof: verify after migration, then break every managed capability.
set -euo pipefail
cd "$(dirname "$0")"

python3 -m unittest tests.test_post_migration_verify -v
echo "post-migration verification: OK"
