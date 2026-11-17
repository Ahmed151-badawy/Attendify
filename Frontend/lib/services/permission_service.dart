import 'package:permission_handler/permission_handler.dart';
import 'package:device_info_plus/device_info_plus.dart';
import 'dart:io' show Platform;

class PermissionService {
  /// Request all necessary Bluetooth and Location permissions
  Future<bool> requestBluetoothPermissions() async {
    print('ðŸ” Starting permission request...');

    try {
      // Different permissions for Android 12+ vs older versions
      Map<Permission, PermissionStatus> statuses;

      if (Platform.isAndroid) {
        // Check Android version
        final androidInfo = await _getAndroidVersion();
        print('ðŸ“± Android API Level: $androidInfo');

        if (androidInfo >= 31) {
          // Android 12+ (API 31+)
          print('ðŸ“‹ Requesting Android 12+ permissions...');
          statuses = await [
            Permission.bluetoothScan,
            Permission.bluetoothConnect,
            Permission.bluetoothAdvertise, // âœ… ADDED - Required for broadcasting beacons
            Permission.locationWhenInUse,
          ].request();
        } else {
          // Android 11 and below
          print('ðŸ“‹ Requesting Android 11 and below permissions...');
          statuses = await [
            Permission.bluetooth,
            Permission.locationWhenInUse,
          ].request();
        }
      } else if (Platform.isIOS) {
        // iOS permissions
        print('ðŸ“‹ Requesting iOS permissions...');
        statuses = await [
          Permission.bluetooth,
          Permission.locationWhenInUse,
        ].request();
      } else {
        print('âŒ Unsupported platform');
        return false;
      }

      // Log each permission status
      print('ðŸ“Š Permission Results:');
      statuses.forEach((permission, status) {
        print('   ${permission.toString()}: ${status.toString()}');

        if (status.isDenied) {
          print('   âš ï¸ ${permission.toString()} was DENIED');
        } else if (status.isPermanentlyDenied) {
          print('   ðŸš« ${permission.toString()} was PERMANENTLY DENIED');
          print('   â†’ User must enable in Settings');
        } else if (status.isGranted) {
          print('   âœ… ${permission.toString()} was GRANTED');
        }
      });

      // Check if all permissions granted
      final allGranted = statuses.values.every((status) => status.isGranted);

      if (allGranted) {
        print('âœ… All permissions GRANTED');
      } else {
        print('âŒ Some permissions were NOT granted');

        // Check for permanently denied permissions
        final permanentlyDenied = statuses.entries
            .where((entry) => entry.value.isPermanentlyDenied)
            .map((entry) => entry.key)
            .toList();

        if (permanentlyDenied.isNotEmpty) {
          print('ðŸš« Permanently denied permissions detected!');
          print('   User must go to Settings to enable:');
          permanentlyDenied.forEach((p) => print('   - $p'));
        }
      }

      return allGranted;
    } catch (e) {
      print('âŒ Error requesting permissions: $e');
      return false;
    }
  }

