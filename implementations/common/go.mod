module github.com/ipfs/testground/plans/trickle-bitswap/common

go 1.18

require (
	github.com/dgraph-io/badger/v2 v2.2007.4
	github.com/ipfs/go-bitswap v0.10.2
	github.com/ipfs/go-blockservice v0.4.0
	github.com/ipfs/go-cid v0.2.0
	github.com/ipfs/go-datastore v0.5.1
	github.com/ipfs/go-ds-badger2 v0.1.3
	github.com/ipfs/go-ipfs-blockstore v1.2.0
	github.com/ipfs/go-ipfs-chunker v0.0.1
	github.com/ipfs/go-ipfs-delay v0.0.1
	github.com/ipfs/go-ipfs-files v0.1.1
	github.com/ipfs/go-ipfs-posinfo v0.0.1
	github.com/ipfs/go-ipfs-routing v0.2.1
	github.com/ipfs/go-ipld-format v0.3.0
	github.com/ipfs/go-log v1.0.5
	github.com/ipfs/go-log/v2 v2.5.1
	github.com/ipfs/go-merkledag v0.6.0
	github.com/ipfs/go-mfs v0.2.1
	github.com/ipfs/go-unixfs v0.4.0
	github.com/libp2p/go-libp2p v0.22.0
	github.com/multiformats/go-multiaddr v0.6.0
	github.com/multiformats/go-multihash v0.2.1
	github.com/pkg/errors v0.9.1
	github.com/testground/sdk-go v0.3.0
	golang.org/x/sync v0.0.0-20220722155255-886fb9371eb4
)

// This fixes the panic: send on closed channel issue
replace github.com/testground/sdk-go v0.3.0 => github.com/hannahhoward/sdk-go v0.3.1-0.20220106065751-1280c9501986

// Maybe move this below the 'indirect' dependency block?
replace github.com/testground/sync-service v0.1.0 => github.com/ebma/sync-service v0.0.0-20221029105457-490d7b7c876e

require (
	github.com/alecthomas/units v0.0.0-20210927113745-59d0afb8317a // indirect
	github.com/avast/retry-go v2.6.0+incompatible // indirect
	github.com/benbjohnson/clock v1.3.0 // indirect
	github.com/cespare/xxhash v1.1.0 // indirect
	github.com/crackcomm/go-gitignore v0.0.0-20170627025303-887ab5e44cc3 // indirect
	github.com/cskr/pubsub v1.0.2 // indirect
	github.com/decred/dcrd/dcrec/secp256k1/v4 v4.1.0 // indirect
	github.com/dgraph-io/ristretto v0.0.3-0.20200630154024-f66de99634de // indirect
	github.com/dgryski/go-farm v0.0.0-20190423205320-6a90982ecee2 // indirect
	github.com/dustin/go-humanize v1.0.0 // indirect
	github.com/go-logr/logr v1.2.3 // indirect
	github.com/go-logr/stdr v1.2.2 // indirect
	github.com/gogo/protobuf v1.3.2 // indirect
	github.com/golang/protobuf v1.5.2 // indirect
	github.com/golang/snappy v0.0.3 // indirect
	github.com/google/uuid v1.3.0 // indirect
	github.com/hashicorp/errwrap v1.0.0 // indirect
	github.com/hashicorp/go-multierror v1.1.0 // indirect
	github.com/hashicorp/golang-lru v0.5.4 // indirect
	github.com/influxdata/influxdb1-client v0.0.0-20200515024757-02f0bf5dbca3 // indirect
	github.com/ipfs/bbloom v0.0.4 // indirect
	github.com/ipfs/go-bitfield v1.0.0 // indirect
	github.com/ipfs/go-block-format v0.0.3 // indirect
	github.com/ipfs/go-ipfs-ds-help v1.1.0 // indirect
	github.com/ipfs/go-ipfs-exchange-interface v0.2.0 // indirect
	github.com/ipfs/go-ipfs-pq v0.0.2 // indirect
	github.com/ipfs/go-ipfs-util v0.0.2 // indirect
	github.com/ipfs/go-ipld-cbor v0.0.5 // indirect
	github.com/ipfs/go-ipld-legacy v0.1.0 // indirect
	github.com/ipfs/go-metrics-interface v0.0.1 // indirect
	github.com/ipfs/go-path v0.2.1 // indirect
	github.com/ipfs/go-peertaskqueue v0.7.0 // indirect
	github.com/ipfs/go-verifcid v0.0.1 // indirect
	github.com/ipld/go-codec-dagpb v1.3.0 // indirect
	github.com/ipld/go-ipld-prime v0.11.0 // indirect
	github.com/jbenet/goprocess v0.1.4 // indirect
	github.com/json-iterator/go v1.1.12 // indirect
	github.com/klauspost/compress v1.15.1 // indirect
	github.com/klauspost/cpuid/v2 v2.1.0 // indirect
	github.com/libp2p/go-buffer-pool v0.1.0 // indirect
	github.com/libp2p/go-libp2p-core v0.20.1 // indirect
	github.com/libp2p/go-libp2p-record v0.2.0 // indirect
	github.com/libp2p/go-msgio v0.2.0 // indirect
	github.com/libp2p/go-openssl v0.1.0 // indirect
	github.com/mattn/go-isatty v0.0.16 // indirect
	github.com/mattn/go-pointer v0.0.1 // indirect
	github.com/minio/sha256-simd v1.0.0 // indirect
	github.com/mr-tron/base58 v1.2.0 // indirect
	github.com/multiformats/go-base32 v0.0.4 // indirect
	github.com/multiformats/go-base36 v0.1.0 // indirect
	github.com/multiformats/go-multibase v0.1.1 // indirect
	github.com/multiformats/go-multicodec v0.5.0 // indirect
	github.com/multiformats/go-multistream v0.3.3 // indirect
	github.com/multiformats/go-varint v0.0.6 // indirect
	github.com/opentracing/opentracing-go v1.2.0 // indirect
	github.com/polydawn/refmt v0.0.0-20201211092308-30ac6d18308e // indirect
	github.com/rcrowley/go-metrics v0.0.0-20200313005456-10cdbea86bc0 // indirect
	github.com/spacemonkeygo/spacelog v0.0.0-20180420211403-2296661a0572 // indirect
	github.com/spaolacci/murmur3 v1.1.0 // indirect
	github.com/testground/sync-service v0.1.0 // indirect
	github.com/testground/testground v0.5.3 // indirect
	github.com/whyrusleeping/cbor-gen v0.0.0-20200123233031-1cdf64d27158 // indirect
	github.com/whyrusleeping/chunker v0.0.0-20181014151217-fe64bd25879f // indirect
	go.opentelemetry.io/otel v1.7.0 // indirect
	go.opentelemetry.io/otel/trace v1.7.0 // indirect
	go.uber.org/atomic v1.10.0 // indirect
	go.uber.org/multierr v1.8.0 // indirect
	go.uber.org/zap v1.22.0 // indirect
	golang.org/x/crypto v0.0.0-20220525230936-793ad666bf5e // indirect
	golang.org/x/net v0.0.0-20220812174116-3211cb980234 // indirect
	golang.org/x/sys v0.0.0-20220811171246-fbc7d0a398ab // indirect
	golang.org/x/xerrors v0.0.0-20220609144429-65e65417b02f // indirect
	google.golang.org/protobuf v1.28.1 // indirect
	gopkg.in/yaml.v2 v2.4.0 // indirect
	lukechampine.com/blake3 v1.1.7 // indirect
	nhooyr.io/websocket v1.8.6 // indirect
)