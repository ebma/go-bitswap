# Trickle Bitswap

To generate the `go.sum` file, use the following command:

```bash
go generate github.com/your/module/name
go mod tidy
```

# Prerequisites
- Don't use Docker Desktop, as this can cause issues when running testground
- 

# Run the simulation

Before running, you need to extend the default timeout of the daemon scheduler. To do so, you need to edit
the `.env.toml` file of your testground installation and add the following lines (see [here](https://docs.testground.ai/getting-started#configuration-.env.toml)):

```toml
[daemon.scheduler]
task_timeout_min = 30
```

## Importing the test plans

```shell
cd implementations
testground plan import --from ./baseline
testground plan import --from ./trickle-spreading
```


# Troubleshooting

Sometimes, errors pop up randomly, like 'fatal error: inconsistent mutex state' or 'runtime error: invalid memory
address or nil pointer dereference'. Re-running the test usually fixes the
issue.

## pdf.py
Make sure that seaborn is installed with version 0.11.2. If you have a newer version, you can downgrade it with
```bash
pip install seaborn==0.11.2
```
Seaborn v0.12 throws some error about missing `metrics`.


## Testground
If you encounter the following error and you are using Docker Desktop, consider removing it as this probably fixes the issue.
```shell
ERROR  doRun returned err      {"err": "task of type run cancelled: healthcheck fixes failed; aborting:\nChecks:\n- local-outputs-dir: ok; directory exists.\n- control-network: ok; network exists.\n- local-grafana: ok; container state: running\n- local-redis: ok; container state: running\n- local-sync-service: failed; container not found.\n- local-influxdb: ok; container state: running\n- sidecar-container: failed; container not found.\nFixes:\n- local-outputs-dir: unnecessary; \n- control-network: unnecessary; \n- local-grafana: unnecessary; \n- local-redis: unnecessary; \n- local-sync-service: failed; failed to start container.\n- local-influxdb: unnecessary; \n- sidecar-container: failed; failed to start container.\n"}
ERROR  task cancelled due to error     {"err": "task of type run cancelled: healthcheck fixes failed; aborting:\nChecks:\n- local-outputs-dir: ok; directory exists.\n- control-network: ok; network exists.\n- local-grafana: ok; container state: running\n- local-redis: ok; container state: running\n- local-sync-service: failed; container not found.\n- local-influxdb: ok; container state: running\n- sidecar-container: failed; container not found.\nFixes:\n- local-outputs-dir: unnecessary; \n- control-network: unnecessary; \n- local-grafana: unnecessary; \n- local-redis: unnecessary; \n- local-sync-service: failed; failed to start container.\n- local-influxdb: unnecessary; \n- sidecar-container: failed; failed to start container.\n"}
```