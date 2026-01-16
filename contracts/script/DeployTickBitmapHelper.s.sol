// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script} from "forge-std/Script.sol";
import {console2} from "forge-std/console2.sol";
import {TickBitmapHelper} from "../src/TickBitmapHelper.sol";

contract DeployTickBitmapHelper is Script {
    function run() external {
        vm.startBroadcast();

        address stateView = 0x86e8631A016F9068C3f085fAF484Ee3F5fDee8f2; // stateView Unichain Mainnet

        TickBitmapHelper helper = new TickBitmapHelper(stateView);

        console2.log("TickBitmapHelper deployed at:", address(helper));

        vm.stopBroadcast();
    }
}
