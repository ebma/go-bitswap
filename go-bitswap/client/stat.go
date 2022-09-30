package client

import (
	cid "github.com/ipfs/go-cid"
)

// Stat is a struct that provides various statistics on bitswap operations
type Stat struct {
	Wantlist         []cid.Cid
	BlocksReceived   uint64
	DataReceived     uint64
	DupBlksReceived  uint64
	DupDataReceived  uint64
	MessagesReceived uint64

	BlocksSent    uint64
	DataSent      uint64
	Peers         []string
	ProvideBufLen int
}

// Stat returns aggregated statistics about bitswap operations
func (bs *Client) Stat() (st Stat, err error) {
	//st.ProvideBufLen = len(bs.newBlocks)
	st.Wantlist = bs.GetWantlist()
	bs.counterLk.Lock()
	c := bs.counters
	st.BlocksReceived = c.blocksRecvd
	st.DupBlksReceived = c.dupBlocksRecvd
	st.DupDataReceived = c.dupDataRecvd
	st.DataReceived = c.dataRecvd
	st.MessagesReceived = c.messagesRecvd
	bs.counterLk.Unlock()
	st.Wantlist = bs.GetWantlist()

	//st.BlocksSent = c.blocksSent
	//st.DataSent = c.dataSent
	//peers := bs.engine.Peers()
	//st.Peers = make([]string, 0, len(peers))
	//
	//for _, p := range peers {
	//	st.Peers = append(st.Peers, p.Pretty())
	//}
	//sort.Strings(st.Peers)

	return st, nil
}
