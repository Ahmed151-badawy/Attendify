import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import '../models/beacon.dart';

class BluetoothService {
  // CRITICAL: Only accept beacons with this exact UUID
  static const String EXPECTED_UUID = '123E4567-E89B-12D3-A456-426614174000';

  Stream<List<Beacon>> get scanStream {
    return FlutterBluePlus.scanResults.map((results) {
      print('════════════════════════════════');
      print('📡 SCAN UPDATE: ${results.length} devices detected');

      if (results.isEmpty) {
        print('!  No devices found yet – still scanning...');
      }

      final beacons = <Beacon>[];
      int beaconLikeDevices = 0;
      int matched = 0;

      for (var result in results) {
        final mfrKeys = result.advertisementData.manufacturerData.keys
            .map((k) => '0x${k.toRadixString(16).padLeft(4, '0')}')
            .toList();

        // Only print devices that have manufacturer data (reduces noise)
        if (result.advertisementData.manufacturerData.isNotEmpty) {
          print('---');
          print('Device: ${result.device.remoteId}');
          print('MFR keys: $mfrKeys');

          for (var entry in result.advertisementData.manufacturerData.entries) {
            final bytes = entry.value;
            print('  [0x${entry.key.toRadixString(16)}] '
                'len=${bytes.length} '
                'bytes=${bytes.take(8).map((b) => b.toRadixString(16).padLeft(2, '0')).join(' ')}');
          }

          if (_isBeacon(result)) {
            beaconLikeDevices++;
            final beacon = _parseBeacon(result);
            if (beacon != null) {
              print('  UUID : ${beacon.uuid}');
              print('  Major: ${beacon.major}  Minor: ${beacon.minor}');
              if (beacon.uuid.toUpperCase() == EXPECTED_UUID) {
                beacons.add(beacon);
                matched++;
                print('  ✅ CORRECT UUID – added');
              } else {
                print('  ❌ Wrong UUID');
              }
            }
          }
        }
      }

      print('════════════════════════════════');
      print('📊 SUMMARY  total=${results.length}  beacon-like=$beaconLikeDevices  matched=$matched');
      print('');
      return beacons;
    });
  }

  Future<bool> isBluetoothOn() async {
    try {
      final state = await FlutterBluePlus.adapterState.first;
      return state == BluetoothAdapterState.on;
    } catch (e) {
      return false;
    }
  }

  Future<void> startScan({Duration timeout = const Duration(seconds: 30)}) async {
    print('🔍 Starting BLE scan (timeout: $timeout)');
    try {
      if (FlutterBluePlus.isScanningNow) {
        await FlutterBluePlus.stopScan();
        await Future.delayed(const Duration(milliseconds: 200));
      }

      // MsdFilter 0x004C = Apple company ID → matches iBeacon and beacon_broadcast packets
      // This bypasses Android 14/15 scan throttling on MIUI
      try {
        await FlutterBluePlus.startScan(
          timeout: timeout,
          withMsd: [MsdFilter(0x004C)],
          continuousUpdates: true,
        );
        print('✅ Scan started with MsdFilter(0x004C)');
      } catch (filterError) {
        print('⚠️  MsdFilter failed ($filterError), falling back to unfiltered scan');
        await FlutterBluePlus.startScan(
          timeout: timeout,
          continuousUpdates: true,
        );
        print('✅ Scan started (unfiltered fallback)');
      }
    } catch (e) {
      print('❌ ERROR starting scan: $e');
      rethrow;
    }
  }

  Future<void> stopScan() async {
    await FlutterBluePlus.stopScan();
    print('🛑 Scan stopped');
  }

  Stream<bool> get isScanningStream => FlutterBluePlus.isScanning;

  // ─────────────────────────────────────────────────────────────────
  // _isBeacon: any manufacturer data entry with >= 21 bytes
  // ─────────────────────────────────────────────────────────────────
  bool _isBeacon(ScanResult result) {
    for (var entry in result.advertisementData.manufacturerData.entries) {
      if (entry.value.length >= 21) return true;
    }
    return false;
  }

