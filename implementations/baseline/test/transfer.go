package test

import (
	"context"
	"fmt"
	"github.com/ipfs/go-cid"
	files "github.com/ipfs/go-ipfs-files"
	logging "github.com/ipfs/go-log"
	"github.com/ipfs/testground/plans/trickle-bitswap/test/utils"
	"github.com/ipfs/testground/plans/trickle-bitswap/test/utils/dialer"
	"github.com/libp2p/go-libp2p/core/peer"
	"github.com/testground/sdk-go/network"
	"strconv"
	"time"

	"github.com/testground/sdk-go/run"
	"github.com/testground/sdk-go/runtime"
	"github.com/testground/sdk-go/sync"
)

func initializeBaseNetwork(
	ctx context.Context,
	runenv *runtime.RunEnv,
) (*BaseTestData, error) {
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
			testvars.LeechCount+testvars.SeedCount,
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

func initializeIPFSTest(ctx context.Context, runenv *runtime.RunEnv, baseT *TestData) (*NetworkTestData, error) {
	ipfsNode, err := utils.CreateIPFSNodeWithConfig(ctx, baseT.NConfig, runenv)

	if err != nil {
		runenv.RecordFailure(err)
		return nil, err
	}

	err = baseT.SignalAndWaitForAll("file-list-ready")
	if err != nil {
		return nil, err
	}

	host := ipfsNode.Host()
	return &NetworkTestData{
		baseT,
		ipfsNode,
		&host,
	}, nil
}

// Launch bitswap nodes and connect them to each other.
func BitswapTransferBaselineTest(runenv *runtime.RunEnv, initCtx *run.InitContext) error {
	testVars, err := GetEnvVars(runenv)
	if err != nil {
		return err
	}
	logging.SetLogLevel("bs:peermgr", "DEBUG")
	logging.SetLogLevel("dagadder", "DEBUG")
	logging.SetLogLevel("node", "DEBUG")
	//logging.SetLogLevel("bitswap", "DEBUG")
	//logging.SetLogLevel("*", "DEBUG")

	/// --- Set up
	ctx, cancel := context.WithTimeout(context.Background(), testVars.Timeout)
	defer cancel()

	baseTestData, err := initializeBaseNetwork(ctx, runenv)
	if err != nil {
		return err
	}

	globalInfoRecorder := NewGlobalInfoRecorder(runenv)

	testData, err := initializeNodeTypeAndPeers(
		ctx,
		runenv,
		testVars,
		baseTestData,
	)
	if err != nil {
		return err
	}

	var tcpFetch int64

	// Set up network (with traffic shaping)
	if err := utils.SetupNetwork(ctx, runenv, testData.NwClient, testVars.Latency); err != nil {
		return fmt.Errorf("Failed to set up network: %v", err)
	}

	// For each test permutation found in the test
	for pIndex, testParams := range testVars.Permutations {
		pctx, pcancel := context.WithTimeout(ctx, testVars.Timeout)

		runenv.RecordMessage(
			"Running test permutation %d, with latency %d",
			pIndex,
			testVars.Latency,
		)

		// Initialize the bitswap node with trickling delay of test permutation
		nodeTestData, err := initializeIPFSTest(
			pctx,
			runenv,
			testData,
		)
		transferNode := nodeTestData.Node
		signalAndWaitForAll := nodeTestData.SignalAndWaitForAll

		// Log node info
		globalInfoRecorder.RecordNodeInfo(
			fmt.Sprintf(
				"\"nodeId\": \"%s\", \"nodeType\": \"%s\"",
				transferNode.Host().ID().String(),
				nodeTestData.NodeType.String(),
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
				pIndex,
				testParams.File,
				runenv,
			)
		case utils.Leech:
			rootCid, err = nodeTestData.ReadFile(pctx, pIndex, runenv, testVars)
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

			// Used for logging
			meta := CreateMetaFromParams(
				pIndex,
				runNum,
				testVars.Dialer,
				0,
				testVars.Latency,
				nodeTestData.Seq,
				int(testParams.File.Size()),
				nodeTestData.NodeType,
				nodeTestData.TypeIndex,
			)

			runID := fmt.Sprintf("%d-%d", pIndex, runNum)

			// Wait for all nodes to be ready to start the run
			err = signalAndWaitForAll(
				fmt.Sprintf("start-run-%s", runID),
			)
			if err != nil {
				return err
			}

			if nodeTestData.NodeType == utils.Leech {
				runenv.RecordMessage(
					"Starting run %d / %d (%d bytes)",
					runNum,
					testVars.RunCount,
					testParams.File.Size(),
				)
			}

			var dialed []peer.AddrInfo
			if testVars.Dialer == "edge" {
				dialed, err = dialer.DialFixedTopology(
					sctx,
					transferNode.Host(),
					nodeTestData.NodeType,
					nodeTestData.TypeIndex,
					nodeTestData.PeerInfos,
				)
			} else if testVars.Dialer == "center" {
				// TODO
			} else {
				panic("Unknown dialer type")
			}
			runenv.RecordMessage(
				"%s Dialed %d other nodes",
				nodeTestData.NodeType.String(),
				len(dialed),
			)
			if err != nil {
				return err
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

			/// --- Start test
			var timeToFetch time.Duration
			if nodeTestData.NodeType == utils.Leech {
				globalInfoRecorder.RecordInfoWithMeta(
					meta,
					fmt.Sprintf(
						"\"peer\": \"%s\", \"lookingFor\": \"%s\"",
						transferNode.Host().ID().String(),
						rootCid.String(),
					),
				)
				runenv.RecordMessage(
					"Starting to leech %d / %d (%d bytes)",
					runNum,
					testVars.RunCount,
					testParams.File.Size(),
				)
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
					runenv.RecordMessage("Leech fetch of %d complete (%d ms)", s, timeToFetch.Milliseconds())
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
		}
		err = nodeTestData.CleanupFile(pctx, rootCid)
		if err != nil {
			return err
		}

		// cancel permutation context
		pcancel()
	}

	runenv.RecordMessage("Ending testcase")
	return nil
}
