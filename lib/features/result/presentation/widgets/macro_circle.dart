import 'dart:math' as math;
import 'package:flutter/material.dart';

class MacroCircle extends StatelessWidget {
  const MacroCircle({super.key, required this.label, required this.value, required this.target, required this.icon, required this.onTap});
  final String label;
  final double value;
  final double target;
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final ratio = target <= 0 ? 0.0 : value / target;
    final percent = ratio * 100;
    final over = ratio > 1;
    final valueColor = over ? theme.colorScheme.error : theme.colorScheme.primary;

    return Material(
      color: theme.colorScheme.surfaceContainerLow,
      borderRadius: BorderRadius.circular(22),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(22),
        child: Container(
          constraints: const BoxConstraints(minHeight: 236),
          padding: const EdgeInsets.fromLTRB(14, 18, 14, 16),
          decoration: BoxDecoration(borderRadius: BorderRadius.circular(22), border: Border.all(color: theme.colorScheme.outlineVariant)),
          child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
            SizedBox.square(
              dimension: 112,
              child: CustomPaint(
                painter: _TargetRingPainter(
                  ratio: ratio,
                  safeColor: theme.colorScheme.primary,
                  excessColor: theme.colorScheme.error,
                  trackColor: theme.colorScheme.surfaceContainerHighest,
                ),
                child: Center(
                  child: Column(mainAxisSize: MainAxisSize.min, children: [
                    Icon(icon, size: 19, color: valueColor),
                    const SizedBox(height: 5),
                    Text('${percent.round()}%', style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w900, color: valueColor, height: 1)),
                  ]),
                ),
              ),
            ),
            const SizedBox(height: 13),
            FittedBox(fit: BoxFit.scaleDown, child: Text('${_formatNumber(value)} g', style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w900, height: 1))),
            const SizedBox(height: 5),
            Text(target > 0 ? 'Target ${_formatNumber(target)} g' : 'No target available', maxLines: 1, overflow: TextOverflow.ellipsis, style: theme.textTheme.labelSmall?.copyWith(color: theme.colorScheme.onSurfaceVariant, fontWeight: FontWeight.w600)),
            const SizedBox(height: 12),
            Text(label, textAlign: TextAlign.center, maxLines: 2, overflow: TextOverflow.ellipsis, style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w800)),
          ]),
        ),
      ),
    );
  }

  static String _formatNumber(double value) => value >= 10 ? value.toStringAsFixed(1) : value.toStringAsFixed(2);
}

class _TargetRingPainter extends CustomPainter {
  const _TargetRingPainter({required this.ratio, required this.safeColor, required this.excessColor, required this.trackColor});
  final double ratio;
  final Color safeColor;
  final Color excessColor;
  final Color trackColor;

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    const start = -math.pi / 2;
    final baseRadius = math.min(size.width, size.height) / 2 - 12;
    final track = Paint()..style = PaintingStyle.stroke..strokeWidth = 10..strokeCap = StrokeCap.round..color = trackColor;
    final safe = Paint()..style = PaintingStyle.stroke..strokeWidth = 10..strokeCap = StrokeCap.round..color = safeColor;
    canvas.drawCircle(center, baseRadius, track);
    final safeRatio = ratio.clamp(0.0, 1.0).toDouble();
    if (safeRatio > 0) canvas.drawArc(Rect.fromCircle(center: center, radius: baseRadius), start, math.pi * 2 * safeRatio, false, safe);

    // Once 100% is reached the complete green target ring remains visible.
    // Excess grows as a second, immediately-adjacent red arc instead of
    // replacing/painting over the achieved target.
    if (ratio > 1) {
      final excessRatio = (ratio - 1).clamp(0.0, 1.0).toDouble();
      final excess = Paint()..style = PaintingStyle.stroke..strokeWidth = 6..strokeCap = StrokeCap.round..color = excessColor;
      canvas.drawArc(Rect.fromCircle(center: center, radius: baseRadius + 8), start, math.pi * 2 * excessRatio, false, excess);
    }
  }

  @override
  bool shouldRepaint(covariant _TargetRingPainter old) => old.ratio != ratio || old.safeColor != safeColor || old.excessColor != excessColor || old.trackColor != trackColor;
}
