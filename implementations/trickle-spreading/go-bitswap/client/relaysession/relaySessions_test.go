package relaysession

import (
	"context"
	"github.com/ipfs/go-bitswap/client/internal/notifications"
	"testing"

	"github.com/ipfs/go-bitswap/internal/testutil"
	blocks "github.com/ipfs/go-block-format"
	cid "github.com/ipfs/go-cid"
	peer "github.com/libp2p/go-libp2p/core/peer"
)

type fakeSession struct {
	ks         []cid.Cid
	wantBlocks []cid.Cid
	wantHaves  []cid.Cid
	id         uint64
	pm         *fakeSesPeerManager
	notif      notifications.PubSub
	ttl        int32
	relay      bool
}

func (*fakeSession) GetBlock(context.Context, cid.Cid) (blocks.Block, error) {
	return nil, nil
}
func (*fakeSession) GetBlocks(context.Context, []cid.Cid) (<-chan blocks.Block, error) {
	return nil, nil
}
func (fs *fakeSession) ID() uint64 {
	return fs.id
}

func (fs *fakeSession) ReceiveFrom(
	p peer.ID,
	ks []cid.Cid,
	wantBlocks []cid.Cid,
	wantHaves []cid.Cid,
) {
	fs.ks = append(fs.ks, ks...)
	fs.wantBlocks = append(fs.wantBlocks, wantBlocks...)
	fs.wantHaves = append(fs.wantHaves, wantHaves...)
}
func (fs *fakeSession) Shutdown() {
}

type fakeSesPeerManager struct {
}

func TestKeyTracker(t *testing.T) {
	p := testutil.GeneratePeers(1)[0]
	kt := NewKeyTracker(p)
	if len(kt.T) != 0 || kt.Peer != p {
		t.Fatal("Tracker not initialized successfully")
	}

	var i int32 = 0
	cids := testutil.GenerateCids(3)
	for _, c := range cids {
		kt.UpdateTracker(c)
		if kt.T[i].Key != c {
			t.Fatalf("Wrong individual CID update Got: %s - Expected: %s",
				kt.T[i].Key, c)
		}
		i++
	}
	if len(kt.T) != len(cids) {
		t.Fatal("Number of updates not successful")
	}
}
func TestRelaySessions(t *testing.T) {
	peers := testutil.GeneratePeers(2)
	keys := testutil.GenerateCids(5)
	rs := NewRelaySession()
	if rs.Session != nil {
		t.Fatal("Error initializing relaySession")
	}

	// Initialize keytrackers
	kt1 := NewKeyTracker(peers[0])
	kt2 := NewKeyTracker(peers[1])
	for _, c := range keys[:3] {
		kt1.UpdateTracker(c)
	}
	for _, c := range keys[2:] {
		kt2.UpdateTracker(c)
	}

	// Start new relaySession
	rs.Session = &fakeSession{}

	rs.UpdateSession(context.Background(), kt1)
	if len(rs.InterestedPeers(keys[0])) != 1 &&
		len(rs.InterestedPeers(keys[len(keys)-1])) != 0 {
		t.Fatal("First session update failed")
	}

	rs.UpdateSession(context.Background(), kt2)
	if len(rs.InterestedPeers(keys[2])) != 2 &&
		len(rs.InterestedPeers(keys[len(keys)])) != 1 {
		t.Fatal("Second session update failed")
	}

	rs.BlockSeen(keys[0], peers[0])
	rs.RemoveInterest(keys[0], peers[0])
	rs.RemoveInterest(keys[2], peers[0])
	ps := rs.InterestedPeers(keys[2])
	if len(ps) != 1 && ps[peers[1]] != 0 {
		t.Fatalf("Interest for peer not removed successfully")
	}
	_, found := rs.Registry.r[keys[0]]
	if found {
		t.Fatal("Interest CIDs not cleaned correctly")
	}
	_, found = rs.Registry.r[keys[2]]
	if !found {
		t.Fatal("Something went wrong removing peers")
	}
}
