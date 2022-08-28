package test

import (
	"context"
	"fmt"
	"github.com/ipfs/go-cid"
	files "github.com/ipfs/go-ipfs-files"
	"github.com/ipfs/testground/plans/trickle-bitswap/utils"
	"github.com/ipfs/testground/plans/trickle-bitswap/utils/dialer"
	"github.com/libp2p/go-libp2p"
	"github.com/libp2p/go-libp2p-core/crypto"
	"github.com/libp2p/go-libp2p-core/host"
	"github.com/libp2p/go-libp2p-core/peer"
	"github.com/testground/sdk-go/network"
	"strconv"
	"time"

	"github.com/testground/sdk-go/run"
	"github.com/testground/sdk-go/runtime"
	"github.com/testground/sdk-go/sync"
)

// Launch bitswap nodes and connect them to each other.
func BitswapTransferTest(runenv *runtime.RunEnv, initCtx *run.InitContext) error {
	testvars, err := getEnvVars(runenv)
	if err != nil {
		return err
	}
	//logging.SetLogLevel("bitswap", "DEBUG")
	//logging.SetLogLevel("*", "DEBUG")

	nodeType := "bitswap"

	/// --- Set up
	ctx, cancel := context.WithTimeout(context.Background(), testvars.Timeout)
	defer cancel()
	baseT, err := initializeGeneralNetwork(ctx, runenv, testvars)
	if err != nil {
		return err
	}
	testData, err := initializeBitswapNetwork(ctx, runenv, testvars, baseT)

	transferNode := testData.node
	signalAndWaitForAll := testData.signalAndWaitForAll

	// Start still alive process if enabled
	testData.stillAlive(runenv, testvars)

	var tcpFetch int64

	// For each test permutation found in the test
	for pIndex, testParams := range testvars.Permutations {
		// Set up network (with traffic shaping)
		if err := utils.SetupNetwork(ctx, runenv, testData.nwClient, testData.nodetp, testData.tpindex, testParams.Latency,
			testParams.Bandwidth, testParams.JitterPct); err != nil {
			return fmt.Errorf("Failed to set up network: %v", err)
		}

		// Accounts for every file that couldn't be found.
		var leechFails int64
		var rootCid cid.Cid

		// Wait for all nodes to be ready to start the run
		err = signalAndWaitForAll(fmt.Sprintf("start-file-%d", pIndex))
		if err != nil {
			return err
		}

		switch testData.nodetp {
		case utils.Seed:
			rootCid, err = testData.addPublishFile(ctx, pIndex, testParams.File, runenv, testvars)
		case utils.Leech:
			rootCid, err = testData.readFile(ctx, pIndex, runenv, testvars)
		}
		if err != nil {
			return err
		}

		runenv.RecordMessage("File injest complete...")
		// Wait for all nodes to be ready to dial
		err = signalAndWaitForAll(fmt.Sprintf("injest-complete-%d", pIndex))
		if err != nil {
			return err
		}

		if testvars.TCPEnabled {
			runenv.RecordMessage("Running TCP test...")
			switch testData.nodetp {
			case utils.Seed:
				err = testData.runTCPServer(ctx, pIndex, 0, testParams.File, runenv, testvars)
			case utils.Leech:
				tcpFetch, err = testData.runTCPFetch(ctx, pIndex, 0, runenv, testvars)
			}
			if err != nil {
				return err
			}
		}

		runenv.RecordMessage("Starting %s Fetch...", nodeType)

		for runNum := 1; runNum < testvars.RunCount+1; runNum++ {
			// Reset the timeout for each run
			sctx, cancel := context.WithTimeout(ctx, testvars.RunTimeout)
			defer cancel()

			runID := fmt.Sprintf("%d-%d", pIndex, runNum)

			// Wait for all nodes to be ready to start the run
			err = signalAndWaitForAll("start-run-" + runID)
			if err != nil {
				return err
			}

			runenv.RecordMessage("Starting run %d / %d (%d bytes)", runNum, testvars.RunCount, testParams.File.Size())

			dialed, err := testData.dialFn(sctx, transferNode.Host(), testData.nodetp, testData.peerInfos, testvars.MaxConnectionRate)
			if err != nil {
				return err
			}
			runenv.RecordMessage("%s Dialed %d other nodes", testData.nodetp.String(), len(dialed))

			// Wait for all nodes to be connected
			err = signalAndWaitForAll("connect-complete-" + runID)
			if err != nil {
				return err
			}

			/// --- Start test

			var timeToFetch time.Duration
			if testData.nodetp == utils.Leech {
				// For each wave
				for waveNum := 0; waveNum < testvars.NumWaves; waveNum++ {
					// Only leecheers for that wave entitled to leech.
					if (testData.tpindex % testvars.NumWaves) == waveNum {
						runenv.RecordMessage("Starting wave %d", waveNum)
						// Stagger the start of the first request from each leech
						// Note: seq starts from 1 (not 0)
						startDelay := time.Duration(testData.seq-1) * testvars.RequestStagger

						runenv.RecordMessage("Starting to leech %d / %d (%d bytes)", runNum, testvars.RunCount, testParams.File.Size())
						runenv.RecordMessage("Leech fetching data after %s delay", startDelay)
						start := time.Now()
						// TODO: Here we may be able to define requesting pattern. ipfs.DAG()
						// Right now using a path.
						ctxFetch, cancel := context.WithTimeout(sctx, testvars.RunTimeout/2)
						// Pin Add also traverse the whole DAG
						// err := ipfsNode.API.Pin().Add(ctxFetch, fPath)
						rcvFile, err := transferNode.Fetch(ctxFetch, rootCid, testData.peerInfos)
						if err != nil {
							runenv.RecordMessage("Error fetching data: %v", err)
							leechFails++
						} else {
							runenv.RecordMessage("Fetch complete, proceeding")
							err = files.WriteTo(rcvFile, "/tmp/"+strconv.Itoa(testData.tpindex)+time.Now().String())
							if err != nil {
								cancel()
								return err
							}
							timeToFetch = time.Since(start)
							s, _ := rcvFile.Size()
							runenv.RecordMessage("Leech fetch of %d complete (%d ns) for wave %d", s, timeToFetch, waveNum)
						}
						cancel()
					}
					if waveNum < testvars.NumWaves-1 {
						runenv.RecordMessage("Waiting 5 seconds between waves for wave %d", waveNum)
						time.Sleep(5 * time.Second)
					}
					_, err = testData.client.SignalAndWait(sctx, sync.State(fmt.Sprintf("leech-wave-%d", waveNum)), testvars.LeechCount)
				}
			}

			// Wait for all leeches to have downloaded the data from seeds
			err = signalAndWaitForAll("transfer-complete-" + runID)
			if err != nil {
				return err
			}

			/// --- Report stats
			err = testData.emitMetrics(runenv, runNum, nodeType, testParams, timeToFetch, tcpFetch, leechFails, testvars.MaxConnectionRate)
			if err != nil {
				return err
			}
			runenv.RecordMessage("Finishing emitting metrics. Starting to clean...")

			// Sleep a bit to allow the rest of the trickled messages to complete
			//runenv.RecordMessage("Sleeping for 5 seconds to allow trickle messages to complete")
			//time.Sleep(5 * time.Second)

			err = testData.cleanupRun(sctx, rootCid, runenv)
			if err != nil {
				return err
			}
		}
		err = testData.cleanupFile(ctx, rootCid)
		if err != nil {
			return err
		}
	}
	err = testData.close()
	if err != nil {
		return err
	}

	runenv.RecordMessage("Ending testcase")
	return nil
}

