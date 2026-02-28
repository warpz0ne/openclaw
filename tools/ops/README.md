# tools/ops

Utility scripts for repetitive operational tasks.

## Slice helpers

### `slicectl.sh`
Frequent service/debug commands for `slice.service`.

Examples:

```bash
./tools/ops/slicectl.sh status
./tools/ops/slicectl.sh restart
./tools/ops/slicectl.sh logs 120
./tools/ops/slicectl.sh test
./tools/ops/slicectl.sh env-show
./tools/ops/slicectl.sh env-edit
```

Notes:
- `env-show` masks `GOOGLE_CLIENT_SECRET`.
- `env-edit` opens `/etc/default/slice` and restarts service afterward.
- Requires `sudo` privileges for service/log actions.
