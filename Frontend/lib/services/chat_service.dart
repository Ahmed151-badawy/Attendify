import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;

class AttendifyChatService {
  // Swapped to 127.0.0.1 for local Chrome browser testing hooks
  final String baseUrl = "http://127.0.0.1:8050/api/v1";

  /// Tracks the active cross-platform HTTP client for explicit cancellation.
  http.Client? _activeClient;
  bool _isCancelled = false;

  /// Call this to abort an in-flight stream (e.g. when the panel is closed).
  void cancel() {
    _isCancelled = true;
    _activeClient?.close();
    _activeClient = null;
  }

  Stream<String> sendMessageStream({
    required String message,
    required String sessionId,
    required String token,
    required String courseContextId,
  }) async* {
    _isCancelled = false;
    final client = http.Client();
    _activeClient = client;

    try {
      final url = Uri.parse("$baseUrl/chat/message");
      final request = http.Request('POST', url);

      // Inject Authorization Header and Event Stream configurations safely
      request.headers['Authorization'] = 'Bearer $token';
      request.headers['Content-Type'] = 'application/json';
      request.headers['Accept'] = 'text/event-stream';
      request.headers['Cache-Control'] = 'no-cache';

      final body = {
        "session_id": sessionId,
        "message": message,
        "course_context": courseContextId,
      };

      request.body = jsonEncode(body);

      // Send cross-platform streamed request
      final response = await client.send(request);

      if (response.statusCode != 200) {
        yield "❌ Error: Server returned status code ${response.statusCode}";
        return;
      }

      String? currentEventType;

      // Read chunk buffers dynamically across the socket channel
      await for (var line in response.stream
          .transform(utf8.decoder)
          .transform(const LineSplitter())) {
        if (_isCancelled) break;

        if (line.startsWith("event: ")) {
          currentEventType = line.substring(7).trim();

          // Terminal boundary — stop reading
          if (currentEventType == "done") break;
          continue;
        }

        if (line.startsWith("data: ")) {
          final dataContent = line.substring(6).trim();
          if (dataContent == "{}") continue;

          // Handle error events from the backend
          if (currentEventType == "error") {
            try {
              final jsonChunk = jsonDecode(dataContent);
              final errorMsg = jsonChunk['error'] ?? 'Unknown server error';
              yield "❌ $errorMsg";
            } catch (_) {
              yield "❌ Server error";
            }
            continue;
          }

          // Handle text_chunk events (normal AI responses)
          try {
            final jsonChunk = jsonDecode(dataContent);
            if (jsonChunk is Map && jsonChunk.containsKey('text')) {
              yield jsonChunk['text'];
            }
          } catch (_) {
            yield dataContent; // Raw text fallback
          }
        }
      }
    } catch (e) {
      if (!_isCancelled) {
        yield "❌ Connection Error: $e";
      }
    } finally {
      _activeClient = null;
      client.close();
    }
  }
}