func initializeGeneralNetwork(ctx context.Context, runenv *runtime.RunEnv, testvars *TestVars) (*TestData, error) {
	client := sync.MustBoundClient(ctx, runenv)
	nwClient := network.NewClient(client, runenv)

	nConfig, err := utils.GenerateAddrInfo(nwClient.MustGetDataNetworkIP().String())
	if err != nil {
		runenv.RecordMessage("Error generating node config")
		return nil, err
	}

	peers := sync.NewTopic("peers", &peer.AddrInfo{})

	// Get sequence number of this host
	seq, err := client.Publish(ctx, peers, *nConfig.AddrInfo)
	if err != nil {
		return nil, err
	}
	// Type of node and identifiers assigned.
	grpseq, nodetp, tpindex, err := parseType(ctx, runenv, client, nConfig.AddrInfo, seq)
	if err != nil {
		return nil, err
	}

	peerInfos := sync.NewTopic("peerInfos", &utils.PeerInfo{})
	// Publish peer info for dialing
	_, err = client.Publish(ctx, peerInfos, &utils.PeerInfo{Addr: *nConfig.AddrInfo, Nodetp: nodetp})
	if err != nil {
		return nil, err
	}

	var dialFn dialer.Dialer = dialer.DialOtherPeers
	if testvars.Dialer == "sparse" {
		dialFn = dialer.SparseDial
	}

	var seedIndex int64
	if nodetp == utils.Seed {
		if runenv.TestGroupID == "" {
			// If we're not running in group mode, calculate the seed index as
			// the sequence number minus the other types of node (leech / passive).
			// Note: sequence number starts from 1 (not 0)
			seedIndex = seq - int64(testvars.LeechCount+testvars.PassiveCount) - 1
		} else {
			// If we are in group mode, signal other seed nodes to work out the
			// seed index
			seedSeq, err := getNodeSetSeq(ctx, client, nConfig.AddrInfo, "seeds")
			if err != nil {
				return nil, err
			}
			// Sequence number starts from 1 (not 0)
			seedIndex = seedSeq - 1
		}
	}
	runenv.RecordMessage("Seed index %v for: %v", &nConfig.AddrInfo.ID, seedIndex)

	// Get addresses of all peers
	peerCh := make(chan *utils.PeerInfo)
	sctx, cancelSub := context.WithCancel(ctx)
	if _, err := client.Subscribe(sctx, peerInfos, peerCh); err != nil {
		cancelSub()
		return nil, err
	}
	infos, err := dialer.PeerInfosFromChan(peerCh, runenv.TestInstanceCount)
	if err != nil {
		cancelSub()
		return nil, fmt.Errorf("no addrs in %d seconds", testvars.Timeout/time.Second)
	}
	cancelSub()
	runenv.RecordMessage("Got all addresses from other peers and network setup")

	/// --- Warm up

	// Signal that this node is in the given state, and wait for all peers to
	// send the same signal
	signalAndWaitForAll := func(state string) error {
		_, err := client.SignalAndWait(ctx, sync.State(state), runenv.TestInstanceCount)
		return err
	}

	return &TestData{client, nwClient,
		nConfig, infos, dialFn, signalAndWaitForAll,
		seq, grpseq, nodetp, tpindex, seedIndex}, nil
}

