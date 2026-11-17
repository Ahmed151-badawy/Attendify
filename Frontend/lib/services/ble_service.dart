// BLE Beacon Broadcasting Service
// Uses beacon_broadcast ^0.3.1 with AltBeacon's legacy startAdvertising() API.
// Compatible with Bluetooth 4.2 devices (e.g. Samsung A10 / BCM43013 chipset).
//
// The iBeacon layout 'm:2-3=0215,i:4-19,i:20-21,i:22-23,p:24-24' tells
// AltBeacon to place 0x02 0x15 at payload bytes 2-3, UUID at 4-19, etc.
// The scanner's bluetooth_service.dart Layout D parser handles this format.

import 'dart:async';
import 'package:beacon_broadcast/beacon_broadcast.dart';

class BLEService {
  // Must match BluetoothService.EXPECTED_UUID and backend UNIVERSITY_UUID
  static const String beaconUUID = '123e4567-e89b-12d3-a456-426614174000';

  // iBeacon layout: type marker at bytes 2-3, UUID at 4-19, major 20-21,
  // minor 22-23, TX power at 24.  Company ID 0x004C = Apple.
  static const String _iBeaconLayout = 'm:2-3=0215,i:4-19,i:20-21,i:22-23,p:24-24';
  static const int _manufacturerId = 0x004C;

  final BeaconBroadcast _beaconBroadcast = BeaconBroadcast();
  bool _isBroadcasting = false;
  bool get isBroadcasting => _isBroadcasting;

  // -------------------------------------------------------------------------
  // startBroadcasting
  // -------------------------------------------------------------------------
  Future<void> startBroadcasting({
    required int major,
    required int minor,
  }) async {
    print('BLEService.startBroadcasting() major=$major minor=$minor');

    // 1. Check chipset support (uses UPPERCASE enum in beacon_broadcast v0.3.x)
    final status = await _beaconBroadcast.checkTransmissionSupported();
    print('   Transmission support: $status');

    // BeaconStatus.SUPPORTED in v0.3.x
    if (status != BeaconStatus.supported) {
      throw Exception('Cannot broadcast beacon. Device status: $status');
    }

    // 2. Stop any running advertisement first
    if (_isBroadcasting) {
      await stopBroadcasting();
      await Future.delayed(const Duration(milliseconds: 300));
    }

    // 3. Configure and start beacon
    try {
      await _beaconBroadcast
          .setUUID(beaconUUID)
          .setMajorId(major)
          .setMinorId(minor)
          .setTransmissionPower(-59)
          .setAdvertiseMode(AdvertiseMode.lowLatency)
          .setLayout(_iBeaconLayout)
          .setManufacturerId(_manufacturerId)
          .start();

      _isBroadcasting = true;
      print('Broadcasting started  UUID=$beaconUUID  Major=$major  Minor=$minor');
    } catch (e) {
      _isBroadcasting = false;
      print('startBroadcasting failed: $e');
      rethrow;
    }
  }

  // -------------------------------------------------------------------------
  // stopBroadcasting
  // -------------------------------------------------------------------------
  Future<void> stopBroadcasting() async {
    print('BLEService.stopBroadcasting()');
    try {
      await _beaconBroadcast.stop();
      _isBroadcasting = false;
      print('Broadcasting stopped');
    } catch (e) {
      _isBroadcasting = false;
      print('stopBroadcasting error (ignored): $e');
    }
  }

  // -------------------------------------------------------------------------
  // isBluetoothEnabled
  // -------------------------------------------------------------------------
  Future<bool> isBluetoothEnabled() async {
    try {
      final status = await _beaconBroadcast.checkTransmissionSupported();
      return status == BeaconStatus.supported;
    } catch (e) {
      return false;
    }
  }

  void dispose() {
    stopBroadcasting();
  }
}