import 'dart:async';
import 'package:flutter/material.dart';
import 'package:Attendify_project/models/chat_message.dart';
import 'package:Attendify_project/services/chat_service.dart';

class ChatAssistantPanel extends StatefulWidget {
  final VoidCallback onClose;
  final String userToken;
  final String sessionId;
  final String courseId;

  const ChatAssistantPanel({
    required this.onClose,
    required this.userToken,
    required this.sessionId,
    required this.courseId,
    super.key,
  });

  @override
  State<ChatAssistantPanel> createState() => _ChatAssistantPanelState();
}

class _ChatAssistantPanelState extends State<ChatAssistantPanel> {
  final List<ChatMessage> _messages = [];
  final TextEditingController _controller = TextEditingController();
  final AttendifyChatService _chatService = AttendifyChatService();
  final ScrollController _scrollController = ScrollController();

  /// Tracks the active stream subscription so it can be cancelled on dispose.
  StreamSubscription<String>? _activeSubscription;

  /// True while waiting for / receiving the AI response stream.
  bool _isStreaming = false;

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _handleSend() {
    final text = _controller.text.trim();
    if (text.isEmpty || _isStreaming) return;

    _controller.clear();
    setState(() {
      _messages.add(ChatMessage(text: text, isUser: true));
      // Append a placeholder for the incoming stream response
      _messages.add(ChatMessage(text: "", isUser: false));
      _isStreaming = true;
    });
    _scrollToBottom();

    final targetIndex = _messages.length - 1;

    _activeSubscription = _chatService
        .sendMessageStream(
          message: text,
          sessionId: widget.sessionId,
          token: widget.userToken,
          courseContextId: widget.courseId,
        )
        .listen(
      (chunk) {
        if (!mounted) return;
        setState(() {
          _messages[targetIndex] = ChatMessage(
            text: _messages[targetIndex].text + chunk,
            isUser: false,
          );
        });
        _scrollToBottom();
      },
      onError: (error) {
        if (!mounted) return;
        setState(() {
          _messages[targetIndex] = ChatMessage(
            text: "❌ Error: $error",
            isUser: false,
          );
          _isStreaming = false;
        });
      },
      onDone: () {
        if (!mounted) return;
        setState(() {
          _isStreaming = false;
        });
      },
    );
  }

  @override
  void dispose() {
    // Cancel any in-flight stream to prevent setState-after-dispose crashes
    _activeSubscription?.cancel();
    _chatService.cancel();
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      elevation: 16,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: Column(
        children: [
          // ── Top Header Bar ─────────────────────────────────────────────
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: const BoxDecoration(
              border: Border(bottom: BorderSide(color: Colors.black12)),
            ),
            child: Row(
              children: [
                const Icon(Icons.smart_toy_rounded, color: Color(0xFF4A6572)),
                const SizedBox(width: 12),
                const Text(
                  "Attendify AI Assistant",
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                ),
                const Spacer(),
                IconButton(
                  icon: const Icon(Icons.close),
                  tooltip: 'Close',
                  onPressed: widget.onClose,
                ),
              ],
            ),
          ),

          // ── Chat Response Body List view ───────────────────────────────
          Expanded(
            child: _messages.isEmpty
                ? _buildEmptyState()
                : ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.all(16),
                    itemCount: _messages.length,
                    itemBuilder: (context, index) {
                      final msg = _messages[index];
                      final isUser = msg.isUser;

                      // Show typing indicator for empty AI placeholder
                      if (!isUser && msg.text.isEmpty && _isStreaming) {
                        return _buildTypingIndicator();
                      }

                      return Align(
                        alignment: isUser
                            ? Alignment.centerRight
                            : Alignment.centerLeft,
                        child: Container(
                          margin: const EdgeInsets.symmetric(vertical: 4),
                          padding: const EdgeInsets.symmetric(
                            horizontal: 14,
                            vertical: 10,
                          ),
                          constraints: BoxConstraints(
                            maxWidth: MediaQuery.of(context).size.width * 0.78,
                          ),
                          decoration: BoxDecoration(
                            color: isUser
                                ? const Color(0xFFE2F1FF)
                                : const Color(0xFFF5F5F5),
                            borderRadius: BorderRadius.only(
                              topLeft: const Radius.circular(14),
                              topRight: const Radius.circular(14),
                              bottomLeft: Radius.circular(isUser ? 14 : 0),
                              bottomRight: Radius.circular(isUser ? 0 : 14),
                            ),
                          ),
                          child: Text(
                            msg.text,
                            style: TextStyle(
                              color: isUser ? Colors.black : Colors.black87,
                              fontSize: 15,
                            ),
                          ),
                        ),
                      );
                    },
                  ),
          ),

          // ── Bottom Message Entry Controls ──────────────────────────────
          SafeArea(
            top: false,
            child: Padding(
              padding: const EdgeInsets.all(12.0),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _controller,
                      onSubmitted: (_) => _handleSend(),
                      textInputAction: TextInputAction.send,
                      decoration: InputDecoration(
                        hintText: "Type a message...",
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(24),
                        ),
                        contentPadding: const EdgeInsets.symmetric(
                          horizontal: 16,
                          vertical: 8,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  CircleAvatar(
                    backgroundColor: _isStreaming
                        ? Colors.grey
                        : const Color(0xFF3B5998),
                    child: IconButton(
                      icon: const Icon(Icons.send, color: Colors.white, size: 18),
                      onPressed: _isStreaming ? null : _handleSend,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// Empty state shown before any messages are sent.
  Widget _buildEmptyState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.smart_toy_outlined,
              size: 64,
              color: Colors.grey[300],
            ),
            const SizedBox(height: 16),
            Text(
              'Ask me anything about\nthis course!',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 16,
                color: Colors.grey[500],
                height: 1.5,
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// Animated typing indicator shown while waiting for AI response.
  Widget _buildTypingIndicator() {
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        decoration: const BoxDecoration(
          color: Color(0xFFF5F5F5),
          borderRadius: BorderRadius.only(
            topLeft: Radius.circular(14),
            topRight: Radius.circular(14),
            bottomRight: Radius.circular(14),
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            _buildDot(0),
            const SizedBox(width: 4),
            _buildDot(1),
            const SizedBox(width: 4),
            _buildDot(2),
          ],
        ),
      ),
    );
  }

  /// Single animated dot for the typing indicator.
  Widget _buildDot(int index) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0.3, end: 1.0),
      duration: Duration(milliseconds: 600 + (index * 200)),
      builder: (context, value, child) {
        return Opacity(
          opacity: value,
          child: Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              color: Colors.grey[400],
              shape: BoxShape.circle,
            ),
          ),
        );
      },
    );
  }
}