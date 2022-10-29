package dialer

import (
	"bytes"
	"context"
	"fmt"
	"github.com/ipfs/testground/plans/trickle-bitswap/test/utils"
	"math"
	"sort"

	core "github.com/libp2p/go-libp2p/core"
	"github.com/libp2p/go-libp2p/core/peer"
	"golang.org/x/sync/errgroup"
)

// PeerInfosFromChan collects peer information from a channel of peer information
func PeerInfosFromChan(peerCh chan *utils.PeerInfo, count int) ([]utils.PeerInfo, error) {
	var ais []utils.PeerInfo
	for i := 1; i <= count; i++ {
		ai, ok := <-peerCh
		if !ok {
			return ais, fmt.Errorf("subscription closed")
		}
		ais = append(ais, *ai)
	}
	return ais, nil
}

// Dialer is a function that dials other peers, following a specified pattern
type Dialer func(ctx context.Context, self core.Host, selfType utils.NodeType, ais []utils.PeerInfo, maxConnectionRate int) ([]peer.AddrInfo, error)

// SparseDial connects to a set of peers in the experiment, but only those with the correct node type
func SparseDial(
	ctx context.Context,
	self core.Host,
	selfType utils.NodeType,
	ais []utils.PeerInfo,
	maxConnectionRate int,
) ([]peer.AddrInfo, error) {
	// Grab list of other peers that are available for this Run
	var toDial []peer.AddrInfo
	for _, inf := range ais {
		ai := inf.Addr
		id1, _ := ai.ID.MarshalBinary()
		id2, _ := self.ID().MarshalBinary()

		// skip over dialing ourselves, and prevent TCP simultaneous
		// connect (known to fail) by only dialing peers whose peer ID
		// is smaller than ours.
		if bytes.Compare(id1, id2) < 0 {
			// In sparse topology we don't allow leechers and seeders to be directly connected.
			switch selfType {
			case utils.Seed:
				if inf.Nodetp != utils.Leech {
					toDial = append(toDial, ai)
				}
			case utils.Leech:
				if inf.Nodetp != utils.Seed {
					toDial = append(toDial, ai)
				}
			case utils.Passive:
				toDial = append(toDial, ai)
			}
		}
	}

	// Limit max number of connections for the peer according to rate.
	rate := float64(maxConnectionRate) / 100
	toDial = toDial[:int(math.Ceil(float64(len(toDial))*rate))]

	// Dial to all the other peers
	g, ctx := errgroup.WithContext(ctx)
	for _, ai := range toDial {
		ai := ai
		g.Go(func() error {
			if err := self.Connect(ctx, ai); err != nil {
				return fmt.Errorf("Error while dialing peer %v: %w", ai.Addrs, err)
			}
			return nil
		})
	}
	if err := g.Wait(); err != nil {
		return nil, err
	}

	return toDial, nil
}

