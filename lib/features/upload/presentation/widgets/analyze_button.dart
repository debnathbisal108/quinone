import 'package:flutter/material.dart';

class AnalyzeButton extends StatelessWidget {
  const AnalyzeButton({
    super.key,
    required this.enabled,
    required this.loading,
    required this.onPressed,
  });

  final bool enabled;
  final bool loading;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return SizedBox(
      width: double.infinity,
      height: 56,
      child: FilledButton(
        onPressed: enabled && !loading ? onPressed : null,
        child: loading
            ? SizedBox(
                width: 22,
                height: 22,
                child: CircularProgressIndicator(
                  strokeWidth: 2.4,
                  color: theme.colorScheme.onPrimary,
                ),
              )
            : const Text(
                'Analyze Meal',
              ),
      ),
    );
  }
}