func initializeBitswapNetwork(ctx context.Context, runenv *runtime.RunEnv, testvars *TestVars, baseT *TestData) (*NodeTestData, error) {
	h, err := makeHost(baseT)
	if err != nil {
		return nil, err
	}
	runenv.RecordMessage("I am %s with addrs: %v", h.ID(), h.Addrs())

	// Use the same blockstore on all runs for the seed node
	bstoreDelay := time.Duration(runenv.IntParam("bstore_delay_ms")) * time.Millisecond

	dStore, err := utils.CreateDatastore(testvars.DiskStore, bstoreDelay)
	if err != nil {
		return nil, err
	}
	runenv.RecordMessage("created data store %T with params disk_store=%b", dStore, testvars.DiskStore)
	bstore, err := utils.CreateBlockstore(ctx, dStore)
	if err != nil {
		return nil, err
	}
	// Create a new bitswap node from the blockstore
	bsnode, err := utils.CreateBitswapNode(ctx, h, bstore)
	if err != nil {
		return nil, err
	}

	return &NodeTestData{baseT, bsnode, &h}, nil
}

func makeHost(baseT *TestData) (host.Host, error) {
	// Create libp2p node
	privKey, err := crypto.UnmarshalPrivateKey(baseT.nConfig.PrivKey)
	if err != nil {
		return nil, err
	}

	return libp2p.New(libp2p.Identity(privKey), libp2p.ListenAddrs(baseT.nConfig.AddrInfo.Addrs...))
}
