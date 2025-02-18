package test

import (
	"context"
	"fmt"
	"github.com/ipfs/go-cid"
	files "github.com/ipfs/go-ipfs-files"
	"github.com/ipfs/testground/plans/trickle-bitswap/test/utils"
	"github.com/ipfs/testground/plans/trickle-bitswap/test/utils/dialer"
	"github.com/libp2p/go-libp2p"
	"github.com/libp2p/go-libp2p/core/crypto"
	"github.com/libp2p/go-libp2p/core/host"
	"github.com/libp2p/go-libp2p/core/peer"
	"github.com/testground/sdk-go/network"
	"strconv"
	"time"

	"github.com/testground/sdk-go/run"
	"github.com/testground/sdk-go/runtime"
	"github.com/testground/sdk-go/sync"
)

func makeHost(baseT *BaseTestData) (host.Host, error) {
	// Create libp2p node
	privKey, err := crypto.UnmarshalPrivateKey(baseT.NConfig.PrivKey)
	if err != nil {
		return nil, err
	}

	return libp2p.New(libp2p.Identity(privKey), libp2p.ListenAddrs(baseT.NConfig.AddrInfo.Addrs...))
}

func initializeBaseNetwork(
	ctx context.Context,
	runenv *runtime.RunEnv,
) (*BaseTestData, error) {
	client := sync.MustBoundClient(ctx, runenv) // this is the issue with the 1h timeout
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

	return &BaseTestData{Client: client, NwClient: nwClient, NConfig: nConfig, Seq: seq}, nil
}

func initializeNodeTypeAndPeers(
	ctx context.Context,
	runenv *runtime.RunEnv,
	testvars *TestVars,
	baseTestData *BaseTestData,
) (*TestData, error) {
	// Type of node and identifiers assigned.
	seq, nodeType, typeIndex, err := ParseType(
		runenv,
		baseTestData.Seq,
		testvars.LeechCount,
		testvars.SeedCount,
		testvars.EavesdropperCount,
	)
	if err != nil {
		return nil, err
	}

	peerInfos := sync.NewTopic(fmt.Sprintf("peerInfos"), &utils.PeerInfo{})
	// Publish peer info for dialing
	_, err = baseTestData.Client.Publish(
		ctx,
		peerInfos,
		&utils.PeerInfo{
			Addr:      *baseTestData.NConfig.AddrInfo,
			Nodetp:    nodeType,
			Seq:       seq,
			TypeIndex: typeIndex,
		},
	)
	if err != nil {
		return nil, err
	}

	var seedIndex int64
	if nodeType == utils.Seed {
		// If we're not running in group mode, calculate the seed index as
		// the sequence number minus the other types of node (leech / passive).
		// Note: sequence number starts from 1 (not 0)
		seedIndex = baseTestData.Seq - int64(
			testvars.LeechCount+testvars.SeedCount+testvars.EavesdropperCount,
		) - 1
	}
	runenv.RecordMessage("Seed index %v for: %v", &baseTestData.NConfig.AddrInfo.ID, seedIndex)

	// Get addresses of all peers
	peerCh := make(chan *utils.PeerInfo)
	sctx, cancelSub := context.WithCancel(ctx)
	if _, err := baseTestData.Client.Subscribe(sctx, peerInfos, peerCh); err != nil {
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
		_, err := baseTestData.Client.SignalAndWait(
			ctx,
			sync.State(state),
			runenv.TestInstanceCount,
		)
		return err
	}

	return &TestData{baseTestData,
		infos, signalAndWaitForAll,
		seq, nodeType, typeIndex, seedIndex}, nil
}

func initializeBitswapNetwork(
	ctx context.Context,
	runenv *runtime.RunEnv,
	testvars *TestVars,
	baseT *TestData,
	h host.Host,
	delay time.Duration,
	isEavesdropper bool,
) (*NetworkTestData, error) {
	// Use the same blockstore on all runs for the seed node
	bstoreDelay := time.Duration(100) * time.Millisecond

	dStore, err := utils.CreateDatastore(false, bstoreDelay)
	if err != nil {
		return nil, err
	}
	runenv.RecordMessage(
		"created data store %T",
		dStore,
	)
	bstore, err := utils.CreateBlockstore(ctx, dStore)
	if err != nil {
		return nil, err
	}
	// Create a new bitswap node from the blockstore
	bsnode, err := utils.CreateBitswapNode(ctx, h, bstore, delay, isEavesdropper)
	if err != nil {
		return nil, err
	}

	return &NetworkTestData{baseT, bsnode, &h}, nil
}