// Dial nodes with certain rules to create a defined topology
func DialFixedTopology(
	ctx context.Context,
	self core.Host,
	selfType utils.NodeType,
	typeIndex int,
	ais []utils.PeerInfo,
) ([]peer.AddrInfo, error) {
	// Grab list of other peers that are available for this Run
	var toDial []peer.AddrInfo

	// Passive nodes sorted by their typeIndex descending
	var passives []utils.PeerInfo
	for _, inf := range ais {
		if inf.Nodetp == utils.Passive {
			passives = append(passives, inf)
		}
	}
	sort.Slice(passives, func(i, j int) bool {
		return passives[i].TypeIndex < passives[j].TypeIndex
	})

	// degree of leech and seed node
	degree := 3
	gridSize := 3

	if selfType == utils.Seed {
		// Connect Seed to first 3 Passives
		for _, inf := range passives[:degree] {
			toDial = append(toDial, inf.Addr)
		}
	} else if selfType == utils.Leech {
		// Connect Leech to last 3 Passives
		for _, inf := range passives[len(passives)-degree:] {
			toDial = append(toDial, inf.Addr)
		}
	} else if selfType == utils.Passive {
		// Connect Passives to each other in a grid of {gridSize}x{gridSize}

		// Connect to Passive in same row to the right
		var indexSameRow int
		if (typeIndex+1)%gridSize == 0 {
			// wrap around same row
			indexSameRow = typeIndex + 1 - gridSize
		} else {
			indexSameRow = typeIndex + 1
		}
		if indexSameRow < len(passives) {
			toDial = append(toDial, passives[indexSameRow].Addr)
		}
		// Connect to Passive in next row
		indexNextRow := typeIndex + gridSize
		if indexNextRow < len(passives) {
			toDial = append(toDial, passives[indexNextRow].Addr)
		}
	}

	// Dial to all the other peers
	g, ctx := errgroup.WithContext(ctx)
	for _, ai := range toDial {
		ai := ai
		g.Go(func() error {
			if err := self.Connect(ctx, ai); err != nil {
				return fmt.Errorf("Error while dialing peer %v: %w", ai.Addrs, err)
			}
			return nil
		})
	}
	if err := g.Wait(); err != nil {
		return nil, err
	}

	return toDial, nil
}

// DialOtherPeers connects to a set of peers in the experiment, dialing all of them
func DialOtherPeers(
	ctx context.Context,
	self core.Host,
	selfType utils.NodeType,
	ais []utils.PeerInfo,
	maxConnectionRate int,
) ([]peer.AddrInfo, error) {
	// Grab list of other peers that are available for this Run
	var toDial []peer.AddrInfo
	for _, inf := range ais {
		ai := inf.Addr
		id1, _ := ai.ID.MarshalBinary()
		id2, _ := self.ID().MarshalBinary()

		// skip over dialing ourselves, and prevent TCP simultaneous
		// connect (known to fail) by only dialing peers whose peer ID
		// is smaller than ours.
		if bytes.Compare(id1, id2) < 0 {
			toDial = append(toDial, ai)
		}
	}

	// Limit max number of connections for the peer according to rate.
	rate := float64(maxConnectionRate) / 100
	toDial = toDial[:int(math.Ceil(float64(len(toDial))*rate))]

	// Dial to all the other peers
	g, ctx := errgroup.WithContext(ctx)
	for _, ai := range toDial {
		ai := ai
		g.Go(func() error {
			if err := self.Connect(ctx, ai); err != nil {
				return fmt.Errorf("Error while dialing peer %v: %w", ai.Addrs, err)
			}
			return nil
		})
	}
	if err := g.Wait(); err != nil {
		return nil, err
	}

	return toDial, nil
}

// DialAllPeers connects to all peers, ignoring the possible tcp error
func DialAllPeers(
	ctx context.Context,
	self core.Host,
	selfType utils.NodeType,
	ais []utils.PeerInfo,
) ([]peer.AddrInfo, error) {
	// Dial to all the other peers
	var toDial []peer.AddrInfo
	for _, inf := range ais {
		ai := inf.Addr
		id1, _ := ai.ID.MarshalBinary()
		id2, _ := self.ID().MarshalBinary()

		// skip over dialing ourselves
		if bytes.Compare(id1, id2) != 0 {
			switch selfType {
			// don't dial other eavesdropper nodes
			case utils.Eavesdropper:
				if inf.Nodetp != utils.Eavesdropper {
					toDial = append(toDial, ai)
				}
			default:
				toDial = append(toDial, ai)
			}
		}
	}
	g, ctx := errgroup.WithContext(ctx)
	for _, ai := range toDial {
		ai := ai
		g.Go(func() error {
			if err := self.Connect(ctx, ai); err != nil {
				return fmt.Errorf("Error while dialing peer %v: %w", ai.Addrs, err)
			}
			return nil
		})
	}
	if err := g.Wait(); err != nil {
		return nil, err
	}

	return toDial, nil
}
