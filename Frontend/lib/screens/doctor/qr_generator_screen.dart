// QR Generator Screen - Royal Purple Theme (Lecturer Side)

import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:qr_flutter/qr_flutter.dart';
import '../../services/api_service.dart';

class QrGeneratorScreen extends StatefulWidget {
  final String courseTitle;
  final String courseId;
  final int sessionId; // ✅ NEW: required to fetch tokens and projector URL

  const QrGeneratorScreen({
    super.key,
    required this.courseTitle,
    required this.courseId,
    required this.sessionId,
  });

  @override
  State<QrGeneratorScreen> createState() => _QrGeneratorScreenState();
}

class _QrGeneratorScreenState extends State<QrGeneratorScreen>
    with SingleTickerProviderStateMixin {
  // ── Token & countdown state ──────────────────────────────────────────────
  static const int _totalSeconds = 5;

  final _apiService = ApiService();

  /// The JSON string that gets encoded into the QR.
  /// Shape: {"token":"<totp>","session_id":<id>}
  String _qrData = '';
  int _timeLeft = _totalSeconds;
  Timer? _timer;

  bool _isLoadingToken = true;
  String? _tokenError;

  // ── Animation controller for the countdown ring ─────────────────────────
  late final AnimationController _ringController;

  @override
  void initState() {
    super.initState();

    _ringController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: _totalSeconds),
    );

    // Fetch the first token from the backend immediately
    _fetchAndRefreshToken();
    _startRotation();
  }

  // ── Backend call: get current TOTP token for this session ────────────────
  Future<void> _fetchAndRefreshToken() async {
    setState(() {
      _isLoadingToken = true;
      _tokenError = null;
    });

    try {
      final result = await _apiService.getQrToken(
        sessionId: widget.sessionId,
      );

      if (!mounted) return;

      if (result['success'] == true) {
        setState(() {
          // QR encodes a JSON payload the scanner will POST to /api/verify_qr
          _qrData = jsonEncode({
            'token': result['token'],
            'session_id': widget.sessionId,
          });
          _isLoadingToken = false;
        });
      } else {
        setState(() {
          _tokenError = result['message'] ?? 'Failed to load QR token';
          _isLoadingToken = false;
        });
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _tokenError = 'Network error: $e';
        _isLoadingToken = false;
      });
    }
  }

  void _startRotation() {
    _ringController.forward(from: 0.0);

    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!mounted) return;
      setState(() {
        if (_timeLeft <= 1) {
          // Token expired → fetch fresh token from backend
          _fetchAndRefreshToken();
          _timeLeft = _totalSeconds;
          _ringController.forward(from: 0.0);
        } else {
          _timeLeft--;
        }
      });
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    _ringController.dispose();
    super.dispose();
  }

  // ── Projector button handler ─────────────────────────────────────────────
  Future<void> _onProjectorTap() async {
    final result = await _apiService.generateProjectorToken(
      sessionId: widget.sessionId,
    );

    if (!mounted) return;

    if (result['success'] == true) {
      final url = result['url'] as String;
      final expiresIn = result['expires_in'] ?? 60;

      // Copy link to clipboard and show a bottom sheet
      await Clipboard.setData(ClipboardData(text: url));

      if (!mounted) return;
      _showProjectorUrlSheet(url, expiresIn);
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(result['message'] ?? 'Failed to generate projector link'),
          backgroundColor: Colors.red.shade700,
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
      );
    }
  }

  void _showProjectorUrlSheet(String url, int expiresIn) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (ctx) {
        return Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Projector Link Ready',
                style: Theme.of(ctx).textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: Colors.deepPurple.shade900,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Link copied to clipboard. It expires in $expiresIn seconds and can only be used once.',
                style: Theme.of(ctx).textTheme.bodyMedium?.copyWith(
                  color: Colors.grey[600],
                ),
              ),
              const SizedBox(height: 16),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.deepPurple.shade50,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  url,
                  style: Theme.of(ctx).textTheme.bodySmall?.copyWith(
                    color: Colors.deepPurple.shade800,
                    fontFamily: 'monospace',
                  ),
                ),
              ),
              const SizedBox(height: 16),
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: () {
                    Clipboard.setData(ClipboardData(text: url));
                    Navigator.pop(ctx);
                  },
                  icon: const Icon(Icons.copy_rounded),
                  label: const Text('Copy Again & Close'),
                  style: FilledButton.styleFrom(
                    backgroundColor: Colors.deepPurple.shade700,
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  // ── Color helpers ────────────────────────────────────────────────────────
  Color get _borderColor {
    if (_timeLeft >= 4) return Colors.deepPurple.shade400;
    if (_timeLeft >= 2) return Colors.amber.shade600;
    return Colors.red.shade500;
  }

  Color get _glowColor {
    if (_timeLeft >= 4) return Colors.deepPurple.shade400;
    if (_timeLeft >= 2) return Colors.amber.shade600;
    return Colors.red.shade500;
  }

  // ── Build ────────────────────────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      body: Stack(
        children: [
          // Layer 1: Royal Purple gradient
          Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  Colors.deepPurple.shade900,
                  Colors.deepPurple.shade800,
                  Colors.purple.shade700,
                ],
              ),
            ),
          ),

          // Layer 2: Decorative circle pattern
          Positioned.fill(
            child: CustomPaint(painter: _CirclePatternPainter()),
          ),

          // Layer 3: Content
          SafeArea(
            child: Column(
              children: [
                _buildCustomHeader(textTheme),
                Expanded(
                  child: SingleChildScrollView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.all(20.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.center,
                      children: [
                        _buildCourseInfoCard(textTheme),
                        const SizedBox(height: 24),
                        _buildQrCard(textTheme),
                        const SizedBox(height: 24),
                        _buildProjectorButton(textTheme),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ── Custom Header ────────────────────────────────────────────────────────
  Widget _buildCustomHeader(TextTheme textTheme) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Container(
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: Colors.white.withValues(alpha: 0.3)),
            ),
            child: IconButton(
              icon: const Icon(Icons.arrow_back_ios_new_rounded),
              color: Colors.white,
              onPressed: () => Navigator.pop(context),
              tooltip: 'Back',
            ),
          ),
          Text(
            'QR Generator',
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

  // ── Course info card ─────────────────────────────────────────────────────
  Widget _buildCourseInfoCard(TextTheme textTheme) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.95),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: Colors.white.withValues(alpha: 0.5)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.1),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Container(
            width: 52,
            height: 52,
            decoration: BoxDecoration(
              color: Colors.deepPurple.shade50,
              borderRadius: BorderRadius.circular(14),
            ),
            child: Icon(Icons.class_rounded,
                color: Colors.deepPurple.shade700, size: 26),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  widget.courseTitle,
                  style: textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: Colors.deepPurple.shade900,
                    letterSpacing: -0.3,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 4),
                Text(
                  'Attendance Session • #${widget.sessionId}',
                  style: textTheme.bodySmall?.copyWith(color: Colors.grey[600]),
                ),
              ],
            ),
          ),
          // Live badge
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: Colors.green.shade50,
              border: Border.all(color: Colors.green.shade300, width: 1.5),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                _PulsingDot(color: Colors.green.shade500),
                const SizedBox(width: 6),
                Text(
                  'Live',
                  style: textTheme.labelMedium?.copyWith(
                    color: Colors.green.shade700,
                    fontWeight: FontWeight.w600,
                    letterSpacing: 0.5,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ── Main QR card ─────────────────────────────────────────────────────────
  Widget _buildQrCard(TextTheme textTheme) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.95),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: Colors.white.withValues(alpha: 0.5)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.1),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Text(
            'Scan to Mark Attendance',
            style: textTheme.titleLarge?.copyWith(
              fontWeight: FontWeight.bold,
              color: Colors.deepPurple.shade900,
              letterSpacing: -0.3,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            'Students scan the QR code below',
            style: textTheme.bodyMedium?.copyWith(color: Colors.grey[600]),
          ),
          const SizedBox(height: 24),

          // ── Countdown ring + QR ──────────────────────────────────────────
          Stack(
            alignment: Alignment.center,
            children: [
              // Animated countdown ring
              AnimatedBuilder(
                animation: _ringController,
                builder: (context, child) {
                  return SizedBox(
                    width: 310,
                    height: 310,
                    child: CustomPaint(
                      painter: _CountdownRingPainter(
                        progress: 1.0 - _ringController.value,
                        color: _borderColor,
                      ),
                    ),
                  );
                },
              ),

              // QR code or loading/error state
              AnimatedContainer(
                duration: const Duration(milliseconds: 400),
                curve: Curves.easeInOut,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: _borderColor, width: 3),
                  boxShadow: [
                    BoxShadow(
                      color: _glowColor.withValues(alpha: 0.25),
                      blurRadius: 16,
                      spreadRadius: 2,
                    ),
                  ],
                ),
                child: SizedBox(
                  width: 220,
                  height: 220,
                  child: _buildQrContent(),
                ),
              ),
            ],
          ),

          const SizedBox(height: 24),

          // ── Countdown label ──────────────────────────────────────────────
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.refresh_rounded, size: 18, color: _borderColor),
              const SizedBox(width: 8),
              AnimatedSwitcher(
                duration: const Duration(milliseconds: 300),
                transitionBuilder: (child, animation) =>
                    ScaleTransition(scale: animation, child: child),
                child: Text(
                  _isLoadingToken
                      ? 'Fetching token...'
                      : 'Refreshing in $_timeLeft s',
                  key: ValueKey(_isLoadingToken ? 'loading' : _timeLeft),
                  style: textTheme.bodyLarge?.copyWith(
                    color: _borderColor,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  /// Shows a spinner while loading, an error state, or the actual QR.
  Widget _buildQrContent() {
    if (_isLoadingToken) {
      return Center(
        child: CircularProgressIndicator(
          strokeWidth: 3,
          color: Colors.deepPurple.shade400,
        ),
      );
    }

    if (_tokenError != null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.error_outline_rounded,
                color: Colors.red.shade400, size: 40),
            const SizedBox(height: 8),
            Text(
              _tokenError!,
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.red.shade600, fontSize: 12),
            ),
            const SizedBox(height: 8),
            TextButton(
              onPressed: _fetchAndRefreshToken,
              child: const Text('Retry'),
            ),
          ],
        ),
      );
    }

    return QrImageView(
      data: _qrData,
      version: QrVersions.auto,
      size: 220.0,
      eyeStyle: QrEyeStyle(
        eyeShape: QrEyeShape.square,
        color: Colors.deepPurple.shade800,
      ),
      dataModuleStyle: QrDataModuleStyle(
        dataModuleShape: QrDataModuleShape.square,
        color: Colors.deepPurple.shade800,
      ),
    );
  }

  // ── Projector mode button ────────────────────────────────────────────────
  Widget _buildProjectorButton(TextTheme textTheme) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.95),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: Colors.white.withValues(alpha: 0.5)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.1),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: _onProjectorTap, // ✅ wired up
          borderRadius: BorderRadius.circular(16),
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    color: Colors.deepPurple.shade50,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(Icons.cast_rounded,
                      color: Colors.deepPurple.shade700, size: 22),
                ),
                const SizedBox(width: 16),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Projector Mode',
                      style: textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: Colors.deepPurple.shade900,
                      ),
                    ),
                    Text(
                      'Open full-screen QR for projection',
                      style: textTheme.bodySmall?.copyWith(
                          color: Colors.grey[600]),
                    ),
                  ],
                ),
                const Spacer(),
                Icon(Icons.arrow_forward_ios_rounded,
                    size: 18, color: Colors.grey[400]),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ── Countdown Ring Painter ───────────────────────────────────────────────────