// Launch bitswap nodes and connect them to each other.
func BitswapTransferTrickleTest(runenv *runtime.RunEnv, initCtx *run.InitContext) error {
	testVars, err := GetEnvVars(runenv)
	if err != nil {
		return err
	}
	//logging.SetLogLevel("bs:peermgr", "DEBUG")
	//logging.SetLogLevel("node", "DEBUG")
	//logging.SetLogLevel("*", "DEBUG")

	/// --- Set up
	ctx, cancel := context.WithTimeout(context.Background(), testVars.Timeout)
	defer cancel()

	baseTestData, err := initializeBaseNetwork(ctx, runenv)
	if err != nil {
		return err
	}

	globalInfoRecorder := NewGlobalInfoRecorder(runenv)

	// Run test with different topologies
	runenv.RecordMessage("Running test with %v eavesdroppers", testVars.EavesdropperCount)
	testData, err := initializeNodeTypeAndPeers(
		ctx,
		runenv,
		testVars,
		baseTestData,
	)
	if err != nil {
		return err
	}

	// Initialize libp2p host
	h, err := makeHost(baseTestData)
	if err != nil {
		return err
	}
	runenv.RecordMessage("I am %s with addrs: %v", h.ID(), h.Addrs())

	var tcpFetch int64

	// Set up network (with traffic shaping)
	if err := utils.SetupNetwork(ctx, runenv, testData.NwClient, testVars.Latency); err != nil {
		return fmt.Errorf("Failed to set up network: %v", err)
	}

	// For each test permutation found in the test
	for pIndex, testParams := range testVars.Permutations {
		pctx, pcancel := context.WithTimeout(ctx, testVars.Timeout)
		defer pcancel()

		runenv.RecordMessage(
			"Running test permutation %d, with latency %d and delay %d",
			pIndex,
			testVars.Latency,
			testParams.TricklingDelay,
		)

		// Initialize the bitswap node with trickling delay of test permutation
		tricklingDelay := testParams.TricklingDelay
		nodeTestData, err := initializeBitswapNetwork(
			pctx,
			runenv,
			testVars,
			testData,
			h,
			tricklingDelay,
			testData.NodeType == utils.Eavesdropper,
		)
		transferNode := nodeTestData.Node
		signalAndWaitForAll := nodeTestData.SignalAndWaitForAll

		//if nodeTestData.NodeType == utils.Leech || nodeTestData.NodeType == utils.Eavesdropper {
		//	logging.SetLogLevel("mq", "DEBUG")
		//	logging.SetLogLevel("bsize", "DEBUG")
		//	logging.SetLogLevel("bitswap", "DEBUG")
		//}

		// Log node info
		globalInfoRecorder.RecordNodeInfo(
			fmt.Sprintf(
				"\"nodeId\": \"%s\", \"nodeType\": \"%s\", \"dialer\": \"%s\", \"exType\": \"trickle\", \"eavesCount\": \"%d\"",
				h.ID().String(),
				nodeTestData.NodeType.String(),
				testVars.Dialer,
				testVars.EavesdropperCount,
			),
		)

		// Accounts for every file that couldn't be found.
		var leechFails int64
		var rootCid cid.Cid

		// Wait for all nodes to be ready to start the run
		err = signalAndWaitForAll(fmt.Sprintf("start-file-%d", pIndex))
		if err != nil {
			return err
		}

		switch nodeTestData.NodeType {
		case utils.Seed:
			rootCid, err = nodeTestData.AddPublishFile(
				pctx,
				string(rune(pIndex)),
				testParams.File,
				runenv,
			)
		case utils.Leech:
			rootCid, err = nodeTestData.ReadFile(pctx, string(rune(pIndex)), runenv, testVars)
		}
		if err != nil {
			return err
		}

		runenv.RecordMessage("File injest complete...")
		// Wait for all nodes to be ready to dial
		err = signalAndWaitForAll(
			fmt.Sprintf("injest-complete-%d", pIndex),
		)
		if err != nil {
			return err
		}

		if testVars.TCPEnabled {
			runenv.RecordMessage("Running TCP test...")
			runNum := 0
			switch nodeTestData.NodeType {
			case utils.Seed:
				err = nodeTestData.RunTCPServer(
					pctx,
					pIndex,
					runNum,
					testParams.File,
					runenv,
					testVars,
				)
			case utils.Leech:
				tcpFetch, err = nodeTestData.RunTCPFetch(pctx, pIndex, runNum, runenv, testVars)
			default:
				err = nodeTestData.SignalAndWaitForAll(
					fmt.Sprintf("tcp-fetch-%d-%d", pIndex, runNum),
				)
			}

			if err != nil {
				return err
			}
		}

		runenv.RecordMessage("Starting Fetch...")

		for runNum := 1; runNum < testVars.RunCount+1; runNum++ {
			// Reset the timeout for each run
			sctx, scancel := context.WithTimeout(pctx, testVars.RunTimeout)
			defer scancel()

			runID := fmt.Sprintf("%d-%d", pIndex, runNum)

			// Reset every node here again to be sure that the network is clean and no old messages are still in the queue
			// This is necessary because otherwise the pending messages from old runs interfere with the new run
			runenv.RecordMessage("Resetting node...")
			nodeTestData, err = initializeBitswapNetwork(
				pctx,
				runenv,
				testVars,
				testData,
				h,
				tricklingDelay,
				testData.NodeType == utils.Eavesdropper,
			)
			transferNode = nodeTestData.Node
			signalAndWaitForAll = nodeTestData.SignalAndWaitForAll

			err = signalAndWaitForAll(fmt.Sprintf("start-file-%s", runID))
			if err != nil {
				return err
			}

			switch nodeTestData.NodeType {
			case utils.Seed:
				rootCid, err = nodeTestData.AddPublishFile(
					pctx,
					runID,
					testParams.File,
					runenv,
				)
			case utils.Leech:
				rootCid, err = nodeTestData.ReadFile(pctx, runID, runenv, testVars)
			}
			if err != nil {
				return err
			}

			runenv.RecordMessage("File injest complete...")
			// Wait for all nodes to be ready to dial
			err = signalAndWaitForAll(
				fmt.Sprintf("injest-complete-%s", runID),
			)
			if err != nil {
				return err
			}

			// Used for logging
			meta := CreateMetaFromParams(
				pIndex,
				runNum,
				testVars.Dialer,
				testVars.EavesdropperCount,
				testVars.Latency,
				tricklingDelay,
				nodeTestData.Seq,
				int(testParams.File.Size()),
				nodeTestData.NodeType,
				nodeTestData.TypeIndex,
			)

			messageHistoryRecorder := NewMessageHistoryRecorder(
				runenv,
				meta,
				nodeTestData.Node.Host().ID().String(),
			)

			nodeTestData.Node.Instance().Server.Tracer = messageHistoryRecorder

			// Wait for all nodes to be ready to start the run
			err = signalAndWaitForAll(
				fmt.Sprintf("start-run-%s", runID),
			)
			if err != nil {
				return err
			}

			if nodeTestData.NodeType == utils.Leech {
				runenv.RecordMessage(
					"Starting run %d / %d (%d bytes) | Permutation %d",
					runNum,
					testVars.RunCount,
					testParams.File.Size(),
					pIndex,
				)
			}

			if nodeTestData.NodeType != utils.Eavesdropper {
				var dialed []peer.AddrInfo
				if testVars.Dialer == "edge" {
					dialed, err = dialer.DialFixedTopologyEdgeLeech(
						sctx,
						transferNode.Host(),
						nodeTestData.NodeType,
						nodeTestData.TypeIndex,
						nodeTestData.PeerInfos,
					)
				} else if testVars.Dialer == "center" {
					dialed, err = dialer.DialFixedTopologyCenteredLeech(
						sctx,
						transferNode.Host(),
						nodeTestData.NodeType,
						nodeTestData.TypeIndex,
						nodeTestData.PeerInfos,
					)
				} else {
					panic("Unknown dialer type")
				}
				runenv.RecordMessage(
					"%s %d Dialed %d other nodes (%s)",
					nodeTestData.NodeType.String(),
					nodeTestData.TypeIndex,
					len(dialed),
					testVars.Dialer,
				)
				if err != nil {
					return err
				}
			}

			// Wait for normal nodes to be connected
			err = signalAndWaitForAll(
				fmt.Sprintf(
					"connect-normal-complete-%s",
					runID,
				),
			)
			if err != nil {
				return err
			}

			if nodeTestData.NodeType == utils.Eavesdropper {
				// Let eavesdropper nodes dial all peers
				// we do this separately from the other call because of a TCP error when many instances are running
				dialed, err := dialer.DialAllPeers(
					sctx,
					transferNode.Host(),
					nodeTestData.NodeType,
					nodeTestData.PeerInfos,
				)
				runenv.RecordMessage(
					"%s Dialed %d other nodes",
					nodeTestData.NodeType.String(),
					len(dialed),
				)
				if err != nil {
					return err
				}
			}
			// Wait for eavesdropper nodes to be connected
			err = signalAndWaitForAll(
				fmt.Sprintf(
					"connect-eavesdropper-complete-%s",
					runID,
				),
			)
			if err != nil {
				return err
			}

			/// --- Start test
			var timeToFetch time.Duration
			if nodeTestData.NodeType == utils.Leech {
				globalInfoRecorder.RecordInfoWithMeta(
					meta,
					fmt.Sprintf(
						"\"peer\": \"%s\", \"lookingFor\": \"%s\"",
						nodeTestData.Node.Host().ID().String(),
						rootCid.String(),
					),
				)
				runenv.RecordMessage(
					"Starting to leech %d / %d (%d bytes) | Permutation: %d",
					runNum,
					testVars.RunCount,
					testParams.File.Size(),
					pIndex)
				start := time.Now()
				ctxFetch, fetchCancel := context.WithTimeout(sctx, testVars.RunTimeout)
				rcvFile, err := transferNode.Fetch(ctxFetch, rootCid, nodeTestData.PeerInfos)
				if err != nil {
					runenv.RecordMessage("Error fetching data: %v", err)
					leechFails++
				} else {
					runenv.RecordMessage("Fetch complete, proceeding")
					err = files.WriteTo(rcvFile, "/tmp/"+strconv.Itoa(nodeTestData.TypeIndex)+time.Now().String())
					if err != nil {
						fetchCancel()
						return err
					}
					timeToFetch = time.Since(start)
					s, _ := rcvFile.Size()
					runenv.RecordMessage("Leech fetch of %d complete (%d ns)", s, timeToFetch)
				}
				fetchCancel()
			}

			// Wait for all leeches to have downloaded the data from seeds
			err = signalAndWaitForAll(
				fmt.Sprintf("transfer-complete-%s", runID),
			)
			if err != nil {
				return err
			}

			/// --- Report stats
			err = nodeTestData.EmitMetrics(runenv, meta, timeToFetch, tcpFetch, leechFails)
			if err != nil {
				return err
			}

			runenv.RecordMessage("Finishing emitting metrics. Starting to clean...")

			// Disconnect and clear data
			err = nodeTestData.CleanupRun(sctx, rootCid, runenv)
			if err != nil {
				return err
			}
			// wait for all nodes to finish cleanup
			err = signalAndWaitForAll(
				fmt.Sprintf(
					"cleanup-complete-%s",
					runID,
				),
			)
		}
		// cancel permutation context
		pcancel()
	}

	// Close host at end of eavesdropper test permutation
	if h != nil {
		err = h.Close()
		if err != nil {
			return err
		}
	}

	runenv.RecordMessage("Ending testcase")
	return nil
}
