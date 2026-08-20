import 'dart:math' as math;
import 'package:flutter/material.dart';

import 'nutrient_target_view_data.dart';

class MacroCircle extends StatelessWidget {
  const MacroCircle({
    super.key,
    required this.label,
    required this.value,
    required this.target,
    required this.icon,
    required this.onTap,
  });

  final String label;
  final double value;
  final NutrientTargetViewData target;
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final percent = target.percentFor(value);
    final over = target.isExcess(value);
    final aboveReference = !over && target.isAboveReference(value);
    final ratio = over
        ? target.visualRatioFor(value)
        : aboveReference
            ? target.referenceOverflowRatioFor(value)
            : target.visualRatioFor(value);
    final overflowColor = over ? theme.colorScheme.error : Colors.orange;
    final valueColor = over
        ? theme.colorScheme.error
        : aboveReference
            ? Colors.orange
            : theme.colorScheme.primary;

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
                  excessColor: overflowColor,
                  trackColor: theme.colorScheme.surfaceContainerHighest,
                  isExcess: over || aboveReference,
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
            Text(
              target.displayText,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: theme.textTheme.labelSmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
                fontWeight: FontWeight.w600,
              ),
            ),
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
  const _TargetRingPainter({required this.ratio, required this.safeColor, required this.excessColor, required this.trackColor, required this.isExcess});
  final double ratio;
  final Color safeColor;
  final Color excessColor;
  final Color trackColor;
  final bool isExcess;

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    const start = -math.pi / 2;
    final baseRadius = math.min(size.width, size.height) / 2 - 12;
    final track = Paint()..style = PaintingStyle.stroke..strokeWidth = 10..strokeCap = StrokeCap.round..color = trackColor;
    final safe = Paint()..style = PaintingStyle.stroke..strokeWidth = 10..strokeCap = StrokeCap.round..color = safeColor;
    canvas.drawCircle(center, baseRadius, track);

    final ring = Rect.fromCircle(center: center, radius: baseRadius);
    if (!isExcess || ratio <= 1) {
      final safeRatio = ratio.clamp(0.0, 1.0).toDouble();
      if (safeRatio > 0) {
        canvas.drawArc(
          ring,
          start,
          math.pi * 2 * safeRatio,
          false,
          safe,
        );
      }
      return;
    }

    // Above 100%, target and overflow share the same complete ring. Red is
    // reserved for true excess; minimum/reference-only overflow is amber.
    final targetShare = (1 / ratio).clamp(0.0, 1.0).toDouble();
    final excessShare = 1 - targetShare;
    final targetSweep = math.pi * 2 * targetShare;
    final excessSweep = math.pi * 2 * excessShare;
    final targetSegment = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 10
      ..strokeCap = StrokeCap.butt
      ..color = safeColor;
    final excessSegment = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 10
      ..strokeCap = StrokeCap.butt
      ..color = excessColor;

    canvas.drawArc(ring, start, targetSweep, false, targetSegment);
    canvas.drawArc(
      ring,
      start + targetSweep,
      excessSweep,
      false,
      excessSegment,
    );
  }

  @override
  bool shouldRepaint(covariant _TargetRingPainter old) => old.ratio != ratio || old.isExcess != isExcess || old.safeColor != safeColor || old.excessColor != excessColor || old.trackColor != trackColor;
}
