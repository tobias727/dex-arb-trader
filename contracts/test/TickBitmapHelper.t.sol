// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {TickBitmapHelper, IStateView} from "../src/TickBitmapHelper.sol";


contract MockStateView is IStateView {
    mapping(bytes32 => mapping(int16 => uint256)) public bitmaps;
    struct TickInfo {
        uint128 liquidityGross;
        int128 liquidityNet;
        uint256 feeGrowthOutside0X128;
        uint256 feeGrowthOutside1X128;
    }

    mapping(bytes32 => mapping(int24 => TickInfo)) public ticks;

    function setTickBitmap(bytes32 poolId, int16 word, uint256 value) external {
        bitmaps[poolId][word] = value;
    }

    function setTickInfo(
        bytes32 poolId,
        int24 tick,
        uint128 liquidityGross,
        int128 liquidityNet,
        uint256 feeGrowthOutside0X128,
        uint256 feeGrowthOutside1X128
    ) external {
        ticks[poolId][tick] = TickInfo({
            liquidityGross: liquidityGross,
            liquidityNet: liquidityNet,
            feeGrowthOutside0X128: feeGrowthOutside0X128,
            feeGrowthOutside1X128: feeGrowthOutside1X128
        });
    }

    function getTickBitmap(bytes32 poolId, int16 word)
        external
        view
        override
        returns (uint256 tickBitmap)
    {
        return bitmaps[poolId][word];
    }

    function getTickInfo(bytes32 poolId, int24 tick)
        external
        view
        override
        returns (
            uint128 liquidityGross,
            int128 liquidityNet,
            uint256 feeGrowthOutside0X128,
            uint256 feeGrowthOutside1X128
        )
    {
        TickInfo memory t = ticks[poolId][tick];
        return (
            t.liquidityGross,
            t.liquidityNet,
            t.feeGrowthOutside0X128,
            t.feeGrowthOutside1X128
        );
    }
}

contract TickBitmapHelperTest is Test {
    MockStateView mock;
    TickBitmapHelper helper;
    bytes32 poolId = keccak256("POOL");

    function setUp() public {
        mock = new MockStateView();
        helper = new TickBitmapHelper(address(mock));
    }

    function testConstructorRevertsOnZeroAddress() public {
        vm.expectRevert(bytes("stateView is zero"));
        new TickBitmapHelper(address(0));
    }

    function testGetTickBitmapsRangeBasic() public {
        // Arrange
        mock.setTickBitmap(poolId, 0, 0x1234);
        mock.setTickBitmap(poolId, 1, 0x5678);

        // Act
        uint256[] memory res = helper.getTickBitmapsRange(poolId, 0, 1);

        // Assert
        assertEq(res.length, 2);
        assertEq(res[0], 0x1234);
        assertEq(res[1], 0x5678);
    }

    function testGetTickBitmapsRangeRevertsOnInvalidRange() public {
        vm.expectRevert(bytes("invalid range"));
        helper.getTickBitmapsRange(poolId, 2, 1);
    }

    function testGetTicksBasic() public {
        // Arrange
        int24[] memory indices = new int24[](2);
        indices[0] = 10;
        indices[1] = -5;

        mock.setTickInfo(
            poolId,
            10,
            100,
            50,
            1e18,
            2e18
        );
        mock.setTickInfo(
            poolId,
            -5,
            200,
            -30,
            3e18,
            4e18
        );

        // Act
        TickBitmapHelper.TickData[] memory ticks =
            helper.getTicks(poolId, indices);

        // Assert
        assertEq(ticks.length, 2);
        // Tick 0
        assertEq(ticks[0].index, 10);
        assertEq(ticks[0].liquidityGross, 100);
        assertEq(ticks[0].liquidityNet, 50);
        assertEq(ticks[0].feeGrowthOutside0X128, 1e18);
        assertEq(ticks[0].feeGrowthOutside1X128, 2e18);
        // Tick 1
        assertEq(ticks[1].index, -5);
        assertEq(ticks[1].liquidityGross, 200);
        assertEq(ticks[1].liquidityNet, -30);
        assertEq(ticks[1].feeGrowthOutside0X128, 3e18);
        assertEq(ticks[1].feeGrowthOutside1X128, 4e18);
    }
}
