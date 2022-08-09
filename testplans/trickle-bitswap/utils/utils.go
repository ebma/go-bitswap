package utils

import (
	"crypto/rand"
	"fmt"
	ci "github.com/libp2p/go-libp2p-core/crypto"
	"github.com/libp2p/go-libp2p-core/peer"
	ma "github.com/multiformats/go-multiaddr"
	mathRand "math/rand"
	"net"
	"strconv"
	"time"
)

type NodeConfig struct {
	Addrs    []string
	AddrInfo *peer.AddrInfo
	PrivKey  []byte
}

func getFreePort() string {
	mathRand.Seed(time.Now().UnixNano())
	notAvailable := true
	port := 0
	for notAvailable {
		port = 3000 + mathRand.Intn(5000)
		ln, err := net.Listen("tcp", ":"+strconv.Itoa(port))
		if err == nil {
			notAvailable = false
			_ = ln.Close()
		}
	}
	return strconv.Itoa(port)
}

func GenerateAddrInfo(ip string) (*NodeConfig, error) {
	// Use a free port
	port := getFreePort()
	// Generate new KeyPair instead of using existing one.
	priv, pub, err := ci.GenerateKeyPairWithReader(ci.RSA, 2048, rand.Reader)
	if err != nil {
		panic(err)
	}
	// Generate PeerID
	pid, err := peer.IDFromPublicKey(pub)
	if err != nil {
		panic(err)
	}
	privKeyB, err := ci.MarshalPrivateKey(priv)
	if err != nil {
		panic(err)
	}

	addrs := []string{
		fmt.Sprintf("/ip4/%s/tcp/%s", ip, port),
		"/ip6/::/tcp/" + port,
		fmt.Sprintf("/ip4/%s/udp/%s/quic", ip, port),
		fmt.Sprintf("/ip6/::/udp/%s/quic", port),
	}
	multiAddrs := make([]ma.Multiaddr, 0)

	for _, a := range addrs {
		maddr, err := ma.NewMultiaddr(a)
		if err != nil {
			return nil, err
		}
		multiAddrs = append(multiAddrs, maddr)
	}

	return &NodeConfig{addrs, &peer.AddrInfo{ID: pid, Addrs: multiAddrs}, privKeyB}, nil
}