  /// Check if all required Bluetooth permissions are granted
  Future<bool> hasBluetoothPermissions() async {
    print('ðŸ” Checking current permission status...');

    try {
      bool bluetoothScanGranted = false;
      bool bluetoothConnectGranted = false;
      bool bluetoothAdvertiseGranted = false; // âœ… ADDED
      bool locationGranted = false;

      if (Platform.isAndroid) {
        final androidInfo = await _getAndroidVersion();

        if (androidInfo >= 31) {
          // Android 12+
          bluetoothScanGranted = await Permission.bluetoothScan.isGranted;
          bluetoothConnectGranted = await Permission.bluetoothConnect.isGranted;
          bluetoothAdvertiseGranted = await Permission.bluetoothAdvertise.isGranted; // âœ… ADDED
          locationGranted = await Permission.locationWhenInUse.isGranted;

          print('   Bluetooth Scan: ${bluetoothScanGranted ? "âœ…" : "âŒ"}');
          print('   Bluetooth Connect: ${bluetoothConnectGranted ? "âœ…" : "âŒ"}');
          print('   Bluetooth Advertise: ${bluetoothAdvertiseGranted ? "âœ…" : "âŒ"}'); // âœ… ADDED
          print('   Location: ${locationGranted ? "âœ…" : "âŒ"}');
        } else {
          // Android 11 and below
          bluetoothScanGranted = await Permission.bluetooth.isGranted;
          bluetoothConnectGranted = true; // Not needed on older Android
          bluetoothAdvertiseGranted = true; // Not needed on older Android
          locationGranted = await Permission.locationWhenInUse.isGranted;

          print('   Bluetooth: ${bluetoothScanGranted ? "âœ…" : "âŒ"}');
          print('   Location: ${locationGranted ? "âœ…" : "âŒ"}');
        }
      } else if (Platform.isIOS) {
        bluetoothScanGranted = await Permission.bluetooth.isGranted;
        bluetoothConnectGranted = true; // Handled differently on iOS
        bluetoothAdvertiseGranted = true; // Handled differently on iOS
        locationGranted = await Permission.locationWhenInUse.isGranted;

        print('   Bluetooth: ${bluetoothScanGranted ? "âœ…" : "âŒ"}');
        print('   Location: ${locationGranted ? "âœ…" : "âŒ"}');
      }

      final allGranted = bluetoothScanGranted &&
          bluetoothConnectGranted &&
          bluetoothAdvertiseGranted && // âœ… ADDED
          locationGranted;
      print(allGranted ? 'âœ… All permissions granted' : 'âŒ Missing permissions');

      return allGranted;
    } catch (e) {
      print('âŒ Error checking permissions: $e');
      return false;
    }
  }

  /// Check if location services are enabled (different from permission!)
  Future<bool> isLocationServiceEnabled() async {
    try {
      final serviceStatus = await Permission.locationWhenInUse.serviceStatus;
      final isEnabled = serviceStatus.isEnabled;

      print('ðŸ“ Location Service Status: ${isEnabled ? "ENABLED" : "DISABLED"}');

      if (!isEnabled) {
        print('âš ï¸ Location service is DISABLED!');
        print('   User must enable Location in device settings');
      }

      return isEnabled;
    } catch (e) {
      print('âŒ Error checking location service: $e');
      return false;
    }
  }

  /// Open app settings so user can manually grant permissions
  Future<void> openSettings() async {
    print('âš™ï¸ Opening app settings...');
    await openAppSettings();
  }

  /// Get Android API level
  Future<int> _getAndroidVersion() async {
    if (!Platform.isAndroid) return 0;

    try {
      final deviceInfo = DeviceInfoPlugin();
      final androidInfo = await deviceInfo.androidInfo;
      final sdkInt = androidInfo.version.sdkInt;
      print('ðŸ“± Android SDK: $sdkInt (Android ${androidInfo.version.release})');
      return sdkInt;
    } catch (e) {
      print('âš ï¸ Could not detect Android version: $e');
      return 31; // Default to Android 12+
    }
  }