class _CountdownRingPainter extends CustomPainter {
  final double progress;
  final Color color;

  const _CountdownRingPainter({required this.progress, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = (size.width / 2) - 6;

    final trackPaint = Paint()
      ..color = Colors.grey.shade200
      ..style = PaintingStyle.stroke
      ..strokeWidth = 6
      ..strokeCap = StrokeCap.round;
    canvas.drawCircle(center, radius, trackPaint);

    final progressPaint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 6
      ..strokeCap = StrokeCap.round;
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      -math.pi / 2,
      2 * math.pi * progress,
      false,
      progressPaint,
    );
  }

  @override
  bool shouldRepaint(covariant _CountdownRingPainter oldDelegate) =>
      oldDelegate.progress != progress || oldDelegate.color != color;
}

// ── Pulsing Dot ──────────────────────────────────────────────────────────────
class _PulsingDot extends StatefulWidget {
  final Color color;
  const _PulsingDot({super.key, required this.color});

  @override
  State<_PulsingDot> createState() => _PulsingDotState();
}

class _PulsingDotState extends State<_PulsingDot>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (_, __) {
        final opacity = 0.4 + (math.sin(_ctrl.value * math.pi) * 0.6);
        return Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(
            color: widget.color.withValues(alpha: opacity),
            shape: BoxShape.circle,
          ),
        );
      },
    );
  }
}

// ── Circle Pattern Painter ───────────────────────────────────────────────────
class _CirclePatternPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Colors.white.withValues(alpha: 0.08)
      ..style = PaintingStyle.fill;

    canvas.drawCircle(Offset(size.width * 0.9, size.height * 0.2), 60, paint);
    canvas.drawCircle(Offset(size.width * 0.15, size.height * 0.8), 45, paint);
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