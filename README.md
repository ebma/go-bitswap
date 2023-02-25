# Increasing Bitswap Privacy with Request Obfuscation

This repository contains the code and simulation results for the master thesis "Increasing Bitswap Privacy with Request
Obfuscation".

## Folder Structure

- `/experiments`
    - Contains testground composition files to facilitate running the simulations with appropriate parameters
    - Contains shell scripts that can be used to automatically run the simulations
    - Will contain the results of the simulations as well as pdf files after running them with one of the
      contained `run_xxx.sh` scripts
- `/implementations`
    - Contains the code for both the baseline and the trickle-spreading testground test plans
    - `/trickle-spreading`
        - Contains the manifest and main.go file for the trickle-spreading test plan
        - `/go-bitswap`
            - Contains a customized implementation of `go-bitswap` v0.10.0 which is copied into the docker container and
              used for the trickle-spreading simulations.
            - As mentioned in the thesis, the forwarding logic bases on the works of de la Rocha et al.
              The respective branch can be found [here](https://github.com/adlrocha/go-bitswap/tree/feature/rfcBBL102).
              The code on that branch implements message forwarding on `go-bitswap` v0.2.19.
              For this work, it was adjusted and implemented for `go-bitswap` v0.10.0, the Time-To-Live (TTL) for
              messages was removed and a configurable trickling delay was added.
            - Relevant changes compared to the 'original' `go-bitswap`
              implementation ([v0.10.0](https://github.com/ipfs/go-bitswap/tree/v0.10.0)) were
              made to the following files:
                - `server/internal/decision/engine.go`
                - `server/server.go`
                - `client/internal/relaysession/relaySessions.go`
                - `client/internal/peermanager/peermanager.go`
                - `client/internal/peermanager/peerwantmanager.go`
                - `client/internal/session/session.go`
                - `client/internal/sessionmanager/sessionmanager.go`
                - `client/client.go`
                - `client/internal/defaults/defaults.go`
        - `/test`
            - Contains the test plan for the trickle-spreading testground simulations
            - `/utils`
                - Contains utility functions that are used in the test plan
                - These are adopted from the testbed of the beyond-bitswap project
                  (
                  see [here](https://github.com/protocol/beyond-bitswap/tree/0aa224c4944a9a3e49c39277bfb51e9a51422d54/testbed/testbed))
                - The utility functions were mostly adopted as they are, but changes were made
                  to `utils/dialer/dialer.go` and `utils/bitswap.go`
    - `/baseline`
        - Contains the manifest and main.go file for the trickle-spreading test plan
        - `/test`
            - Contains the test plan for the baseline testground simulations
            - `/utils`
                - Contains utility functions that are used in the test plan
                - These are adopted from the testbed of the beyond-bitswap project
                  (
                  see [here](https://github.com/protocol/beyond-bitswap/tree/0aa224c4944a9a3e49c39277bfb51e9a51422d54/testbed/testbed))
                - The utility functions were mostly adopted as they are, but changes were made
                  to `utils/dialer/dialer.go` and `utils/ipfs.go`
- `/scripts`
    - Contains shell scripts that are used to automate the process of running the testground test plans
      - The `exec.sh` and `random-file.sh` scripts are copied from the Beyond Bitswap testbed.
    - Contains Python scripts that are used to analyze and visualize the results of the simulations

## Simulation results

The simulation results are available as a zip file in the release section of this repository.
The zip file contains the results of all simulations that were run for the thesis.
These results can be used to reproduce the results of the thesis.
In order to do so, the content of the zip file should be extracted into the `experiments/results` folder of this repository.
The results can then be analyzed and visualized by running the `pdf.py` script in the `scripts` folder.
More details on how to do this can be found below.

## Prerequisites

- You should have a working installation of [testground](https://testground.github.io/docs/master/#/getting-started).
- You should have a working installation of Docker
    - Don't use Docker Desktop, as this can cause issues when running testground

### For the scripts

- You should have a working installation of [python3](https://www.python.org/downloads/).
- Then run the following commands from the root of this repository:

```shell
pip3 install virtualenv
virtualenv env
source ~/env/bin/activate
cd scripts
pip install -r requirements.txt
```

## Running the simulation

Before running, you need to extend the default timeout of the daemon scheduler.
This is because by default the daemon is stopped automatically after 10 minutes.
But the simulations can take up to an hour so we need to extend the timeout.
To do so, you need to edit the `.env.toml` file of your testground installation and add the following lines (
see [here](https://docs.testground.ai/getting-started#configuration-.env.toml)):

```toml
[daemon.scheduler]
task_timeout_min = 55
```

### Importing the test plans

```shell
cd implementations
testground plan import --from ./baseline
testground plan import --from ./trickle-spreading
```

### Automatically running the simulations

To facilitate the process of running the simulations, we provide shell scripts that automatically run the simulations,
collect the data and run the python scripts to analyze and visualize the result.
To run them, use the following commands from the `./experiments` directory:

```shell
# Navigate to the experiments directory, if necessary
cd experiments

# Run the baseline simulation
./experiments/run_experiment-baseline.sh

# Run an eavesdropper simulation. 
# The first argument is the number of eavesdroppers used. 
# Note that only the arguments 0,1,4,7 are supported because only for these numbers do composition files exist.
./experiments/run_experiment-docker-eaves.sh 0
./experiments/run_experiment-docker-eaves.sh 1
./experiments/run_experiment-docker-eaves.sh 4
./experiments/run_experiment-docker-eaves.sh 7
```

### Only running the python scripts

You can also run the python scripts manually to analyze and visualize the results.
Make sure that you have some results in the `./experiments/results` directory.
Then run the following commands from the root of this repository:

```shell
./scripts/pdf.py
```

## Troubleshooting

Sometimes, errors pop up randomly, like 'fatal error: inconsistent mutex state' or 'runtime error: invalid memory
address or nil pointer dereference'.
Re-running the test usually fixes the issue.

### Problems with `pdf.py`

Make sure that seaborn is installed with version 0.11.2. If you have a newer version, you can downgrade it with

```bash
pip install seaborn==0.11.2
```

Seaborn v0.12 throws some error about missing `metrics`.

### Testground

If you encounter the following error and you are using Docker Desktop, consider removing it as this probably fixes the
issue.

```shell
ERROR  doRun returned err      {"err": "task of type run cancelled: healthcheck fixes failed; aborting:\nChecks:\n- local-outputs-dir: ok; directory exists.\n- control-network: ok; network exists.\n- local-grafana: ok; container state: running\n- local-redis: ok; container state: running\n- local-sync-service: failed; container not found.\n- local-influxdb: ok; container state: running\n- sidecar-container: failed; container not found.\nFixes:\n- local-outputs-dir: unnecessary; \n- control-network: unnecessary; \n- local-grafana: unnecessary; \n- local-redis: unnecessary; \n- local-sync-service: failed; failed to start container.\n- local-influxdb: unnecessary; \n- sidecar-container: failed; failed to start container.\n"}
ERROR  task cancelled due to error     {"err": "task of type run cancelled: healthcheck fixes failed; aborting:\nChecks:\n- local-outputs-dir: ok; directory exists.\n- control-network: ok; network exists.\n- local-grafana: ok; container state: running\n- local-redis: ok; container state: running\n- local-sync-service: failed; container not found.\n- local-influxdb: ok; container state: running\n- sidecar-container: failed; container not found.\nFixes:\n- local-outputs-dir: unnecessary; \n- control-network: unnecessary; \n- local-grafana: unnecessary; \n- local-redis: unnecessary; \n- local-sync-service: failed; failed to start container.\n- local-influxdb: unnecessary; \n- sidecar-container: failed; failed to start container.\n"}
```