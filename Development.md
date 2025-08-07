
# Pool Selection

unichain_v4_pools.json contains pool data retrieved from `https://thegraph.com/explorer/subgraphs/Bd8UnJU8jCRJKVjcW16GHM3FNdfwTojmWb3QwSAmv8Uc?view=Query&chain=arbitrum-one`
using:

```
{
  pools(where:{id_in: [
    "0x3258f413c7a88cda2fa8709a589d221a80f6574f63df5a5b6774485d8acc39d9",
		"0x764afe9ab22a5c80882918bb4e59b954912b17a22c3524c68a8cf08f7386e08f",
		"0xb2f3bbaf23e0197ec2e6f9ab730d00aaf26a9119ecd583bbb9ef3146b4afa248",
		"0x5cbba0e9f8bfe322fd873263095b31777fad6ae4642310808eff8d5fa9fa9ef9",
		"0x3d4d39a2ec28d80efa72679e47b8d4621caeecc15af8f21be97db234657d5fa7",
		"0x2c93042f78d28e3912fcba2268d48b2b911f18ccac8dd6fa2e1524614906d851",
		"0x229ef2ccd211bd4ae9405c33a5b18b1a22c0bdee7df8ba1363527db7f8c5f1f9",
		"0xe452cd9b74c641fb3f6c2ff593c3d34f90f2da9155e5ab66798f72bee4f5fe8e"
  ]}) {
    id
    feeTier
    tickSpacing
    totalValueLockedUSD
    token0{
      id
      symbol
      decimals
    }
    token1{
      id
      symbol
      decimals
    }
  }
}
```
