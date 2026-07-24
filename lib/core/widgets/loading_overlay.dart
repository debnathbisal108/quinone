import 'package:flutter/material.dart';

class LoadingOverlay extends StatelessWidget {
  final bool isLoading;
  final Widget child;
  final Widget? overlay;

  const LoadingOverlay({
    super.key,
    required this.isLoading,
    required this.child,
    this.overlay,
  });

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        child,

        if (isLoading)
          Positioned.fill(
            child: IgnorePointer(
              ignoring: false,
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 250),
                color: Colors.black.withOpacity(0.45),
                child: Center(
                  child: overlay ??
                      const _DefaultLoadingCard(),
                ),
              ),
            ),
          ),
      ],
    );
  }
}

class _DefaultLoadingCard extends StatelessWidget {
  const _DefaultLoadingCard();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Material(
      color: theme.colorScheme.surface,
      elevation: 12,
      borderRadius: BorderRadius.circular(24),
      child: Container(
        width: 280,
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(
              width: 56,
              height: 56,
              child: CircularProgressIndicator(
                strokeWidth: 4,
              ),
            ),

            const SizedBox(height: 24),

            Text(
              "Processing...",
              style: theme.textTheme.titleLarge,
            ),

            const SizedBox(height: 10),

            Text(
              "Please wait while Quinone analyzes your meal.",
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyMedium,
            ),
          ],
        ),
      ),
    );
  }
}