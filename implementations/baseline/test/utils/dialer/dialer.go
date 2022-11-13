package dialer

import (
	"context"
	"fmt"
	"github.com/ipfs/testground/plans/trickle-bitswap/test/utils"
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

// Dial nodes with certain rules to create a defined topology
func DialFixedTopologyCenteredLeech(
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

	if selfType == utils.Seed {
		// Connect Seed to first 3 Passives
		for _, inf := range passives[:3] {
			toDial = append(toDial, inf.Addr)
		}
	} else if selfType == utils.Leech {
		// Make leech connect to passives 1, 3, 4 and 6
		// so that it is centered in the overall topology
		toDial = append(toDial, passives[1].Addr)
		toDial = append(toDial, passives[3].Addr)
		toDial = append(toDial, passives[4].Addr)
		toDial = append(toDial, passives[6].Addr)
	} else if selfType == utils.Passive {
		// Manually connect passives to each other so that they form a grid with the leech in the center
		if typeIndex == 0 {
			toDial = append(toDial, passives[1].Addr)
			toDial = append(toDial, passives[2].Addr)
			toDial = append(toDial, passives[3].Addr)
		} else if typeIndex == 1 {
			toDial = append(toDial, passives[2].Addr)
		} else if typeIndex == 2 {
			toDial = append(toDial, passives[4].Addr)
		} else if typeIndex == 3 {
			toDial = append(toDial, passives[5].Addr)
		} else if typeIndex == 4 {
			toDial = append(toDial, passives[7].Addr)
		} else if typeIndex == 5 {
			toDial = append(toDial, passives[6].Addr)
			toDial = append(toDial, passives[7].Addr)
			toDial = append(toDial, passives[8].Addr)
		} else if typeIndex == 6 {
			toDial = append(toDial, passives[7].Addr)
			toDial = append(toDial, passives[8].Addr)
		} else if typeIndex == 7 {
			toDial = append(toDial, passives[8].Addr)
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

// Dial nodes with certain rules to create a defined topology
func DialFixedTopologyEdgeLeech(
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
