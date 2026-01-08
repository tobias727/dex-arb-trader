// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @notice Minimal interface for StateView contract
interface IStateView {
    function getTickBitmap(bytes32 poolId, int16 word)
        external
        view
        returns (uint256 tickBitmap);

    function getTickInfo(bytes32 poolId, int24 tick)
        external
        view
        returns (
            uint128 liquidityGross,
            int128 liquidityNet,
            uint256 feeGrowthOutside0X128,
            uint256 feeGrowthOutside1X128
        );
}

contract TickBitmapHelper {
    IStateView public immutable STATE_VIEW;

    struct TickData {
        int24 index;
        uint128 liquidityGross;
        int128 liquidityNet;
        uint256 feeGrowthOutside0X128;
        uint256 feeGrowthOutside1X128;
    }

    constructor(address _stateView) {
        require(_stateView != address(0), "stateView is zero");
        STATE_VIEW = IStateView(_stateView);
    }

    /// @notice Get bitmaps for the inclusive range [startWord, endWord]
    function getTickBitmapsRange(
        bytes32 poolId,
        int16 startWord,
        int16 endWord
    ) external view returns (uint256[] memory bitmaps) {
        require(endWord >= startWord, "invalid range");

        int256 diff = int256(endWord) - int256(startWord) + 1;
        require(diff > 0, "invalid diff");

        uint256 len = uint256(diff);
        bitmaps = new uint256[](len);

        int16 w = startWord;
        for (uint256 i = 0; i < len; i++) {
            bitmaps[i] = STATE_VIEW.getTickBitmap(poolId, w);
            unchecked {
                w++;
            }
        }
    }

    /// @notice Get tick info for all given tick indices in a single call
    function getTicks(
        bytes32 poolId,
        int24[] calldata tickIndices
    ) external view returns (TickData[] memory ticks) {
        uint256 len = tickIndices.length;
        ticks = new TickData[](len);

        for (uint256 i = 0; i < len; i++) {
            int24 idx = tickIndices[i];

            (
                uint128 liquidityGross,
                int128 liquidityNet,
                uint256 feeGrowthOutside0X128,
                uint256 feeGrowthOutside1X128
            ) = STATE_VIEW.getTickInfo(poolId, idx);

            ticks[i] = TickData({
                index: idx,
                liquidityGross: liquidityGross,
                liquidityNet: liquidityNet,
                feeGrowthOutside0X128: feeGrowthOutside0X128,
                feeGrowthOutside1X128: feeGrowthOutside1X128
            });
        }
    }
}
