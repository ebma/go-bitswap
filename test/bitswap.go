package test

import (
	"context"
	"fmt"
	"github.com/ipfs/go-cid"
	files "github.com/ipfs/go-ipfs-files"
	logging "github.com/ipfs/go-log"
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

func makeHost(baseT *BaseTestData) (host.Host, error) {
	// Create libp2p node
	privKey, err := crypto.UnmarshalPrivateKey(baseT.nConfig.PrivKey)
	if err != nil {
		return nil, err
	}

	return libp2p.New(libp2p.Identity(privKey), libp2p.ListenAddrs(baseT.nConfig.AddrInfo.Addrs...))
}

func initializeBaseNetwork(ctx context.Context, runenv *runtime.RunEnv) (*BaseTestData, error) {
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

	return &BaseTestData{client, nwClient, nConfig, seq}, nil
}

func initializeNodeTypeAndPeers(
	ctx context.Context,
	runenv *runtime.RunEnv,
	testvars *TestVars,
	baseTestData *BaseTestData,
	eavesdropperCount int,
) (*TestData, error) {
	// Type of node and identifiers assigned.
	seq, nodetp, tpindex, err := parseType(
		runenv,
		baseTestData.seq,
		eavesdropperCount,
	)
	if err != nil {
		return nil, err
	}

	peerInfos := sync.NewTopic(fmt.Sprintf("peerInfos-%d", eavesdropperCount), &utils.PeerInfo{})
	// Publish peer info for dialing
	_, err = baseTestData.client.Publish(
		ctx,
		peerInfos,
		&utils.PeerInfo{Addr: *baseTestData.nConfig.AddrInfo, Nodetp: nodetp},
	)
	if err != nil {
		return nil, err
	}

	var dialFn dialer.Dialer = dialer.DialOtherPeers
	if testvars.Dialer == "sparse" {
		dialFn = dialer.SparseDial
	}

	var seedIndex int64
	if nodetp == utils.Seed {
		// If we're not running in group mode, calculate the seed index as
		// the sequence number minus the other types of node (leech / passive).
		// Note: sequence number starts from 1 (not 0)
		seedIndex = baseTestData.seq - int64(testvars.LeechCount+testvars.PassiveCount) - 1
	}
	runenv.RecordMessage("Seed index %v for: %v", &baseTestData.nConfig.AddrInfo.ID, seedIndex)

	// Get addresses of all peers
	peerCh := make(chan *utils.PeerInfo)
	sctx, cancelSub := context.WithCancel(ctx)
	if _, err := baseTestData.client.Subscribe(sctx, peerInfos, peerCh); err != nil {
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
		_, err := baseTestData.client.SignalAndWait(
			ctx,
			sync.State(state),
			runenv.TestInstanceCount,
		)
		return err
	}

	return &TestData{baseTestData,
		infos, dialFn, signalAndWaitForAll,
		seq, nodetp, tpindex, seedIndex}, nil
}

func initializeBitswapNetwork(
	ctx context.Context,
	runenv *runtime.RunEnv,
	testvars *TestVars,
	baseT *TestData,
	h host.Host,
	delay time.Duration,
) (*NetworkTestData, error) {
	// Use the same blockstore on all runs for the seed node
	bstoreDelay := time.Duration(runenv.IntParam("bstore_delay_ms")) * time.Millisecond

	dStore, err := utils.CreateDatastore(testvars.DiskStore, bstoreDelay)
	if err != nil {
		return nil, err
	}
	runenv.RecordMessage(
		"created data store %T with params disk_store=%b",
		dStore,
		testvars.DiskStore,
	)
	bstore, err := utils.CreateBlockstore(ctx, dStore)
	if err != nil {
		return nil, err
	}
	// Create a new bitswap node from the blockstore
	bsnode, err := utils.CreateBitswapNode(ctx, h, bstore, delay)
	if err != nil {
		return nil, err
	}

	return &NetworkTestData{baseT, bsnode, &h}, nil
}

// Launch bitswap nodes and connect them to each other.
func BitswapTransferTest(runenv *runtime.RunEnv, initCtx *run.InitContext) error {
	testvars, err := getEnvVars(runenv)
	if err != nil {
		return err
	}
	//logging.SetLogLevel("bitswap", "DEBUG")
	//logging.SetLogLevel("messagequeue", "DEBUG")
	//logging.SetLogLevel("*", "DEBUG")

	/// --- Set up
	ctx, cancel := context.WithTimeout(context.Background(), testvars.Timeout)
	defer cancel()

	baseTestData, err := initializeBaseNetwork(ctx, runenv)
	if err != nil {
		return err
	}

	globalInfoRecorder := newGlobalInfoRecorder(runenv)

	// Run test with different topologies
	for _, eavesdropperCount := range testvars.EavesdropperCount {
		runenv.RecordMessage("Running test with %v eavesdroppers", eavesdropperCount)
		testData, err := initializeNodeTypeAndPeers(
			ctx,
			runenv,
			testvars,
			baseTestData,
			eavesdropperCount,
		)
		if err != nil {
			return err
		}

		// Initialize libp2p host
		// This has to be closed and re-initialized for each test run of eavesdroppers, since the dialed connections of the host change
		h, err := makeHost(baseTestData)
		if err != nil {
			return err
		}
		runenv.RecordMessage("I am %s with addrs: %v", h.ID(), h.Addrs())

		var tcpFetch int64

		// For each test permutation found in the test
		for pIndex, testParams := range testvars.Permutations {
			runenv.RecordMessage("Running test permutation %d", pIndex)

			// Initialize the bitswap node with trickling delay of test permutation
			tricklingDelay := testParams.TricklingDelay
			nodeTestData, err := initializeBitswapNetwork(
				ctx,
				runenv,
				testvars,
				testData,
				h,
				tricklingDelay,
			)
			transferNode := nodeTestData.node
			signalAndWaitForAll := nodeTestData.signalAndWaitForAll
			// Start still alive process if enabled
			nodeTestData.stillAlive(runenv, testvars)

			// Log node info
			globalInfoRecorder.RecordNodeInfo(
				fmt.Sprintf(
					"\"topology\": \"%s\", \"nodeId\": \"%s\", \"nodeType\": \"%s\"",
					CreateTopologyString(
						runenv.TestInstanceCount,
						testvars.LeechCount,
						testvars.PassiveCount,
						eavesdropperCount,
					),
					h.ID().String(),
					nodeTestData.nodetp.String(),
				),
			)

			// Set up network (with traffic shaping)
			if err := utils.SetupNetwork(ctx, runenv, nodeTestData.nwClient, nodeTestData.nodetp, nodeTestData.tpindex, testParams.Latency,
				testParams.Bandwidth, testParams.JitterPct); err != nil {
				return fmt.Errorf("Failed to set up network: %v", err)
			}

			// Accounts for every file that couldn't be found.
			var leechFails int64
			var rootCid cid.Cid

			// Wait for all nodes to be ready to start the run
			err = signalAndWaitForAll(fmt.Sprintf("start-file-%d-%d", eavesdropperCount, pIndex))
			if err != nil {
				return err
			}

			switch nodeTestData.nodetp {
			case utils.Seed:
				rootCid, err = nodeTestData.addPublishFile(
					ctx,
					pIndex,
					testParams.File,
					runenv,
					testvars,
				)
			case utils.Leech:
				logging.SetLogLevel("bs:peermgr", "DEBUG")
				rootCid, err = nodeTestData.readFile(ctx, pIndex, runenv, testvars)
			}
			if err != nil {
				return err
			}

			runenv.RecordMessage("File injest complete...")
			// Wait for all nodes to be ready to dial
			err = signalAndWaitForAll(
				fmt.Sprintf("injest-complete-%d-%d", eavesdropperCount, pIndex),
			)
			if err != nil {
				return err
			}

			if testvars.TCPEnabled {
				runenv.RecordMessage("Running TCP test...")
				switch nodeTestData.nodetp {
				case utils.Seed:
					err = nodeTestData.runTCPServer(
						ctx,
						pIndex,
						0,
						testParams.File,
						runenv,
						testvars,
					)
				case utils.Leech:
					tcpFetch, err = nodeTestData.runTCPFetch(ctx, pIndex, 0, runenv, testvars)
				}
				if err != nil {
					return err
				}
			}

			runenv.RecordMessage("Starting %s Fetch...")

			for runNum := 1; runNum < testvars.RunCount+1; runNum++ {
				// Reset the timeout for each run
				sctx, cancel := context.WithTimeout(ctx, testvars.RunTimeout)
				defer cancel()

				// Used for logging
				meta := CreateMetaFromParams(
					runenv,
					runNum,
					eavesdropperCount,
					nodeTestData.seq,
					testParams.Latency,
					testParams.Bandwidth,
					int(testParams.File.Size()),
					nodeTestData.nodetp,
					nodeTestData.tpindex,
					testvars.MaxConnectionRate,
					pIndex,
					tricklingDelay,
				)

				runID := fmt.Sprintf("%d-%d", pIndex, runNum)

				// Wait for all nodes to be ready to start the run
				err = signalAndWaitForAll(
					fmt.Sprintf("start-run-%d-%d-%s", eavesdropperCount, pIndex, runID),
				)
				if err != nil {
					return err
				}

				runenv.RecordMessage(
					"Starting run %d / %d (%d bytes)",
					runNum,
					testvars.RunCount,
					testParams.File.Size(),
				)

				if nodeTestData.nodetp != utils.Eavesdropper {
					dialed, err := nodeTestData.dialFn(
						sctx,
						transferNode.Host(),
						nodeTestData.nodetp,
						nodeTestData.peerInfos,
						testvars.MaxConnectionRate,
					)
					runenv.RecordMessage(
						"%s Dialed %d other nodes",
						nodeTestData.nodetp.String(),
						len(dialed),
					)
					if err != nil {
						return err
					}
				}

				// Wait for normal nodes to be connected
				err = signalAndWaitForAll(
					fmt.Sprintf(
						"connect-normal-complete-%d-%d-%s",
						eavesdropperCount,
						pIndex,
						runID,
					),
				)
				if err != nil {
					return err
				}

				if nodeTestData.nodetp == utils.Eavesdropper {
					// Let eavesdropper nodes dial all peers
					// we do this separately from the other call because of a TCP error when many instances are running
					dialed, err := dialer.DialAllPeers(
						sctx,
						transferNode.Host(),
						nodeTestData.peerInfos,
					)
					runenv.RecordMessage(
						"%s Dialed %d other nodes",
						nodeTestData.nodetp.String(),
						len(dialed),
					)
					if err != nil {
						return err
					}
				}
				// Wait for eavesdropper nodes to be connected
				err = signalAndWaitForAll(
					fmt.Sprintf(
						"connect-eavesdropper-complete-%d-%d-%s",
						eavesdropperCount,
						pIndex,
						runID,
					),
				)
				if err != nil {
					return err
				}

				/// --- Start test
				var timeToFetch time.Duration
				if nodeTestData.nodetp == utils.Leech {
					globalInfoRecorder.RecordInfoWithMeta(
						meta,
						fmt.Sprintf(
							"\"peer\": \"%s\", \"lookingFor\": \"%s\"",
							nodeTestData.node.Host().ID().String(),
							rootCid.String(),
						),
					)
					runenv.RecordMessage(
						"Starting to leech %d / %d (%d bytes)",
						runNum,
						testvars.RunCount,
						testParams.File.Size(),
					)
					start := time.Now()
					ctxFetch, cancel := context.WithTimeout(sctx, testvars.RunTimeout/2)
					rcvFile, err := transferNode.Fetch(ctxFetch, rootCid, nodeTestData.peerInfos)
					if err != nil {
						runenv.RecordMessage("Error fetching data: %v", err)
						leechFails++
					} else {
						runenv.RecordMessage("Fetch complete, proceeding")
						err = files.WriteTo(rcvFile, "/tmp/"+strconv.Itoa(nodeTestData.tpindex)+time.Now().String())
						if err != nil {
							cancel()
							return err
						}
						timeToFetch = time.Since(start)
						s, _ := rcvFile.Size()
						runenv.RecordMessage("Leech fetch of %d complete (%d ns)", s, timeToFetch)
					}
					cancel()
				}

				// Wait for all leeches to have downloaded the data from seeds
				err = signalAndWaitForAll(
					fmt.Sprintf("transfer-complete-%d-%d-%s", eavesdropperCount, pIndex, runID),
				)
				if err != nil {
					return err
				}

				/// --- Report stats
				err = nodeTestData.emitMetrics(runenv, meta, timeToFetch, tcpFetch, leechFails)
				if err != nil {
					return err
				}
				err = nodeTestData.emitMessageHistory(
					runenv,
					meta,
					nodeTestData.node.Host().ID().String(),
				)
				if err != nil {
					return err
				}
				runenv.RecordMessage("Finishing emitting metrics. Starting to clean...")

				err = nodeTestData.cleanupRun(sctx, rootCid, runenv)
				if err != nil {
					return err
				}
			}
			err = nodeTestData.cleanupFile(ctx, rootCid)
			if err != nil {
				return err
			}
		}

		// Close host at end of eavesdropper test permutation
		if h != nil {
			err = h.Close()
			if err != nil {
				return err
			}
		}
	}

	runenv.RecordMessage("Ending testcase")
	return nil
}