  // ─────────────────────────────────────────────────────────────────
  // _parseBeacon: tries four layouts in order of specificity
  // ─────────────────────────────────────────────────────────────────
  Beacon? _parseBeacon(ScanResult result) {
    try {
      for (var entry in result.advertisementData.manufacturerData.entries) {
        final id = entry.key;
        final data = entry.value;

        if (data.length < 21) continue;

        // ── Layout A ──────────────────────────────────────────────
        // flutter_blue_plus scanner sees the payload AFTER company ID.
        // When the broadcaster sends: [companyId(2)] [0x02][0x15][uuid(16)][maj(2)][min(2)][txpow(1)]
        // flutter_blue_plus gives data = [0x02, 0x15, uuid..., major_hi, major_lo, minor_hi, minor_lo, txpow]
        // Requires: manufacturer 0x004C, data[0]==0x02, data[1]==0x15, length >= 23
        if (id == 0x004C && data.length >= 23 && data[0] == 0x02 && data[1] == 0x15) {
          print('  Layout A (standard iBeacon, prefix at 0-1)');
          return _buildBeacon(result, data, uuidStart: 2, majorIdx: 18, minorIdx: 20);
        }

        // ── Layout D ──────────────────────────────────────────────
        // beacon_broadcast with layout 'm:2-3=0215,i:4-19,i:20-21,i:22-23,p:24-24'
        // AltBeacon builds the full payload as:
        //   [reserved(2)][0x02][0x15][uuid(16)][major(2)][minor(2)][txpow(1)] = 25 bytes
        // flutter_blue_plus gives data = full payload (25 bytes)
        // So 0x02 0x15 appear at data[2] and data[3].
        if (id == 0x004C && data.length >= 25 && data[2] == 0x02 && data[3] == 0x15) {
          print('  Layout D (beacon_broadcast AltBeacon layout, prefix at 2-3)');
          return _buildBeacon(result, data, uuidStart: 4, majorIdx: 20, minorIdx: 22);
        }

        // ── Layout B ──────────────────────────────────────────────
        // Some chipsets strip the 0x02 0x15 prefix.
        // UUID starts at byte 0, major at 16, minor at 18.
        if (id == 0x004C && data.length >= 20) {
          print('  Layout B (no prefix, UUID at 0)');
          return _buildBeacon(result, data, uuidStart: 0, majorIdx: 16, minorIdx: 18);
        }

        // ── Layout C ──────────────────────────────────────────────
        // Unknown company ID – still try as iBeacon if prefix matches
        if (data.length >= 23 && data[0] == 0x02 && data[1] == 0x15) {
          print('  Layout C (non-Apple company ID with prefix at 0-1)');
          return _buildBeacon(result, data, uuidStart: 2, majorIdx: 18, minorIdx: 20);
        }
      }

      return null;
    } catch (e) {
      print('  ❌ Parse error: $e');
      return null;
    }
  }

  // ─────────────────────────────────────────────────────────────────
  // _buildBeacon: extract UUID/major/minor from byte offsets
  // ─────────────────────────────────────────────────────────────────
  Beacon? _buildBeacon(
      ScanResult result,
      List<int> data, {
        required int uuidStart,
        required int majorIdx,
        required int minorIdx,
      }) {
    if (data.length < minorIdx + 2) return null;

    final uuidHex = data
        .sublist(uuidStart, uuidStart + 16)
        .map((b) => b.toRadixString(16).padLeft(2, '0'))
        .join()
        .toUpperCase();

    final uuid = '${uuidHex.substring(0, 8)}-'
        '${uuidHex.substring(8, 12)}-'
        '${uuidHex.substring(12, 16)}-'
        '${uuidHex.substring(16, 20)}-'
        '${uuidHex.substring(20, 32)}';

    final major = (data[majorIdx] << 8) | data[majorIdx + 1];
    final minor = (data[minorIdx] << 8) | data[minorIdx + 1];

    return Beacon(
      uuid: uuid,
      major: major,
      minor: minor,
      rssi: result.rssi,
      detectedAt: DateTime.now(),
    );
  }
}