  /// Comprehensive permission check with detailed diagnostics
  Future<Map<String, dynamic>> getDiagnostics() async {
    print('ðŸ”¬ Running permission diagnostics...');

    final diagnostics = <String, dynamic>{};

    try {
      // Check individual permissions
      if (Platform.isAndroid) {
        final androidInfo = await _getAndroidVersion();
        diagnostics['platform'] = 'Android';
        diagnostics['androidVersion'] = androidInfo;

        if (androidInfo >= 31) {
          diagnostics['bluetoothScan'] = await Permission.bluetoothScan.status;
          diagnostics['bluetoothConnect'] = await Permission.bluetoothConnect.status;
          diagnostics['bluetoothAdvertise'] = await Permission.bluetoothAdvertise.status; // âœ… ADDED
        } else {
          diagnostics['bluetooth'] = await Permission.bluetooth.status;
        }

        diagnostics['location'] = await Permission.locationWhenInUse.status;
        diagnostics['locationService'] = await Permission.locationWhenInUse.serviceStatus;
      } else if (Platform.isIOS) {
        diagnostics['platform'] = 'iOS';
        diagnostics['bluetooth'] = await Permission.bluetooth.status;
        diagnostics['location'] = await Permission.locationWhenInUse.status;
        diagnostics['locationService'] = await Permission.locationWhenInUse.serviceStatus;
      }

      print('ðŸ“Š Diagnostics:');
      diagnostics.forEach((key, value) {
        print('   $key: $value');
      });

      return diagnostics;
    } catch (e) {
      print('âŒ Error getting diagnostics: $e');
      return {'error': e.toString()};
    }
  }
  /// Comprehensive check: returns map with all required keys for UI logic
  Future<Map<String, dynamic>> performComprehensiveCheck() async {
    try {
      final hasPerms = await hasBluetoothPermissions();
      final locationEnabled = await isLocationServiceEnabled();
      final permDenied = await hasPermissionsPermanentlyDenied();
      // isBluetoothEnabled requires flutter_blue_plus; we approximate via permissions
      // If BT permissions are granted the adapter is likely on; callers handle the
      // actual adapter check separately via flutter_blue_plus when scanning starts.
      final isReady = hasPerms && locationEnabled;

      String userMessage;
      if (!hasPerms) {
        userMessage = permDenied
            ? 'Bluetooth/Location permissions permanently denied. Open Settings to enable.'
            : 'Bluetooth and Location permissions are required.';
      } else if (!locationEnabled) {
        userMessage = 'Location services are disabled. Please enable them.';
      } else {
        userMessage = 'Ready to scan';
      }

      return {
        'isReady': isReady,
        'hasPermissions': hasPerms,
        'isBluetoothEnabled': hasPerms, // adapter state checked live during scan
        'isLocationEnabled': locationEnabled,
        'permanentlyDenied': permDenied,
        'allGranted': hasPerms,
        'locationServiceEnabled': locationEnabled,
        'success': isReady,
        'userMessage': userMessage,
      };
    } catch (e) {
      return {
        'isReady': false,
        'hasPermissions': false,
        'isBluetoothEnabled': false,
        'isLocationEnabled': false,
        'permanentlyDenied': false,
        'allGranted': false,
        'locationServiceEnabled': false,
        'success': false,
        'userMessage': 'Error checking permissions: ${e.toString()}',
        'error': e.toString(),
      };
    }
  }

  /// Check if any required permissions are permanently denied
  Future<bool> hasPermissionsPermanentlyDenied() async {
    try {
      if (Platform.isAndroid) {
        final androidVersion = await _getAndroidVersion();
        if (androidVersion >= 31) {
          final scan = await Permission.bluetoothScan.isPermanentlyDenied;
          final connect = await Permission.bluetoothConnect.isPermanentlyDenied;
          final advertise = await Permission.bluetoothAdvertise.isPermanentlyDenied;
          final location = await Permission.locationWhenInUse.isPermanentlyDenied;
          return scan || connect || advertise || location;
        } else {
          final bt = await Permission.bluetooth.isPermanentlyDenied;
          final location = await Permission.locationWhenInUse.isPermanentlyDenied;
          return bt || location;
        }
      } else if (Platform.isIOS) {
        final bt = await Permission.bluetooth.isPermanentlyDenied;
        final location = await Permission.locationWhenInUse.isPermanentlyDenied;
        return bt || location;
      }
      return false;
    } catch (e) {
      print('Error checking permanently denied: $e');
      return false;
    }
  }

  /// Attempt to enable Bluetooth programmatically (Android only).
  /// Returns true if Bluetooth is enabled after the attempt.
  Future<bool> promptEnableBluetooth() async {
    try {
      // On Android we cannot programmatically enable BT without BLUETOOTH_ADMIN (deprecated).
      // The best we can do is check current state and guide the user.
      // If flutter_blue_plus is available it can request enable; here we return false
      // so the caller falls back to showing a manual enable dialog.
      print('promptEnableBluetooth: Please enable Bluetooth manually.');
      return false;
    } catch (e) {
      print('Error prompting Bluetooth enable: $e');
      return false;
    }
  }

  /// Open system Location settings page
  Future<void> openLocationSettings() async {
    print('Opening location settings...');
    await openAppSettings();
  }


}