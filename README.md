# Trickle Bitswap

To generate the `go.sum` file, use the following command:

```bash
go generate github.com/your/module/name
go mod tidy
```

# Run the simulation

Before running, you need to extend the default timeout of the daemon scheduler. To do so, you need to edit
the `.env.toml` file of your testground installation and add the following lines:

```toml
[daemon.scheduler]
task_timeout_min = 30
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