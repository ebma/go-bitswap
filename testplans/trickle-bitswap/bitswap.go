package main

import (
	"context"
	"fmt"
	"github.com/ipfs/go-bitswap"
	bsnet "github.com/ipfs/go-bitswap/network"
	"github.com/ipfs/go-cid"
	"github.com/ipfs/go-datastore"
	blockstore "github.com/ipfs/go-ipfs-blockstore"
	exchange "github.com/ipfs/go-ipfs-exchange-interface"
	"github.com/libp2p/go-libp2p"
	"github.com/libp2p/go-libp2p-core/peer"
	"github.com/multiformats/go-multiaddr"
	"github.com/multiformats/go-multihash"
	"math/rand"
	"time"

	"github.com/testground/sdk-go/network"
	"github.com/testground/sdk-go/run"
	"github.com/testground/sdk-go/runtime"
	"github.com/testground/sdk-go/sync"

	block "github.com/ipfs/go-block-format"
	bstats "github.com/ipfs/go-ipfs-regression/bitswap"

	"github.com/libp2p/go-libp2p-core/host"
	"github.com/libp2p/go-libp2p-core/routing"
)

var (
	networkState  = sync.State("network-configured")
	readyState    = sync.State("ready-to-publish")
	readyDLState  = sync.State("ready-to-download")
	doneState     = sync.State("done")
	providerTopic = sync.NewTopic("provider", &peer.AddrInfo{})
	blockTopic    = sync.NewTopic("blocks", &multihash.Multihash{})
)

// Launch bitswap nodes and connect them to each other.
func BitswapSpeedTest(runenv *runtime.RunEnv, initCtx *run.InitContext) error {
	var (
		ctx = context.Background()
	)

	var router routing.ContentRouting

	client := sync.MustBoundClient(ctx, runenv)
	defer client.Close()

	initCtx.NetClient.MustConfigureNetwork(ctx, &network.Config{
		Network:        "default",
		Enable:         true,
		Default:        network.LinkShape{},
		CallbackState:  networkState,
		CallbackTarget: runenv.TestGroupInstanceCount,
		RoutingPolicy:  network.AllowAll,
	})

	seq := client.MustSignalEntry(ctx, networkState)
	runenv.RecordMessage("network configured, my sequence ID is %d", seq)

	port :=

	listen, err := multiaddr.NewMultiaddr(fmt.Sprintf("/ip4/%s/tcp/3333", initCtx.NetClient.MustGetDataNetworkIP().String()))
	if err != nil {
		return err
	}
	h, err := libp2p.New(libp2p.ListenAddrs(listen))
	if err != nil {
		return err
	}
	for _, a := range h.Addrs() {
		runenv.RecordMessage("listening on addr: %s", a.String())
	}

	bitswapNetwork := bsnet.NewFromIpfsHost(h, router)
	bstore := blockstore.NewBlockstore(datastore.NewMapDatastore())
	excha := bitswap.New(ctx, bitswapNetwork, bstore)

	if seq%2 == 0 {
		runenv.RecordMessage("running provider")
		err = runProvide(ctx, runenv, h, bstore, excha)
	} else {
		runenv.RecordMessage("running requestor")
		err = runRequest(ctx, runenv, h, bstore, excha)
	}

	return err
}

func runProvide(ctx context.Context, runenv *runtime.RunEnv, h host.Host, bstore blockstore.Blockstore, ex exchange.Interface) error {
	tgc := sync.MustBoundClient(ctx, runenv)
	ai := peer.AddrInfo{
		ID:    h.ID(),
		Addrs: h.Addrs(),
	}
	tgc.MustPublish(ctx, providerTopic, &ai)
	tgc.MustSignalAndWait(ctx, readyState, runenv.TestInstanceCount)

	size := runenv.SizeParam("size")
	count := runenv.IntParam("count")
	for i := 0; i <= count; i++ {
		runenv.RecordMessage("generating %d-sized random block", size)
		buf := make([]byte, size)
		rand.Read(buf)
		blk := block.NewBlock(buf)
		err := bstore.Put(ctx, blk)
		if err != nil {
			return err
		}
		//err = ex.HasBlock(blk)
		//if err != nil {
		//	return err
		//}
		mh := blk.Multihash()
		runenv.RecordMessage("publishing block %s", mh.String())
		tgc.MustPublish(ctx, blockTopic, &mh)
	}
	tgc.MustSignalAndWait(ctx, readyDLState, runenv.TestInstanceCount)
	tgc.MustSignalAndWait(ctx, doneState, runenv.TestInstanceCount)
	return nil
}

func runRequest(ctx context.Context, runenv *runtime.RunEnv, h host.Host, bstore blockstore.Blockstore, ex exchange.Interface) error {
	tgc := sync.MustBoundClient(ctx, runenv)
	providers := make(chan *peer.AddrInfo)
	blkmhs := make(chan *multihash.Multihash)
	providerSub, err := tgc.Subscribe(ctx, providerTopic, providers)
	if err != nil {
		return err
	}
	ai := <-providers

	runenv.RecordMessage("connecting  to provider provider: %s", fmt.Sprint(*ai))
	providerSub.Done()

	err = h.Connect(ctx, *ai)
	if err != nil {
		return fmt.Errorf("could not connect to provider: %w", err)
	}

	runenv.RecordMessage("connected to provider")

	blockmhSub, err := tgc.Subscribe(ctx, blockTopic, blkmhs)
	if err != nil {
		return fmt.Errorf("could not subscribe to block sub: %w", err)
	}
	defer blockmhSub.Done()

	// tell the provider that we're ready for it to publish blocks
	tgc.MustSignalAndWait(ctx, readyState, runenv.TestInstanceCount)
	// wait until the provider is ready for us to start downloading
	tgc.MustSignalAndWait(ctx, readyDLState, runenv.TestInstanceCount)

	begin := time.Now()
	count := runenv.IntParam("count")
	for i := 0; i <= count; i++ {
		mh := <-blkmhs
		runenv.RecordMessage("downloading block %s", mh.String())
		dlBegin := time.Now()
		blk, err := ex.GetBlock(ctx, cid.NewCidV0(*mh))
		if err != nil {
			return fmt.Errorf("could not download get block %s: %w", mh.String(), err)
		}
		dlDuration := time.Since(dlBegin)
		s := &bstats.BitswapStat{
			SingleDownloadSpeed: &bstats.SingleDownloadSpeed{
				Cid:              blk.Cid().String(),
				DownloadDuration: dlDuration,
			},
		}
		runenv.RecordMessage(bstats.Marshal(s))

		stored, err := bstore.Has(ctx, blk.Cid())
		if err != nil {
			return fmt.Errorf("error checking if blck was stored %s: %w", mh.String(), err)
		}
		if !stored {
			return fmt.Errorf("block was not stored %s: %w", mh.String(), err)
		}
	}
	duration := time.Since(begin)
	s := &bstats.BitswapStat{
		MultipleDownloadSpeed: &bstats.MultipleDownloadSpeed{
			BlockCount:    count,
			TotalDuration: duration,
		},
	}
	runenv.RecordMessage(bstats.Marshal(s))
	tgc.MustSignalEntry(ctx, doneState)
	return nil
}
