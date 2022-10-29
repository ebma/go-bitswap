package utils

import (
	"context"
	"time"

	bs "github.com/ipfs/go-bitswap"
	bsnet "github.com/ipfs/go-bitswap/network"
	"github.com/ipfs/go-blockservice"
	blockstore "github.com/ipfs/go-ipfs-blockstore"
	nilrouting "github.com/ipfs/go-ipfs-routing/none"
	"github.com/ipfs/go-merkledag"
	"github.com/libp2p/go-libp2p/core/host"

	"github.com/ipfs/testground/plans/trickle-bitswap/common/utils"
)

func CreateBitswapNode(
	ctx context.Context,
	h host.Host,
	bstore blockstore.Blockstore,
	tricklingDelay time.Duration,
	isEavesdropper bool,
) (*utils.BitswapNode, error) {
	routing, err := nilrouting.ConstructNilRouting(ctx, nil, nil, nil)
	if err != nil {
		return nil, err
	}
	net := bsnet.NewFromIpfsHost(h, routing)

	tricklingOption := bs.SetTricklingDelay(tricklingDelay)
	eavesdropperOption := bs.SetEavesdropper(isEavesdropper)
	options := []bs.Option{tricklingOption, eavesdropperOption}
	bitswap := bs.New(ctx, net, bstore, options...)

	bserv := blockservice.New(bstore, bitswap)
	dserv := merkledag.NewDAGService(bserv)
	return &utils.BitswapNode{bitswap, bstore, dserv, h}, nil
}
