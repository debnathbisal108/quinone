import 'package:flutter/material.dart';

class AnalyzeButton extends StatelessWidget {
  final bool enabled;
  final VoidCallback onPressed;
  final bool isLoading;

  const AnalyzeButton({
    super.key,
    required this.enabled,
    required this.onPressed,
    this.isLoading = false,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return SizedBox(
      width: double.infinity,
      child: FilledButton.icon(
        onPressed:
            enabled && !isLoading ? onPressed : null,
        icon: isLoading
            ? const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(
                  strokeWidth: 2.4,
                ),
              )
            : const Icon(
                Icons.auto_awesome_rounded,
              ),
        label: Padding(
          padding: const EdgeInsets.symmetric(
            vertical: 4,
          ),
          child: Text(
            isLoading
                ? 'Analyzing meal…'
                : 'Analyze meal',
            style: theme.textTheme.titleMedium?.copyWith(
              color: enabled && !isLoading
                  ? theme.colorScheme.onPrimary
                  : theme.colorScheme.onSurface
                      .withValues(alpha: 0.38),
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
        style: FilledButton.styleFrom(
          minimumSize: const Size.fromHeight(56),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(18),
          ),
        ),
      ),
    );
  }
}
