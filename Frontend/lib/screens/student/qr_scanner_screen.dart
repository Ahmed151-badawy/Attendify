// QR Scanner Screen - Sky Blue Theme (Student Side)

import 'dart:convert';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:geolocator/geolocator.dart';
import 'package:device_info_plus/device_info_plus.dart';
import '../../services/api_service.dart';
import '../../services/localization_service.dart';
import 'dart:ui' as ui;

class QrScannerScreen extends StatefulWidget {
  final String courseId;
  final String courseTitle;

  const QrScannerScreen({
    super.key,
    required this.courseId,
    required this.courseTitle,
  });

  @override
  State<QrScannerScreen> createState() => _QrScannerScreenState();
}

class _QrScannerScreenState extends State<QrScannerScreen>
    with SingleTickerProviderStateMixin {
  // ── Scan state ───────────────────────────────────────────────────────────
  bool _isProcessing = false;
  bool _isSuccess = false;
  String _statusMessage = '';

  final _apiService = ApiService();

  // ── Scanner controller — lets us pause/resume to prevent re-scan loops ──
  final MobileScannerController _scannerController = MobileScannerController();

  // ── Animation controller for the scan-frame pulse ───────────────────────
  late final AnimationController _pulseController;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1800),
    )..repeat();
  }

  @override
  void dispose() {
    _scannerController.dispose();
    _pulseController.dispose();
    super.dispose();
  }

  // ── Real device ID helper ────────────────────────────────────────────────
  Future<String> _getDeviceId() async {
    final deviceInfo = DeviceInfoPlugin();
    try {
      if (Theme.of(context).platform == TargetPlatform.iOS) {
        final ios = await deviceInfo.iosInfo;
        return ios.identifierForVendor ?? 'ios_unknown';
      } else {
        final android = await deviceInfo.androidInfo;
        return android.id; // stable hardware ID
      }
    } catch (_) {
      return 'fallback_device_id';
    }
  }

  // ── Location permission + fetch ──────────────────────────────────────────
  Future<Position> _getLocation() async {
    bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      throw Exception('Location services are disabled. Please enable them.');
    }

    LocationPermission permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
      if (permission == LocationPermission.denied) {
        throw Exception('Location permission denied.');
      }
    }
    if (permission == LocationPermission.deniedForever) {
      throw Exception(
          'Location permission permanently denied. Please enable it in Settings.');
    }

    return Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high);
  }

  // ── Core scan logic ──────────────────────────────────────────────────────
  void _onDetect(BarcodeCapture capture) async {
    if (_isProcessing) return;
    final barcodes = capture.barcodes;
    if (barcodes.isEmpty || barcodes.first.rawValue == null) return;

    // ✅ Pause immediately so the same frame isn't re-processed while we await
    await _scannerController.stop();
    setState(() => _isProcessing = true);

    final String rawValue = barcodes.first.rawValue!;

    try {
      // ── 1. Parse QR payload ──────────────────────────────────────────────
      // Expected shape: {"token":"<totp>","session_id":<int>}
      Map<String, dynamic> payload;
      try {
        payload = jsonDecode(rawValue) as Map<String, dynamic>;
      } catch (_) {
        throw Exception('Invalid QR code format. Please scan the class QR.');
      }

      final token = payload['token'] as String?;
      final sessionId = payload['session_id'];

      if (token == null || sessionId == null) {
        throw Exception('QR code is missing required fields.');
      }

      // ── 2. Get real device ID (anti-buddy-punching) ──────────────────────
      final deviceId = await _getDeviceId();

      // ── 3. Get GPS location (anti-remote check) ──────────────────────────
      final position = await _getLocation();

      // ── 4. POST to /api/verify_qr ────────────────────────────────────────
      final result = await _apiService.verifyQr(
        token: token,
        sessionId: sessionId is int ? sessionId : int.parse(sessionId.toString()),
        deviceId: deviceId,
        lat: position.latitude,
        lon: position.longitude,
      );

      if (!mounted) return;

      if (result['success'] == true) {
        // ✅ Stay paused — success overlay shows, then we pop
        setState(() {
          _isSuccess = true;
          _statusMessage = result['message'] ?? 'Attendance Marked!';
        });
        await Future.delayed(const Duration(milliseconds: 1800));
        if (mounted) Navigator.pop(context);
      } else {
        // ✅ Show error with a manual retry button; do NOT resume automatically
        _showError(result['message'] ?? 'Check-in failed. Please try again.');
        // _isProcessing stays true until the user taps "Try Again"
      }
    } catch (e) {
      if (!mounted) return;
      _showError(e.toString().replaceFirst('Exception: ', ''));
      // _isProcessing stays true — scanner stays paused
    }
  }

  // ── Resume scanner so the user can try a fresh scan ──────────────────────
  Future<void> _resetAndRetry() async {
    setState(() => _isProcessing = false);
    await _scannerController.start();
  }

  void _showError(String message) {
    if (!mounted) return;
    setState(() => _isProcessing = false); // keeps overlay gone but scanner paused

    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        icon: Icon(Icons.error_outline_rounded,
            color: Colors.red.shade400, size: 48),
        title: const Text('Check-in Failed',
            textAlign: TextAlign.center,
            style: TextStyle(fontWeight: FontWeight.bold)),
        content: Text(message,
            textAlign: TextAlign.center,
            style: TextStyle(color: Colors.grey[700])),
        actionsAlignment: MainAxisAlignment.center,
        actions: [
          FilledButton.icon(
            onPressed: () {
              Navigator.pop(ctx);
              _resetAndRetry(); // resume camera for a fresh scan
            },
            icon: const Icon(Icons.qr_code_scanner_rounded),
            label: const Text('Try Again'),
            style: FilledButton.styleFrom(
              backgroundColor: Colors.blue.shade700,
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12)),
            ),
          ),
        ],
      ),
    );
  }

  // ── Build ────────────────────────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      body: Stack(
        children: [
          // ── Layer 1: Sky Blue gradient ────────────────────────────────────
          Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  Colors.blue.shade700,
                  Colors.blue.shade600,
                  Colors.lightBlue.shade500,
                ],
              ),
            ),
          ),

          // ── Layer 2: Decorative circles ───────────────────────────────────
          Positioned.fill(
            child: CustomPaint(painter: _CirclePatternPainter()),
          ),

          // ── Layer 3: Content ──────────────────────────────────────────────
          SafeArea(
            child: Column(
              children: [
                _buildCustomHeader(textTheme),
                Expanded(
                  child: Stack(
                    children: [
                      // Live camera feed
                      ClipRRect(
                        borderRadius: const BorderRadius.only(
                          bottomLeft: Radius.circular(24),
                          bottomRight: Radius.circular(24),
                        ),
                        child: MobileScanner(
                          controller: _scannerController,
                          onDetect: _onDetect,
                        ),
                      ),

                      // Animated scan frame
                      Center(child: _buildScanFrame()),

                      // Bottom instruction card
                      Positioned(
                        left: 20,
                        right: 20,
                        bottom: 32,
                        child: _buildInstructionCard(textTheme),
                      ),

                      // Processing overlay
                      if (_isProcessing && !_isSuccess)
                        _buildProcessingOverlay(textTheme),

                      // Success overlay
                      if (_isSuccess) _buildSuccessOverlay(textTheme),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ── Custom Header ─────────────────────────────────────────────────────────
  Widget _buildCustomHeader(TextTheme textTheme) {
    final loc = context.loc;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Container(
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(12),
              border:
              Border.all(color: Colors.white.withValues(alpha: 0.3)),
            ),
            child: IconButton(
              icon: const Icon(Icons.arrow_back_ios_new_rounded),
              color: Colors.white,
              onPressed: () => Navigator.pop(context),
              tooltip: 'Back',
            ),
          ),
          Text(
            loc?.qrScannerTitle ?? 'QR Scanner',
            style: textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.bold,
              color: Colors.white,
              letterSpacing: -0.3,
            ),
          ),
          const SizedBox(width: 48),
        ],
      ),
    );
  }

  // ── Animated Scan Frame ───────────────────────────────────────────────────
  Widget _buildScanFrame() {
    return AnimatedBuilder(
      animation: _pulseController,
      builder: (context, child) {
        final opacity =
            0.5 + (math.sin(_pulseController.value * math.pi) * 0.5);
        final glowSpread =
            4.0 + (math.sin(_pulseController.value * math.pi) * 6.0);

        return Container(
          width: 240,
          height: 240,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(24),
            boxShadow: [
              BoxShadow(
                color: Colors.lightBlue.shade300
                    .withValues(alpha: opacity * 0.5),
                blurRadius: 20,
                spreadRadius: glowSpread,
              ),
            ],
          ),
          child: CustomPaint(
            painter: _ScanFramePainter(opacity: opacity),
          ),
        );
      },
    );
  }

  // ── Bottom instruction card ───────────────────────────────────────────────
  Widget _buildInstructionCard(TextTheme textTheme) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(20),
      child: BackdropFilter(
        filter: ui.ImageFilter.blur(sigmaX: 10, sigmaY: 10),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.15),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: Colors.white.withValues(alpha: 0.3)),
          ),
          child: Row(
            children: [
              Icon(Icons.qr_code_scanner_rounded,
                  color: Colors.white, size: 28),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Point camera at the QR code',
                      style: textTheme.bodyMedium?.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    Text(
                      widget.courseTitle,
                      style: textTheme.bodySmall
                          ?.copyWith(color: Colors.grey[300]),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ── Processing Overlay ────────────────────────────────────────────────────
  Widget _buildProcessingOverlay(TextTheme textTheme) {
    final loc = context.loc;
    return Container(
      decoration:
      BoxDecoration(color: Colors.black.withValues(alpha: 0.6)),
      child: BackdropFilter(
        filter: ui.ImageFilter.blur(sigmaX: 8, sigmaY: 8),
        child: Center(
          child: Container(
            padding: const EdgeInsets.all(40),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.95),
              borderRadius: BorderRadius.circular(24),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.15),
                  blurRadius: 20,
                  offset: const Offset(0, 8),
                ),
              ],
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                SizedBox(
                  width: 48,
                  height: 48,
                  child: CircularProgressIndicator(
                    strokeWidth: 3.5,
                    color: Colors.blue.shade600,
                  ),
                ),
                const SizedBox(height: 20),
                Text(
                  loc?.processing ?? 'Processing...',
                  style: textTheme.titleMedium?.copyWith(
                    color: Colors.blue.shade900,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  'Verifying location & QR code',
                  style: textTheme.bodySmall?.copyWith(
                    color: Colors.grey[600],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  // ── Success Overlay ───────────────────────────────────────────────────────
  Widget _buildSuccessOverlay(TextTheme textTheme) {
    return Container(
      decoration:
      BoxDecoration(color: Colors.black.withValues(alpha: 0.6)),
      child: BackdropFilter(
        filter: ui.ImageFilter.blur(sigmaX: 8, sigmaY: 8),
        child: Center(
          child: Container(
            padding: const EdgeInsets.all(44),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.97),
              borderRadius: BorderRadius.circular(28),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.15),
                  blurRadius: 24,
                  offset: const Offset(0, 8),
                ),
              ],
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 80,
                  height: 80,
                  decoration: BoxDecoration(
                    color: Colors.green.shade50,
                    shape: BoxShape.circle,
                    border: Border.all(
                        color: Colors.green.shade300, width: 2.5),
                  ),
                  child: Icon(Icons.check_rounded,
                      color: Colors.green.shade600, size: 44),
                ),
                const SizedBox(height: 20),
                Text(
                  _statusMessage.isNotEmpty
                      ? _statusMessage
                      : (context.loc?.attendanceMarked ??
                      'Attendance Marked!'),
                  style: textTheme.titleLarge?.copyWith(
                    color: Colors.green.shade800,
                    fontWeight: FontWeight.bold,
                    letterSpacing: -0.3,
                  ),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 6),
                Text(
                  widget.courseTitle,
                  style:
                  textTheme.bodyMedium?.copyWith(color: Colors.grey[600]),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ── Scan Frame Painter ────────────────────────────────────────────────────────
class _ScanFramePainter extends CustomPainter {
  final double opacity;
  const _ScanFramePainter({required this.opacity});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Colors.white.withValues(alpha: opacity)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3.5
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;

    const double cornerLen = 28;
    const double radius = 20.0;
    final w = size.width;
    final h = size.height;

    // Top-Left
    canvas.drawPath(
      Path()
        ..moveTo(0, cornerLen)
        ..lineTo(0, radius)
        ..quadraticBezierTo(0, 0, radius, 0)
        ..lineTo(cornerLen, 0),
      paint,
    );
    // Top-Right
    canvas.drawPath(
      Path()
        ..moveTo(w - cornerLen, 0)
        ..lineTo(w - radius, 0)
        ..quadraticBezierTo(w, 0, w, radius)
        ..lineTo(w, cornerLen),
      paint,
    );
    // Bottom-Right
    canvas.drawPath(
      Path()
        ..moveTo(w, h - cornerLen)
        ..lineTo(w, h - radius)
        ..quadraticBezierTo(w, h, w - radius, h)
        ..lineTo(w - cornerLen, h),
      paint,
    );
    // Bottom-Left
    canvas.drawPath(
      Path()
        ..moveTo(cornerLen, h)
        ..lineTo(radius, h)
        ..quadraticBezierTo(0, h, 0, h - radius)
        ..lineTo(0, h - cornerLen),
      paint,
    );
  }

  @override
  bool shouldRepaint(covariant _ScanFramePainter oldDelegate) =>
      oldDelegate.opacity != opacity;
}

// ── Circle Pattern Painter ───────────────────────────────────────────────────
class _CirclePatternPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Colors.white.withValues(alpha: 0.08)
      ..style = PaintingStyle.fill;

    canvas.drawCircle(
        Offset(size.width * 0.9, size.height * 0.2), 60, paint);
    canvas.drawCircle(
        Offset(size.width * 0.15, size.height * 0.8), 45, paint);
    canvas.drawCircle(
        Offset(size.width * 1.05, size.height * 0.85), 80, paint);

    final wavePaint = Paint()
      ..color = Colors.white.withValues(alpha: 0.05)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2;

    final path = Path();
    path.moveTo(0, size.height * 0.4);
    for (double i = 0; i <= size.width; i++) {
      path.lineTo(
        i,
        size.height * 0.4 + math.sin((i / size.width) * 2 * math.pi) * 20,
      );
    }
    canvas.drawPath(path, wavePaint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}